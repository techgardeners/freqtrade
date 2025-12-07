# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
from datetime import datetime
from typing import Optional

from pandas import DataFrame
import pandas as pd
import numpy as np

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

import talib.abstract as ta


class OpeningRangeFakeoutStrategy(IStrategy):
    """
    4-Hour Opening Range Fakeout Scalping Strategy
    Author: Antigravity
    Version: 1.2.0

    Trades failed breakouts (fakeouts) of a price range.
    Simpler implementation using Bollinger Bands as range proxy.

    When price spikes outside the bands and reverses back inside,
    we enter in the reversal direction.

    Based on: 4-HORanfeFakeoutScalp.md specification (simplified)
    """

    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0}

    stoploss = -0.02
    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 100

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # ===== Hyperopt Parameters =====

    # Bollinger Bands for range definition
    bb_period = IntParameter(20, 60, default=48, space="buy", optimize=True)
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # ATR for stops
    atr_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    atr_sl_multiplier = DecimalParameter(1.0, 3.0, default=1.5, space="buy", optimize=True)

    # Risk-Reward Target
    target_rr = DecimalParameter(1.5, 3.0, default=2.0, space="sell", optimize=True)

    # Risk Management
    risk_per_trade = DecimalParameter(0.005, 0.02, default=0.01, space="buy", optimize=True)
    max_stake_ratio = DecimalParameter(0.1, 0.4, default=0.25, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate range using Bollinger Bands and detect fakeout patterns.
        """

        # ===== Bollinger Bands as Range Proxy =====
        bollinger = ta.BBANDS(
            dataframe,
            timeperiod=self.bb_period.value,
            nbdevup=self.bb_std.value,
            nbdevdn=self.bb_std.value,
        )
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]

        # ===== Fakeout Detection =====
        # Fakeout above: previous candle closed above upper band, current closes inside
        dataframe["prev_above_upper"] = dataframe["close"].shift(1) > dataframe["bb_upper"].shift(1)
        dataframe["curr_inside_upper"] = dataframe["close"] < dataframe["bb_upper"]

        # Bearish fakeout (short signal)
        dataframe["fakeout_above"] = (
            dataframe["prev_above_upper"]
            & dataframe["curr_inside_upper"]
            & (dataframe["close"] < dataframe["open"])  # Bearish candle
        )

        # Fakeout below: previous candle closed below lower band, current closes inside
        dataframe["prev_below_lower"] = dataframe["close"].shift(1) < dataframe["bb_lower"].shift(1)
        dataframe["curr_inside_lower"] = dataframe["close"] > dataframe["bb_lower"]

        # Bullish fakeout (long signal)
        dataframe["fakeout_below"] = (
            dataframe["prev_below_lower"]
            & dataframe["curr_inside_lower"]
            & (dataframe["close"] > dataframe["open"])  # Bullish candle
        )

        # ===== Alternative: Wick Fakeout =====
        # When wick pierces the band but body closes inside
        dataframe["wick_fakeout_above"] = (
            (dataframe["high"] > dataframe["bb_upper"])  # Wick above upper band
            & (dataframe["close"] < dataframe["bb_upper"])  # Close inside
            & (dataframe["close"] < dataframe["open"])  # Bearish candle
            & (dataframe["high"] - dataframe["close"])
            > (dataframe["close"] - dataframe["low"])  # Upper wick > lower wick
        )

        dataframe["wick_fakeout_below"] = (
            (dataframe["low"] < dataframe["bb_lower"])  # Wick below lower band
            & (dataframe["close"] > dataframe["bb_lower"])  # Close inside
            & (dataframe["close"] > dataframe["open"])  # Bullish candle
            & (dataframe["close"] - dataframe["low"])
            > (dataframe["high"] - dataframe["close"])  # Lower wick > upper wick
        )

        # Combined signals
        dataframe["enter_long_signal"] = (
            dataframe["fakeout_below"] | dataframe["wick_fakeout_below"]
        )
        dataframe["enter_short_signal"] = (
            dataframe["fakeout_above"] | dataframe["wick_fakeout_above"]
        )

        # ===== ATR for Stop Loss =====
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        # Volume filter
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        # RSI for momentum confirmation
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry on fakeout reversal patterns.
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # ===== LONG ENTRY =====
        # Failed breakdown - price dipped below lower band and reversed
        long_conditions = (
            dataframe["enter_long_signal"]
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.5)
            & (dataframe["rsi"] < 70)  # Not overbought
        )

        dataframe.loc[long_conditions, "enter_long"] = 1

        # ===== SHORT ENTRY =====
        # Failed breakout - price spiked above upper band and reversed
        short_conditions = (
            dataframe["enter_short_signal"]
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.5)
            & (dataframe["rsi"] > 30)  # Not oversold
        )

        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit at middle band (mean reversion target).
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Exit long near middle band
        dataframe.loc[(dataframe["close"] >= dataframe["bb_middle"] * 0.998), "exit_long"] = 1

        # Exit short near middle band
        dataframe.loc[(dataframe["close"] <= dataframe["bb_middle"] * 1.002), "exit_short"] = 1

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
        Dynamic Stop Loss based on ATR.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        if atr == 0 or pd.isna(atr):
            return self.stoploss

        sl_distance = atr * self.atr_sl_multiplier.value

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
        Take Profit at target R:R.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return None

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        if atr == 0 or pd.isna(atr):
            return None

        risk = atr * self.atr_sl_multiplier.value

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
        Position sizing based on risk percentage.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return proposed_stake

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        if atr == 0 or pd.isna(atr):
            return proposed_stake

        capital = self.wallets.get_total_stake_amount()
        risk_amount = capital * self.risk_per_trade.value

        stop_distance = atr * self.atr_sl_multiplier.value

        if stop_distance == 0:
            return proposed_stake

        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate

        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake

        max_allowed_stake = capital * self.max_stake_ratio.value
        if size_stake > max_allowed_stake:
            size_stake = max_allowed_stake

        return size_stake
