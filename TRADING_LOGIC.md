# COMPLETE TRADING DECISION LOGIC

## Configuration Constants

```python
BOT_MIN_GROWTH_24H = -10.0%           # Minimum 24h growth
BOT_VOLUME_LIMIT = €500,000           # Minimum 24h volume
BOT_ENTRY_MIN_CONFIDENCE = 60%        # Minimum confidence to BUY
BOT_EXIT_MIN_CONFIDENCE = 65%         # Minimum confidence to SELL
BOT_TRAILING_STOP_LOSS_PCT = 8.0%     # Trailing stop-loss threshold
BOT_NUM_POSITIONS = 5                 # Maximum positions
BOT_MAX_ALLOCATION_PERCENT = 5.0%     # % of funds to use
```

---

## DECISION 1: IGNORE (Symbol Not Owned)

### Pre-Filter Conditions (Fast Rejection)

Symbol is IGNORED if ANY of these are true:

```python
# Pre-filter rejections:
symbol == "EUR"                                    → IGNORE
symbol in existing_positions                       → IGNORE
growth_24h < BOT_MIN_GROWTH_24H (-10%)            → IGNORE
volume_24h < BOT_VOLUME_LIMIT (€500k)             → IGNORE
len(existing_positions) >= BOT_NUM_POSITIONS       → IGNORE
```

### Strategy Analysis (Passed Pre-Filter)

Symbol passes to multi-strategy confluence analysis:

```python
# Get 3 independent strategy signals:
rsi_macd_signal = strategy_rsi_macd(candles)
ema_signal = strategy_ema_crossover(candles)
bb_signal = strategy_bollinger_mean_reversion(candles)

# Count agreements:
buy_signals = count(signal in [BUY, STRONG_BUY])
sell_signals = count(signal in [SELL, STRONG_SELL])

# Multi-strategy confluence decision:
if buy_signals == 3:
    signal = STRONG_BUY
    confidence = min(95%, avg_confidence + 20%)

elif buy_signals >= 2:
    signal = BUY
    confidence = avg_confidence

elif sell_signals == 3:
    signal = STRONG_SELL
    confidence = min(95%, avg_confidence + 20%)

elif sell_signals >= 2:
    signal = SELL
    confidence = avg_confidence

else:
    signal = HOLD
    confidence = 50%
```

Symbol is IGNORED if:

```python
signal NOT in [BUY, STRONG_BUY]                   → IGNORE (X_ chart)
confidence < BOT_ENTRY_MIN_CONFIDENCE (60%)       → IGNORE (X_ chart)
insufficient_funds_remaining                       → IGNORE
```

---

## DECISION 2: BUY (Open New Position)

Symbol is BOUGHT if ALL conditions are met:

```python
# Must pass ALL pre-filters:
growth_24h >= -10%                                 ✓
volume_24h >= €500,000                             ✓
symbol not in existing_positions                   ✓
len(existing_positions) < BOT_NUM_POSITIONS        ✓

# AND must pass strategy analysis:
signal in [BUY, STRONG_BUY]                        ✓
confidence >= BOT_ENTRY_MIN_CONFIDENCE (60%)       ✓

# AND must have funds:
available_funds * 0.05 >= min_position_size        ✓

# RESULT:
→ Execute market BUY order (B_ chart generated)
→ Track position with buy_datetime, buy_price, ATH
```

**Mathematical Example:**
```
Symbol: ETH
growth_24h = -3.5% (>= -10% ✓)
volume_24h = €2,150,000 (>= €500k ✓)
rsi_macd = BUY (confidence 70%)
ema_crossover = BUY (confidence 65%)
bollinger = HOLD
→ buy_signals = 2
→ signal = BUY, confidence = 67.5%
→ 67.5% >= 60% ✓
→ BUY EXECUTED
```

---

## DECISION 3: SELL (Close Existing Position)

For each existing position, check conditions in THIS ORDER:

### Priority 1: Trailing Stop-Loss (Safety Override)

```python
# Calculate stop-loss threshold:
ATH = max(position.ath, current_price)
stop_loss_threshold = ATH * (1 - 0.08)  # 8% trailing

# SELL immediately if:
current_price < stop_loss_threshold                → SELL (S_ chart)

# Example:
# ATH = €100
# Threshold = €100 * 0.92 = €92
# Current = €91
# → SELL IMMEDIATELY (trailing stop triggered)
```

### Priority 2: Strategy-Based Exit

