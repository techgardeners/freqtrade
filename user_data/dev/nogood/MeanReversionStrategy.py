"""
MeanReversionStrategy - Mean Reversion Strategy for Range-Bound Markets

This strategy targets sideways/ranging markets by identifying oversold and overbought
conditions using multiple oscillators and volatility bands. It only activates when
ADX indicates weak trend strength (ADX < 20).

Key Features:
- Multiple oscillators: RSI, Stochastic RSI, Z-Score
- Bollinger Bands and Keltner Channels for volatility analysis
- ADX filter to avoid trending markets
- Tight ATR-based stops (1× ATR)
- Mean reversion targets (SMA20)
- Time-based and fail-safe exits
- Consecutive loss protection

Recommended Timeframes: 5m, 15m, 30m
Recommended Markets: BTC, ETH, liquid altcoins

Author: Freqtrade Strategy Development
Version: 1.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from functools import reduce
import numpy as np
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter
)
from freqtrade.persistence import Trade


STRATEGY_VERSION = "1.0.0"


class MeanReversionStrategy(IStrategy):
    """
    Mean Reversion Strategy - Contrarian approach for ranging markets
    
    Strategy activates only when ADX < 20 (weak trend).
    Buys oversold conditions, sells overbought conditions.
    Targets mean (SMA20) for profit taking.
    """

    # Strategy Metadata
    INTERFACE_VERSION = 3
    can_short = True
    
    # Timeframe Configuration
    timeframe = '15m'
    
    # Startup candle count (need enough for EMA200 + indicator calculations)
    startup_candle_count: int = 250
    
    # ROI table (will be overridden by custom exit logic)
    minimal_roi = {
        "0": 0.05  # 5% as fallback
    }
    
    # Stoploss (will be overridden by custom_stoploss)
    stoploss = -0.05  # -5% as hard stop
    
    # Trailing stop (disabled, managed by custom logic)
    trailing_stop = False
    
    # Order types
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    # Order time in force
    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }
    
    # Position adjustment (for partial closes)
    position_adjustment_enable = True
    max_entry_position_adjustment = 0  # No DCA, only exits
    
    # ============================================================================
    # HYPEROPT PARAMETERS
    # ============================================================================
    
    # --- RSI Parameters ---
    rsi_period = IntParameter(9, 21, default=14, space='buy', optimize=True)
    rsi_oversold = IntParameter(25, 35, default=30, space='buy', optimize=True)
    rsi_overbought = IntParameter(65, 75, default=70, space='sell', optimize=True)
    
    # --- Stochastic RSI Parameters ---
    stoch_rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    stoch_rsi_k = IntParameter(3, 5, default=3, space='buy', optimize=True)
    stoch_rsi_d = IntParameter(3, 5, default=3, space='buy', optimize=True)
    stoch_oversold = IntParameter(15, 25, default=20, space='buy', optimize=True)
    stoch_overbought = IntParameter(75, 85, default=80, space='sell', optimize=True)
    
    # --- Bollinger Bands Parameters ---
    bb_period = IntParameter(15, 25, default=20, space='buy', optimize=True)
    bb_std = DecimalParameter(1.8, 2.5, default=2.0, decimals=1, space='buy', optimize=True)
    
    # --- Keltner Channels Parameters ---
    keltner_period = IntParameter(15, 25, default=20, space='buy', optimize=True)
    keltner_atr_mult = DecimalParameter(1.0, 2.0, default=1.5, decimals=1, space='buy', optimize=True)
    
    # --- Z-Score Parameters ---
    zscore_period = IntParameter(15, 25, default=20, space='buy', optimize=True)
    zscore_threshold = DecimalParameter(1.0, 1.5, default=1.25, decimals=2, space='buy', optimize=True)
    
    # --- ADX Parameters (Range Detection) ---
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    adx_max_threshold = IntParameter(18, 22, default=20, space='buy', optimize=True)
    adx_exit_threshold = IntParameter(22, 26, default=22, space='sell', optimize=True)
    
    # --- EMA Parameters (Trend Bias) ---
    ema_short_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    ema_long_period = IntParameter(180, 220, default=200, space='buy', optimize=True)
    
    # --- ATR Parameters (Volatility & Stops) ---
    atr_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    atr_stop_multiplier = DecimalParameter(0.7, 1.2, default=1.0, decimals=1, space='sell', optimize=True)
    atr_spike_threshold = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space='buy', optimize=True)
    
    # --- Entry Signal Requirements ---
    min_excess_signals = IntParameter(2, 3, default=2, space='buy', optimize=True)
    
    # --- Take Profit Parameters ---
    use_dual_tp = CategoricalParameter([True, False], default=True, space='sell', optimize=True)
    tp1_close_percentage = DecimalParameter(0.4, 0.6, default=0.5, decimals=1, space='sell', optimize=True)
    
    # --- Time-Based Exit ---
    max_trade_duration_bars = IntParameter(10, 20, default=15, space='sell', optimize=True)
    
    # --- Candlestick Filter Parameters ---
    min_candle_body_ratio = DecimalParameter(0.2, 0.5, default=0.3, decimals=1, space='buy', optimize=True)
    max_shadow_ratio = DecimalParameter(0.4, 0.6, default=0.5, decimals=1, space='buy', optimize=True)
    
    # --- Risk Management ---
    risk_per_trade = DecimalParameter(0.005, 0.01, default=0.01, decimals=3, space='buy', optimize=False)
    max_position_size_btc_eth = DecimalParameter(0.2, 0.3, default=0.25, decimals=2, space='buy', optimize=False)
    max_position_size_altcoins = DecimalParameter(0.1, 0.2, default=0.15, decimals=2, space='buy', optimize=False)
    
    # --- Consecutive Loss Protection ---
    max_consecutive_losses = IntParameter(4, 6, default=5, space='buy', optimize=False)
    pause_bars_after_losses = IntParameter(15, 25, default=20, space='buy', optimize=False)
    
    # Track consecutive losses (class variable)
    consecutive_losses = 0
    pause_until_bar = 0
    
    # ============================================================================
    # INDICATOR POPULATION
    # ============================================================================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate all technical indicators for mean reversion analysis"""
        
        # === Moving Averages ===
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=self.zscore_period.value)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=self.ema_short_period.value)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=self.ema_long_period.value)
        
        # EMA Slope (to detect flat trend)
        dataframe['ema_50_slope'] = (
            (dataframe['ema_50'] - dataframe['ema_50'].shift(3)) / 
            (dataframe['ema_50'].shift(3) + 1e-10)
        )
        dataframe['ema_200_slope'] = (
            (dataframe['ema_200'] - dataframe['ema_200'].shift(5)) / 
            (dataframe['ema_200'].shift(5) + 1e-10)
        )
        
        # EMA Distance (to detect convergence)
        dataframe['ema_distance'] = (
            abs(dataframe['ema_50'] - dataframe['ema_200']) / 
            (dataframe['ema_200'] + 1e-10)
        )
        
        # === Oscillators ===
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # Stochastic RSI
        stoch_rsi = ta.STOCHRSI(
            dataframe, 
            timeperiod=self.stoch_rsi_period.value,
            fastk_period=self.stoch_rsi_k.value,
            fastd_period=self.stoch_rsi_d.value
        )
        dataframe['stoch_rsi_k'] = stoch_rsi['fastk']
        dataframe['stoch_rsi_d'] = stoch_rsi['fastd']
        
        # Z-Score (deviation from SMA20)
        dataframe['price_std'] = dataframe['close'].rolling(window=self.zscore_period.value).std()
        dataframe['zscore'] = (
            (dataframe['close'] - dataframe['sma_20']) / 
            (dataframe['price_std'] + 1e-10)
        )
        
        # === Volatility Bands ===
        # Bollinger Bands
        bollinger = ta.BBANDS(
            dataframe, 
            timeperiod=self.bb_period.value,
            nbdevup=self.bb_std.value,
            nbdevdn=self.bb_std.value
        )
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_width'] = (
            (dataframe['bb_upper'] - dataframe['bb_lower']) / 
            (dataframe['bb_middle'] + 1e-10)
        )
        
        # Keltner Channels
        dataframe['keltner_middle'] = ta.EMA(dataframe, timeperiod=self.keltner_period.value)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        dataframe['keltner_upper'] = dataframe['keltner_middle'] + (
            self.keltner_atr_mult.value * dataframe['atr']
        )
        dataframe['keltner_lower'] = dataframe['keltner_middle'] - (
            self.keltner_atr_mult.value * dataframe['atr']
        )
        
        # Squeeze Indicator (BB inside Keltner)
        dataframe['squeeze'] = (
            (dataframe['bb_lower'] > dataframe['keltner_lower']) &
            (dataframe['bb_upper'] < dataframe['keltner_upper'])
        ).astype(int)
        
        # === Trend Strength ===
        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # === Volatility Metrics ===
        dataframe['atr_ma'] = ta.SMA(dataframe['atr'], timeperiod=20)
        
        # === Candlestick Metrics ===
        dataframe['candle_body'] = abs(dataframe['close'] - dataframe['open'])
        dataframe['candle_range'] = dataframe['high'] - dataframe['low']
        dataframe['candle_body_ratio'] = dataframe['candle_body'] / (dataframe['candle_range'] + 1e-10)
        
        # Upper and lower shadows
        dataframe['upper_shadow'] = dataframe['high'] - dataframe[['open', 'close']].max(axis=1)
        dataframe['lower_shadow'] = dataframe[['open', 'close']].min(axis=1) - dataframe['low']
        dataframe['shadow_ratio'] = (
            (dataframe['upper_shadow'] + dataframe['lower_shadow']) / 
            (dataframe['candle_range'] + 1e-10)
        )
        
        # === Distance to Mean ===
        dataframe['distance_to_sma20'] = (
            (dataframe['close'] - dataframe['sma_20']) / 
            (dataframe['sma_20'] + 1e-10)
        )
        
        return dataframe
    
    # ============================================================================
    # ENTRY SIGNAL LOGIC
    # ============================================================================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate entry signals for LONG and SHORT positions in ranging markets"""
        
        # Check if strategy is paused due to consecutive losses
        current_bar = len(dataframe)
        if current_bar < self.pause_until_bar:
            # Strategy is paused, no entries
            return dataframe
        
        # === LONG Entry Conditions ===
        long_conditions = []
        
        # 1. Market Context: Ranging Market (ADX < threshold)
        long_context = (
            (dataframe['adx'] < self.adx_max_threshold.value) &
            (abs(dataframe['ema_50_slope']) < 0.002) &  # Flat EMA50
            (abs(dataframe['ema_200_slope']) < 0.001) &  # Flat EMA200
            (dataframe['close'] > dataframe['ema_200'])  # Above long-term trend
        )
        long_conditions.append(long_context)
        
        # 2. Excess Signals (count how many are triggered)
        excess_rsi = dataframe['rsi'] < self.rsi_oversold.value
        excess_stoch = dataframe['stoch_rsi_k'] < self.stoch_oversold.value
        excess_bb = dataframe['close'] < dataframe['bb_lower']
        excess_zscore = dataframe['zscore'] < -self.zscore_threshold.value
        
        # Count excess signals
        dataframe['long_excess_count'] = (
            excess_rsi.astype(int) + 
            excess_stoch.astype(int) + 
            excess_bb.astype(int) + 
            excess_zscore.astype(int)
        )
        
        long_excess = dataframe['long_excess_count'] >= self.min_excess_signals.value
        long_conditions.append(long_excess)
        
        # 3. Reversal Trigger
        long_reversal = (
            # Bullish candle closing above previous high
            ((dataframe['close'] > dataframe['open']) & 
             (dataframe['close'] > dataframe['high'].shift(1))) |
            # OR RSI crosses above oversold
            ((dataframe['rsi'] > self.rsi_oversold.value) & 
             (dataframe['rsi'].shift(1) <= self.rsi_oversold.value)) |
            # OR Stoch RSI crosses up
            ((dataframe['stoch_rsi_k'] > dataframe['stoch_rsi_d']) &
             (dataframe['stoch_rsi_k'].shift(1) <= dataframe['stoch_rsi_d'].shift(1)))
        )
        long_conditions.append(long_reversal)
        
        # 4. Candlestick Quality Filter
        long_candle = (
            (dataframe['candle_body_ratio'] > self.min_candle_body_ratio.value) &
            (dataframe['shadow_ratio'] < self.max_shadow_ratio.value)
        )
        long_conditions.append(long_candle)
        
        # 5. Volatility Filter (avoid extreme spikes)
        long_volatility = (
            dataframe['candle_range'] < self.atr_spike_threshold.value * dataframe['atr']
        )
        long_conditions.append(long_volatility)
        
        # Combine all LONG conditions
        if long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, long_conditions),
                'enter_long'] = 1
        
        # === SHORT Entry Conditions ===
        short_conditions = []
        
        # 1. Market Context: Ranging Market
        short_context = (
            (dataframe['adx'] < self.adx_max_threshold.value) &
            (abs(dataframe['ema_50_slope']) < 0.002) &
            (abs(dataframe['ema_200_slope']) < 0.001) &
            (dataframe['close'] < dataframe['ema_200'])  # Below long-term trend
        )
        short_conditions.append(short_context)
        
        # 2. Excess Signals
        excess_rsi_short = dataframe['rsi'] > self.rsi_overbought.value
        excess_stoch_short = dataframe['stoch_rsi_k'] > self.stoch_overbought.value
        excess_bb_short = dataframe['close'] > dataframe['bb_upper']
        excess_zscore_short = dataframe['zscore'] > self.zscore_threshold.value
        
        dataframe['short_excess_count'] = (
            excess_rsi_short.astype(int) + 
            excess_stoch_short.astype(int) + 
            excess_bb_short.astype(int) + 
            excess_zscore_short.astype(int)
        )
        
        short_excess = dataframe['short_excess_count'] >= self.min_excess_signals.value
        short_conditions.append(short_excess)
        
        # 3. Reversal Trigger
        short_reversal = (
            # Bearish candle closing below previous low
            ((dataframe['close'] < dataframe['open']) & 
             (dataframe['close'] < dataframe['low'].shift(1))) |
            # OR RSI crosses below overbought
            ((dataframe['rsi'] < self.rsi_overbought.value) & 
             (dataframe['rsi'].shift(1) >= self.rsi_overbought.value)) |
            # OR Stoch RSI crosses down
            ((dataframe['stoch_rsi_k'] < dataframe['stoch_rsi_d']) &
             (dataframe['stoch_rsi_k'].shift(1) >= dataframe['stoch_rsi_d'].shift(1)))
        )
        short_conditions.append(short_reversal)
        
        # 4. Candlestick Quality Filter
        short_candle = (
            (dataframe['candle_body_ratio'] > self.min_candle_body_ratio.value) &
            (dataframe['shadow_ratio'] < self.max_shadow_ratio.value)
        )
        short_conditions.append(short_candle)
        
        # 5. Volatility Filter
        short_volatility = (
            dataframe['candle_range'] < self.atr_spike_threshold.value * dataframe['atr']
        )
        short_conditions.append(short_volatility)
        
        # Combine all SHORT conditions
        if short_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, short_conditions),
                'enter_short'] = 1
        
        return dataframe
    
    # ============================================================================
    # EXIT SIGNAL LOGIC
    # ============================================================================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate exit signals based on mean reversion and fail-safes"""
        
        # === LONG Exit Conditions ===
        long_exit_conditions = []
        
        # 1. Mean Reversion Complete (price reached SMA20)
        long_exit_mean = (
            dataframe['close'] >= dataframe['sma_20']
        )
        long_exit_conditions.append(long_exit_mean)
        
        # 2. Trend Activation (ADX rises, market no longer ranging)
        long_exit_trend = (
            dataframe['adx'] > self.adx_exit_threshold.value
        )
        long_exit_conditions.append(long_exit_trend)
        
        # 3. Range Break (price closes below BB lower for 2 bars)
        long_exit_break = (
            (dataframe['close'] < dataframe['bb_lower']) &
            (dataframe['close'].shift(1) < dataframe['bb_lower'].shift(1))
        )
        long_exit_conditions.append(long_exit_break)
        
        # Combine LONG exit conditions (OR logic)
        if long_exit_conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, long_exit_conditions),
                'exit_long'] = 1
        
        # === SHORT Exit Conditions ===
        short_exit_conditions = []
        
        # 1. Mean Reversion Complete
        short_exit_mean = (
            dataframe['close'] <= dataframe['sma_20']
        )
        short_exit_conditions.append(short_exit_mean)
        
        # 2. Trend Activation
        short_exit_trend = (
            dataframe['adx'] > self.adx_exit_threshold.value
        )
        short_exit_conditions.append(short_exit_trend)
        
        # 3. Range Break (price closes above BB upper for 2 bars)
        short_exit_break = (
            (dataframe['close'] > dataframe['bb_upper']) &
            (dataframe['close'].shift(1) > dataframe['bb_upper'].shift(1))
        )
        short_exit_conditions.append(short_exit_break)
        
        # Combine SHORT exit conditions
        if short_exit_conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, short_exit_conditions),
                'exit_short'] = 1
        
        return dataframe
    
    # ============================================================================
    # CUSTOM STOPLOSS
    # ============================================================================
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stop loss based on ATR (tight stops for mean reversion)
        
        Returns:
            float: Stop loss percentage (negative value)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        atr = last_candle['atr']
        
        # Calculate stop distance: 1× ATR
        if trade.is_short:
            stop_distance = self.atr_stop_multiplier.value * atr
            stop_price = trade.open_rate + stop_distance
            stop_loss_pct = (stop_price - current_rate) / current_rate
        else:
            stop_distance = self.atr_stop_multiplier.value * atr
            stop_price = trade.open_rate - stop_distance
            stop_loss_pct = (current_rate - stop_price) / current_rate
        
        # Move to break-even after reaching SMA20 (TP1)
        if current_profit >= 0.01:  # 1% profit
            return 0.001  # Minimal profit to ensure break-even
        
        return stop_loss_pct
    
    # ============================================================================
    # POSITION ADJUSTMENT (Partial Closes)
    # ============================================================================
    
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                             current_rate: float, current_profit: float,
                             min_stake: Optional[float], max_stake: float,
                             current_entry_rate: float, current_exit_rate: float,
                             current_entry_profit: float, current_exit_profit: float,
                             **kwargs) -> Optional[float]:
        """
        Manage partial position closes at TP1 (SMA20) and TP2 (opposite BB)
        
        Returns:
            Optional[float]: Stake amount to reduce (negative value) or None
        """
        
        # Only use dual TP if enabled
        if not self.use_dual_tp.value:
            return None
        
        # Get trade metadata
        if not hasattr(trade, 'tp1_hit'):
            trade.tp1_hit = False
        if not hasattr(trade, 'tp2_hit'):
            trade.tp2_hit = False
        
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # TP1: Close partial at SMA20
        if not trade.tp1_hit:
            if trade.is_short:
                # SHORT: TP1 when price reaches SMA20 from above
                if current_rate <= last_candle['sma_20']:
                    trade.tp1_hit = True
                    close_amount = trade.stake_amount * self.tp1_close_percentage.value
                    return -close_amount
            else:
                # LONG: TP1 when price reaches SMA20 from below
                if current_rate >= last_candle['sma_20']:
                    trade.tp1_hit = True
                    close_amount = trade.stake_amount * self.tp1_close_percentage.value
                    return -close_amount
        
        # TP2: Close remaining at opposite Bollinger Band
        if trade.tp1_hit and not trade.tp2_hit:
            if trade.is_short:
                # SHORT: TP2 at lower Bollinger Band
                if current_rate <= last_candle['bb_lower']:
                    trade.tp2_hit = True
                    return -trade.stake_amount  # Close all remaining
            else:
                # LONG: TP2 at upper Bollinger Band
                if current_rate >= last_candle['bb_upper']:
                    trade.tp2_hit = True
                    return -trade.stake_amount  # Close all remaining
        
        return None
    
    # ============================================================================
    # CUSTOM EXIT
    # ============================================================================
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Custom exit logic for time-based exits and fail-safes
        
        Returns:
            Optional[str]: Exit reason or None
        """
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Time-based exit (if mean reversion doesn't happen within X bars)
        trade_duration_bars = (current_time - trade.open_date_utc).total_seconds() / (
            60 * int(self.timeframe[:-1])  # Convert timeframe to minutes
        )
        if trade_duration_bars > self.max_trade_duration_bars.value:
            return 'time_based_exit'
        
        # Volatility spike exit (ATR suddenly increases)
        if last_candle['atr'] > 2 * last_candle['atr_ma']:
            return 'volatility_spike'
        
        # Trend activation exit (ADX rises significantly)
        if last_candle['adx'] > self.adx_exit_threshold.value + 5:
            return 'trend_activation'
        
        return None
    
    # ============================================================================
    # CUSTOM STAKE AMOUNT (Position Sizing)
    # ============================================================================
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float],
                           max_stake: float, leverage: float, entry_tag: Optional[str],
                           side: str, **kwargs) -> float:
        """
        Calculate position size based on fixed risk percentage
        
        Larger positions allowed for BTC/ETH (25%) vs altcoins (15%)
        
        Returns:
            float: Stake amount in quote currency
        """
        
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get wallet balance
        wallet_balance = self.wallets.get_total_stake_amount()
        
        # Calculate stop distance
        atr = last_candle['atr']
        stop_distance = self.atr_stop_multiplier.value * atr
        stop_distance_pct = stop_distance / current_rate
        
        # Calculate position size based on risk
        risk_amount = wallet_balance * self.risk_per_trade.value
        position_size = risk_amount / stop_distance_pct
        
        # Apply maximum position size limit (different for BTC/ETH vs altcoins)
        if 'BTC' in pair or 'ETH' in pair:
            max_position = wallet_balance * self.max_position_size_btc_eth.value
        else:
            max_position = wallet_balance * self.max_position_size_altcoins.value
        
        position_size = min(position_size, max_position)
        
        # Ensure within min/max stake bounds
        if min_stake is not None:
            position_size = max(position_size, min_stake)
        position_size = min(position_size, max_stake)
        
        return position_size
    
    # ============================================================================
    # TRADE TRACKING (Consecutive Loss Protection)
    # ============================================================================
    
    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                          rate: float, time_in_force: str, exit_reason: str,
                          current_time: datetime, **kwargs) -> bool:
        """
        Track consecutive losses and pause strategy if needed
        
        Returns:
            bool: True to confirm exit, False to cancel
        """
        
        # Check if trade is a loss
        if trade.calc_profit_ratio(rate) < 0:
            self.consecutive_losses += 1
            
            # If max consecutive losses reached, pause strategy
            if self.consecutive_losses >= self.max_consecutive_losses.value:
                # Calculate pause until bar
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                current_bar = len(dataframe)
                self.pause_until_bar = current_bar + self.pause_bars_after_losses.value
                
                # Log pause
                self.dp.send_msg(
                    f"⚠️ Mean Reversion Strategy PAUSED after {self.consecutive_losses} "
                    f"consecutive losses. Will resume after {self.pause_bars_after_losses.value} bars."
                )
                
                # Reset counter
                self.consecutive_losses = 0
        else:
            # Winning trade, reset counter
            self.consecutive_losses = 0
        
        return True
