"""Main trading bot application with position tracking and multi-strategy support."""

import time
from datetime import datetime
from typing import Any

from tqdm import tqdm

from coinbot_backend.config import settings
from coinbot_backend.core.logging_setup import setup_logging
from coinbot_backend.models.trading import OpenPosition, Signal
from coinbot_backend.services.bitvavo_client import get_bitvavo_client
from coinbot_backend.services.s3_storage import get_s3_storage
from coinbot_backend.services.trading_strategies import strategy_multi_confluence


logger = setup_logging(__name__)


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

        # Load existing positions from S3 if exists (silently, will log after banner)
        self._load_positions(silent=True)


    def run(self) -> None:
        """Run one iteration of the trading bot."""
        logger.info(f"Bot iteration {self.iteration_number} started at {datetime.now()}")

        # Get current state
        balance = self.get_account_balance()
        logger.info(f"Available funds: {balance['available_funds']:.2f} EUR")

        # Update positions
        self.get_current_positions()

        # Evaluate existing positions (may sell some)
        self.evaluate_existing_positions()

        # Look for new opportunities
        self.open_new_positions(settings.bot_num_positions)

        logger.info(f"Iteration complete. Open positions: {len(self.positions)}")
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
            logger.info(f"Position {symbol} no longer owned, removing from tracking")
            del self.positions[symbol]

        # Add new positions that aren't tracked yet (from previous sessions or manual trades)
        for symbol in owned_symbols:
            if symbol not in self.positions:
                amount = self.client.get_symbol_owned_amount(symbol)
                price = self.client.get_symbol_price(symbol)
                logger.warning(f"Found untracked position {symbol}, adding with estimated data")
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
        """
        Analyze a position using the multi-strategy confluence approach.

        Returns:
            Tuple of (signal, confidence, reason)
        """
        try:
            candles = self.client.get_candles(
                symbol,
                settings.bot_analysis_time_resolution,
                settings.bot_analysis_time_span
            )

            if len(candles.timestamps) < settings.bot_min_candles_required:
                logger.warning(f"Insufficient data for advanced strategies on {symbol}")
                return Signal.HOLD, 0.5, "Insufficient historical data"

            confluence = strategy_multi_confluence(candles)

            return confluence.signal, confluence.confidence, confluence.reason

        except Exception as e:
            logger.error(f"Failed to analyze {symbol} with strategies: {e}")
            return Signal.HOLD, 0.5, f"Analysis error: {str(e)}"

    def evaluate_existing_positions(self) -> None:
        """Evaluate all existing positions and decide whether to hold or sell."""
        logger.info(f"Evaluating {len(self.positions)} existing positions...")

        for symbol, position in list(self.positions.items()):
            logger.info(f"Analyzing {symbol} (held since {position.buy_datetime})")

            # Get current price
            current_price = self.client.get_symbol_price(symbol)

            # Update ATH
            new_ath = max(position.ath, current_price)

            # Check trailing stop-loss (safety mechanism - highest priority)
            stop_loss_threshold = new_ath * (1 - settings.bot_trailing_stop_loss_pct / 100)
            if current_price < stop_loss_threshold:
                drop_from_ath_pct = ((new_ath - current_price) / new_ath) * 100
                logger.warning(
                    f"TRAILING STOP-LOSS triggered for {symbol}: "
                    f"price {current_price:.2f} dropped {drop_from_ath_pct:.1f}% from ATH {new_ath:.2f}"
                )
                self.sell_position(
                    symbol,
                    f"Trailing stop-loss: {drop_from_ath_pct:.1f}% drop from ATH {new_ath:.2f}"
                )
                continue

            # Multi-strategy confluence analysis
            signal, confidence, reason = self.analyze_position_with_strategies(symbol)

            # Sell if strategies indicate exit with sufficient confidence
            if signal in [Signal.SELL, Signal.STRONG_SELL] and confidence >= settings.bot_exit_min_confidence:
                logger.info(f"Strategy SELL signal for {symbol}: {reason} (confidence: {confidence:.0%})")
                self.sell_position(symbol, f"{reason} (conf: {confidence:.0%})")
                continue

            # Update ATH if new high reached
            if new_ath > position.ath:
                position.ath = new_ath
                self._save_positions()
                logger.info(f"{symbol} HOLDING - {reason} (ATH updated to {new_ath:.2f}, conf: {confidence:.0%})")
            else:
                logger.info(f"{symbol} HOLDING - {reason} (conf: {confidence:.0%})")

    def sell_position(self, symbol: str, reason: str) -> bool:
        """Sell a position and log the trade."""
        try:
            if symbol not in self.positions:
                logger.error(f"Cannot sell {symbol}: position not tracked")
                return False

            position = self.positions[symbol]
            amount = self.client.get_symbol_owned_amount(symbol)

            # Execute sell order
            response = self.client.sell(symbol, amount)

            if "error" in response:
                logger.error(f"Failed to sell {symbol}: {response['error']}")
                return False

            # Calculate actual execution price and profit/loss
            filled_amount = float(response['filledAmount'])
            sell_value = float(response['filledAmountQuote'])
            sell_fee = float(response['feePaid'])
            actual_sell_price = sell_value / filled_amount if filled_amount > 0 else 0
            profit_loss = sell_value - sell_fee - position.total_cost
            profit_loss_pct = (profit_loss / position.total_cost) * 100

            logger.info(
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
            logger.error(f"Error selling {symbol}: {e}")
            return False

    # Buying
    def find_opportunities(self, max_positions: int) -> list[tuple[str, str]]:
        """
        Find trading opportunities using multi-strategy confluence analysis.

        Returns:
            List of (symbol, reason) tuples
        """
        current_positions = len(self.positions)
        positions_to_open = max_positions - current_positions

        if positions_to_open <= 0:
            logger.info(f"Already at max positions ({current_positions}/{max_positions})")
            return []

        logger.info(f"Looking for {positions_to_open} new opportunities...")

        # Step 1: Pre-filter symbols by growth and volume
        logger.info("Filtering symbols by 24h growth > 0% and volume >= €{:,.0f}...".format(
            settings.bot_volume_limit
        ))

        candidates: list[tuple[str, float, float]] = []  # (symbol, growth_24h, volume_24h)
        available_symbols = self.client.get_available_symbols()

        for symbol in tqdm(
            available_symbols,
            desc="Pre-filtering symbols",
            unit="symbol",
            leave=False
        ):
            # Skip if already owned or is EUR
            if symbol in self.positions or symbol == "EUR":
                continue

            try:
                # Pre-filter: Check 24h growth (must be positive)
                growth_24h = self.client.get_symbol_24h_percentual_change(symbol)
                if growth_24h <= 0:
                    continue

                # Pre-filter: Check volume (must meet minimum threshold)
                volume_24h = self.client.get_symbol_24h_volume(symbol)
                if volume_24h < settings.bot_volume_limit:
                    continue

                candidates.append((symbol, growth_24h, volume_24h))

            except Exception as e:
                logger.debug(f"Skipping {symbol}: {e}")

        logger.info(f"Pre-filtered to {len(candidates)} candidate(s) with positive growth and sufficient volume")
        logger.info(f"  Candidates: {[symbol for symbol, _, _ in candidates]}")

        if not candidates:
            logger.info("No symbols passed pre-filtering criteria")
            return []

        # Step 2: Sort by 24h growth (integer %), then volume
        candidates.sort(key=lambda x: (int(x[1]), x[2]), reverse=True)

        logger.info(f"Analyzing top candidates (sorted by growth and volume)...")

        # Step 3: Analyze candidates in order until we have enough positions
        opportunities: list[tuple[str, str, float, float]] = []

        for symbol, growth_24h, volume_24h in candidates:
            # Early exit if we already have enough opportunities
            if len(opportunities) >= positions_to_open:
                logger.info(f"Found {positions_to_open} opportunities, stopping analysis early")
                break

            try:
                # Multi-strategy confluence analysis
                signal, confidence, reason = self.analyze_position_with_strategies(symbol)

                # Only consider BUY signals with sufficient confidence
                if signal not in [Signal.BUY, Signal.STRONG_BUY]:
                    logger.debug(f"{symbol}: {signal.value} signal (not buying)")
                    continue

                if confidence < settings.bot_entry_min_confidence:
                    logger.debug(f"{symbol}: {confidence:.0%} confidence (below {settings.bot_entry_min_confidence:.0%} threshold)")
                    continue

                full_reason = (
                    f"{reason} | 24h: +{growth_24h:.1f}% | "
                    f"Vol: €{volume_24h:,.0f} | Conf: {confidence:.0%}"
                )
                opportunities.append((symbol, full_reason, volume_24h, confidence))

                logger.info(f"Opportunity {len(opportunities)}/{positions_to_open}: {symbol} - {confidence:.0%} confidence, +{growth_24h:.1f}% growth")

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")

        # Log final results
        if opportunities:
            logger.info(f"Selected {len(opportunities)} opportunity/ies:")
            for i, (sym, reason, vol, conf) in enumerate(opportunities, 1):
                logger.info(f"  {i}. {sym}: {conf:.0%} confidence, €{vol:,.0f} volume")
        else:
            logger.info("No opportunities found matching entry criteria (signal + confidence)")

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
            logger.warning(
                f"Insufficient funds to open {positions_to_open} positions "
                f"({tradeable:.2f} EUR available, need {min_per_position * positions_to_open:.2f} EUR)"
            )
            return

        # Find opportunities
        opportunities = self.find_opportunities(max_positions)

        if not opportunities:
            logger.info("No opportunities found")
            return

        # Calculate amount per position
        amount_per_position = tradeable / len(opportunities)

        logger.info(
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
            # Execute buy order
            response = self.client.buy(symbol, amount_eur)

            if "error" in response:
                logger.error(f"Failed to buy {symbol}: {response['error']}")
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

            logger.info(
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
            logger.error(f"Error buying {symbol}: {e}")
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
                if not silent:
                    logger.info(f"Loaded {len(self.positions)} existing positions from S3 ({settings.s3_positions_key})")
            else:
                self.positions = {}
                if not silent:
                    logger.info("No existing positions found in S3")
        except Exception as e:
            if not silent:
                logger.error(f"Failed to load positions from S3: {e}")
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
                logger.info(f"Saved {len(self.positions)} positions to S3 ({settings.s3_positions_key})")
            else:
                logger.error("Failed to save positions to S3")
        except Exception as e:
            logger.error(f"Failed to save positions to S3: {e}")

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
                logger.info(f"Logged {action} trade for {symbol} to S3")
            else:
                logger.error(f"Failed to log {action} trade for {symbol} to S3")
        except Exception as e:
            logger.error(f"Failed to log trade to S3: {e}")


def main() -> None:
    """Entry point for the trading bot."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
