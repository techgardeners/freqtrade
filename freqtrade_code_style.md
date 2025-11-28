# Code Style Rules -- Freqtrade Strategies

## 1. Purpose

This document defines the **coding standards** for all Freqtrade
strategies in this project.\
Its goals are:

-   keep code clean, consistent, and easy to maintain\
-   separate trading logic from parameters and risk\
-   standardize structure across all strategies\
-   simplify backtesting, debugging, and collaboration

**All comments and documentation must always be written in English.**

------------------------------------------------------------------------

## 2. General Python Rules

### 2.1 PEP8 as baseline

-   4 spaces indentation\
-   \~100 characters per line (soft limit)\
-   always use a formatter (e.g., `black`) when possible

### 2.2 Naming conventions

-   Class names: `CamelCase` → `TrendFollowingStrategy`\
-   Methods & variables: `snake_case` → `populate_indicators`,
    `ema_fast`\
-   Boolean variables start with `is_`, `has_`, `should_`\
-   Indicator names must be descriptive:
    -   `ema_fast`, `rsi_14`, `atr_14`, `bb_lower`

### 2.3 Comments and language

-   All comments **must be in English**\
-   No Italian variable names\
-   Use docstrings for every strategy class

### 2.4 Type hints

Use type hints especially in custom methods:

``` python
def custom_entry_price(self, pair: str, trade: Trade, current_time: datetime,
                       proposed_rate: float, **kwargs) -> float:
    ...
```

------------------------------------------------------------------------

## 3. Strategy File Structure

A strategy file must follow this structure:

1.  **Imports**
    -   Standard library\
    -   Third‑party libraries\
    -   Freqtrade modules\
    -   Project modules
2.  **Class docstring**
3.  **Core settings** (timeframe, minimal_roi, stoploss, trailing,
    protections...)\
4.  **Hyperopt parameters**\
5.  **populate_indicators**\
6.  **populate_entry_trend / populate_buy_trend**\
7.  **populate_exit_trend / populate_sell_trend**\
8.  **custom_stoploss**\
9.  **custom_entry_price / custom_exit_price**\
10. **leverage** (if futures)\
11. **custom_stake_amount**\
12. **Private helper methods**

------------------------------------------------------------------------

## 4. Indicators Rules

### 4.1 Naming

-   Prefix clearly: `ema_fast`, `ema_slow`, `rsi_14`, `atr_14`\
-   No generic names like `x1`, `test`, `tmp`

### 4.2 Calculation location

-   **All indicators must be calculated only inside
    `populate_indicators`**\
-   Entry/exit functions must never compute indicators again

### 4.3 Comment complex indicators

``` python
# Volatility calculation: ATR-based stop distance
dataframe['atr_14'] = ta.ATR(...)
```

------------------------------------------------------------------------

## 5. Entry & Exit Logic

### 5.1 Entry rules

Define conditions with readable names:

``` python
ema_trend_long = dataframe['ema_fast'] > dataframe['ema_slow']
rsi_oversold = dataframe['rsi_14'] < self.buy_rsi.value

dataframe.loc[ema_trend_long & rsi_oversold, 'enter_long'] = 1
```

### 5.2 Exit rules

Must be explicit: trend change, TP, volatility exit, etc.

### 5.3 Custom stoploss

-   Must be documented\
-   No unexplained formulas\
-   Keep it short and readable

------------------------------------------------------------------------

## 6. Risk & Position Sizing

### 6.1 Centralize risk in `custom_stake_amount`

Do not allocate stake directly elsewhere.

### 6.2 Naming conventions

-   `risk_per_trade_fraction`\
-   `max_leverage`\
-   `max_risk_per_pair`\
-   `max_daily_drawdown`

### 6.3 Comment formulas

Every risk formula must explain the financial logic.

------------------------------------------------------------------------

## 7. Logging Standards

### 7.1 No `print()`

Use strategy logger only.

### 7.2 Use correct log levels

-   `debug` for indicator values\
-   `info` for important events

### 7.3 Meaningful log messages

Not allowed: `"debug here"`\
Allowed: `"EMA trend reversed, closing long position."`

------------------------------------------------------------------------

## 8. Versioning

Each strategy must include:

``` python
STRATEGY_VERSION = "1.0.0"  # Initial version
```

Include short change notes in the docstring.

------------------------------------------------------------------------

## 9. Repository Structure

Suggested structure:

    strategies/
        base/
        trend/
        mean_reversion/
    tests/
    docs/
        strategies/

Each strategy must have a documentation file in `docs/strategies/`.

------------------------------------------------------------------------

## 10. Helpers / Utilities

-   Shared indicator logic must be in `helpers_indicators.py`\
-   Shared risk logic must be in `helpers_risk.py`\
-   No code duplication between strategies
