# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file

import logging  # <-- added

from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

import talib.abstract as ta

# Logger for this strategy module (added)
logger = logging.getLogger(__name__)


class Trend_VWAP_V1(IStrategy):
    """
    VWAP + DMI Trend Strategy (Safe Version)
    --------------------------------------------------
    Core idea:
        - Trade only when the market is in a "clean" trending regime.
        - Use Rolling VWAP + DMI/ADX to define directional entries.
        - Use ATR-based dynamic stoploss and position sizing.
        - Take profit using a fixed R:R target (no ROI time-based exits).

    Regime filter:
        Composite regime based on:
            1) ADX (trend strength)
            2) ATR ratio (short-term volatility vs long-term volatility)
            3) Volume vs volume_mean (market participation)

        Each condition contributes +1 to regime_score.
        Trading is allowed only when:
            regime_score >= regime_min_score

    Category in your bot map:
        -> Bot 1 – Trend Bot
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True

    # -------------------------------------------------------------------------
    # ROI / EXIT BEHAVIOR
    # -------------------------------------------------------------------------
    # We use pure R:R exits:
    #   - custom_stoploss (ATR-based)
    #   - custom_exit (R-multiple target)
    #
    # minimal_roi is set very high so it does NOT interfere with custom_exit.
    minimal_roi = {"0": 100}

    # Fallback stoploss:
    #   - Used if custom_stoploss returns this value or something invalid.
    #   - Also used by Freqtrade to know the "worst case" loss.
    stoploss = -0.247

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # We need enough candles to compute slow ATR(100), etc.
    startup_candle_count: int = 200

    # Order type configuration (you can tune this later in config if needed).
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "gtc", "exit": "gtc"}

    # -------------------------------------------------------------------------
    # VISUALIZATION CONFIG (Freqtrade UI / plot-dataframe)
    # -------------------------------------------------------------------------
    # This tells Freqtrade which indicators to show on the chart.
    # You can see these via:
    #   - freqtrade plot-dataframe -s VWAPDMISSafe_V3 ...
    #   - or from the Web UI chart.
    plot_config = {
        # Main price chart overlays
        "main_plot": {
            "rolling_vwap": {},  # Rolling VWAP
            "plus_di": {},  # +DI from DMI
            "minus_di": {},  # -DI from DMI
        },
        # Extra subplots
        "subplots": {
            # ADX and DMI strength
            "ADX": {
                "adx": {},
            },
            # ATR (fast and slow) and volatility ratio
            "ATR / Volatility": {
                "atr": {},
                "atr_slow": {},
                "atr_ratio": {},
            },
            # Volume behavior
            "Volume": {
                "volume": {},
                "volume_mean": {},
            },
            # Regime filter internals
            "Regime": {
                "regime_score": {},  # Composite score (0-3)
                "is_trending_regime": {},  # Boolean regime ON/OFF (plotted as 0/1)
            },
        },
    }

    # -------------------------------------------------------------------------
    # HYPEROPT PARAMETERS (entry / risk)
    # -------------------------------------------------------------------------
    # Core entry parameters based on VWAP + DMI
    vwap_window = IntParameter(150, 300, default=300, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 30, default=29, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.0, 2.5, default=1.785, space="buy", optimize=True)
    target_rr = DecimalParameter(2.0, 4.0, default=3.83, space="sell", optimize=True)

    # Risk per trade (fraction of available capital).
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.012, space="buy", optimize=True)

    # SAFETY: Max Stake Ratio (cap per-trade stake vs available capital)
    max_stake_ratio = DecimalParameter(0.1, 0.5, default=0.153, space="buy", optimize=True)

    # -------------------------------------------------------------------------
    # COMPOSITE REGIME FILTER PARAMETERS
    # -------------------------------------------------------------------------
    # These hyperopt parameters control the regime filter behavior.
    # The regime is considered "favorable" if enough conditions are true.
    #
    # 1) ADX threshold:
    #    - Measures trend strength.
    #    - Higher ADX -> stronger trend.
    regime_adx_threshold = IntParameter(18, 30, default=21, space="buy", optimize=True)

    # 2) ATR ratio threshold:
    #    - atr_ratio = ATR(14) / ATR(100)
    #    - If atr_ratio > 1.0, short-term volatility is greater than long-term.
    #    - This often corresponds to trend acceleration or more directional moves.
    regime_atr_threshold = DecimalParameter(
        0.9, 1.5, default=1.31, decimals=2, space="buy", optimize=True
    )

    # 3) Minimum composite score:
    #    - regime_score ranges from 0 to 3.
    #    - Each condition (ADX, ATR ratio, Volume) adds +1 if satisfied.
    #    - We require at least regime_min_score to allow trading.
    regime_min_score = IntParameter(1, 3, default=3, space="buy", optimize=True)

    # -------------------------------------------------------------------------
    # INDICATORS
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate all required indicators.

        This method runs once per candle and fills the dataframe with
        the columns used by the strategy, including those we want to visualize.

        Indicators included:
            - rolling_vwap: rolling VWAP over a configurable window.
            - adx, plus_di, minus_di: Directional Movement Index.
            - atr: fast ATR (14) for stoploss and risk.
            - atr_slow: slow ATR (100) for volatility regime baseline.
            - atr_ratio: atr / atr_slow, used for regime filter.
            - volume_mean: rolling mean of volume.
        """

        # -------------------------------
        # Rolling VWAP (Volume Weighted Average Price)
        # -------------------------------
        # VWAP formula:
        #   VWAP = Sum(price * volume) / Sum(volume)
        #
        # We use a rolling window so that the VWAP is not anchored to the
        # beginning of the dataset, but to a recent sliding window of candles.
        window = self.vwap_window.value
        pv = dataframe["close"] * dataframe["volume"]
        dataframe["rolling_vwap"] = (
            pv.rolling(window=window).sum() / dataframe["volume"].rolling(window=window).sum()
        )

        # -------------------------------
        # DMI / ADX (Directional Movement Index)
        # -------------------------------
        # ADX measures trend strength (0-100).
        # plus_di and minus_di measure bullish / bearish directional movement.
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # -------------------------------
        # ATR (Average True Range)
        # -------------------------------
        # Fast ATR (14) for:
        #   - dynamic stoploss distance
        #   - position sizing
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Slow ATR (100) used as a baseline for volatility regime:
        #   atr_ratio = atr_fast / atr_slow
        #   - atr_ratio > 1   -> volatility expansion (good for trend-following)
        #   - atr_ratio ~ 1   -> normal volatility
        #   - atr_ratio < 1   -> compressed volatility (might be more range-like)
        dataframe["atr_slow"] = ta.ATR(dataframe, timeperiod=100)

        # Protect against division by zero:
        dataframe["atr_ratio"] = 0.0
        valid_atr_mask = dataframe["atr_slow"] > 0
        dataframe.loc[valid_atr_mask, "atr_ratio"] = (
            dataframe.loc[valid_atr_mask, "atr"] / dataframe.loc[valid_atr_mask, "atr_slow"]
        )

        # -------------------------------
        # Volume mean
        # -------------------------------
        # Used for:
        #   - basic liquidity filter
        #   - 1 of the regime components (market participation)
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()

        # Initialize regime columns (filled later in populate_entry_trend).
        # We create them here so they exist also when plotting indicators.
        dataframe["regime_score"] = 0
        dataframe["is_trending_regime"] = False

        return dataframe

    # -------------------------------------------------------------------------
    # ENTRIES
    # -------------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic

        LONG entry conditions:
            1) Price action:
                - close > rolling_vwap
                - plus_di > minus_di  (bullish DMI)
            2) ADX filter:
                - adx > adx_threshold (minimum trend strength)
            3) Volume filter:
                - volume > volume_mean
            4) Regime filter:
                - Composite regime_score >= regime_min_score

        SHORT entry conditions:
            1) Price action:
                - close < rolling_vwap
                - minus_di > plus_di (bearish DMI)
            2) ADX filter:
                - adx > adx_threshold
            3) Volume filter:
                - volume > volume_mean
            4) Regime filter:
                - Composite regime_score >= regime_min_score
        """

        # Initialize entry columns
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # ---------------------------------------------------------------------
        # Composite Regime Filter
        # ---------------------------------------------------------------------
        # We build a score from 0 to 3:
        #   +1 if ADX > regime_adx_threshold
        #   +1 if atr_ratio > regime_atr_threshold
        #   +1 if volume > volume_mean
        #
        # Then we allow trading only when:
        #   regime_score >= regime_min_score
        #
        # This helps the bot stay out of:
        #   - flat, noisy ranges (low trend, low volatility, low volume)
        #   - extremely dead markets.
        dataframe["regime_score"] = 0

        # ADX component: trend strength
        dataframe.loc[
            dataframe["adx"] > self.regime_adx_threshold.value,
            "regime_score",
        ] += 1

        # ATR ratio component: volatility regime
        dataframe.loc[
            dataframe["atr_ratio"] > float(self.regime_atr_threshold.value),
            "regime_score",
        ] += 1

        # Volume component: market participation
        dataframe.loc[
            dataframe["volume"] > dataframe["volume_mean"],
            "regime_score",
        ] += 1

        # Boolean flag: True if regime is considered favorable for trend-following
        dataframe["is_trending_regime"] = dataframe["regime_score"] >= self.regime_min_score.value

        # ---------------------------------------------------------------------
        # LONG Conditions
        # ---------------------------------------------------------------------
        long_conditions = (
            (dataframe["close"] > dataframe["rolling_vwap"])  # Price above VWAP -> bullish bias
            & (dataframe["plus_di"] > dataframe["minus_di"])  # DMI confirms bullish direction
            & (dataframe["adx"] > self.adx_threshold.value)  # Minimum trend strength
            & (dataframe["volume"] > dataframe["volume_mean"])  # Avoid illiquid bars
            & (dataframe["is_trending_regime"])  # Composite regime filter
        )

        dataframe.loc[long_conditions, "enter_long"] = 1

        # ---------------------------------------------------------------------
        # SHORT Conditions
        # ---------------------------------------------------------------------
        short_conditions = (
            (dataframe["close"] < dataframe["rolling_vwap"])  # Price below VWAP -> bearish bias
            & (dataframe["minus_di"] > dataframe["plus_di"])  # DMI confirms bearish direction
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["volume"] > dataframe["volume_mean"])
            & (dataframe["is_trending_regime"])
        )

        dataframe.loc[short_conditions, "enter_short"] = 1

        # ---------------- LOGGING (added, non-destructive) -------------------
        try:
            pair = metadata.get("pair", "UNKNOWN")
        except Exception:
            pair = "UNKNOWN"

        if len(dataframe) > 0:
            last = dataframe.iloc[-1]

            # Log when regime is ON
            if last["is_trending_regime"]:
                logger.debug(
                    f"[{pair}] TREND REGIME ON | time={last['date']} | "
                    f"regime_score={int(last['regime_score'])} | "
                    f"adx={last['adx']:.2f} | atr_ratio={last['atr_ratio']:.2f} | "
                    f"volume={last['volume']:.0f} vol_mean={last['volume_mean']:.0f}"
                )

            # Log when we emit entry signals
            if last["enter_long"] == 1:
                logger.info(
                    f"[{pair}] ENTER LONG signal | time={last['date']} | "
                    f"close={last['close']:.4f} vwap={last['rolling_vwap']:.4f} | "
                    f"+DI={last['plus_di']:.2f} -DI={last['minus_di']:.2f} | "
                    f"adx={last['adx']:.2f} | regime_score={int(last['regime_score'])}"
                )

            if last["enter_short"] == 1:
                logger.info(
                    f"[{pair}] ENTER SHORT signal | time={last['date']} | "
                    f"close={last['close']:.4f} vwap={last['rolling_vwap']:.4f} | "
                    f"+DI={last['plus_di']:.2f} -DI={last['minus_di']:.2f} | "
                    f"adx={last['adx']:.2f} | regime_score={int(last['regime_score'])}"
                )
        # ---------------------------------------------------------------------

        return dataframe

    # -------------------------------------------------------------------------
    # EXITS (signal-based, but we actually rely on custom_exit/custom_stoploss)
    # -------------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit Logic:
            - We keep exit signals disabled.
            - Real exits are managed by:
                - custom_stoploss (ATR-based stop)
                - custom_exit (R-multiple target)
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # -------------------------------------------------------------------------
    # Helper: get ATR at entry candle
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_entry_atr(
        dataframe: DataFrame,
        trade: Trade,
    ) -> float:
        """
        Helper method to retrieve the ATR value at (or just before) the trade's
        open candle.

        Why this matters:
            - We want the stoploss distance and R-multiple calculation to be
              based on the volatility at entry time, not current volatility.
            - This makes the risk per trade more stable and predictable.

        Implementation:
            - Filter all candles up to trade.open_date_utc.
            - Take the last one as the "entry candle".
        """
        entry_date = trade.open_date_utc

        df_entry = dataframe.loc[dataframe["date"] <= entry_date]

        if not df_entry.empty and "atr" in df_entry.columns:
            return float(df_entry.iloc[-1]["atr"])

        # Fallback: if for some reason we do not find the candle,
        # use the last available ATR.
        return float(dataframe.iloc[-1]["atr"])

    # -------------------------------------------------------------------------
    # Dynamic Stoploss (ATR-based)
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
        Dynamic stoploss based on ATR at entry.

        Freqtrade expects the return value to be a RATIO relative to
        trade.open_rate:

            stoploss_price = open_rate * (1 + returned_value)

        Therefore:
            - For LONG trades:
                - A stop below entry must be a NEGATIVE value.
                - Example: -0.05 => stop at -5% from open_rate.
            - For SHORT trades:
                - A stop above entry must be a POSITIVE value.
                - Example: 0.05  => stop at +5% from open_rate.

        Here we use:
            stop_distance = atr_at_entry * atr_multiplier
        """

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        atr = self._get_entry_atr(dataframe, trade)

        if atr <= 0:
            # Fallback: if ATR is not valid, use the static stoploss.
            logger.warning(
                f"[{pair}] custom_stoploss fallback to static stoploss | "
                f"trade_id={trade.id} | atr={atr}"
            )
            return self.stoploss

        # Distance in price units (e.g. in USDT)
        sl_distance = atr * self.atr_multiplier.value

        if sl_distance <= 0:
            logger.warning(
                f"[{pair}] custom_stoploss invalid sl_distance, fallback | "
                f"trade_id={trade.id} | sl_distance={sl_distance}"
            )
            return self.stoploss

        if trade.is_short:
            # SHORT:
            #   - Stop is ABOVE entry.
            #   - stop_price = open_rate + sl_distance
            #   - ratio = sl_distance / open_rate
            ratio = sl_distance / trade.open_rate
        else:
            # LONG:
            #   - Stop is BELOW entry.
            #   - stop_price = open_rate - sl_distance
            #   - ratio = -sl_distance / open_rate
            ratio = -sl_distance / trade.open_rate

        logger.debug(
            f"[{pair}] custom_stoploss | trade_id={trade.id} | "
            f"atr={atr:.6f} atr_mult={float(self.atr_multiplier.value):.2f} "
            f"sl_distance={sl_distance:.6f} ratio={ratio:.4f}"
        )

        return ratio

    # -------------------------------------------------------------------------
    # Take profit based on Target R:R (ATR-based)
    # -------------------------------------------------------------------------
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
        Take profit when a target R-multiple is reached.

        Definitions:
            - R (risk) = atr_at_entry * atr_multiplier
            - profit_amount:
                * LONG:  current_rate - open_rate
                * SHORT: open_rate   - current_rate
            - R-multiple:
                r_multiple = profit_amount / R

        If r_multiple >= target_rr:
            -> Close the trade (full exit).
        """

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        atr = self._get_entry_atr(dataframe, trade)
        if atr <= 0:
            return None

        risk = atr * self.atr_multiplier.value
        if risk <= 0:
            return None

        # Profit in price units
        if trade.is_short:
            profit_amount = trade.open_rate - current_rate
        else:
            profit_amount = current_rate - trade.open_rate

        r_multiple = profit_amount / risk

        if r_multiple >= self.target_rr.value:
            logger.info(
                f"[{pair}] EXIT target R:R | trade_id={trade.id} | "
                f"R={r_multiple:.2f} target_rr={float(self.target_rr.value):.2f} | "
                f"profit={current_profit:.4f}"
            )
            return "target_rr_reached"

        return None

    # -------------------------------------------------------------------------
    # Position sizing based on risk (ATR)
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
        Position sizing based on ATR risk.

        Goal:
            Keep the monetary risk per trade (in stake currency) around
            risk_per_trade * available_capital.

        Steps:
            1. Get current ATR (fast ATR 14).
            2. Compute stop distance:
                    stop_distance = atr * atr_multiplier
            3. Compute the amount of "coin" such that:
                    risk_amount = capital * risk_per_trade
                    size_coin  = risk_amount / stop_distance
            4. Convert to stake currency:
                    size_stake = size_coin * current_rate
            5. Clamp to:
                    [min_stake, max_stake]
                    and max_stake_ratio * capital.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        atr = last_candle["atr"]

        if atr <= 0:
            # If ATR is not usable (e.g. early candles), use the proposed stake.
            logger.debug(
                f"[{pair}] custom_stake_amount fallback to proposed_stake | "
                f"time={current_time} | atr={atr}"
            )
            return proposed_stake

        # Available capital in stake currency (more conservative than total stake).
        capital = self.wallets.get_available_stake_amount()

        if capital <= 0:
            logger.warning(
                f"[{pair}] custom_stake_amount no available capital | time={current_time}"
            )
            return min_stake

        # Risk to allocate to this trade (in stake currency).
        risk_amount = capital * self.risk_per_trade.value

        # Price distance to stoploss in stake currency per 1 unit of coin.
        stop_distance = atr * self.atr_multiplier.value

        if stop_distance <= 0:
            logger.debug(
                f"[{pair}] custom_stake_amount invalid stop_distance, using proposed_stake | "
                f"time={current_time} | stop_distance={stop_distance}"
            )
            return proposed_stake

        # Position size in coin units
        size_coin = risk_amount / stop_distance

        # Convert to stake currency
        size_stake = size_coin * current_rate

        # Respect exchange-imposed min/max
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake

        # Additional safety: cap stake by max_stake_ratio of available capital
        max_allowed_stake = capital * self.max_stake_ratio.value
        if size_stake > max_allowed_stake:
            size_stake = max_allowed_stake

        logger.debug(
            f"[{pair}] custom_stake_amount | time={current_time} | "
            f"capital={capital:.2f} risk_per_trade={float(self.risk_per_trade.value):.4f} "
            f"risk_amount={risk_amount:.2f} atr={atr:.6f} stop_distance={stop_distance:.6f} "
            f"size_stake={size_stake:.2f} (min={min_stake:.2f}, max={max_stake:.2f})"
        )

        return size_stake
