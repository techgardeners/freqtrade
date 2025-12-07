# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

import talib.abstract as ta


class FiveMinScalpingStrategy(IStrategy):
    """
    5-Minute Scalping Strategy
    Author: Antigravity
    Version: 1.0.0

    High-probability trend-following scalping system for the 5-minute timeframe.
    Uses multi-confirmation approach with EMA 200/55/9, MACD Histogram, and RSI.
    Enters trades ONLY in the direction of the dominant trend.

    Based on: FiveMinScalping.md specification
    """

    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True

    # ROI: 1:1.5 Risk-Reward as per specification
    minimal_roi = {"0": 0.03, "30": 0.02, "60": 0.01, "120": 0}

    stoploss = -0.02  # 2% initial, dynamic SL managed via custom_stoploss
    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 210  # Need 200+ candles for EMA 200

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # ===== Hyperopt Parameters =====

    # EMA Periods (as per optimization section 6)
    ema_fast = IntParameter(8, 10, default=9, space="buy", optimize=True)
    ema_medium = IntParameter(50, 60, default=55, space="buy", optimize=True)
    ema_slow = IntParameter(180, 220, default=200, space="buy", optimize=True)

    # RSI Threshold (as per optimization section 6)
    rsi_threshold = IntParameter(48, 52, default=50, space="buy", optimize=True)

    # ATR for Stop Loss
    atr_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.0, 2.5, default=1.5, space="buy", optimize=True)

    # Risk-Reward Target (as per specification: 1:1.5)
    target_rr = DecimalParameter(1.0, 2.0, default=1.5, space="sell", optimize=True)

    # Risk Management
    risk_per_trade = DecimalParameter(0.005, 0.02, default=0.01, space="buy", optimize=True)
    max_stake_ratio = DecimalParameter(0.1, 0.4, default=0.25, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Indicators Setup (Section 2 of spec):
        - EMA 200: Long-term trend direction
        - EMA 55: Medium-term dynamic support/resistance
        - EMA 9: Entry trigger reference
        - MACD Histogram (12, 26, 9): Momentum trigger
        - RSI 14: Directional strength confirmation
        """

        # === EMAs ===
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast.value)
        dataframe["ema_medium"] = ta.EMA(dataframe, timeperiod=self.ema_medium.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow.value)

        # === MACD (12, 26, 9) - Only Histogram used ===
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd_hist"] = macd["macdhist"]
        dataframe["macd_hist_prev"] = dataframe["macd_hist"].shift(1)

        # === RSI 14 ===
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # === ATR for Stop Loss ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        # === Volume Filter ===
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        # === Trend Detection (avoid choppy markets - Section 5.1) ===
        # EMAs should NOT be flat and overlapping
        ema_diff_fast_medium = abs(dataframe["ema_fast"] - dataframe["ema_medium"])
        ema_diff_medium_slow = abs(dataframe["ema_medium"] - dataframe["ema_slow"])
        dataframe["ema_separation"] = (ema_diff_fast_medium + ema_diff_medium_slow) / dataframe[
            "close"
        ]

        # Detect ranging market: EMAs too close together
        dataframe["is_ranging"] = dataframe["ema_separation"] < 0.002  # Less than 0.2% separation

        # === Pullback Detection (Section 3.3 / 4.3) ===
        # Price pulled back toward EMAs but not closed below EMA 55
        dataframe["near_ema_medium"] = (dataframe["low"] <= dataframe["ema_medium"] * 1.01) & (
            dataframe["close"] > dataframe["ema_medium"]
        )
        dataframe["near_ema_medium_short"] = (
            dataframe["high"] >= dataframe["ema_medium"] * 0.99
        ) & (dataframe["close"] < dataframe["ema_medium"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic based on Sections 3 (Long) and 4 (Short) of specification.
        ALL conditions must be met.
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # ===== LONG ENTRY (Section 3) =====
        # 3.1 Trend Filter: Price above 200 EMA
        # 3.2 EMA Alignment: EMA 9 > EMA 55
        # 3.4 RSI Confirmation: RSI > 50
        # 3.5 MACD Momentum: Histogram green (> 0)
        # 5.1 Not ranging market
        # Volume filter for confirmation

        long_conditions = (
            (dataframe["close"] > dataframe["ema_slow"])  # 3.1 Price above EMA 200
            & (dataframe["ema_fast"] > dataframe["ema_medium"])  # 3.2 EMA 9 > EMA 55
            & (dataframe["rsi"] > self.rsi_threshold.value)  # 3.4 RSI above 50
            & (dataframe["macd_hist"] > 0)  # 3.5 MACD Histogram green
            & (~dataframe["is_ranging"])  # 5.1 Not choppy market
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.5)  # Volume confirmation
        )

        dataframe.loc[long_conditions, "enter_long"] = 1

        # ===== SHORT ENTRY (Section 4) =====
        # 4.1 Trend Filter: Price below 200 EMA
        # 4.2 EMA Alignment: EMA 9 < EMA 55
        # 4.4 RSI Confirmation: RSI < 50
        # 4.5 MACD Momentum: Histogram red (< 0)
        # 5.1 Not ranging market

        short_conditions = (
            (dataframe["close"] < dataframe["ema_slow"])  # 4.1 Price below EMA 200
            & (dataframe["ema_fast"] < dataframe["ema_medium"])  # 4.2 EMA 9 < EMA 55
            & (dataframe["rsi"] < self.rsi_threshold.value)  # 4.4 RSI below 50
            & (dataframe["macd_hist"] < 0)  # 4.5 MACD Histogram red
            & (~dataframe["is_ranging"])  # 5.1 Not choppy market
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.5)  # Volume confirmation
        )

        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit via custom_exit for R:R target and custom_stoploss
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Exit long if trend reverses (price closes below EMA 55)
        dataframe.loc[
            (dataframe["close"] < dataframe["ema_medium"]) & (dataframe["macd_hist"] < 0),
            "exit_long",
        ] = 1

        # Exit short if trend reverses (price closes above EMA 55)
        dataframe.loc[
            (dataframe["close"] > dataframe["ema_medium"]) & (dataframe["macd_hist"] > 0),
            "exit_short",
        ] = 1

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
        Dynamic Stop Loss based on ATR (Section 3.7 / 4.7)
        Places SL below/above recent swing using ATR as proxy
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        if atr == 0:
            return self.stoploss

        # Stop distance = ATR * Multiplier
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
        Take Profit at 1:1.5 Risk-Reward (Section 3.8 / 4.8)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return None

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        if atr == 0:
            return None

        # Risk = ATR * Multiplier
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
        Position sizing based on risk percentage per trade
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) == 0:
            return proposed_stake

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

        # Safety: Max Stake Ratio
        max_allowed_stake = capital * self.max_stake_ratio.value
        if size_stake > max_allowed_stake:
            size_stake = max_allowed_stake

        return size_stake
