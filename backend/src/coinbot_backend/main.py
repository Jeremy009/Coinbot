"""Main trading bot application with position tracking and multi-strategy support."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from coinbot_backend.config import settings
from coinbot_backend.models.trading import OpenPosition
from coinbot_backend.services.bitvavo_client import get_bitvavo_client
from coinbot_backend.services.indicators import macd_indicator
from coinbot_backend.services.signals import TradebotAction, macd_signal
from coinbot_backend.services.strategies import Signal, get_all_signals

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Trading bot with position tracking and multi-strategy support.

    The bot manages open positions, tracks buy/sell decisions with reasons,
    and logs all trades to a JSON file for analysis.
    """

    def __init__(self, positions_file: str = "positions.json", trades_log_file: str = "trades.log.json"):
        """Initialize the trading bot."""
        self.client = get_bitvavo_client()
        self.positions_file = Path(positions_file)
        self.trades_log_file = Path(trades_log_file)
        self.positions: dict[str, OpenPosition] = {}

        # Load existing positions if file exists
        if self.positions_file.exists():
            self._load_positions()

    def _load_positions(self) -> None:
        """Load positions from JSON file."""
        try:
            with open(self.positions_file) as f:
                data = json.load(f)
                self.positions = {
                    symbol: OpenPosition(**pos_data)
                    for symbol, pos_data in data.items()
                }
            logger.info(f"Loaded {len(self.positions)} existing positions from {self.positions_file}")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            self.positions = {}

    def _save_positions(self) -> None:
        """Save positions to JSON file."""
        try:
            data = {
                symbol: pos.model_dump(mode="json")
                for symbol, pos in self.positions.items()
            }
            with open(self.positions_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.positions)} positions to {self.positions_file}")
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def _log_trade(self, action: str, symbol: str, details: dict[str, Any]) -> None:
        """Log a trade to the trades log file."""
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            **details
        }

        try:
            # Append to log file
            logs = []
            if self.trades_log_file.exists():
                with open(self.trades_log_file) as f:
                    logs = json.load(f)

            logs.append(trade_entry)

            with open(self.trades_log_file, "w") as f:
                json.dump(logs, f, indent=2, default=str)

            logger.info(f"Logged {action} trade for {symbol}")
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def get_account_balance(self) -> dict[str, float]:
        """Get current account balance information."""
        return {
            "available_funds": self.client.get_available_funds(),
            "total_deposited": self.client.get_total_deposited(),
            "total_withdrawn": self.client.get_total_withdrawn(),
            "total_gains": self.client.get_total_gains(),
        }

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
                    total_cost=amount * price,
                    reason_for_buying="Pre-existing or manual trade (not tracked)"
                )

        self._save_positions()
        return self.positions

    def analyze_position_with_macd(self, symbol: str) -> TradebotAction:
        """Analyze a position using MACD indicator."""
        try:
            candles = self.client.get_candles(
                symbol,
                settings.bot_macd_timeresolution,
                "1m"
            )

            if len(candles.timestamps) < 90:
                logger.warning(f"Insufficient candle data for {symbol}")
                return TradebotAction.HOLD

            macd_df = macd_indicator(
                candles,
                settings.bot_macd_short_period,
                settings.bot_macd_long_period,
                settings.bot_macd_signal_period
            )

            return macd_signal(macd_df)

        except Exception as e:
            logger.error(f"Failed to analyze {symbol} with MACD: {e}")
            return TradebotAction.HOLD

    def analyze_position_with_strategies(self, symbol: str) -> tuple[Signal, float, str]:
        """
        Analyze a position using the multi-strategy confluence approach.

        Returns:
            Tuple of (signal, confidence, reason)
        """
        try:
            candles = self.client.get_candles(symbol, "1h", "1w")

            if len(candles.timestamps) < 200:
                logger.warning(f"Insufficient data for advanced strategies on {symbol}")
                return Signal.HOLD, 0.5, "Insufficient historical data"

            signals = get_all_signals(candles)
            confluence = signals["confluence"]

            return confluence.signal, confluence.confidence, confluence.reason

        except Exception as e:
            logger.error(f"Failed to analyze {symbol} with strategies: {e}")
            return Signal.HOLD, 0.5, f"Analysis error: {str(e)}"

    def evaluate_existing_positions(self) -> None:
        """Evaluate all existing positions and decide whether to hold or sell."""
        logger.info(f"Evaluating {len(self.positions)} existing positions...")

        for symbol, position in list(self.positions.items()):
            logger.info(f"Analyzing {symbol} (held since {position.buy_datetime})")

            # Use MACD for quick decision
            macd_action = self.analyze_position_with_macd(symbol)

            if macd_action == TradebotAction.SELL:
                logger.info(f"MACD signals SELL for {symbol}")
                self.sell_position(symbol, "MACD sell signal")

            elif macd_action == TradebotAction.BUY:
                logger.info(f"{symbol} shows MACD BUY signal - HOLDING")

            else:  # HOLD
                # Use advanced strategies for additional confirmation
                signal, confidence, reason = self.analyze_position_with_strategies(symbol)

                if signal in [Signal.SELL, Signal.STRONG_SELL] and confidence > 0.65:
                    logger.info(f"Advanced strategies signal SELL for {symbol}: {reason}")
                    self.sell_position(symbol, f"Strategy sell: {reason}")
                else:
                    logger.info(f"{symbol} HOLDING - {reason}")

    def sell_position(self, symbol: str, reason: str) -> bool:
        """Sell a position and log the trade."""
        try:
            if symbol not in self.positions:
                logger.error(f"Cannot sell {symbol}: position not tracked")
                return False

            position = self.positions[symbol]
            amount = self.client.get_symbol_owned_amount(symbol)
            current_price = self.client.get_symbol_price(symbol)

            # Execute sell order
            response = self.client.sell(symbol, amount)

            if "error" in response:
                logger.error(f"Failed to sell {symbol}: {response['error']}")
                return False

            # Calculate profit/loss
            sell_value = float(response['filledAmountQuote'])
            profit_loss = sell_value - position.total_cost
            profit_loss_pct = (profit_loss / position.total_cost) * 100

            logger.info(
                f"SOLD {symbol}: {response['filledAmount']} @ {current_price:.2f} EUR/coin "
                f"(P/L: {profit_loss:+.2f} EUR / {profit_loss_pct:+.2f}%)"
            )

            # Log the trade
            self._log_trade("SELL", symbol, {
                "reason": reason,
                "amount": float(response['filledAmount']),
                "sell_price": current_price,
                "sell_value": sell_value,
                "buy_price": position.buy_price,
                "buy_cost": position.total_cost,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "hold_duration_hours": (datetime.now() - position.buy_datetime).total_seconds() / 3600,
                "fee": float(response['feePaid']),
            })

            # Remove from positions
            del self.positions[symbol]
            self._save_positions()

            return True

        except Exception as e:
            logger.error(f"Error selling {symbol}: {e}")
            return False

    def find_opportunities(self, max_positions: int) -> list[tuple[str, str]]:
        """
        Find trading opportunities using MACD analysis.

        Returns:
            List of (symbol, reason) tuples
        """
        current_positions = len(self.positions)
        positions_to_open = max_positions - current_positions

        if positions_to_open <= 0:
            logger.info(f"Already at max positions ({current_positions}/{max_positions})")
            return []

        logger.info(f"Looking for {positions_to_open} new opportunities...")

        opportunities: list[tuple[str, str, float]] = []

        for symbol in self.client.get_available_symbols():
            # Skip if already owned
            if symbol in self.positions:
                continue

            # Skip EUR
            if symbol == "EUR":
                continue

            try:
                # Check 24h growth
                growth_24h = self.client.get_symbol_24h_percentual_change(symbol)
                if growth_24h <= 0:
                    continue

                # Check volume
                volume_24h = self.client.get_symbol_24h_volume(symbol)
                if volume_24h < settings.bot_volume_limit:
                    continue

                # Check MACD
                macd_action = self.analyze_position_with_macd(symbol)
                if macd_action != TradebotAction.BUY:
                    continue

                reason = f"MACD BUY signal, 24h growth: {growth_24h:.2f}%, volume: {volume_24h:,.0f} EUR"
                opportunities.append((symbol, reason, volume_24h))

                logger.debug(f"Opportunity: {symbol} - {reason}")

            except Exception as e:
                logger.debug(f"Skipping {symbol}: {e}")

        # Sort by volume and return top opportunities
        opportunities.sort(key=lambda x: x[2], reverse=True)
        return [(sym, reason) for sym, reason, _ in opportunities[:positions_to_open]]

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
                "fee": fee,
            })

            return True

        except Exception as e:
            logger.error(f"Error buying {symbol}: {e}")
            return False

    def open_new_positions(self, max_positions: int) -> None:
        """Find and open new trading positions."""
        balance = self.get_account_balance()
        available = balance["available_funds"]

        # Keep some buffer
        tradeable = available * 0.975
        min_per_position = 5.1

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

        logger.info(f"Opening {len(opportunities)} positions with {amount_per_position:.2f} EUR each")

        # Buy the symbols
        for symbol, reason in opportunities:
            self.buy_symbol(symbol, amount_per_position, reason)
            time.sleep(1)  # Small delay between buys

    def run_iteration(self) -> None:
        """Run one iteration of the trading bot."""
        logger.info("=" * 80)
        logger.info(f"Bot iteration started at {datetime.now()}")
        logger.info("=" * 80)

        # Get current state
        balance = self.get_account_balance()
        logger.info(f"Available funds: {balance['available_funds']:.2f} EUR")
        logger.info(f"Total gains: {balance['total_gains']:+.2f} EUR")

        # Update positions
        self.get_current_positions()

        # Evaluate existing positions (may sell some)
        self.evaluate_existing_positions()

        # Look for new opportunities
        self.open_new_positions(settings.bot_num_positions)

        logger.info(f"Iteration complete. Open positions: {len(self.positions)}")

    def run(self) -> None:
        """Run the bot in an infinite loop."""
        if not settings.bot_enabled:
            logger.error("Bot is not enabled in settings. Set BOT_ENABLED=true to start.")
            return

        logger.info("=" * 80)
        logger.info(f"Starting {settings.app_name} Trading Bot v{settings.app_version}")
        logger.info(f"Max positions: {settings.bot_num_positions}")
        logger.info(f"Update interval: {settings.bot_update_interval} minutes")
        logger.info(f"Volume threshold: {settings.bot_volume_limit:,.0f} EUR")
        logger.info("=" * 80)

        while True:
            try:
                iteration_start = datetime.now()

                self.run_iteration()

                # Calculate sleep time
                iteration_duration = (datetime.now() - iteration_start).total_seconds()
                sleep_time = (settings.bot_update_interval * 60) - iteration_duration

                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time:.0f} seconds until next iteration...")
                    logger.info("=" * 80)
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Iteration took {iteration_duration:.0f}s (longer than update interval)")

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in bot iteration: {e}", exc_info=True)
                logger.info("Sleeping 60 seconds before retry...")
                time.sleep(60)


def main() -> None:
    """Entry point for the trading bot."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
