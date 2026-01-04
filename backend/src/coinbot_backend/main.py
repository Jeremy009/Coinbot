"""Main trading bot application with position tracking and multi-strategy support."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from tqdm import tqdm

from coinbot_backend import __version__
from coinbot_backend.config import settings
from coinbot_backend.core.logging_setup import setup_logging
from coinbot_backend.models.trading import OpenPosition, Signal
from coinbot_backend.services.bitvavo_client import get_bitvavo_client
from coinbot_backend.services.s3_storage import get_s3_storage
from coinbot_backend.services.technical_analysis_plot import plot_technical_analysis
from coinbot_backend.services.trading_strategies import strategy_multi_confluence


class TradingBot:
    """
    Trading bot with position tracking and multi-strategy support.

    The bot manages open positions, tracks buy/sell decisions with reasons,
    and logs all trades to a JSON file for analysis.
    """

    def __init__(self) -> None:
        """Initialize the trading bot."""
        self.client = get_bitvavo_client()
        self.s3_storage = get_s3_storage()
        self.positions: dict[str, OpenPosition] = {}
        self.iteration_number = 0
        self.run_folder: str | None = None  # Will be set in run()
        self.charts_to_upload: dict[str, bytes] = {}  # Charts pending upload
        self.logger = None  # Will be initialized in run()

        # Load existing positions from S3 if exists (silently, will log after banner)
        self._load_positions(silent=True)


    def run(self, run_name: str | None = None) -> None:
        """
        Run one iteration of the trading bot.

        Args:
            run_name: Optional run name (YYYYMMDD_HHMM format).
                     If None, generates from current timestamp.
        """
        # Create run folder
        if run_name is None:
            run_name = datetime.now().strftime("%Y%m%d_%H%M")
        self.run_folder = f"{settings.s3_run_key_prefix}{run_name}/"

        # Initialize logger with run folder
        self.logger = setup_logging(__name__, run_folder=self.run_folder)
        self.logger.info(f"Bot iteration started at {datetime.now()} using coinbot V{__version__}")
        self.logger.info(f"Run folder: s3://{settings.s3_bucket_name}/{self.run_folder}")

        # Get current state
        balance = self.get_account_balance()
        self.logger.info(f"Available funds: {balance['available_funds']:.2f} EUR")

        # Update positions
        self.get_current_positions()

        # Evaluate existing positions (may sell some)
        self.evaluate_existing_positions()

        # Look for new opportunities
        self.open_new_positions(settings.bot_num_positions)

        # Upload all charts to S3
        self._upload_all_charts()

        self.logger.info(f"Iteration complete. Open positions: {len(self.positions)}")
        self.logger.info(f"Run completed: s3://{settings.s3_bucket_name}/{self.run_folder}")
        self.iteration_number += 1

    def get_account_balance(self) -> dict[str, float]:
        """Get current account balance information."""
        return {
            "available_funds": self.client.get_available_funds(),
            "total_deposited": self.client.get_total_deposited(),
            "total_withdrawn": self.client.get_total_withdrawn(),
            "total_gains": self.client.get_total_gains(),
        }

    # Selling
    def get_current_positions(self) -> dict[str, OpenPosition]:
        """
        Get current open positions by checking owned symbols.

        Updates internal positions dict and removes positions that have been closed.
        """
        owned_symbols = self.client.get_owned_symbols()

        # Remove positions that are no longer owned
        symbols_to_remove = [s for s in self.positions.keys() if s not in owned_symbols]
        for symbol in symbols_to_remove:
            self.logger.info(f"Position {symbol} no longer owned, removing from tracking")
            del self.positions[symbol]

        # Add new positions that aren't tracked yet (from previous sessions or manual trades)
        for symbol in owned_symbols:
            if symbol not in self.positions:
                amount = self.client.get_symbol_owned_amount(symbol)
                price = self.client.get_symbol_price(symbol)
                self.logger.warning(f"Found untracked position {symbol}, adding with estimated data")
                self.positions[symbol] = OpenPosition(
                    symbol=symbol,
                    buy_datetime=datetime.now(),
                    amount=amount,
                    buy_price=price,
                    ath=price,  # Initialize ATH to current price for untracked positions
                    total_cost=amount * price,
                    reason_for_buying="Pre-existing or manual trade (not tracked)"
                )

        self._save_positions()
        return self.positions

    def analyze_position_with_strategies(self, symbol: str) -> tuple[Signal, float, str]:
        """Analyze a position using the multi-strategy confluence approach."""
        try:
            candles = self.client.get_candles(
                symbol,
                settings.bot_analysis_time_resolution,
                settings.bot_analysis_time_span
            )

            if len(candles.timestamps) < settings.bot_min_candles_required:
                self.logger.warning(f"Insufficient data for advanced strategies on {symbol}")
                return Signal.HOLD, 0.5, "Insufficient historical data"

            confluence = strategy_multi_confluence(candles)

            return confluence.signal, confluence.confidence, confluence.reason

        except Exception as e:
            self.logger.error(f"Failed to analyze {symbol} with strategies: {e}")
            return Signal.HOLD, 0.5, f"Analysis error: {str(e)}"

    def evaluate_existing_positions(self) -> None:
        """Evaluate all existing positions and decide whether to hold or sell."""
        self.logger.info(f"Evaluating {len(self.positions)} existing positions...")

        for symbol, position in list(self.positions.items()):
            self.logger.info(f"Analyzing {symbol} (held since {position.buy_datetime})")

            # Get current price
            current_price = self.client.get_symbol_price(symbol)

            # Update ATH
            new_ath = max(position.ath, current_price)

            # Fetch candles for analysis and charting
            try:
                candles = self.client.get_candles(
                    symbol,
                    settings.bot_analysis_time_resolution,
                    settings.bot_analysis_time_span
                )
            except Exception as e:
                self.logger.error(f"Failed to fetch candles for {symbol}: {e}")
                continue

            # Check trailing stop-loss (safety mechanism - highest priority)
            stop_loss_threshold = new_ath * (1 - settings.bot_trailing_stop_loss_pct / 100)
            if current_price < stop_loss_threshold:
                drop_from_ath_pct = ((new_ath - current_price) / new_ath) * 100
                self.logger.warning(
                    f"TRAILING STOP-LOSS triggered for {symbol}: "
                    f"price {current_price:.2f} dropped {drop_from_ath_pct:.1f}% from ATH {new_ath:.2f}"
                )
                # Generate S_ chart before selling
                try:
                    chart_bytes = plot_technical_analysis(candles, symbol=symbol, return_bytes=True)
                    self._add_chart(symbol, "S", chart_bytes)
                except Exception as e:
                    self.logger.error(f"Failed to generate chart for {symbol}: {e}")

                self.sell_position(
                    symbol,
                    f"Trailing stop-loss: {drop_from_ath_pct:.1f}% drop from ATH {new_ath:.2f}"
                )
                continue

            # Multi-strategy confluence analysis
            if len(candles.timestamps) < settings.bot_min_candles_required:
                self.logger.warning(f"Insufficient data for {symbol}, holding by default")
                signal, confidence, reason = Signal.HOLD, 0.5, "Insufficient historical data"
            else:
                confluence = strategy_multi_confluence(candles)
                signal, confidence, reason = confluence.signal, confluence.confidence, confluence.reason

            # Sell if strategies indicate exit with sufficient confidence
            if signal in [Signal.SELL, Signal.STRONG_SELL] and confidence >= settings.bot_exit_min_confidence:
                self.logger.info(f"Strategy SELL signal for {symbol}: {reason} (confidence: {confidence:.0%})")
                # Generate S_ chart before selling
                try:
                    chart_bytes = plot_technical_analysis(candles, symbol=symbol, return_bytes=True)
                    self._add_chart(symbol, "S", chart_bytes)
                except Exception as e:
                    self.logger.error(f"Failed to generate chart for {symbol}: {e}")

                self.sell_position(symbol, f"{reason} (conf: {confidence:.0%})")
                continue

            # Holding the position - generate H_ chart with buy marker
            try:
                chart_bytes = plot_technical_analysis(
                    candles,
                    symbol=symbol,
                    buy_datetime=position.buy_datetime,
                    return_bytes=True
                )
                self._add_chart(symbol, "H", chart_bytes)
            except Exception as e:
                self.logger.error(f"Failed to generate chart for {symbol}: {e}")

            # Update ATH if new high reached
            if new_ath > position.ath:
                position.ath = new_ath
                self._save_positions()
                self.logger.info(f"{symbol} HOLDING - {reason} (ATH updated to {new_ath:.2f}, conf: {confidence:.0%})")
            else:
                self.logger.info(f"{symbol} HOLDING - {reason} (conf: {confidence:.0%})")

    def sell_position(self, symbol: str, reason: str) -> bool:
        """Sell a position and log the trade."""
        try:
            if symbol not in self.positions:
                self.logger.error(f"Cannot sell {symbol}: position not tracked")
                return False

            position = self.positions[symbol]
            amount = self.client.get_symbol_owned_amount(symbol)

            # Execute sell order
            response = self.client.sell(symbol, amount)

            if "error" in response:
                self.logger.error(f"Failed to sell {symbol}: {response['error']}")
                return False

            # Calculate actual execution price and profit/loss
            filled_amount = float(response['filledAmount'])
            sell_value = float(response['filledAmountQuote'])
            sell_fee = float(response['feePaid'])
            actual_sell_price = sell_value / filled_amount if filled_amount > 0 else 0
            profit_loss = sell_value - sell_fee - position.total_cost
            profit_loss_pct = (profit_loss / position.total_cost) * 100

            self.logger.info(
                f"SOLD {symbol}: {filled_amount} @ {actual_sell_price:.2f} EUR/coin "
                f"(P/L: {profit_loss:+.2f} EUR / {profit_loss_pct:+.2f}%)"
            )

            # Log the trade
            self._log_trade("SELL", symbol, {
                "reason": reason,
                "amount": filled_amount,
                "sell_price": actual_sell_price,
                "sell_value": sell_value,
                "buy_price": position.buy_price,
                "buy_cost": position.total_cost,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "hold_duration_hours": (datetime.now() - position.buy_datetime).total_seconds() / 3600,
                "sell_fee": sell_fee,
            })

            # Remove from positions
            del self.positions[symbol]
            self._save_positions()

            return True

        except Exception as e:
            self.logger.error(f"Error selling {symbol}: {e}")
            return False

    # Buying
    def _check_symbol_filters(self, symbol: str) -> tuple[str, float, float] | None:
        """ Check if a symbol passes pre-filtering criteria (growth and volume). """
        # Skip if already owned or is EUR
        if symbol in self.positions or symbol == "EUR":
            return None

        try:
            # Pre-filter: Check 24h growth
            growth_24h = self.client.get_symbol_24h_percentual_change(symbol)
            if growth_24h < settings.bot_min_growth_24h:
                return None

            # Pre-filter: Check volume (must meet minimum threshold)
            volume_24h = self.client.get_symbol_24h_volume(symbol)
            if volume_24h < settings.bot_volume_limit:
                return None

            return (symbol, growth_24h, volume_24h)

        except Exception as e:
            self.logger.warning(f"Skipping {symbol}: {e}")
            return None

    def _analyze_symbol_for_opportunity(
        self, symbol: str, growth_24h: float, volume_24h: float
    ) -> dict[str, Any]:
        """Analyze a symbol with technical analysis to determine if it's a buy opportunity."""
        try:
            # Fetch candles for analysis
            candles = self.client.get_candles(
                symbol,
                settings.bot_analysis_time_resolution,
                settings.bot_analysis_time_span
            )

            # Check if we have enough data
            if len(candles.timestamps) < settings.bot_min_candles_required:
                return {
                    "status": "insufficient_data",
                    "symbol": symbol,
                    "candles": None,
                }

            # Run multi-strategy confluence analysis
            confluence = strategy_multi_confluence(candles)
            signal, confidence, reason = confluence.signal, confluence.confidence, confluence.reason

            # Check if it's a BUY signal with sufficient confidence
            if signal not in [Signal.BUY, Signal.STRONG_BUY]:
                return {
                    "status": "rejected_signal",
                    "symbol": symbol,
                    "signal": signal,
                    "candles": candles,
                }

            if confidence < settings.bot_entry_min_confidence:
                return {
                    "status": "rejected_confidence",
                    "symbol": symbol,
                    "confidence": confidence,
                    "candles": candles,
                }

            # It's an opportunity!
            full_reason = (
                f"{reason} | 24h: +{growth_24h:.1f}% | "
                f"Vol: €{volume_24h:,.0f} | Conf: {confidence:.0%}"
            )
            return {
                "status": "opportunity",
                "symbol": symbol,
                "reason": full_reason,
                "volume": volume_24h,
                "confidence": confidence,
                "growth_24h": growth_24h,
            }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e),
            }

    def find_opportunities(self, max_positions: int) -> list[tuple[str, str]]:
        """Find trading opportunities using multi-strategy confluence analysis."""
        current_positions = len(self.positions)
        positions_to_open = max_positions - current_positions

        if positions_to_open <= 0:
            self.logger.info(f"Already at max positions ({current_positions}/{max_positions})")
            return []

        self.logger.info(f"Looking for {positions_to_open} new opportunities...")

        # Step 1: Pre-filter symbols by growth and volume (parallelized)
        self.logger.info(
            f"Filtering symbols by 24h growth > {settings.bot_min_growth_24h}% "
            f"and volume >= {settings.bot_volume_limit:,.0f} euro..."
        )

        candidates: list[tuple[str, float, float]] = []  # (symbol, growth_24h, volume_24h)
        available_symbols = self.client.get_available_symbols()

        # Parallelize pre-filtering with ThreadPoolExecutor
        max_workers = min(32, len(available_symbols))  # Limit to 32 threads max

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all symbol checks
            future_to_symbol = {
                executor.submit(self._check_symbol_filters, symbol): symbol
                for symbol in available_symbols
            }

            # Collect results with progress bar
            for future in tqdm(
                as_completed(future_to_symbol),
                total=len(available_symbols),
                desc="Pre-filtering symbols",
                unit="symbol",
                leave=False,
                disable=(not settings.show_loading_bars)
            ):
                result = future.result()
                if result is not None:
                    candidates.append(result)

        self.logger.info(f"Pre-filtered to {len(candidates)} candidate(s) with positive growth and sufficient volume")
        self.logger.debug(f"  Candidates: {[symbol for symbol, _, _ in candidates]}")

        if not candidates:
            self.logger.info("No symbols passed pre-filtering criteria")
            return []

        # Step 2: Sort by volume and then by growth
        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)

        self.logger.info("Analyzing top candidates (sorted by growth and volume)...")

        # Step 3: Analyze candidates with technical analysis (parallelized)
        opportunities: list[tuple[str, str, float, float]] = []
        rejected_symbols: list[tuple[str, Any]] = []  # (symbol, candles) for X_ charts

        # Parallelize technical analysis with ThreadPoolExecutor
        max_workers = min(16, len(candidates))  # Limit to 16 threads (analysis is CPU-intensive)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all candidate analyses
            future_to_candidate = {
                executor.submit(
                    self._analyze_symbol_for_opportunity,
                    symbol,
                    growth_24h,
                    volume_24h
                ): (symbol, growth_24h, volume_24h)
                for symbol, growth_24h, volume_24h in candidates
            }

            # Collect results with progress bar
            results = []
            for future in tqdm(
                as_completed(future_to_candidate),
                total=len(candidates),
                desc="Analyzing candidates",
                unit="symbol",
                leave=False,
                disable=(not settings.show_loading_bars)
            ):
                result = future.result()
                results.append(result)

        # Process results
        for result in results:
            status = result["status"]
            symbol = result["symbol"]

            if status == "opportunity":
                opportunities.append((
                    symbol,
                    result["reason"],
                    result["volume"],
                    result["confidence"]
                ))
                self.logger.info(
                    f"Opportunity found: {symbol} - {result['confidence']:.0%} confidence, "
                    f"+{result['growth_24h']:.1f}% growth"
                )

            elif status == "rejected_signal":
                self.logger.debug(f"{symbol}: {result['signal'].value} signal (not buying)")
                if result["candles"] is not None:
                    rejected_symbols.append((symbol, result["candles"]))

            elif status == "rejected_confidence":
                self.logger.debug(
                    f"{symbol}: {result['confidence']:.0%} confidence "
                    f"(below {settings.bot_entry_min_confidence:.0%} threshold)"
                )
                if result["candles"] is not None:
                    rejected_symbols.append((symbol, result["candles"]))

            elif status == "insufficient_data":
                self.logger.warning(f"Insufficient data for {symbol}, skipping")

            elif status == "error":
                self.logger.debug(f"Error analyzing {symbol}: {result['error']}")

        # Sort opportunities by confidence (descending), then volume
        opportunities.sort(key=lambda x: (x[3], x[2]), reverse=True)

        # Select top N opportunities
        opportunities = opportunities[:positions_to_open]

        # Generate X_ charts for rejected symbols (parallelized)
        if rejected_symbols:
            self.logger.info(f"Generating charts for {len(rejected_symbols)} rejected symbol(s)...")

            with ThreadPoolExecutor(max_workers=min(8, len(rejected_symbols))) as executor:
                # Submit all chart generation tasks
                futures = [
                    executor.submit(self._generate_chart, symbol, candles)
                    for symbol, candles in rejected_symbols
                ]

                # Collect results
                for future in as_completed(futures):
                    symbol, chart_bytes = future.result()
                    if chart_bytes is not None:
                        self._add_chart(symbol, "X", chart_bytes)

        # Log final results
        if opportunities:
            self.logger.info(f"Selected {len(opportunities)} opportunity/ies:")
            for i, (sym, _reason, vol, conf) in enumerate(opportunities, 1):
                self.logger.info(f"  {i}. {sym}: {conf:.0%} confidence, €{vol:,.0f} volume")
        else:
            self.logger.info("No opportunities found matching entry criteria (signal + confidence)")

        return [(sym, reason) for sym, reason, _, _ in opportunities]

    def open_new_positions(self, max_positions: int) -> None:
        """Find and open new trading positions."""
        balance = self.get_account_balance()
        available = balance["available_funds"]

        # Use configured percentage of available funds
        tradeable = available * (settings.bot_max_allocation_percent / 100)
        min_per_position = settings.bot_min_position_size

        current_positions = len(self.positions)
        positions_to_open = max_positions - current_positions

        if positions_to_open <= 0:
            return

        if tradeable < min_per_position * positions_to_open:
            self.logger.warning(
                f"Insufficient funds to open {positions_to_open} positions "
                f"({tradeable:.2f} EUR available, need {min_per_position * positions_to_open:.2f} EUR)"
            )
            return

        # Find opportunities
        opportunities = self.find_opportunities(max_positions)

        if not opportunities:
            return

        # Calculate amount per position
        amount_per_position = tradeable / len(opportunities)

        self.logger.info(
            f"Using {settings.bot_max_allocation_percent}% of available funds ({tradeable:.2f} EUR) "
            f"to open {len(opportunities)} positions with {amount_per_position:.2f} EUR each"
        )

        # Buy the symbols
        for symbol, reason in opportunities:
            self.buy_symbol(symbol, amount_per_position, reason)
            time.sleep(settings.bot_buy_delay_seconds)

    def buy_symbol(self, symbol: str, amount_eur: float, reason: str) -> bool:
        """Buy a symbol and track the position."""
        try:
            # Generate B_ chart before buying
            try:
                candles = self.client.get_candles(
                    symbol,
                    settings.bot_analysis_time_resolution,
                    settings.bot_analysis_time_span
                )
                chart_bytes = plot_technical_analysis(candles, symbol=symbol, return_bytes=True)
                self._add_chart(symbol, "B", chart_bytes)
            except Exception as e:
                self.logger.error(f"Failed to generate chart for {symbol}: {e}")

            # Execute buy order
            response = self.client.buy(symbol, amount_eur)

            if "error" in response:
                self.logger.error(f"Failed to buy {symbol}: {response['error']}")
                return False

            # Track the position
            filled_amount = float(response['filledAmount'])
            filled_quote = float(response['filledAmountQuote'])
            buy_price = filled_quote / filled_amount if filled_amount > 0 else 0
            fee = float(response['feePaid'])

            position = OpenPosition(
                symbol=symbol,
                buy_datetime=datetime.now(),
                amount=filled_amount,
                buy_price=buy_price,
                ath=buy_price,  # Initialize ATH to purchase price
                total_cost=filled_quote + fee,
                reason_for_buying=reason
            )

            self.positions[symbol] = position
            self._save_positions()

            self.logger.info(
                f"BOUGHT {symbol}: {filled_amount} @ {buy_price:.2f} EUR/coin "
                f"(total: {filled_quote:.2f} EUR + {fee:.2f} fee)"
            )

            # Log the trade
            self._log_trade("BUY", symbol, {
                "reason": reason,
                "amount": filled_amount,
                "buy_price": buy_price,
                "total_cost": filled_quote + fee,
                "buy_fee": fee,
            })

            return True

        except Exception as e:
            self.logger.error(f"Error buying {symbol}: {e}")
            return False

    # Private helpers
    def _load_positions(self, silent: bool = False) -> None:
        """Load positions from S3."""
        try:
            data = self.s3_storage.download_json(settings.s3_positions_key)
            if data is not None:
                self.positions = {
                    symbol: OpenPosition(**pos_data)
                    for symbol, pos_data in data.items()
                }

                # In dry-run mode, restore balances from loaded positions
                # This prevents positions from being removed on next run
                if self.client.dry_run and data:
                    self.client.restore_dry_run_balances_from_positions(data)

                if not silent:
                    self.logger.info(f"Loaded {len(self.positions)} existing positions from S3 ({settings.s3_positions_key})")
            else:
                self.positions = {}
                if not silent:
                    self.logger.info("No existing positions found in S3")
        except Exception as e:
            if not silent:
                self.logger.error(f"Failed to load positions from S3: {e}")
            self.positions = {}

    def _save_positions(self) -> None:
        """Save positions to S3."""
        try:
            data = {
                symbol: pos.model_dump(mode="json")
                for symbol, pos in self.positions.items()
            }
            success = self.s3_storage.upload_json(settings.s3_positions_key, data)
            if success:
                self.logger.info(f"Saved {len(self.positions)} positions to S3 ({settings.s3_positions_key})")
            else:
                self.logger.error("Failed to save positions to S3")
        except Exception as e:
            self.logger.error(f"Failed to save positions to S3: {e}")

    def _log_trade(self, action: str, symbol: str, details: dict[str, Any]) -> None:
        """Log a trade to S3."""
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            **details
        }

        try:
            # Download existing logs from S3
            logs = self.s3_storage.download_json(settings.s3_trades_key)
            if logs is None:
                logs = []

            # Append new trade
            logs.append(trade_entry)

            # Upload back to S3
            success = self.s3_storage.upload_json(settings.s3_trades_key, logs)
            if success:
                self.logger.info(f"Logged {action} trade for {symbol} to S3")
            else:
                self.logger.error(f"Failed to log {action} trade for {symbol} to S3")
        except Exception as e:
            self.logger.error(f"Failed to log trade to S3: {e}")

    def _generate_chart(self, symbol: str, candles: Any) -> tuple[str, bytes | None]:
        """Generate a technical analysis chart for a symbol."""
        try:
            chart_bytes = plot_technical_analysis(candles, symbol=symbol, return_bytes=True)
            return (symbol, chart_bytes)
        except Exception as e:
            self.logger.error(f"Failed to generate chart for {symbol}: {e}")
            return (symbol, None)

    def _add_chart(self, symbol: str, prefix: str, chart_bytes: bytes) -> None:
        """Add a chart to the upload queue."""
        chart_key = f"{prefix}_{symbol}.png"
        self.charts_to_upload[chart_key] = chart_bytes
        self.logger.debug(f"Queued chart for upload: {chart_key}")

    def _upload_all_charts(self) -> None:
        """Upload all queued charts to S3."""
        if not self.charts_to_upload:
            return

        total_charts = len(self.charts_to_upload)
        uploaded = 0
        failed = 0

        # Upload with progress bar
        for chart_filename, chart_bytes in tqdm(
            self.charts_to_upload.items(),
            desc="Uploading charts",
            unit="chart",
            leave=False,
            disable=(not settings.show_loading_bars)
        ):
            chart_key = f"{self.run_folder}{chart_filename}"
            try:
                success = self.s3_storage.upload_chart(chart_key, chart_bytes)
                if success:
                    uploaded += 1
                else:
                    failed += 1
                    self.logger.error(f"Failed to upload {chart_filename}")
            except Exception as e:
                failed += 1
                self.logger.error(f"Error uploading {chart_filename}: {e}")

        # Log summary
        self.logger.info(
            f"Uploaded {uploaded}/{total_charts} technical analysis charts to S3: "
            f"s3://{self.s3_storage.bucket_name}/{self.run_folder}"
        )
        if failed > 0:
            self.logger.warning(f"{failed} chart(s) failed to upload")

        # Clear the queue
        self.charts_to_upload.clear()


def main() -> None:
    """Entry point for the trading bot."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
