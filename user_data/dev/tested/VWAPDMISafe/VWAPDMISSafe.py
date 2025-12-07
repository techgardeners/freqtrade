# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

import talib.abstract as ta


class VWAPDMISSafe(IStrategy):
    """
    VWAP + DMI Trend Strategy (Safe Version)
    Author: Antigravity
    Version: 1.1.0

    Strategy based on Rolling VWAP and DMI/ADX to identify clean trends on 1H timeframe.
    Includes MAX STAKE LIMIT (30%).
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    minimal_roi = {"0": 0.386, "273": 0.106, "929": 0.033, "1858": 0}

    stoploss = -0.247
    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # Hyperopt Parameters (Optimized)
    vwap_window = IntParameter(150, 300, default=167, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 30, default=17, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(2.0, 3.5, default=2.04, space="buy", optimize=True)
    target_rr = DecimalParameter(2.0, 4.0, default=2.078, space="sell", optimize=True)
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.008, space="buy", optimize=True)

    # SAFETY: Max Stake Ratio
    max_stake_ratio = DecimalParameter(0.1, 0.5, default=0.3, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Indicators: Rolling VWAP, DMI, ADX, ATR
        """

        # Rolling VWAP
        # VWAP = Sum(Price * Volume) / Sum(Volume)
        # Rolling version uses a window
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

        # Volume Mean for filter
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # LONG Conditions
        # 1. Price above VWAP
        # 2. +DI > -DI
        # 3. ADX > Threshold
        # 4. Volume filter
        dataframe.loc[
            (
                (dataframe["close"] > dataframe["rolling_vwap"])
                & (dataframe["plus_di"] > dataframe["minus_di"])
                & (dataframe["adx"] > self.adx_threshold.value)
                & (dataframe["volume"] > dataframe["volume_mean"])
            ),
            "enter_long",
        ] = 1

        # SHORT Conditions
        # 1. Price below VWAP
        # 2. -DI > +DI
        # 3. ADX > Threshold
        # 4. Volume filter
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["rolling_vwap"])
                & (dataframe["minus_di"] > dataframe["plus_di"])
                & (dataframe["adx"] > self.adx_threshold.value)
                & (dataframe["volume"] > dataframe["volume_mean"])
            ),
            "enter_short",
        ] = 1

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
        Dynamic stoploss based on ATR
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        atr = last_candle["atr"]

        # Stoploss distance = Multiplier * ATR
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
        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        # Risk = Multiplier * ATR
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
