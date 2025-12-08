# pragma pylint: disable=missing-docstring, invalid-name, stateless-moments
# pragma pylint: disable=attribute-defined-outside-init

"""
ICT_OB_Momentum_V1
------------------

Fully programmatic approximation of an ICT-style Order Block + Liquidity + FVG
momentum strategy for low timeframes (1m / 5m / 15m).

Core concepts implemented:

    - Liquidity grabs above/below swing highs/lows.
    - Displacement candles (large, impulsive, body-dominant).
    - Fair Value Gaps (3-candle imbalance).
    - Order Block as last opposite candle before displacement.
    - Break Of Structure (BOS) vs prior swing.
    - Entry only on retest of the OB zone (limit-style logic).
    - SL under/above liquidity grab / OB.
    - TP levels based on R-multiples (TP1, TP2) per ICT-style RR emphasis.
    - Hard fail-safes: time-based exit, ATR spike exit (optional safety).

This is *not* a simplified EMA crossover: it tries to follow the full ICT workflow
in a discrete, algorithmic form.

Category in your bot map:
    -> Bot 3 – Volatility Breakout Bot (ICT / Order Flow flavored)
"""

import logging
from datetime import datetime
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


# Logger for this strategy
logger = logging.getLogger(__name__)


class ICT_OB_Momentum_V1(IStrategy):
    """
    ICT Order Block Momentum Strategy – Algorithmic Implementation.

    Timeframe:
        Default: 5m (works also on 1m / 15m, conceptually).

    High-level logic per side (LONG example, SHORT is symmetric):

        1. Detect a significant swing low (liquidity pool).
        2. Detect a liquidity grab:
                price wicks below that swing low, then closes back above it.
        3. Detect a displacement up:
                big bullish, impulsive candle with wide body and ATR-based range,
                ideally accompanied by a Fair Value Gap (FVG).
        4. Define the Order Block:
                last bearish candle before the displacement candle.
        5. Confirm Break Of Structure (BOS):
                price breaks a prior swing high.
        6. WAIT for price to return to the OB zone in an orderly retrace:
                entry on OB body / mid-point zone.
        7. Set SL below OB / liquidity grab, TP in R multiples (TP1, TP2).

    For automation, this is implemented as a simple state machine per side
    processed over the candle sequence.
    """

    INTERFACE_VERSION = 3
    can_short = True

    # -------------------------------------------------------------------------
    # BASIC CONFIG
    # -------------------------------------------------------------------------
    timeframe = "5m"
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count = 300  # need enough history for swings, ATR, etc.

    # We rely on custom_stoploss / custom_exit, so ROI is disabled via huge value.
    minimal_roi = {"0": 100}
    stoploss = -0.99  # safety net

    # Enable partial exits via adjust_trade_position
    position_adjustment_enable = True

    # -------------------------------------------------------------------------
    # VISUALIZATION CONFIG (Freqtrade UI / plot-dataframe)
    # -------------------------------------------------------------------------
    plot_config = {
        "main_plot": {
            "ema_50": {},
            "ema_200": {},
            "ob_long_high": {},
            "ob_long_low": {},
            "ob_short_high": {},
            "ob_short_low": {},
        },
        "subplots": {
            "ATR": {
                "atr": {},
            },
            "Volume": {
                "volume": {},
                "volume_mean": {},
            },
            "Structure": {
                "swing_high": {},
                "swing_low": {},
                "liq_grab_long": {},
                "liq_grab_short": {},
            },
            "FVG & Displacement": {
                "bull_fvg": {},
                "bear_fvg": {},
                "displacement_long": {},
                "displacement_short": {},
            },
            "OB Setup State": {
                "long_state": {},
                "short_state": {},
            },
        },
    }

    # -------------------------------------------------------------------------
    # HYPEROPT PARAMETERS / TUNABLES
    # -------------------------------------------------------------------------

    # Swing structure parameters
    swing_lookback_left = IntParameter(2, 5, default=3, space="buy", optimize=True)
    swing_lookback_right = IntParameter(2, 5, default=3, space="buy", optimize=True)

    # Displacement characteristics
    displacement_atr_mult = DecimalParameter(
        1.0, 4.0, default=2.0, decimals=1, space="buy", optimize=True
    )
    displacement_min_body_ratio = DecimalParameter(
        0.5, 0.9, default=0.6, decimals=2, space="buy", optimize=True
    )

    # OB detection lookback (how far back we look for the last opposite candle)
    ob_lookback_bars = IntParameter(1, 8, default=5, space="buy", optimize=True)

    # OB entry zone: fraction inside the OB body.
    # 0.0 => at body low, 1.0 => at body high (for longs, top of bullish body)
    ob_entry_fraction = DecimalParameter(
        0.3, 0.8, default=0.5, decimals=2, space="buy", optimize=True
    )

    # Max bars allowed between liquidity grab and displacement + retest
    max_setup_bars = IntParameter(5, 50, default=20, space="buy", optimize=True)

    # Require FVG with displacement?
    use_fvg_filter = CategoricalParameter([True, False], default=True, space="buy", optimize=True)

    # Trend filter (EMA200 premium/discount idea)
    use_trend_filter = CategoricalParameter([True, False], default=True, space="buy", optimize=True)

    # Risk management parameters (RR)
    tp1_rr = DecimalParameter(1.0, 3.0, default=2.0, decimals=2, space="sell", optimize=True)
    tp2_rr = DecimalParameter(2.0, 8.0, default=4.0, decimals=2, space="sell", optimize=True)
    tp1_close_fraction = DecimalParameter(
        0.2, 0.6, default=0.33, decimals=2, space="sell", optimize=True
    )

    # SL buffer relative to OB / liquidity low/high in ATR multiples
    sl_buffer_atr = DecimalParameter(0.0, 1.0, default=0.2, decimals=2, space="sell", optimize=True)

    # Global risk per trade
    risk_per_trade = DecimalParameter(
        0.003, 0.02, default=0.01, decimals=3, space="buy", optimize=True
    )

    # Fail-safes
    max_trade_duration_hours = IntParameter(4, 72, default=36, space="sell", optimize=True)
    max_atr_spike = DecimalParameter(2.0, 6.0, default=4.0, decimals=1, space="sell", optimize=True)

    # -------------------------------------------------------------------------
    # INDICATORS
    # -------------------------------------------------------------------------
    def _compute_swings(self, dataframe: DataFrame, left: int, right: int) -> DataFrame:
        """
        Compute swing highs / lows based on local window comparisons.

        A point i is a swing high if:
            high[i] is greater than all highs in the previous `left` candles
            and greater/equal than all highs in the next `right` candles.

        Similarly for swing lows with inverted comparisons.

        This is a discrete approximation to ICT-style swing structure.
        """
        length = len(dataframe)
        swing_high = np.zeros(length, dtype=int)
        swing_low = np.zeros(length, dtype=int)

        highs = dataframe["high"].values
        lows = dataframe["low"].values

        for i in range(left, length - right):
            # Swing high
            is_high = True
            for j in range(1, left + 1):
                if highs[i] <= highs[i - j]:
                    is_high = False
                    break
            if is_high:
                for j in range(1, right + 1):
                    if highs[i] < highs[i + j]:
                        is_high = False
                        break
            if is_high:
                swing_high[i] = 1

            # Swing low
            is_low = True
            for j in range(1, left + 1):
                if lows[i] >= lows[i - j]:
                    is_low = False
                    break
            if is_low:
                for j in range(1, right + 1):
                    if lows[i] > lows[i + j]:
                        is_low = False
                        break
            if is_low:
                swing_low[i] = 1

        dataframe["swing_high"] = swing_high
        dataframe["swing_low"] = swing_low
        return dataframe

    def _compute_fvg(self, dataframe: DataFrame) -> DataFrame:
        """
        Compute Fair Value Gaps (FVG) as 3-candle imbalances.

        Bullish FVG (marked at the middle candle index i-1):
            high[i-2] < low[i]

        Bearish FVG:
            low[i-2] > high[i]

        This is a simplified, but structurally consistent, ICT-style definition.
        """
        length = len(dataframe)
        bull_fvg = np.zeros(length, dtype=int)
        bear_fvg = np.zeros(length, dtype=int)

        highs = dataframe["high"].values
        lows = dataframe["low"].values

        for i in range(2, length):
            # Center index is i-1
            mid = i - 1
            if highs[i - 2] < lows[i]:
                bull_fvg[mid] = 1
            if lows[i - 2] > highs[i]:
                bear_fvg[mid] = 1

        dataframe["bull_fvg"] = bull_fvg
        dataframe["bear_fvg"] = bear_fvg
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate core indicators and all structural helper fields.

        Indicators:
            - EMA 50 / EMA 200
            - ATR 14
            - Volume mean
            - Swing highs/lows
            - FVG flags
        """

        # EMAs (for trend / premium-discount context)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # ATR (used for displacement, SL buffer, ATR spike)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Volume mean
        dataframe["volume_mean"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Swings
        dataframe = self._compute_swings(
            dataframe,
            left=int(self.swing_lookback_left.value),
            right=int(self.swing_lookback_right.value),
        )

        # Fair Value Gaps (FVG)
        dataframe = self._compute_fvg(dataframe)

        # Initialize ICT-specific helper columns (for plotting and debugging)
        for col in [
            "liq_grab_long",
            "liq_grab_short",
            "displacement_long",
            "displacement_short",
            "long_state",
            "short_state",
            "ob_long_high",
            "ob_long_low",
            "ob_short_high",
            "ob_short_low",
        ]:
            dataframe[col] = 0.0

        # Columns where we store per-entry ICT prices (for custom SL/TP)
        for col in [
            "ict_long_entry",
            "ict_long_sl",
            "ict_long_tp1",
            "ict_long_tp2",
            "ict_short_entry",
            "ict_short_sl",
            "ict_short_tp1",
            "ict_short_tp2",
        ]:
            dataframe[col] = np.nan

        return dataframe

    # -------------------------------------------------------------------------
    # ENTRY LOGIC – ICT STATE MACHINE
    # -------------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Implements ICT-style workflow for both LONG and SHORT as a discrete state machine.

        Long side states (long_state):

            0 = idle
            1 = liquidity grab detected
            2 = displacement detected + OB defined
            3 = BOS confirmed, waiting for OB retest

        Short side is symmetric (short_state).
        """

        pair = metadata.get("pair", "UNKNOWN")

        # Initialize entry columns
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # Internal state variables for long & short
        long_state = 0
        short_state = 0
        long_bars_since_setup = 0
        short_bars_since_setup = 0

        last_swing_low = None
        last_swing_high = None
        last_swing_low_index = None
        last_swing_high_index = None

        # For long setup
        long_liq_level = None
        long_liq_index = None
        long_pre_grab_swing_high = None
        long_displacement_index = None
        long_ob_low = None
        long_ob_high = None
        long_entry_price = None

        # For short setup
        short_liq_level = None
        short_liq_index = None
        short_pre_grab_swing_low = None
        short_displacement_index = None
        short_ob_low = None
        short_ob_high = None
        short_entry_price = None

        # Helper arrays (for speed)
        o = dataframe["open"].values
        h = dataframe["high"].values
        l = dataframe["low"].values
        c = dataframe["close"].values
        atr = dataframe["atr"].values
        ema200 = dataframe["ema_200"].values
        vol = dataframe["volume"].values
        vol_mean = dataframe["volume_mean"].values
        swing_high = dataframe["swing_high"].values
        swing_low = dataframe["swing_low"].values
        bull_fvg = dataframe["bull_fvg"].values
        bear_fvg = dataframe["bear_fvg"].values

        length = len(dataframe)
        ob_lookback = int(self.ob_lookback_bars.value)
        max_setup = int(self.max_setup_bars.value)
        use_fvg = bool(self.use_fvg_filter.value)
        use_trend = bool(self.use_trend_filter.value)
        min_body_ratio = float(self.displacement_min_body_ratio.value)
        disp_atr_mult = float(self.displacement_atr_mult.value)
        ob_entry_frac = float(self.ob_entry_fraction.value)

        for i in range(length):
            # -------------------------------------------------------------
            # Update structure (latest swings)
            # -------------------------------------------------------------
            if swing_low[i] == 1:
                last_swing_low = l[i]
                last_swing_low_index = i

            if swing_high[i] == 1:
                last_swing_high = h[i]
                last_swing_high_index = i

            # Trend filter context
            long_trend_ok = True
            short_trend_ok = True
            if use_trend:
                long_trend_ok = c[i] > ema200[i]  # buy in discount relative to HTF trend
                short_trend_ok = c[i] < ema200[i]

            # =============================================================
            # LONG SIDE ICT STATE MACHINE
            # =============================================================

            # Reset if setup took too long
            if long_state > 0:
                long_bars_since_setup += 1
                if long_bars_since_setup > max_setup:
                    long_state = 0
                    long_liq_level = None
                    long_liq_index = None
                    long_displacement_index = None
                    long_ob_low = None
                    long_ob_high = None
                    long_entry_price = None

            # -------------------- State 0: Idle --------------------------
            if long_state == 0:
                # Liquidity grab below last swing low
                if last_swing_low is not None and last_swing_low_index is not None:
                    # Candle wicks below the swing low but closes back above it
                    if l[i] < last_swing_low and c[i] > last_swing_low:
                        long_state = 1
                        long_bars_since_setup = 0
                        long_liq_level = last_swing_low
                        long_liq_index = i
                        # BOS reference: last known swing high before the grab
                        long_pre_grab_swing_high = last_swing_high

                        dataframe.at[i, "liq_grab_long"] = 1
                        logger.debug(
                            f"[{pair}] LONG liquidity grab at index={i} | "
                            f"time={dataframe['date'].iat[i]} | "
                            f"liq_level={long_liq_level:.6f}"
                        )

            # ---------------- State 1: After Liquidity Grab ---------------
            elif long_state == 1:
                # Look for displacement up
                is_bull = c[i] > o[i]
                candle_range = h[i] - l[i]
                body = abs(c[i] - o[i])
                body_ratio = body / candle_range if candle_range > 0 else 0.0
                is_displacement_range = candle_range > disp_atr_mult * atr[i]
                has_fvg = bull_fvg[i] == 1 if use_fvg else True

                if (
                    is_bull
                    and is_displacement_range
                    and body_ratio >= min_body_ratio
                    and has_fvg
                    and long_trend_ok
                ):
                    # Mark displacement
                    dataframe.at[i, "displacement_long"] = 1
                    long_displacement_index = i

                    # Find last bearish candle before this displacement, within lookback window
                    ob_idx = None
                    j_start = max(0, i - ob_lookback)
                    for j in range(i - 1, j_start - 1, -1):
                        if c[j] < o[j]:
                            ob_idx = j
                            break

                    if ob_idx is not None:
                        ob_open = o[ob_idx]
                        ob_close = c[ob_idx]
                        ob_high = h[ob_idx]
                        ob_low = l[ob_idx]

                        body_low = min(ob_open, ob_close)
                        body_high = max(ob_open, ob_close)

                        # OB entry price: inside the body portion (e.g. 50%)
                        long_entry_price = body_low + ob_entry_frac * (body_high - body_low)
                        long_ob_low = ob_low
                        long_ob_high = ob_high

                        long_state = 2
                        long_bars_since_setup = 0

                        dataframe.at[ob_idx, "ob_long_low"] = long_ob_low
                        dataframe.at[ob_idx, "ob_long_high"] = long_ob_high

                        logger.debug(
                            f"[{pair}] LONG displacement + OB | disp_idx={i} ob_idx={ob_idx} | "
                            f"time={dataframe['date'].iat[i]} | "
                            f"ob_low={long_ob_low:.6f} ob_high={long_ob_high:.6f} "
                            f"entry_price={long_entry_price:.6f}"
                        )
                    else:
                        # No valid OB found – abort setup
                        logger.debug(
                            f"[{pair}] LONG displacement but no OB found | index={i} | "
                            f"time={dataframe['date'].iat[i]}"
                        )
                        long_state = 0
                        long_liq_level = None
                        long_liq_index = None
                        long_displacement_index = None
                        long_ob_low = None
                        long_ob_high = None
                        long_entry_price = None

            # --------------- State 2: OB defined, wait BOS ---------------
            elif long_state == 2:
                # BOS: break above previous swing high (pre-grab)
                if long_pre_grab_swing_high is not None and h[i] > long_pre_grab_swing_high:
                    long_state = 3
                    long_bars_since_setup = 0
                    logger.debug(
                        f"[{pair}] LONG BOS confirmed | index={i} | "
                        f"time={dataframe['date'].iat[i]} | "
                        f"pre_grab_swing_high={long_pre_grab_swing_high:.6f}"
                    )

            # --------------- State 3: BOS confirmed, wait retest OB -------
            if long_state == 3 and long_entry_price is not None:
                # We want a retest: candle trades into OB zone around entry price.
                # Check if price range touches the OB entry area and candle is not
                # an impulsive rejection in the opposite direction.
                in_ob_zone = l[i] <= long_entry_price <= h[i]

                if in_ob_zone and long_trend_ok:
                    # Entry LONG signal
                    dataframe.at[i, "enter_long"] = 1

                    # Compute SL and TP in price terms
                    # ICT-style: SL below liquidity grab low and/or OB low, with ATR buffer
                    ob_sl_base = min(long_ob_low, long_liq_level) if long_liq_level else long_ob_low
                    sl_price = ob_sl_base - float(self.sl_buffer_atr.value) * atr[i]
                    risk_per_unit = max(1e-8, long_entry_price - sl_price)

                    tp1 = long_entry_price + float(self.tp1_rr.value) * risk_per_unit
                    tp2 = long_entry_price + float(self.tp2_rr.value) * risk_per_unit

                    dataframe.at[i, "ict_long_entry"] = long_entry_price
                    dataframe.at[i, "ict_long_sl"] = sl_price
                    dataframe.at[i, "ict_long_tp1"] = tp1
                    dataframe.at[i, "ict_long_tp2"] = tp2

                    logger.info(
                        f"[{pair}] ENTER LONG ICT OB | index={i} | "
                        f"time={dataframe['date'].iat[i]} | "
                        f"entry={long_entry_price:.6f} sl={sl_price:.6f} "
                        f"tp1={tp1:.6f} tp2={tp2:.6f} | "
                        f"liq_level={(long_liq_level if long_liq_level is not None else float('nan')):.6f}"
                    )

                    # Reset long state after emitting the signal
                    long_state = 0
                    long_liq_level = None
                    long_liq_index = None
                    long_displacement_index = None
                    long_ob_low = None
                    long_ob_high = None
                    long_entry_price = None
                    long_bars_since_setup = 0

            # Track state for plotting
            dataframe.at[i, "long_state"] = long_state

            # =============================================================
            # SHORT SIDE – symmetric implementation
            # =============================================================

            # Reset if setup took too long
            if short_state > 0:
                short_bars_since_setup += 1
                if short_bars_since_setup > max_setup:
                    short_state = 0
                    short_liq_level = None
                    short_liq_index = None
                    short_displacement_index = None
                    short_ob_low = None
                    short_ob_high = None
                    short_entry_price = None

            # -------------------- State 0: Idle --------------------------
            if short_state == 0:
                # Liquidity grab above last swing high
                if last_swing_high is not None and last_swing_high_index is not None:
                    if h[i] > last_swing_high and c[i] < last_swing_high:
                        short_state = 1
                        short_bars_since_setup = 0
                        short_liq_level = last_swing_high
                        short_liq_index = i
                        short_pre_grab_swing_low = last_swing_low

                        dataframe.at[i, "liq_grab_short"] = 1
                        logger.debug(
                            f"[{pair}] SHORT liquidity grab at index={i} | "
                            f"time={dataframe['date'].iat[i]} | "
                            f"liq_level={short_liq_level:.6f}"
                        )

            # ---------------- State 1: After Liquidity Grab ---------------
            elif short_state == 1:
                # Displacement down
                is_bear = c[i] < o[i]
                candle_range = h[i] - l[i]
                body = abs(c[i] - o[i])
                body_ratio = body / candle_range if candle_range > 0 else 0.0
                is_displacement_range = candle_range > disp_atr_mult * atr[i]
                has_fvg = bear_fvg[i] == 1 if use_fvg else True

                if (
                    is_bear
                    and is_displacement_range
                    and body_ratio >= min_body_ratio
                    and has_fvg
                    and short_trend_ok
                ):
                    dataframe.at[i, "displacement_short"] = 1
                    short_displacement_index = i

                    # Find last bullish candle before this displacement
                    ob_idx = None
                    j_start = max(0, i - ob_lookback)
                    for j in range(i - 1, j_start - 1, -1):
                        if c[j] > o[j]:
                            ob_idx = j
                            break

                    if ob_idx is not None:
                        ob_open = o[ob_idx]
                        ob_close = c[ob_idx]
                        ob_high = h[ob_idx]
                        ob_low = l[ob_idx]

                        body_low = min(ob_open, ob_close)
                        body_high = max(ob_open, ob_close)

                        # For SHORT, entry is typically in upper body portion
                        short_entry_price = body_high - ob_entry_frac * (body_high - body_low)
                        short_ob_low = ob_low
                        short_ob_high = ob_high

                        short_state = 2
                        short_bars_since_setup = 0

                        dataframe.at[ob_idx, "ob_short_low"] = short_ob_low
                        dataframe.at[ob_idx, "ob_short_high"] = short_ob_high

                        logger.debug(
                            f"[{pair}] SHORT displacement + OB | disp_idx={i} ob_idx={ob_idx} | "
                            f"time={dataframe['date'].iat[i]} | "
                            f"ob_low={short_ob_low:.6f} ob_high={short_ob_high:.6f} "
                            f"entry_price={short_entry_price:.6f}"
                        )
                    else:
                        logger.debug(
                            f"[{pair}] SHORT displacement but no OB found | index={i} | "
                            f"time={dataframe['date'].iat[i]}"
                        )
                        short_state = 0
                        short_liq_level = None
                        short_liq_index = None
                        short_displacement_index = None
                        short_ob_low = None
                        short_ob_high = None
                        short_entry_price = None

            # --------------- State 2: OB defined, wait BOS ---------------
            elif short_state == 2:
                # BOS: break below previous swing low (pre-grab)
                if short_pre_grab_swing_low is not None and l[i] < short_pre_grab_swing_low:
                    short_state = 3
                    short_bars_since_setup = 0
                    logger.debug(
                        f"[{pair}] SHORT BOS confirmed | index={i} | "
                        f"time={dataframe['date'].iat[i]} | "
                        f"pre_grab_swing_low={short_pre_grab_swing_low:.6f}"
                    )

            # --------------- State 3: BOS confirmed, wait retest OB -------
            if short_state == 3 and short_entry_price is not None:
                in_ob_zone = l[i] <= short_entry_price <= h[i]

                if in_ob_zone and short_trend_ok:
                    dataframe.at[i, "enter_short"] = 1

                    # SL above liquidity grab high / OB high with ATR buffer
                    ob_sl_base = (
                        max(short_ob_high, short_liq_level) if short_liq_level else short_ob_high
                    )
                    sl_price = ob_sl_base + float(self.sl_buffer_atr.value) * atr[i]
                    risk_per_unit = max(1e-8, sl_price - short_entry_price)

                    tp1 = short_entry_price - float(self.tp1_rr.value) * risk_per_unit
                    tp2 = short_entry_price - float(self.tp2_rr.value) * risk_per_unit

                    dataframe.at[i, "ict_short_entry"] = short_entry_price
                    dataframe.at[i, "ict_short_sl"] = sl_price
                    dataframe.at[i, "ict_short_tp1"] = tp1
                    dataframe.at[i, "ict_short_tp2"] = tp2

                    logger.info(
                        f"[{pair}] ENTER SHORT ICT OB | index={i} | "
                        f"time={dataframe['date'].iat[i]} | "
                        f"entry={short_entry_price:.6f} sl={sl_price:.6f} "
                        f"tp1={tp1:.6f} tp2={tp2:.6f} | "
                        f"liq_level={(short_liq_level if short_liq_level is not None else float('nan')):.6f}"
                    )

                    short_state = 0
                    short_liq_level = None
                    short_liq_index = None
                    short_displacement_index = None
                    short_ob_low = None
                    short_ob_high = None
                    short_entry_price = None
                    short_bars_since_setup = 0

            dataframe.at[i, "short_state"] = short_state

        return dataframe

    # -------------------------------------------------------------------------
    # EXIT LOGIC (signal-based – disabled)
    # -------------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        We rely on custom_exit + custom_stoploss for exits.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # -------------------------------------------------------------------------
    # UTILITY – Fetch ICT prices at entry
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_entry_row(dataframe: DataFrame, trade: Trade) -> Optional[pd.Series]:
        """
        Retrieve the dataframe row corresponding to (or just before) the trade's
        open_time, to access stored ICT prices (entry, SL, TP1, TP2).

        This mirrors the same pattern used for ATR-based lookups in other bots.
        """
        entry_date = trade.open_date_utc
        df_slice = dataframe.loc[dataframe["date"] <= entry_date]
        if df_slice.empty:
            return None
        return df_slice.iloc[-1]

    # -------------------------------------------------------------------------
    # CUSTOM STOPLOSS – ICT SL price
    # -------------------------------------------------------------------------
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
        Use the ICT-based SL stored at entry (ict_long_sl / ict_short_sl).

        If unavailable, fall back to static stoploss.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        row = self._get_entry_row(dataframe, trade)
        if row is None:
            logger.warning(
                f"[{pair}] custom_stoploss: no entry row found, fallback to static | trade_id={trade.id}"
            )
            return self.stoploss

        if trade.is_short:
            sl_price = row.get("ict_short_sl", np.nan)
        else:
            sl_price = row.get("ict_long_sl", np.nan)

        if sl_price is None or not np.isfinite(sl_price):
            logger.warning(
                f"[{pair}] custom_stoploss: no ICT SL stored, fallback to static | "
                f"trade_id={trade.id}"
            )
            return self.stoploss

        # Freqtrade expects ratio relative to open_rate:
        # stop_price = open_rate * (1 + ratio)
        ratio = (sl_price - trade.open_rate) / trade.open_rate

        logger.debug(
            f"[{pair}] custom_stoploss | trade_id={trade.id} | "
            f"open={trade.open_rate:.6f} sl={sl_price:.6f} ratio={ratio:.4f}"
        )

        return ratio

    # -------------------------------------------------------------------------
    # CUSTOM EXIT – ICT TP2 + fail-safes
    # -------------------------------------------------------------------------
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
        Full exits triggered by:
            1) Hard time stop (max_trade_duration_hours).
            2) ATR spike relative to ATR at entry (max_atr_spike).
            3) TP2 hit (based on ICT TP2 price).
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        # 1) Time-based exit
        trade_duration_h = (current_time - trade.open_date_utc).total_seconds() / 3600.0
        if trade_duration_h > float(self.max_trade_duration_hours.value):
            logger.info(
                f"[{pair}] custom_exit: time-based exit | trade_id={trade.id} | "
                f"duration_h={trade_duration_h:.2f} | profit={current_profit:.4f}"
            )
            return "time_exit"

        # 2) ATR spike exit
        # We compare current ATR vs ATR at entry row
        row_entry = self._get_entry_row(dataframe, trade)
        if row_entry is None:
            return None

        atr_entry = row_entry.get("atr", np.nan)
        atr_current = float(dataframe.iloc[-1]["atr"])

        if np.isfinite(atr_entry) and atr_entry > 0 and np.isfinite(atr_current):
            atr_ratio = atr_current / atr_entry
            if atr_ratio >= float(self.max_atr_spike.value):
                logger.warning(
                    f"[{pair}] custom_exit: ATR spike exit | trade_id={trade.id} | "
                    f"atr_entry={atr_entry:.6f} atr_current={atr_current:.6f} "
                    f"atr_ratio={atr_ratio:.2f} | profit={current_profit:.4f}"
                )
                return "atr_spike_exit"

        # 3) TP2 price-based exit
        if trade.is_short:
            tp2_price = row_entry.get("ict_short_tp2", np.nan)
            if np.isfinite(tp2_price) and current_rate <= tp2_price:
                logger.info(
                    f"[{pair}] custom_exit: SHORT TP2 hit | trade_id={trade.id} | "
                    f"tp2={tp2_price:.6f} current={current_rate:.6f} "
                    f"profit={current_profit:.4f}"
                )
                return "tp2_exit"
        else:
            tp2_price = row_entry.get("ict_long_tp2", np.nan)
            if np.isfinite(tp2_price) and current_rate >= tp2_price:
                logger.info(
                    f"[{pair}] custom_exit: LONG TP2 hit | trade_id={trade.id} | "
                    f"tp2={tp2_price:.6f} current={current_rate:.6f} "
                    f"profit={current_profit:.4f}"
                )
                return "tp2_exit"

        return None

    # -------------------------------------------------------------------------
    # PARTIAL EXIT – TP1 via adjust_trade_position
    # -------------------------------------------------------------------------
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
        Partial exit logic for TP1.

        We look for TP1 being hit (price-based), and then close a fraction
        of the position ONCE per trade.
        """
        pair = trade.pair
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        row_entry = self._get_entry_row(dataframe, trade)
        if row_entry is None:
            return None

        if trade.is_short:
            tp1_price = row_entry.get("ict_short_tp1", np.nan)
            condition_hit = np.isfinite(tp1_price) and current_rate <= tp1_price
            exit_side = "buy"
        else:
            tp1_price = row_entry.get("ict_long_tp1", np.nan)
            condition_hit = np.isfinite(tp1_price) and current_rate >= tp1_price
            exit_side = "sell"

        if not condition_hit:
            return None

        # Check if we already performed a partial exit (there is a closed exit order)
        if trade.is_short:
            exit_orders = [o for o in trade.orders if o.side == "buy" and o.status == "closed"]
        else:
            exit_orders = [o for o in trade.orders if o.side == "sell" and o.status == "closed"]

        if len(exit_orders) > 0:
            return None

        close_amount = trade.amount * float(self.tp1_close_fraction.value)

        logger.info(
            f"[{pair}] adjust_trade_position: TP1 partial exit | "
            f"trade_id={trade.id} | side={exit_side} | "
            f"tp1={tp1_price:.6f} current={current_rate:.6f} "
            f"close_amount={close_amount:.6f} | "
            f"fraction={float(self.tp1_close_fraction.value):.2f} "
            f"| profit={current_profit:.4f}"
        )

        # Negative => reduce position by this amount
        return -close_amount

    # -------------------------------------------------------------------------
    # POSITION SIZING – ATR-based risk per trade
    # -------------------------------------------------------------------------
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
        Risk-based position sizing.

        We use ATR as a proxy for expected stop-distance (since the exact ICT
        SL is only known at signal time, but custom_stake_amount is called a bit earlier).

        Approximation:
            - stop_distance ≈ atr * displacement_atr_mult
            - risk_amount  = available_capital * risk_per_trade
            - size_coin    = risk_amount / stop_distance
            - size_stake   = size_coin * current_rate

        This is a consistent way to keep risk ~constant in % of equity.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last = dataframe.iloc[-1]
        atr = float(last["atr"])
        capital = self.wallets.get_available_stake_amount()

        if atr <= 0 or capital <= 0:
            logger.debug(
                f"[{pair}] custom_stake_amount: fallback to proposed_stake | "
                f"time={current_time} | atr={atr} capital={capital}"
            )
            return proposed_stake

        stop_distance = atr * float(self.displacement_atr_mult.value)
        if stop_distance <= 0:
            return proposed_stake

        risk_amount = capital * float(self.risk_per_trade.value)
        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate

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

    # -------------------------------------------------------------------------
    # ENTRY CONFIRMATION HOOK
    # -------------------------------------------------------------------------
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
        Called right before the order is placed.

        For now:
            - We simply log the intended entry.
            - You could add extra safeguards here if needed.
        """
        logger.info(
            f"[{pair}] CONFIRM ENTRY | side={side} | type={order_type} | "
            f"amount={amount:.6f} | rate={rate:.6f} | "
            f"time={current_time} | entry_tag={entry_tag}"
        )
        return True
