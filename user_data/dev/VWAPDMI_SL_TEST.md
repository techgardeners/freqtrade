# VWAPDMIS Stop Loss Testing

## Versions to Test

### 1. Original (Current)

- `atr_multiplier = 2.04`
- No max stop loss limit
- **Problem**: Can have 24%+ stop loss

### 2. Version with Max SL Cap

- `atr_multiplier = 2.04`
- `max_stoploss_pct = 0.05` (5% max)
- **Fix**: Caps stop loss at 5%

### 3. Version with Reduced ATR + Cap

- `atr_multiplier = 1.5`
- `max_stoploss_pct = 0.05` (5% max)
- **Fix**: Tighter stops + safety cap

## Test Plan

1. Backtest original (baseline)
2. Create V2 with max_stoploss_pct
3. Backtest V2
4. Create V3 with reduced ATR
5. Backtest V3
6. Compare results