```python
# If stop-loss NOT triggered, run strategy analysis:
confluence = strategy_multi_confluence(candles)
signal = confluence.signal
confidence = confluence.confidence

# SELL if BOTH conditions met:
signal in [SELL, STRONG_SELL]                      AND
confidence >= BOT_EXIT_MIN_CONFIDENCE (65%)        → SELL (S_ chart)

# Example:
# signal = SELL
# confidence = 70%
# → 70% >= 65% ✓
# → SELL EXECUTED
```

---

## DECISION 4: HOLD (Keep Existing Position)

Position is HELD if:

```python
# Stop-loss NOT triggered:
current_price >= ATH * 0.92                        ✓

# AND strategy does NOT indicate strong exit:
NOT (signal in [SELL, STRONG_SELL] AND confidence >= 65%)  ✓

# Possible scenarios:
# 1. signal = BUY → HOLD (bullish, keep holding)
# 2. signal = HOLD → HOLD (neutral, wait)
# 3. signal = SELL, confidence = 55% → HOLD (weak sell, below 65% threshold)

# RESULT:
→ Update ATH if current_price > position.ath
→ Generate H_ chart with green buy marker
→ Position remains open
```

**Mathematical Example:**
```
Position: SOL
buy_price = €80
current_price = €85
ATH = €90
stop_loss_threshold = €90 * 0.92 = €82.80

Check 1: €85 >= €82.80 ✓ (stop-loss OK)
Check 2: confluence analysis
  → signal = SELL, confidence = 62%
  → 62% < 65% (below exit threshold)
→ HOLD (insufficient confidence to sell)
```

---

## Individual Strategy Conditions

### Strategy 1: RSI + MACD

```python
RSI = calculate_rsi(close_prices, period=14)
MACD_line, MACD_signal, MACD_histogram = calculate_macd(close, 12, 26, 9)

# STRONG BUY conditions:
RSI[-1] < 30                          AND    # Oversold
MACD_histogram[-1] > 0                AND    # Bullish momentum
MACD_line[-1] > MACD_signal[-1]       AND    # MACD above signal
MACD_histogram[-1] > MACD_histogram[-2]      # Strengthening
→ STRONG_BUY (confidence 85%)

# BUY conditions:
RSI[-1] < 45                          AND    # Moderately oversold
MACD_histogram[-1] > 0                AND    # Bullish momentum
MACD_line[-1] > MACD_signal[-1]            # MACD above signal
→ BUY (confidence 70%)

# STRONG SELL conditions:
RSI[-1] > 70                          AND    # Overbought
MACD_histogram[-1] < 0                AND    # Bearish momentum
MACD_line[-1] < MACD_signal[-1]       AND    # MACD below signal
MACD_histogram[-1] < MACD_histogram[-2]      # Weakening
→ STRONG_SELL (confidence 85%)

# SELL conditions:
RSI[-1] > 55                          AND    # Moderately overbought
MACD_histogram[-1] < 0                AND    # Bearish momentum
MACD_line[-1] < MACD_signal[-1]            # MACD below signal
→ SELL (confidence 70%)

# Otherwise: HOLD (confidence 50%)
```

### Strategy 2: EMA Crossover

```python
EMA_12 = calculate_ema(close, 12)
EMA_50 = calculate_ema(close, 50)
EMA_200 = calculate_ema(close, 200)

# STRONG BUY (Golden Cross with trend):
EMA_12[-1] > EMA_50[-1]               AND    # Fast above slow
EMA_12[-2] <= EMA_50[-2]              AND    # Crossover just happened
EMA_50[-1] > EMA_200[-1]              AND    # Above long-term trend
price[-1] > EMA_200[-1]                      # Price above trend
→ STRONG_BUY (confidence 85%)

# BUY (Bullish alignment):
EMA_12[-1] > EMA_50[-1] > EMA_200[-1] AND    # All aligned
price[-1] > EMA_12[-1]                       # Price leading
→ BUY (confidence 70%)

# STRONG SELL (Death Cross):
EMA_12[-1] < EMA_50[-1]               AND    # Fast below slow
EMA_12[-2] >= EMA_50[-2]              AND    # Crossover just happened
EMA_50[-1] < EMA_200[-1]              AND    # Below long-term trend
price[-1] < EMA_200[-1]                      # Price below trend
→ STRONG_SELL (confidence 85%)

# SELL (Bearish alignment):
EMA_12[-1] < EMA_50[-1] < EMA_200[-1] AND    # All aligned bearish
price[-1] < EMA_12[-1]                       # Price trailing
→ SELL (confidence 70%)

# Otherwise: HOLD (confidence 50%)
```

