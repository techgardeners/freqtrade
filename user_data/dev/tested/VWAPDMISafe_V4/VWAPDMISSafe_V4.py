# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
from datetime import datetime
from typing import Optional

from pandas import DataFrame
import numpy as np

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
from freqtrade.persistence import Trade

import talib.abstract as ta


class VWAPDMISSafe_V4(IStrategy):
    """
    VWAP + DMI Trend Strategy V4 - Long-Term Optimized
    Author: Antigravity
    Version: 2.0.0

    Improvements over V3:
    - Added ATR volatility filter to avoid low-volatility (ranging) markets
    - Added trend strength filter using longer-term EMA
    - Added momentum confirmation with RSI
    - Optimized for 2-year performance with walk-forward validation
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    minimal_roi = {"0": 0.5, "300": 0.15, "1000": 0.05, "2000": 0}

    stoploss = -0.25
    trailing_stop = False
    use_custom_stoploss = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 250

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # === CORE PARAMETERS ===
    vwap_window = IntParameter(100, 300, default=167, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 35, default=20, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.0, 3.0, default=1.5, space="buy", optimize=True)
    target_rr = DecimalParameter(1.5, 4.0, default=2.0, space="sell", optimize=True)
    risk_per_trade = DecimalParameter(0.003, 0.015, default=0.006, space="buy", optimize=True)
    max_stake_ratio = DecimalParameter(0.1, 0.4, default=0.25, space="buy", optimize=True)

    # === NEW FILTERS ===
    # Volatility Filter: only trade when ATR is above average
    use_volatility_filter = BooleanParameter(default=True, space="buy", optimize=True)
    atr_percentile = IntParameter(20, 60, default=40, space="buy", optimize=True)

    # Trend Filter: use longer EMA to confirm trend direction
    use_trend_filter = BooleanParameter(default=True, space="buy", optimize=True)
    trend_ema_period = IntParameter(100, 300, default=200, space="buy", optimize=True)

    # Momentum Filter: RSI confirmation
    use_rsi_filter = BooleanParameter(default=True, space="buy", optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    rsi_long_threshold = IntParameter(40, 55, default=50, space="buy", optimize=True)
    rsi_short_threshold = IntParameter(45, 60, default=50, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Indicators: Rolling VWAP, DMI, ADX, ATR, EMA, RSI
        """

        # Rolling VWAP
        window = self.vwap_window.value
        pv = dataframe["close"] * dataframe["volume"]
        dataframe["rolling_vwap"] = (
            pv.rolling(window=window).sum() / dataframe["volume"].rolling(window=window).sum()
        )

        # DMI / ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ATR for Stoploss and Volatility Filter
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        # ATR percentile over last 100 candles for volatility filter
        dataframe["atr_percentile"] = (
            dataframe["atr"]
            .rolling(window=100)
            .apply(lambda x: np.percentile(x, self.atr_percentile.value), raw=True)
        )

        # Volume Mean for filter
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        # Trend EMA for trend filter
        dataframe["trend_ema"] = ta.EMA(dataframe, timeperiod=self.trend_ema_period.value)

        # RSI for momentum filter
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic with Enhanced Filters
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === BASE CONDITIONS ===
        # LONG: Price > VWAP, +DI > -DI, ADX > threshold, Volume > mean
        long_base = (
            (dataframe["close"] > dataframe["rolling_vwap"])
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
        )

        # SHORT: Price < VWAP, -DI > +DI, ADX > threshold, Volume > mean
        short_base = (
            (dataframe["close"] < dataframe["rolling_vwap"])
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
        )

        # === APPLY FILTERS ===
        # Volatility Filter: ATR must be above its percentile threshold
        if self.use_volatility_filter.value:
            volatility_ok = dataframe["atr"] > dataframe["atr_percentile"]
            long_base = long_base & volatility_ok
            short_base = short_base & volatility_ok

        # Trend Filter: Price must be on correct side of long-term EMA
        if self.use_trend_filter.value:
            long_trend = dataframe["close"] > dataframe["trend_ema"]
            short_trend = dataframe["close"] < dataframe["trend_ema"]
            long_base = long_base & long_trend
            short_base = short_base & short_trend

        # RSI Filter: Momentum confirmation
        if self.use_rsi_filter.value:
            long_rsi = dataframe["rsi"] > self.rsi_long_threshold.value
            short_rsi = dataframe["rsi"] < self.rsi_short_threshold.value
            long_base = long_base & long_rsi
            short_base = short_base & short_rsi

        # Apply entries
        dataframe.loc[long_base, "enter_long"] = 1
        dataframe.loc[short_base, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit Logic is handled by custom_exit and custom_stoploss
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Dynamic stoploss based on entry ATR (static risk)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        entry_date = trade.open_date_utc
        entry_candle = dataframe.loc[dataframe["date"] == entry_date]

        if not entry_candle.empty:
            atr = entry_candle.iloc[0]["atr"]
        else:
            atr = dataframe.iloc[-1]["atr"]

        sl_distance = atr * self.atr_multiplier.value

        if trade.is_short:
            sl_price = trade.open_rate + sl_distance
            return (sl_price - current_rate) / current_rate
        else:
            sl_price = trade.open_rate - sl_distance
            return (sl_price - current_rate) / current_rate

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        Take profit at target R:R
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        entry_date = trade.open_date_utc
        entry_candle = dataframe.loc[dataframe["date"] == entry_date]

        if not entry_candle.empty:
            atr = entry_candle.iloc[0]["atr"]
        else:
            atr = dataframe.iloc[-1]["atr"]

        risk = atr * self.atr_multiplier.value

        if risk == 0:
            return None

        profit_amount = (
            (current_rate - trade.open_rate)
            if not trade.is_short
            else (trade.open_rate - current_rate)
        )
        r_multiple = profit_amount / risk

        if r_multiple >= self.target_rr.value:
            return "target_rr_reached"

        return None

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Position sizing based on risk
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        atr = last_candle["atr"]
        if atr == 0:
            return proposed_stake

        capital = self.wallets.get_total_stake_amount()
        risk_amount = capital * self.risk_per_trade.value

        stop_distance = atr * self.atr_multiplier.value

        if stop_distance == 0:
            return proposed_stake

        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate

        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake

        # SAFETY: Max Stake Ratio
        max_allowed_stake = capital * self.max_stake_ratio.value
        if size_stake > max_allowed_stake:
            size_stake = max_allowed_stake

        return size_stake
