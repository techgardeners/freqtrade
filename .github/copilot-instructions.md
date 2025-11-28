# Freqtrade AI Coding Agent Instructions

## Project Overview
Freqtrade is an open-source cryptocurrency trading bot written in Python. Key architectural components:

- **Core Engine**: `freqtrade/freqtradebot.py` - main bot orchestration
- **Strategies**: `user_data/strategies/` - trading logic (inherit from `IStrategy`)  
- **Exchange Layer**: `freqtrade/exchange/` - handles all exchange interactions via CCXT
- **Data Management**: `freqtrade/data/` - OHLCV data, backtesting datasets
- **FreqAI**: `freqtrade/freqai/` - machine learning prediction framework
- **Persistence**: `freqtrade/persistence/` - SQLAlchemy models for trades, orders

## Strategy Development Patterns

### Strategy Structure
All strategies inherit from `IStrategy` with required methods:
```python
class MyStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    minimal_roi = {"0": 0.04}
    stoploss = -0.10
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Add technical indicators here
        
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Define buy conditions
        
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Define sell conditions
```

### Key Conventions
- Use `@informative` decorator for higher timeframe data
- Hyperopt parameters: `IntParameter()`, `DecimalParameter()`, etc.
- Always include `startup_candle_count` for indicator warmup
- Use `qtpylib` and `talib.abstract` for technical analysis

## Configuration Architecture

### JSON Schema Validation
All configs validated against `build_helpers/schema.json`. Key sections:
- `exchange`: Exchange-specific settings (API keys, sandbox mode)
- `trading_mode`: "spot" or "futures" 
- `stake_currency`/`stake_amount`: Position sizing
- `pairlists`: Dynamic pair selection plugins
- `freqai`: ML model configuration (if using)

### Config Hierarchy
1. CLI arguments override
2. User config.json  
3. Strategy defaults
4. System defaults in `constants.py`

## Development Workflow

### Setup Commands
```bash
./setup.sh                    # Auto-detects Python 3.11+, uses uv if available
freqtrade create-userdir      # Creates user_data/ structure  
freqtrade new-strategy --strategy MyStrategy
```

### Testing Commands
```bash
pytest tests/                 # Full test suite
freqtrade backtesting --strategy MyStrategy --config config.json
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT
```

### Key CLI Commands
- `freqtrade trade`: Live trading mode
- `freqtrade hyperopt`: Strategy optimization
- `freqtrade plot-dataframe`: Generate strategy plots
- `freqtrade webserver`: Launch web UI

## FreqAI Integration

When working with machine learning features:
- Models in `freqtrade/freqai/prediction_models/`
- Data preprocessing in `freqai/data_kitchen.py`
- Feature engineering in strategy's `populate_any_indicators()`
- Use `freqai_config` section in main config

## Database & Persistence

- Uses SQLAlchemy ORM with models in `freqtrade/persistence/`
- Default SQLite: `tradesv3.sqlite` (live), `tradesv3.dryrun.sqlite` (paper)
- Key models: `Trade`, `Order`, `PairLocks`
- Migration scripts handle schema updates

## Plugin Architecture

### Pairlists
Located in `freqtrade/plugins/pairlist/`, dynamically filter trading pairs:
- `StaticPairList`: Fixed pair list
- `VolumePairList`: Volume-based filtering
- `PriceFilter`: Price range filtering

### Protections  
In `freqtrade/plugins/protections/`, implement risk management:
- `StoplossGuard`: Prevent trading after stop losses
- `CooldownPeriod`: Time-based trading locks

## Exchange Integration

- All exchange logic via CCXT in `freqtrade/exchange/`
- Exchange-specific quirks handled in dedicated files
- Rate limiting and retry logic built-in
- Support for both spot and futures trading modes

## Common Pitfalls

1. **Indicator Lag**: Use `startup_candle_count` to ensure indicators have sufficient data
2. **Look-ahead Bias**: Never use future data in `populate_*` methods  
3. **Paper Trading**: Always test with `dry_run: true` before live trading
4. **Timeframe Alignment**: Ensure all timeframes are exchange-supported
5. **Schema Validation**: Invalid configs fail at startup - check against schema.json

## File Modification Guidelines

- Strategy changes: Only modify files in `user_data/`
- Core changes: Follow existing patterns in `freqtrade/`
- Tests required for new features in `tests/`
- Use type hints throughout (project targets Python 3.11+)
- Follow existing import organization (see strategy template)

## Resources

- Configuration schema: `build_helpers/schema.json`
- Strategy examples: `freqtrade/templates/`  
- Documentation: https://www.freqtrade.io/
- Exchange notes: `docs/exchanges.md`