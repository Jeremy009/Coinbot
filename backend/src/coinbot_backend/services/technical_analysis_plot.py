"""
Comprehensive Technical Analysis Plotting

This module creates detailed charts showing all technical indicators used by trading strategies:
- Candlestick chart with EMA overlays and Bollinger Bands
- RSI with overbought/oversold levels
- MACD with signal line and histogram
- Trading volume

Usage:
    from coinbot_backend.services.technical_analysis_plot import plot_technical_analysis
    from coinbot_backend.services.bitvavo_client import get_bitvavo_client

    client = get_bitvavo_client()
    candles = client.get_candles("BTC", "1h", "2w")

    # Show interactive plot
    plot_technical_analysis(candles, show=True)

    # Save to file
    plot_technical_analysis(candles, save_path="analysis.png")

    # Get bytes for S3 upload
    chart_bytes = plot_technical_analysis(candles, return_bytes=True)
"""

import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.figure import Figure
from typing import Optional

from coinbot_backend.models.candles import OHLCVCandles
from coinbot_backend.services.trading_strategies import (
    calculate_rsi,
    calculate_macd,
    calculate_ema,
    calculate_bollinger_bands,
    strategy_multi_confluence,
    strategy_rsi_macd,
    strategy_ema_crossover,
    strategy_bollinger_mean_reversion,
)


def plot_technical_analysis(
    candles: OHLCVCandles,
    symbol: Optional[str] = None,
    buy_datetime: Optional[datetime] = None,
    show: bool = False,
    save_path: Optional[str] = None,
    return_bytes: bool = False,
    figsize: tuple[float, float] = (14, 10)
) -> Figure | bytes:
    """
    Create a comprehensive technical analysis chart with all indicators.

    Args:
        candles: OHLCVCandles object with price data
        symbol: Symbol name (optional, extracted from candles if available)
        buy_datetime: If provided, draws a green vertical line at the buy datetime
        show: If True, display the plot interactively
        save_path: If provided, save the plot to this path
        return_bytes: If True, return PNG bytes instead of Figure object
        figsize: Figure size in inches (width, height)

    Returns:
        Matplotlib Figure object or PNG bytes (if return_bytes=True)
    """
    # Extract data
    df = candles.as_dataframe()
    symbol = symbol or getattr(candles, 'symbol', 'Unknown')

    # Calculate all indicators
    close_prices = df['close'].to_numpy()
    high_prices = df['high'].to_numpy()
    low_prices = df['low'].to_numpy()

    # EMAs for price chart
    ema_12 = calculate_ema(close_prices, 12)
    ema_50 = calculate_ema(close_prices, 50)
    ema_200 = calculate_ema(close_prices, 200)

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close_prices, 20, 2.0)

    # RSI
    rsi = calculate_rsi(close_prices, 14)

    # MACD
    macd_line, macd_signal, macd_histogram = calculate_macd(close_prices, 12, 26, 9)

    # Get overall strategy signal
    try:
        signal = strategy_multi_confluence(candles)
        signal_text = f"{signal.signal.value.upper()} ({signal.confidence:.0%}): {signal.reason}"
    except Exception as e:
        signal_text = f"Signal calculation failed: {e}"

    # Get individual strategy signals
    individual_signals = []
    try:
        rsi_macd_sig = strategy_rsi_macd(candles)
        individual_signals.append(f"RSI+MACD: {rsi_macd_sig.signal.value.title()}")
    except Exception:
        individual_signals.append("RSI+MACD: Error")

    try:
        ema_sig = strategy_ema_crossover(candles)
        individual_signals.append(f"EMA Cross: {ema_sig.signal.value.title()}")
    except Exception:
        individual_signals.append("EMA Cross: Error")

    try:
        bb_sig = strategy_bollinger_mean_reversion(candles)
        individual_signals.append(f"Bollinger: {bb_sig.signal.value.title()}")
    except Exception:
        individual_signals.append("Bollinger: Error")

    strategies_text = " | ".join(individual_signals)

    # Create figure with subplots using constrained_layout (better than tight_layout)
    fig = plt.figure(figsize=figsize, constrained_layout=True)
    title_with_signal = f"{symbol} - Technical Analysis\n{signal_text}\n{strategies_text}"
    fig.suptitle(title_with_signal, fontsize=14, fontweight='bold')

    # Create grid for subplots (4 rows with different heights)
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.3)

    # 1. CANDLESTICK CHART with EMAs and Bollinger Bands
    ax1 = fig.add_subplot(gs[0])
    _plot_candlesticks_with_indicators(
        ax1, df, ema_12, ema_50, ema_200, bb_upper, bb_middle, bb_lower
    )

    # 2. RSI
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    _plot_rsi(ax2, df.index, rsi)

    # 3. MACD
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    _plot_macd(ax3, df.index, macd_line, macd_signal, macd_histogram)

    # 4. VOLUME
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    _plot_volume(ax4, df)

    # Add buy marker if provided (green vertical line)
    if buy_datetime is not None:
        # Find the index corresponding to the buy datetime
        buy_index = None
        for i, dt in enumerate(candles.timelabels):
            if isinstance(dt, datetime) and dt >= buy_datetime:
                buy_index = i
                break

        if buy_index is not None:
            # Add vertical line to all subplots
            for ax in [ax1, ax2, ax3, ax4]:
                ax.axvline(x=buy_index, color='green', linestyle='--', linewidth=1.5,
                          alpha=0.7, label='Buy' if ax == ax1 else None)

            # Update legend on first subplot to include buy marker
            ax1.legend(loc='upper left', fontsize=8, ncol=4)

    # Format x-axis (only show on bottom subplot)
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    plt.setp(ax3.get_xticklabels(), visible=False)

    # Add time labels to bottom subplot
    _format_time_axis(ax4, candles)

    # Save or return bytes
    if return_bytes:
        # Return PNG bytes for S3 upload
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf.read()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Chart saved to: {save_path}")

    if show:
        plt.show()

    return fig