### Strategy 3: Bollinger Bands Mean Reversion

```python
BB_upper, BB_middle, BB_lower = calculate_bollinger_bands(close, 20, 2.0)
RSI = calculate_rsi(close, 14)

# STRONG BUY (Oversold bounce):
price[-1] < BB_lower[-1]              AND    # Below lower band
RSI[-1] < 30                          AND    # RSI oversold
price[-1] > price[-2]                        # Starting to bounce
→ STRONG_BUY (confidence 80%)

# BUY (Near lower band):
price[-1] <= BB_lower[-1] * 1.02      AND    # Within 2% of lower band
RSI[-1] < 40                                 # Moderately oversold
→ BUY (confidence 65%)

# STRONG SELL (Overbought reversal):
price[-1] > BB_upper[-1]              AND    # Above upper band
RSI[-1] > 70                          AND    # RSI overbought
price[-1] < price[-2]                        # Starting to reverse
→ STRONG_SELL (confidence 80%)

# SELL (Near upper band):
price[-1] >= BB_upper[-1] * 0.98      AND    # Within 2% of upper band
RSI[-1] > 60                                 # Moderately overbought
→ SELL (confidence 65%)

# Otherwise: HOLD (confidence 50%)
```

---

## Complete Decision Tree

```
START
  ↓
Is symbol owned?
  ├─ YES → Go to EXISTING POSITION LOGIC
  └─ NO → Go to NEW POSITION LOGIC

NEW POSITION LOGIC:
  ↓
Pre-filter checks:
  ├─ growth_24h < -10%? → IGNORE
  ├─ volume_24h < €500k? → IGNORE
  ├─ symbol == "EUR"? → IGNORE
  ├─ positions >= 5? → IGNORE
  └─ ALL PASS → Continue
  ↓
Run 3 strategies:
  ├─ RSI+MACD → signal_1
  ├─ EMA Cross → signal_2
  └─ Bollinger → signal_3
  ↓
Count agreements:
  ├─ 3 BUY signals → STRONG_BUY (confidence ~85%)
  ├─ 2 BUY signals → BUY (confidence ~68%)
  ├─ 3 SELL signals → STRONG_SELL (confidence ~85%)
  ├─ 2 SELL signals → SELL (confidence ~68%)
  └─ else → HOLD (confidence 50%)
  ↓
Is signal BUY/STRONG_BUY?
  ├─ NO → IGNORE (generate X_ chart)
  └─ YES → Continue
  ↓
Is confidence >= 60%?
  ├─ NO → IGNORE (generate X_ chart)
  └─ YES → BUY (generate B_ chart)

EXISTING POSITION LOGIC:
  ↓
Get current_price and ATH
  ↓
Trailing stop check:
  current_price < ATH * 0.92?
  ├─ YES → SELL immediately (generate S_ chart)
  └─ NO → Continue
  ↓
Run confluence strategy:
  → signal, confidence
  ↓
Is (signal == SELL/STRONG_SELL) AND (confidence >= 65%)?
  ├─ YES → SELL (generate S_ chart)
  └─ NO → HOLD (generate H_ chart with buy marker)
```

---

## Key Thresholds Summary

| Decision | Minimum Confluence | Minimum Confidence |
|----------|-------------------|-------------------|
| BUY new position | 2+ strategies agree BUY | 60% |
| SELL existing position (strategy) | 2+ strategies agree SELL | 65% |
| SELL existing position (stop-loss) | N/A (price-based) | N/A |
| IGNORE symbol | <2 strategies agree | <60% confidence |
| HOLD position | <2 SELL strategies OR <65% confidence | N/A |

---

## Chart Types

All analyzed symbols generate technical analysis charts uploaded to S3:

- **B_SYMBOL.png**: Position was BOUGHT (shows conditions at entry)
- **H_SYMBOL.png**: Position is HELD (includes green vertical line at buy datetime)
- **S_SYMBOL.png**: Position was SOLD (shows conditions at exit)
- **X_SYMBOL.png**: Symbol was REJECTED (passed pre-filter but failed strategy criteria)

Charts are saved to: `s3://{bucket}/runs/YYYYMMDD_HHMM/{chart}.png`
