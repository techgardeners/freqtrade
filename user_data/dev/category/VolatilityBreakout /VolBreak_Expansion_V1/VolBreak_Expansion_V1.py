# pragma pylint: disable=missing-docstring, invalid-name, stateless-moments
# pragma pylint: disable=attribute-defined-outside-init

import logging  # <-- added

from datetime import datetime, timedelta
from typing import Optional, Union

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
)

# Logger for this strategy module (added)
logger = logging.getLogger(__name__)


class VolBreak_Expansion_V1(IStrategy):
    """
    VolBreak_Expansion_V1
    ---------------------
    Breakout Volatility Expansion Strategy

    High-level idea:
        - Identify volatility "squeezes":
            Bollinger Bands are inside Keltner Channels -> volatility compression.
        - Wait for a volatility "expansion":
            Price breaks out of the Bollinger Bands with:
                * high volume
                * wide candle range relative to ATR
        - Confirm direction with an optional trend filter (EMA200).
        - Manage risk using:
            * ATR-based technical stoploss (volatility-adjusted)
            * R-multiple exits:
                - TP1: partial take profit (via adjust_trade_position)
                - TP2: full exit (via custom_exit)
            * Time-based exit and ATR spike exit as safety valves.

    Category in your bot map:
        -> Bot 3 – Volatility Breakout Bot
    """

    INTERFACE_VERSION = 3
    can_short = True

    # -------------------------------------------------------------------------
    # ROI / EXIT BEHAVIOR
    # -------------------------------------------------------------------------
    # We rely on:
    #   - custom_stoploss (ATR-based)
    #   - custom_exit (R-multiples, time-based, ATR spike)
    #   - adjust_trade_position (TP1 partial exit)
    #
    # To avoid conflicts, minimal_roi is set very high so that it effectively
    # never triggers by itself.
    minimal_roi = {"0": 100}

    # Safety net stoploss:
    #   - Used if custom_stoploss returns this value or something invalid.
    #   - Also used as "worst-case" bound in Freqtrade.
    stoploss = -0.99

    # Timeframe:
    #   - 15m is a good compromise for volatility breakout strategies:
    #     fast enough to catch expansions, not too noisy like 1m/5m.
    timeframe = "15m"

    # Process only new candles (no intrabar evaluation).
    process_only_new_candles = True

    # Standard Freqtrade flags:
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before signals are valid:
    #   - Must be >= longest indicator period (e.g., kc_length, bb_length, etc.).
    startup_candle_count = 200

    # Enable partial exits through adjust_trade_position.
    position_adjustment_enable = True

    # -------------------------------------------------------------------------
    # VISUALIZATION CONFIG (Freqtrade UI / plot-dataframe)
    # -------------------------------------------------------------------------
    # This section controls what is plotted in the Freqtrade charts.
    # You can inspect it using:
    #   freqtrade plot-dataframe -s VolBreak_Expansion_V1 ...
    # or via the Web UI.
    plot_config = {
        "main_plot": {
            # Price overlays:
            "ema_20": {},  # Short-term EMA
            "ema_50": {},  # Medium-term EMA
            "ema_200": {},  # Long-term trend filter
            "bb_upper": {},  # Bollinger upper band
            "bb_middle": {},  # Bollinger middle band
            "bb_lower": {},  # Bollinger lower band
            "kc_upper": {},  # Keltner upper channel
            "kc_lower": {},  # Keltner lower channel
        },
        "subplots": {
            # Volatility and ATR
            "ATR": {
                "atr": {},  # ATR used for candle range check & stops
            },
            # Volume behavior
            "Volume": {
                "volume": {},
                "volume_mean": {},
            },
            # Squeeze / Breakout state and regime ON/OFF
            "Squeeze & Breakout": {
                "squeeze_on": {},  # Compression: BB inside KC
                "was_in_squeeze": {},  # Recently in squeeze (window-based)
                "break_regime_long": {},  # Regime ON for potential long breakouts
                "break_regime_short": {},  # Regime ON for potential short breakouts
                "break_regime_any": {},  # 1 if either long or short regime is ON
            },
        },
    }

    # -------------------------------------------------------------------------
    # HYPEROPT PARAMETERS
    # -------------------------------------------------------------------------
    # These parameters control the squeeze / breakout behavior and risk logic.
    # They can be tuned via hyperopt.

    # --- Squeeze Parameters ---
    # Bollinger Bands:
    #   - bb_length: period for moving average
    #   - bb_std: number of standard deviations
    bb_length = IntParameter(10, 30, default=15, space="buy", optimize=True)
    bb_std = DecimalParameter(1.5, 2.5, default=1.8, decimals=1, space="buy", optimize=True)

    # Keltner Channels:
    #   - kc_length: EMA/ATR period
    #   - kc_mult: ATR multiplier for channel width
    kc_length = IntParameter(10, 30, default=22, space="buy", optimize=True)
    kc_mult = DecimalParameter(1.0, 2.0, default=1.0, decimals=1, space="buy", optimize=True)

    # --- Breakout Validation ---
    # breakout_volume_mult:
    #   - Minimum volume multiple vs volume_mean (e.g. 1.1x, 1.5x, etc.).
    # breakout_range_atr_mult:
    #   - Minimum candle range (high - low) in ATR units.
    breakout_volume_mult = DecimalParameter(
        1.0, 2.0, default=1.1, decimals=1, space="buy", optimize=True
    )
    breakout_range_atr_mult = DecimalParameter(
        1.0, 3.0, default=2.8, decimals=1, space="buy", optimize=True
    )

    # min_squeeze_candles:
    #   - How many recent candles must have been in squeeze to consider a breakout valid.
    #   - This captures the idea of "longer compression => stronger follow-through".
    min_squeeze_candles = IntParameter(1, 10, default=10, space="buy", optimize=True)

    # --- Trend Filter ---
    # use_trend_filter:
    #   - If True:
    #       Longs only when price > EMA200 (bull trend).
    #       Shorts only when price < EMA200 (bear trend).
    #   - If False:
    #       Trend filter is disabled; breakout can occur in any regime.
    use_trend_filter = CategoricalParameter([True, False], default=True, space="buy", optimize=True)

    # --- Risk Management (R-multiples) ---
    # tp1_risk_reward:
    #   - R multiple for TP1 (partial exit).
    # tp2_risk_reward:
    #   - R multiple for TP2 (full exit).
    # tp1_close_percentage:
    #   - Fraction of the position closed at TP1 (e.g. 0.2 = 20%).
    tp1_risk_reward = DecimalParameter(
        0.8, 1.5, default=1.0, decimals=1, space="sell", optimize=True
    )
    tp2_risk_reward = DecimalParameter(
        1.5, 3.0, default=2.2, decimals=1, space="sell", optimize=True
    )
    tp1_close_percentage = DecimalParameter(
        0.2, 0.5, default=0.2, decimals=1, space="sell", optimize=True
    )

    # --- Additional Risk Controls ---
    # atr_stop_multiplier:
    #   - Multiplier for ATR-based stop distance.
    # max_trade_duration_hours:
    #   - Hard time stop: close trade after this many hours.
    # max_atr_spike:
    #   - If ATR_current / ATR_entry >= max_atr_spike, exit due to volatility spike.
    atr_stop_multiplier = DecimalParameter(
        1.0, 3.0, default=1.2, decimals=1, space="sell", optimize=True
    )
    max_trade_duration_hours = IntParameter(4, 48, default=36, space="sell", optimize=True)
    max_atr_spike = DecimalParameter(2.0, 5.0, default=4.6, decimals=1, space="sell", optimize=True)

    # --- Position sizing (risk-based) ---
    # risk_per_trade:
    #   - Fraction of available capital risked per trade (e.g. 0.01 = 1%).
    risk_per_trade = DecimalParameter(
        0.005, 0.02, default=0.01, decimals=3, space="buy", optimize=True
    )

    # ==========================================================================
    # INDICATORS
    # ==========================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators needed for squeeze + breakout detection and risk.

        Indicators:
            - EMA 20 / 50 / 200: basic trend context, EMA200 used as macro filter.
            - ATR 14: volatility measure used for:
                * breakout candle range validation
                * ATR-based stoploss
                * risk-based position sizing
            - volume_mean: rolling average volume used to define "high volume" bars.
            - Bollinger Bands (BB):
                * bb_upper, bb_middle, bb_lower
            - Keltner Channels (KC):
                * kc_upper, kc_lower
            - squeeze_on:
                * 1 when BB are inside KC -> volatility compression regime.
            - was_in_squeeze, break_regime_*:
                * initialized here so they are always plottable.
        """

        # --- Moving Averages (trend context) ---
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # --- ATR (Average True Range) ---
        # ATR(14) is used:
        #   - to validate that breakout candles have a wide range
        #   - to build our ATR-based stoploss and position sizing
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # --- Volume Mean ---
        # volume_mean is a simple 20-period SMA of volume.
        # We consider "high volume" candles when:
        #   volume > volume_mean * breakout_volume_mult
        dataframe["volume_mean"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # --- Bollinger Bands (parameterized) ---
        bb_len = self.bb_length.value
        bb_std = float(self.bb_std.value)

        bollinger = ta.BBANDS(
            dataframe,
            timeperiod=bb_len,
            nbdevup=bb_std,
            nbdevdn=bb_std,
        )
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]

        # --- Keltner Channels (parameterized) ---
        kc_len = self.kc_length.value
        kc_mult = float(self.kc_mult.value)

        kc_ema = ta.EMA(dataframe, timeperiod=kc_len)
        kc_atr = ta.ATR(dataframe, timeperiod=kc_len)

        dataframe["kc_upper"] = kc_ema + kc_atr * kc_mult
        dataframe["kc_lower"] = kc_ema - kc_atr * kc_mult

        # --- Squeeze Detection ---
        # Squeeze ON when:
        #   - BB upper < KC upper
        #   - AND BB lower > KC lower
        #
        # Interpretation:
        #   - Price volatility is "contained" inside a tighter range than usual.
        #   - Often precedes a strong volatility expansion (breakout).
        dataframe["squeeze_on"] = (
            (dataframe["bb_upper"] < dataframe["kc_upper"])
            & (dataframe["bb_lower"] > dataframe["kc_lower"])
        ).astype(int)

        # Initialize "was_in_squeeze" so it exists on the dataframe for plots.
        dataframe["was_in_squeeze"] = 0

        # Initialize breakout regime flags so they exist on the dataframe
        # and can be plotted even before populate_entry_trend runs.
        dataframe["break_regime_long"] = 0
        dataframe["break_regime_short"] = 0
        dataframe["break_regime_any"] = 0

        return dataframe

    # ==========================================================================
    # ENTRY LOGIC
    # ==========================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry conditions:

        STEP 1: Recent Squeeze
            - Check if any of the last N candles (`min_squeeze_candles`) had squeeze_on = 1.
            - This captures the idea that "compression first, then expansion".

        STEP 2: Breakout Candle
            For a LONG breakout:
                - close > bb_upper        (price closes above the upper Bollinger band)
                - high volume vs volume_mean
                - wide candle range vs ATR

            For a SHORT breakout:
                - close < bb_lower
                - high volume vs volume_mean
                - wide candle range vs ATR

        STEP 3: Trend Filter (optional, EMA200)
            - If enabled:
                * LONG only if close > ema_200 (bull regime)
                * SHORT only if close < ema_200 (bear regime)

        Additional:
            - We also expose explicit "regime ON/OFF" flags:
                * break_regime_long
                * break_regime_short
                * break_regime_any

              These help understand when the bot is "armed" for long/short breakouts,
              independently of whether the final breakout candle has happened.
        """

        # ----------------------------------------------------------------------
        # STEP 1: Recent squeeze detection (multi-candle window)
        # ----------------------------------------------------------------------
        squeeze_window = self.min_squeeze_candles.value

        # was_in_squeeze:
        #   - True if there was at least one squeeze_on==1 in the previous N candles.
        #   - We shift by 1 to ensure that the breakout candle itself is NOT counted
        #     as part of the squeeze period.
        dataframe["was_in_squeeze"] = (
            dataframe["squeeze_on"].shift(1).rolling(window=squeeze_window).max() > 0
        )

        # ----------------------------------------------------------------------
        # STEP 2: Breakout conditions (candle-level)
        # ----------------------------------------------------------------------

        # LONG breakout candle:
        long_breakout = (
            (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["volume"] > dataframe["volume_mean"] * self.breakout_volume_mult.value)
            & (
                (dataframe["high"] - dataframe["low"])
                > dataframe["atr"] * self.breakout_range_atr_mult.value
            )
        )

        # SHORT breakout candle:
        short_breakout = (
            (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["volume"] > dataframe["volume_mean"] * self.breakout_volume_mult.value)
            & (
                (dataframe["high"] - dataframe["low"])
                > dataframe["atr"] * self.breakout_range_atr_mult.value
            )
        )

        # ----------------------------------------------------------------------
        # STEP 3: Trend filter (EMA200)
        # ----------------------------------------------------------------------
        if self.use_trend_filter.value:
            trend_long = dataframe["close"] > dataframe["ema_200"]
            trend_short = dataframe["close"] < dataframe["ema_200"]
        else:
            # When trend filter is disabled, we accept both sides regardless of EMA200.
            trend_long = True
            trend_short = True

        # ----------------------------------------------------------------------
        # BREAKOUT REGIME FLAGS (ON/OFF view)
        # ----------------------------------------------------------------------
        # We define a breakout regime as:
        #   - recently in squeeze (was_in_squeeze)
        #   - AND directionally allowed by the trend filter (if enabled).
        #
        # This does NOT require the breakout candle itself to have occurred.
        # It simply means:
        #   "If a valid breakout candle appears now, we would be willing to trade it."
        dataframe["break_regime_long"] = (dataframe["was_in_squeeze"] & trend_long).astype(int)

        dataframe["break_regime_short"] = (dataframe["was_in_squeeze"] & trend_short).astype(int)

        # Any regime ON (either long or short) -> useful to see if the bot is "active" at all.
        dataframe["break_regime_any"] = (
            (dataframe["break_regime_long"] == 1) | (dataframe["break_regime_short"] == 1)
        ).astype(int)

        # ----------------------------------------------------------------------
        # FINAL ENTRY SIGNALS
        # ----------------------------------------------------------------------
        # Initialize entry columns
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # Final LONG entry conditions:
        #   - Context: break_regime_long == 1
        #   - Candle:  long_breakout == True
        dataframe.loc[
            dataframe["break_regime_long"].astype(bool) & long_breakout,
            "enter_long",
        ] = 1

        # Final SHORT entry conditions:
        #   - Context: break_regime_short == 1
        #   - Candle:  short_breakout == True
        dataframe.loc[
            dataframe["break_regime_short"].astype(bool) & short_breakout,
            "enter_short",
        ] = 1

        # ---------------- LOGGING (added, non-destructive) -------------------
        try:
            pair = metadata.get("pair", "UNKNOWN")
        except Exception:
            pair = "UNKNOWN"

        if len(dataframe) > 0:
            last = dataframe.iloc[-1]

            # Log when any breakout regime is ON
            if last["break_regime_any"] == 1:
                logger.debug(
                    f"[{pair}] BREAK REGIME ON | time={last['date']} | "
                    f"regime_long={int(last['break_regime_long'])} "
                    f"regime_short={int(last['break_regime_short'])} | "
                    f"was_in_squeeze={bool(last['was_in_squeeze'])} | "
                    f"close={last['close']:.4f} ema200={last['ema_200']:.4f}"
                )

            # Log when we emit entry signals
            if last["enter_long"] == 1:
                logger.info(
                    f"[{pair}] ENTER LONG breakout | time={last['date']} | "
                    f"close={last['close']:.4f} bb_upper={last['bb_upper']:.4f} | "
                    f"volume={last['volume']:.0f} vol_mean={last['volume_mean']:.0f} | "
                    f"atr={last['atr']:.6f}"
                )

            if last["enter_short"] == 1:
                logger.info(
                    f"[{pair}] ENTER SHORT breakout | time={last['date']} | "
                    f"close={last['close']:.4f} bb_lower={last['bb_lower']:.4f} | "
                    f"volume={last['volume']:.0f} vol_mean={last['volume_mean']:.0f} | "
                    f"atr={last['atr']:.6f}"
                )
        # ---------------------------------------------------------------------

        return dataframe

    # ==========================================================================
    # EXIT LOGIC (SIGNAL-BASED)
    # ==========================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        We primarily use:
            - custom_exit
            - custom_stoploss

        Therefore, we keep standard exit signals disabled here:
            exit_long = 0
            exit_short = 0
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    @staticmethod
    def _get_entry_atr(dataframe: DataFrame, trade: Trade) -> float:
        """
        Helper to get ATR at (or just before) the trade's open candle.

        Rationale:
            - We want risk and stoploss to be based on volatility at entry time.
            - Using the ATR at entry makes R-multiple logic consistent and stable.

        Implementation:
            - Filter candles with date <= trade.open_date_utc.
            - Take the last one as the "entry candle".
        """
        entry_date = trade.open_date_utc
        df_entry = dataframe.loc[dataframe["date"] <= entry_date]

        if not df_entry.empty and "atr" in df_entry.columns:
            return float(df_entry.iloc[-1]["atr"])

        # Fallback for very old trades not in current dataframe.
        return float(dataframe.iloc[-1]["atr"])

    # ==========================================================================
    # CUSTOM STOPLOSS (ATR-based, fixed R)
    # ==========================================================================
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
        ATR-based technical stoploss.

        Freqtrade expects:
            returned_value = ratio relative to trade.open_rate

        So the actual stoploss price is:
            stoploss_price = open_rate * (1 + returned_value)

        Therefore:
            - LONG:
                * Stop below entry  -> returned_value < 0
                * Example: -0.05 => stop at -5% from open_rate.
            - SHORT:
                * Stop above entry -> returned_value > 0
                * Example: 0.05  => stop at +5% from open_rate.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        atr = self._get_entry_atr(dataframe, trade)
        if atr <= 0:
            logger.warning(
                f"[{pair}] custom_stoploss fallback to static stoploss | "
                f"trade_id={trade.id} | atr={atr}"
            )
            return self.stoploss

        # Stop distance in price units (e.g., USDT)
        sl_distance = atr * self.atr_stop_multiplier.value
        if sl_distance <= 0:
            logger.warning(
                f"[{pair}] custom_stoploss invalid sl_distance, fallback | "
                f"trade_id={trade.id} | sl_distance={sl_distance}"
            )
            return self.stoploss

        if trade.is_short:
            # SHORT: stop above entry -> positive ratio
            ratio = sl_distance / trade.open_rate
        else:
            # LONG: stop below entry -> negative ratio
            ratio = -sl_distance / trade.open_rate

        logger.debug(
            f"[{pair}] custom_stoploss | trade_id={trade.id} | "
            f"atr={atr:.6f} atr_mult={float(self.atr_stop_multiplier.value):.2f} "
            f"sl_distance={sl_distance:.6f} ratio={ratio:.4f}"
        )

        return ratio

    # ==========================================================================
    # CUSTOM ENTRY PRICE (no change)
    # ==========================================================================
    def custom_entry_price(
        self,
        pair: str,
        trade: Trade | None,
        current_time: datetime,
        proposed_rate: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        Keep proposed_rate.
        Stoploss is handled entirely via custom_stoploss based on ATR.
        """
        return proposed_rate

    # ==========================================================================
    # CUSTOM EXIT (TP2 + time-based + ATR spike)
    # ==========================================================================
    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[Union[str, bool]]:
        """
        Manage full exits (no partials here):

            1) Time-based exit:
                - If trade age exceeds max_trade_duration_hours => close.

            2) ATR spike exit:
                - If ATR_current / ATR_entry >= max_atr_spike => close.
                - Idea: volatility exploded beyond what was expected or desired.

            3) TP2 full exit:
                - Based on R-multiple relative to stoploss distance:
                    R = |open_rate - stop_loss|
                    For LONG:  current_r = (current_rate - open_rate) / R
                    For SHORT: current_r = (open_rate - current_rate) / R
                - If current_r >= tp2_risk_reward => close trade.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        # --- 1) Time-based exit ---
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600.0
        if trade_duration > self.max_trade_duration_hours.value:
            logger.info(
                f"[{pair}] EXIT time-based | trade_id={trade.id} | "
                f"duration_h={trade_duration:.2f} | profit={current_profit:.4f}"
            )
            return "time_based_exit"

        # --- 2) ATR spike exit ---
        atr_entry = self._get_entry_atr(dataframe, trade)
        atr_current = float(dataframe.iloc[-1]["atr"])
        if atr_entry > 0 and atr_current > 0:
            atr_ratio = atr_current / atr_entry
            if atr_ratio >= self.max_atr_spike.value:
                logger.warning(
                    f"[{pair}] EXIT ATR spike | trade_id={trade.id} | "
                    f"atr_entry={atr_entry:.6f} atr_current={atr_current:.6f} "
                    f"atr_ratio={atr_ratio:.2f} | profit={current_profit:.4f}"
                )
                return "atr_spike_exit"

        # --- 3) TP2 full exit based on R-multiple ---
        if not trade.stop_loss:
            return None

        risk_per_unit = abs(trade.open_rate - trade.stop_loss)
        if risk_per_unit <= 0:
            return None

        if trade.is_short:
            current_r = (trade.open_rate - current_rate) / risk_per_unit
        else:
            current_r = (current_rate - trade.open_rate) / risk_per_unit

        # TP2: full close when target R-multiple is reached
        if current_r >= self.tp2_risk_reward.value:
            logger.info(
                f"[{pair}] EXIT TP2 | trade_id={trade.id} | "
                f"R={current_r:.2f} | tp2_target={float(self.tp2_risk_reward.value):.2f} "
                f"| profit={current_profit:.4f}"
            )
            return "tp2_exit"

        return None

    # ==========================================================================
    # PARTIAL EXIT (TP1) VIA POSITION ADJUSTMENT
    # ==========================================================================
    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        **kwargs,
    ) -> float | int | None:
        """
        Manage partial exits (TP1).
        This method is only called when position_adjustment_enable = True.

        Logic:
            - Requires a valid stop_loss to compute R.
            - Compute current R-multiple using distance from open_rate.
            - If R >= tp1_risk_reward and NO prior exit orders:
                -> Close a fraction of the position (tp1_close_percentage).

        Note:
            - We detect if TP1 was already executed by checking closed exit orders.
        """
        # Need a valid stop loss to compute R
        if not trade.stop_loss:
            return None

        risk_per_unit = abs(trade.open_rate - trade.stop_loss)
        if risk_per_unit <= 0:
            return None

        # Compute current R multiple
        if trade.is_short:
            current_r = (trade.open_rate - current_rate) / risk_per_unit
        else:
            current_r = (current_rate - trade.open_rate) / risk_per_unit

        # Count already closed exit orders to avoid repeating TP1
        if trade.is_short:
            exit_orders = [o for o in trade.orders if o.side == "buy" and o.status == "closed"]
        else:
            exit_orders = [o for o in trade.orders if o.side == "sell" and o.status == "closed"]

        # TP1: partial close once
        if current_r >= self.tp1_risk_reward.value and len(exit_orders) == 0:
            # Return negative amount to reduce position size
            close_amount = trade.amount * float(self.tp1_close_percentage.value)
            logger.info(
                f"[{trade.pair}] TP1 partial exit | trade_id={trade.id} | "
                f"R={current_r:.2f} | tp1_target={float(self.tp1_risk_reward.value):.2f} | "
                f"close_amount={close_amount:.6f} | "
                f"tp1_close_percentage={float(self.tp1_close_percentage.value):.2f} | "
                f"profit={current_profit:.4f}"
            )
            return -close_amount

        return None

    # ==========================================================================
    # POSITION SIZING (RISK-BASED)
    # ==========================================================================
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
        Position sizing based on ATR risk.

        Concept:
            - Instead of using a fixed stake per trade, we adjust the position size
              so that the *monetary risk* per trade is approximately:
                    risk_per_trade * available_capital

        Steps:
            1. Get current ATR (volatility) from the last candle.
            2. Compute stop distance using:
                    stop_distance = atr * atr_stop_multiplier
            3. Compute risk_amount in stake currency:
                    risk_amount = available_capital * risk_per_trade
            4. Compute position size in coin units:
                    size_coin = risk_amount / stop_distance
            5. Convert to stake currency:
                    size_stake = size_coin * current_rate
            6. Clamp to:
                    [min_stake, max_stake]
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        atr = float(last_candle["atr"])

        if atr <= 0:
            # If ATR is not usable, fall back to proposed stake.
            logger.debug(
                f"[{pair}] custom_stake_amount fallback to proposed_stake | "
                f"time={current_time} | atr={atr}"
            )
            return proposed_stake

        # Use available stake (safer than total stake when multiple positions exist).
        capital = self.wallets.get_available_stake_amount()
        if capital <= 0:
            logger.warning(
                f"[{pair}] custom_stake_amount no available capital | time={current_time}"
            )
            return min_stake

        # Monetary risk to allocate to this trade
        risk_amount = capital * float(self.risk_per_trade.value)

        # Stop distance in price units
        stop_distance = atr * float(self.atr_stop_multiplier.value)
        if stop_distance <= 0:
            logger.debug(
                f"[{pair}] custom_stake_amount invalid stop_distance, using proposed_stake | "
                f"time={current_time} | stop_distance={stop_distance}"
            )
            return proposed_stake

        # Size in coin units
        size_coin = risk_amount / stop_distance

        # Convert to stake currency
        size_stake = size_coin * current_rate

        # Respect exchange min/max stake
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake

        logger.debug(
            f"[{pair}] custom_stake_amount | time={current_time} | "
            f"capital={capital:.2f} risk_per_trade={float(self.risk_per_trade.value):.4f} "
            f"risk_amount={risk_amount:.2f} atr={atr:.6f} stop_distance={stop_distance:.6f} "
            f"size_stake={size_stake:.2f} (min={min_stake:.2f}, max={max_stake:.2f})"
        )

        return size_stake

    # ==========================================================================
    # ENTRY CONFIRMATION HOOK
    # ==========================================================================
    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """
        Called right before placing an entry order.

        Currently:
            - Always returns True (no additional filter).
        You can extend this hook to:
            - Validate that the breakout candle is still valid.
            - Check higher timeframe conditions.
            - Block entries during specific market conditions (news, etc.).
        """
        logger.info(
            f"[{pair}] CONFIRM ENTRY | side={side} | type={order_type} | "
            f"amount={amount:.6f} | rate={rate:.4f} | time={current_time} | "
            f"entry_tag={entry_tag}"
        )
        return True