def _plot_candlesticks_with_indicators(
    ax: plt.Axes,
    df: pd.DataFrame,
    ema_12: np.ndarray,
    ema_50: np.ndarray,
    ema_200: np.ndarray,
    bb_upper: np.ndarray,
    bb_middle: np.ndarray,
    bb_lower: np.ndarray
) -> None:
    """Plot candlesticks with EMA and Bollinger Band overlays."""
    candle_width = 0.6
    wick_width = 0.1

    # Separate up and down candles
    up = df[df['close'] >= df['open']]
    down = df[df['close'] < df['open']]

    # Plot up candles (green)
    ax.bar(up.index, up['close'] - up['open'], candle_width,
           bottom=up['open'], color='green', alpha=0.8)
    ax.bar(up.index, up['high'] - up['close'], wick_width,
           bottom=up['close'], color='green')
    ax.bar(up.index, up['low'] - up['open'], wick_width,
           bottom=up['open'], color='green')

    # Plot down candles (red)
    ax.bar(down.index, down['close'] - down['open'], candle_width,
           bottom=down['open'], color='red', alpha=0.8)
    ax.bar(down.index, down['high'] - down['open'], wick_width,
           bottom=down['open'], color='red')
    ax.bar(down.index, down['low'] - down['close'], wick_width,
           bottom=down['close'], color='red')

    # Plot EMAs
    ax.plot(df.index, ema_12, 'c-', linewidth=1, label='EMA 12', alpha=0.9)
    ax.plot(df.index, ema_50, 'b-', linewidth=1, label='EMA 50', alpha=0.9)
    ax.plot(df.index, ema_200, 'm-', linewidth=1.5, label='EMA 200', alpha=0.7)

    # Plot Bollinger Bands
    ax.plot(df.index, bb_upper, 'gray', linewidth=0.8, linestyle='--',
            label='BB Upper', alpha=0.6)
    ax.plot(df.index, bb_middle, 'gray', linewidth=0.8, linestyle='-',
            label='BB Middle', alpha=0.6)
    ax.plot(df.index, bb_lower, 'gray', linewidth=0.8, linestyle='--',
            label='BB Lower', alpha=0.6)
    ax.fill_between(df.index, bb_upper, bb_lower, color='gray', alpha=0.1)

    ax.set_ylabel('Price [EUR]', fontweight='bold')
    ax.set_title('Price Action with EMAs and Bollinger Bands')
    ax.legend(loc='upper left', fontsize=8, ncol=3)
    ax.grid(True, alpha=0.3)


