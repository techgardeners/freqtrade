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


class VWAPDMISSafe_V5(IStrategy):
    """
    VWAP + DMI Trend Strategy V5 - Regime Filters
    Author: Antigravity
    Version: 3.0.0

    This version adds multiple regime filters to avoid unfavorable market conditions:
    - Volatility Regime: ATR ratio filter
    - Trend Strength Regime: ADX momentum filter
    - Market Direction Regime: Long-term EMA trend
    - Volume Regime: Volume above average

    Each filter can be toggled on/off for testing.
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    minimal_roi = {"0": 0.386, "273": 0.106, "929": 0.033, "1858": 0}

    stoploss = -0.247
    trailing_stop = False
    use_custom_stoploss = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 300

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # === CORE PARAMETERS (V3 Baseline) ===
    vwap_window = IntParameter(100, 250, default=167, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 30, default=17, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.0, 2.5, default=1.5, space="buy", optimize=True)
    target_rr = DecimalParameter(1.5, 3.5, default=2.078, space="sell", optimize=True)
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.008, space="buy", optimize=True)
    max_stake_ratio = DecimalParameter(0.1, 0.4, default=0.3, space="buy", optimize=True)

    # === REGIME FILTER 1: Volatility Regime ===
    # Only trade when current volatility is above recent average
    use_volatility_regime = BooleanParameter(default=False, space="buy", optimize=False)
    vol_atr_short = IntParameter(10, 20, default=14, space="buy", optimize=True)
    vol_atr_long = IntParameter(50, 150, default=100, space="buy", optimize=True)
    vol_ratio_threshold = DecimalParameter(0.8, 1.5, default=1.0, space="buy", optimize=True)

    # === REGIME FILTER 2: Trend Strength Regime ===
    # Only trade when ADX is rising (strengthening trend)
    use_trend_strength_regime = BooleanParameter(default=False, space="buy", optimize=False)
    adx_lookback = IntParameter(5, 20, default=10, space="buy", optimize=True)
    adx_rising_threshold = DecimalParameter(0, 5, default=2, space="buy", optimize=True)

    # === REGIME FILTER 3: Market Direction Regime ===
    # Only trade in direction of long-term trend (EMA200)
    use_direction_regime = BooleanParameter(default=False, space="buy", optimize=False)
    direction_ema_period = IntParameter(150, 300, default=200, space="buy", optimize=True)

    # === REGIME FILTER 4: Volume Regime ===
    # Only trade when volume is significantly above average
    use_volume_regime = BooleanParameter(default=False, space="buy", optimize=False)
    volume_ma_period = IntParameter(20, 50, default=30, space="buy", optimize=True)
    volume_threshold = DecimalParameter(1.0, 2.0, default=1.2, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all indicators including regime filters
        """

        # === CORE INDICATORS ===
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

        # ATR for Stoploss
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Volume Mean for base filter
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        # === REGIME FILTER INDICATORS ===

        # Filter 1: Volatility Regime
        dataframe["atr_short"] = ta.ATR(dataframe, timeperiod=self.vol_atr_short.value)
        dataframe["atr_long"] = ta.ATR(dataframe, timeperiod=self.vol_atr_long.value)
        dataframe["atr_ratio"] = dataframe["atr_short"] / dataframe["atr_long"]

        # Filter 2: Trend Strength Regime
        dataframe["adx_prev"] = dataframe["adx"].shift(self.adx_lookback.value)
        dataframe["adx_change"] = dataframe["adx"] - dataframe["adx_prev"]

        # Filter 3: Market Direction Regime
        dataframe["direction_ema"] = ta.EMA(dataframe, timeperiod=self.direction_ema_period.value)

        # Filter 4: Volume Regime
        dataframe["volume_ma_long"] = (
            dataframe["volume"].rolling(window=self.volume_ma_period.value).mean()
        )
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma_long"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic with Regime Filters
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === BASE CONDITIONS (V3 Logic) ===
        long_base = (
            (dataframe["close"] > dataframe["rolling_vwap"])
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
        )

        short_base = (
            (dataframe["close"] < dataframe["rolling_vwap"])
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
        )

        # === APPLY REGIME FILTERS ===

        # Filter 1: Volatility Regime
        if self.use_volatility_regime.value:
            volatility_ok = dataframe["atr_ratio"] > self.vol_ratio_threshold.value
            long_base = long_base & volatility_ok
            short_base = short_base & volatility_ok

        # Filter 2: Trend Strength Regime
        if self.use_trend_strength_regime.value:
            trend_strengthening = dataframe["adx_change"] > self.adx_rising_threshold.value
            long_base = long_base & trend_strengthening
            short_base = short_base & trend_strengthening

        # Filter 3: Market Direction Regime
        if self.use_direction_regime.value:
            # Long only above EMA, Short only below EMA
            long_direction = dataframe["close"] > dataframe["direction_ema"]
            short_direction = dataframe["close"] < dataframe["direction_ema"]
            long_base = long_base & long_direction
            short_base = short_base & short_direction

        # Filter 4: Volume Regime
        if self.use_volume_regime.value:
            volume_ok = dataframe["volume_ratio"] > self.volume_threshold.value
            long_base = long_base & volume_ok
            short_base = short_base & volume_ok

        # Apply entries
        dataframe.loc[long_base, "enter_long"] = 1
        dataframe.loc[short_base, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit Logic handled by custom_exit and custom_stoploss
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
        Dynamic stoploss based on entry ATR
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
    ) -> str | None:
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
        entry_tag: str | None,
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