def _plot_rsi(ax: plt.Axes, index: pd.Index, rsi: np.ndarray) -> None:
    """Plot RSI with overbought/oversold levels."""
    ax.plot(index, rsi, 'purple', linewidth=1.5, label='RSI (14)')

    # Overbought/oversold levels
    ax.axhline(y=70, color='r', linestyle='--', linewidth=0.8, alpha=0.7, label='Overbought (70)')
    ax.axhline(y=30, color='g', linestyle='--', linewidth=0.8, alpha=0.7, label='Oversold (30)')
    ax.axhline(y=50, color='gray', linestyle=':', linewidth=0.6, alpha=0.5)

    # Fill overbought/oversold zones
    ax.fill_between(index, 70, 100, color='red', alpha=0.1)
    ax.fill_between(index, 0, 30, color='green', alpha=0.1)

    ax.set_ylabel('RSI', fontweight='bold')
    ax.set_title('Relative Strength Index (RSI)')
    ax.set_ylim(0, 100)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_macd(
    ax: plt.Axes,
    index: pd.Index,
    macd_line: np.ndarray,
    macd_signal: np.ndarray,
    macd_histogram: np.ndarray
) -> None:
    """Plot MACD with signal line and histogram."""
    # Zero line
    ax.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)

    # MACD line and signal line
    ax.plot(index, macd_line, 'b-', linewidth=1.5, label='MACD Line')
    ax.plot(index, macd_signal, 'r-', linewidth=1.5, label='Signal Line')

    # Histogram (positive = green, negative = red)
    colors = ['green' if h >= 0 else 'red' for h in macd_histogram]
    ax.bar(index, macd_histogram, color=colors, alpha=0.5, width=0.8, label='Histogram')

    ax.set_ylabel('MACD', fontweight='bold')
    ax.set_title('MACD (12, 26, 9)')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_volume(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Plot trading volume with appropriate units."""
    # Color volume bars based on price movement
    colors = ['green' if df.iloc[i]['close'] >= df.iloc[i]['open'] else 'red'
              for i in range(len(df))]

    # Determine appropriate scale and units
    max_volume = df['volume'].max()
    if max_volume >= 1_000_000:
        # Millions
        volume_data = df['volume'] / 1_000_000
        unit_label = 'M EUR'
    elif max_volume >= 1_000:
        # Thousands
        volume_data = df['volume'] / 1_000
        unit_label = 'k EUR'
    else:
        # Raw EUR
        volume_data = df['volume']
        unit_label = 'EUR'

    ax.bar(df.index, volume_data, color=colors, alpha=0.6, width=0.8)
    ax.set_ylabel(f'Volume [{unit_label}]', fontweight='bold')
    ax.set_title('Trading Volume')
    ax.grid(True, alpha=0.3)


def _format_time_axis(ax: plt.Axes, candles: OHLCVCandles) -> None:
    """Format the x-axis with time labels at 00h00 and 12h00."""
    from datetime import datetime

    num_candles = len(candles.timestamps)

    # Find indices where time is 00:00 or 12:00
    label_indices = []
    label_values = []

    if hasattr(candles, 'timelabels') and candles.timelabels:
        for i, dt in enumerate(candles.timelabels):
            if isinstance(dt, datetime):
                # Only show labels at 00:00 and 12:00
                if dt.hour in [0, 12] and dt.minute == 0:
                    label_indices.append(i)
                    # Format as "DD-MM HHhMM" (e.g., "02-01 00h00")
                    label_values.append(dt.strftime('%d-%m %Hh%M'))

    # If no labels found (e.g., short timeframe), fallback to evenly spaced
    if not label_indices:
        mod = max(1, num_candles // 20)
        label_indices = [i for i in range(num_candles) if i % mod == 0]
        if hasattr(candles, 'timelabels') and candles.timelabels:
            for i in label_indices:
                dt = candles.timelabels[i]
                if isinstance(dt, datetime):
                    label_values.append(dt.strftime('%d-%m %Hh%M'))
                else:
                    label_values.append(str(dt))
        else:
            label_values = [str(i) for i in label_indices]

    ax.set_xticks(label_indices)
    ax.set_xticklabels(label_values, rotation=45, ha='right')
    ax.set_xlabel('Time', fontweight='bold')
