"""
TrendFollowingStrategyV1 - Trend Following Strategy with Multi-Timeframe Analysis

This strategy captures prolonged directional movements (bull or bear) in crypto markets
using EMA crossovers, ADX trend strength, and ATR-based volatility management.

Key Features:
- Multi-timeframe analysis (1h main, 4h confirmation, 15m entry)
- Dynamic stop loss based on ATR
- Partial position closing (50% at TP1, 50% at TP2)
- Volume and candlestick pattern filters
- Comprehensive fail-safe mechanisms

Author: Freqtrade Strategy Development
Version: 1.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from functools import reduce
import numpy as np
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
    merge_informative_pair
)
from freqtrade.persistence import Trade


STRATEGY_VERSION = "1.0.0"


class TrendFollowingStrategyV1(IStrategy):
    """
    Trend-Following Strategy with Multi-Timeframe Analysis
    
    Strategy Logic:
    - Identifies trending markets using EMA50/EMA200 alignment and ADX
    - Enters on pullbacks to EMA50 with breakout confirmation
    - Uses ATR-based dynamic stops and partial position management
    - Implements comprehensive filters for trend, volatility, volume, and candlestick patterns
    """

    # Strategy Metadata
    INTERFACE_VERSION = 3
    can_short = True
    
    # Timeframe Configuration
    timeframe = '1h'
    
    # Startup candle count (need enough for EMA200 + ATR calculations)
    startup_candle_count: int = 250
    
    # ROI table (will be overridden by custom exit logic)
    minimal_roi = {
        "0": 0.10  # 10% as fallback
    }
    
    # Stoploss (will be overridden by custom_stoploss)
    stoploss = -0.10  # -10% as hard stop
    
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
    
    # EMA Parameters
    ema_fast_period = IntParameter(20, 100, default=50, space='buy', optimize=True)
    ema_slow_period = IntParameter(100, 250, default=200, space='buy', optimize=True)
    
    # ADX Parameters
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    adx_threshold = IntParameter(18, 30, default=20, space='buy', optimize=True)
    adx_exit_threshold = IntParameter(12, 20, default=15, space='sell', optimize=True)
    
    # ATR Parameters
    atr_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    atr_stop_multiplier = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space='sell', optimize=True)
    
    # Volume Parameters
    volume_ma_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    volume_threshold = DecimalParameter(1.0, 1.5, default=1.2, decimals=1, space='buy', optimize=True)
    
    # Pullback Parameters
    pullback_atr_multiplier = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space='buy', optimize=True)
    
    # EMA Distance Filter
    ema_distance_threshold = DecimalParameter(0.001, 0.01, default=0.005, decimals=3, space='buy', optimize=True)
    
    # Take Profit Parameters
    tp1_risk_reward = DecimalParameter(0.8, 1.5, default=1.0, decimals=1, space='sell', optimize=True)
    tp2_risk_reward = DecimalParameter(1.5, 3.5, default=2.0, decimals=1, space='sell', optimize=True)
    tp1_close_percentage = DecimalParameter(0.3, 0.7, default=0.5, decimals=1, space='sell', optimize=True)
    
    # Trailing Stop Parameters
    use_trailing_stop = CategoricalParameter([True, False], default=False, space='sell', optimize=True)
    trailing_atr_multiplier = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space='sell', optimize=True)
    
    # Candlestick Filter Parameters
    min_candle_body_ratio = DecimalParameter(0.2, 0.5, default=0.3, decimals=1, space='buy', optimize=True)
    max_shadow_ratio = DecimalParameter(0.5, 0.8, default=0.6, decimals=1, space='buy', optimize=True)
    
    # Volatility Filter Parameters
    min_atr_ratio = DecimalParameter(0.6, 1.0, default=0.8, decimals=1, space='buy', optimize=True)
    max_atr_spike = DecimalParameter(2.0, 3.0, default=2.5, decimals=1, space='buy', optimize=True)
    
    # Time-Based Exit
    max_trade_duration_hours = IntParameter(24, 96, default=48, space='sell', optimize=True)
    
    # Risk Management
    risk_per_trade = DecimalParameter(0.005, 0.02, default=0.01, decimals=3, space='buy', optimize=False)
    max_position_size_ratio = DecimalParameter(0.1, 0.3, default=0.2, decimals=1, space='buy', optimize=False)
    
    # ============================================================================
    # INFORMATIVE PAIRS (Multi-Timeframe)
    # ============================================================================
    
    def informative_pairs(self):
        """Define additional timeframes for multi-timeframe analysis"""
        pairs = self.dp.current_whitelist()
        informative_pairs = []
        
        for pair in pairs:
            informative_pairs.append((pair, '4h'))
        
        return informative_pairs
    
    # ============================================================================
    # INDICATOR POPULATION
    # ============================================================================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate all technical indicators for the main timeframe (1h)"""
        
        # EMA Indicators
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast_period.value)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow_period.value)
        
        # EMA Slope (trend direction)
        dataframe['ema_fast_slope'] = (
            (dataframe['ema_fast'] - dataframe['ema_fast'].shift(1)) / 
            (dataframe['ema_fast'].shift(1) + 1e-10)
        )
        
        # EMA Distance (to detect congestion)
        dataframe['ema_distance'] = (
            abs(dataframe['ema_fast'] - dataframe['ema_slow']) / 
            (dataframe['ema_slow'] + 1e-10)
        )
        
        # ADX (Trend Strength)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # ATR (Volatility)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        dataframe['atr_ma'] = ta.SMA(dataframe['atr'], timeperiod=20)
        
        # Volume
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period.value)
        
        # Candlestick Metrics
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
        
        # Distance from price to EMA50
        dataframe['distance_to_ema_fast'] = (
            (dataframe['close'] - dataframe['ema_fast']) / 
            (dataframe['ema_fast'] + 1e-10)
        )
        
        # Multi-Timeframe Indicators
        dataframe = self.populate_informative_indicators(dataframe, metadata)
        
        return dataframe
    
    def populate_informative_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Populate indicators from higher timeframes (4h for trend confirmation)"""
        
        # Get 4h data for trend confirmation
        informative_4h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='4h')
        
        # Calculate 4h EMAs (use simple names, merge will add _4h suffix)
        informative_4h['ema_fast'] = ta.EMA(informative_4h, timeperiod=self.ema_fast_period.value)
        informative_4h['ema_slow'] = ta.EMA(informative_4h, timeperiod=self.ema_slow_period.value)
        informative_4h['adx'] = ta.ADX(informative_4h, timeperiod=self.adx_period.value)
        
        # Merge 4h data into 1h dataframe
        dataframe = merge_informative_pair(dataframe, informative_4h, self.timeframe, '4h', ffill=True)
        
        return dataframe
    
    # ============================================================================
    # ENTRY SIGNAL LOGIC
    # ============================================================================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate entry signals for LONG and SHORT positions"""
        
        # LONG Entry Conditions
        long_conditions = []
        
        # 1. Trend Filters (1h and 4h alignment)
        long_trend = (
            (dataframe['ema_fast'] > dataframe['ema_slow']) &
            (dataframe['ema_fast_4h'] > dataframe['ema_slow_4h']) &
            (dataframe['close'] > dataframe['ema_fast']) &
            (dataframe['adx'] > self.adx_threshold.value) &
            (dataframe['adx_4h'] > self.adx_threshold.value) &
            (dataframe['ema_distance'] > self.ema_distance_threshold.value) &
            (dataframe['ema_fast_slope'] > 0)
        )
        long_conditions.append(long_trend)
        
        # 2. Pullback Conditions
        long_pullback = (
            (dataframe['distance_to_ema_fast'] >= -self.pullback_atr_multiplier.value * dataframe['atr'] / (dataframe['close'] + 1e-10)) &
            (dataframe['distance_to_ema_fast'] <= self.pullback_atr_multiplier.value * dataframe['atr'] / (dataframe['close'] + 1e-10)) &
            (dataframe['low'] > dataframe['ema_slow'])
        )
        long_conditions.append(long_pullback)
        
        # 3. Breakout Confirmation
        long_breakout = (
            (dataframe['close'] > dataframe['open']) &
            (dataframe['close'] > dataframe['high'].shift(1))
        )
        long_conditions.append(long_breakout)
        
        # 4. Volume Filter
        long_volume = (
            dataframe['volume'] > (self.volume_threshold.value * dataframe['volume_ma'])
        )
        long_conditions.append(long_volume)
        
        # 5. Candlestick Pattern Filters
        long_candle = (
            (dataframe['candle_body_ratio'] > self.min_candle_body_ratio.value) &
            (dataframe['shadow_ratio'] < self.max_shadow_ratio.value)
        )
        long_conditions.append(long_candle)
        
        # 6. Volatility Filters
        long_volatility = (
            (dataframe['atr'] > self.min_atr_ratio.value * dataframe['atr_ma']) &
            (dataframe['candle_range'] < self.max_atr_spike.value * dataframe['atr'])
        )
        long_conditions.append(long_volatility)
        
        # Combine all LONG conditions
        if long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, long_conditions),
                'enter_long'] = 1
        
        # SHORT Entry Conditions
        short_conditions = []
        
        # 1. Trend Filters (1h and 4h alignment)
        short_trend = (
            (dataframe['ema_fast'] < dataframe['ema_slow']) &
            (dataframe['ema_fast_4h'] < dataframe['ema_slow_4h']) &
            (dataframe['close'] < dataframe['ema_fast']) &
            (dataframe['adx'] > self.adx_threshold.value) &
            (dataframe['adx_4h'] > self.adx_threshold.value) &
            (dataframe['ema_distance'] > self.ema_distance_threshold.value) &
            (dataframe['ema_fast_slope'] < 0)
        )
        short_conditions.append(short_trend)
        
        # 2. Pullback Conditions
        short_pullback = (
            (dataframe['distance_to_ema_fast'] >= -self.pullback_atr_multiplier.value * dataframe['atr'] / (dataframe['close'] + 1e-10)) &
            (dataframe['distance_to_ema_fast'] <= self.pullback_atr_multiplier.value * dataframe['atr'] / (dataframe['close'] + 1e-10)) &
            (dataframe['high'] < dataframe['ema_slow'])
        )
        short_conditions.append(short_pullback)
        
        # 3. Breakout Confirmation
        short_breakout = (
            (dataframe['close'] < dataframe['open']) &
            (dataframe['close'] < dataframe['low'].shift(1))
        )
        short_conditions.append(short_breakout)
        
        # 4. Volume Filter
        short_volume = (
            dataframe['volume'] > (self.volume_threshold.value * dataframe['volume_ma'])
        )
        short_conditions.append(short_volume)
        
        # 5. Candlestick Pattern Filters
        short_candle = (
            (dataframe['candle_body_ratio'] > self.min_candle_body_ratio.value) &
            (dataframe['shadow_ratio'] < self.max_shadow_ratio.value)
        )
        short_conditions.append(short_candle)
        
        # 6. Volatility Filters
        short_volatility = (
            (dataframe['atr'] > self.min_atr_ratio.value * dataframe['atr_ma']) &
            (dataframe['candle_range'] < self.max_atr_spike.value * dataframe['atr'])
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
        """Generate exit signals based on trend reversal and fail-safes"""
        
        # LONG Exit Conditions
        long_exit_conditions = []
        
        # 1. Trend Reversal (EMA crossover)
        long_exit_trend = (
            (dataframe['ema_fast'] < dataframe['ema_slow']) |
            (dataframe['close'] < dataframe['ema_slow'])
        )
        long_exit_conditions.append(long_exit_trend)
        
        # 2. ADX Collapse (trend weakness)
        long_exit_adx = (
            dataframe['adx'] < self.adx_exit_threshold.value
        )
        long_exit_conditions.append(long_exit_adx)
        
        # Combine LONG exit conditions (OR logic)
        if long_exit_conditions:
            dataframe.loc[
                reduce(lambda x, y: x | y, long_exit_conditions),
                'exit_long'] = 1
        
        # SHORT Exit Conditions
        short_exit_conditions = []
        
        # 1. Trend Reversal
        short_exit_trend = (
            (dataframe['ema_fast'] > dataframe['ema_slow']) |
            (dataframe['close'] > dataframe['ema_slow'])
        )
        short_exit_conditions.append(short_exit_trend)
        
        # 2. ADX Collapse
        short_exit_adx = (
            dataframe['adx'] < self.adx_exit_threshold.value
        )
        short_exit_conditions.append(short_exit_adx)
        
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
        Dynamic stop loss based on ATR and profit level
        
        Returns:
            float: Stop loss percentage (negative value)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        atr = last_candle['atr']
        
        # Calculate initial stop distance
        if trade.is_short:
            stop_distance = self.atr_stop_multiplier.value * atr
            stop_price = trade.open_rate + stop_distance
            stop_loss_pct = (stop_price - current_rate) / current_rate
        else:
            stop_distance = self.atr_stop_multiplier.value * atr
            stop_price = trade.open_rate - stop_distance
            stop_loss_pct = (current_rate - stop_price) / current_rate
        
        # Move to break-even after TP1 is hit
        if current_profit >= self.tp1_risk_reward.value * abs(self.stoploss):
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
        Manage partial position closes at TP1 and TP2
        
        Returns:
            Optional[float]: Stake amount to reduce (negative value) or None
        """
        
        # Get trade metadata
        if not hasattr(trade, 'tp1_hit'):
            trade.tp1_hit = False
        if not hasattr(trade, 'tp2_hit'):
            trade.tp2_hit = False
        
        # Calculate risk (initial stop distance)
        initial_stop_distance = abs(self.stoploss)
        
        # TP1: Close partial position at 1R
        if not trade.tp1_hit and current_profit >= self.tp1_risk_reward.value * initial_stop_distance:
            trade.tp1_hit = True
            # Close percentage defined by tp1_close_percentage
            close_amount = trade.stake_amount * self.tp1_close_percentage.value
            return -close_amount
        
        # TP2: Close remaining position at 2R (if not using trailing)
        if not self.use_trailing_stop.value and trade.tp1_hit and not trade.tp2_hit:
            if current_profit >= self.tp2_risk_reward.value * initial_stop_distance:
                trade.tp2_hit = True
                # Close remaining position
                return -trade.stake_amount  # Close all remaining
        
        return None
    
    # ============================================================================
    # CUSTOM EXIT
    # ============================================================================
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                   current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """
        Custom exit logic for time-based exits and other fail-safes
        
        Returns:
            Optional[str]: Exit reason or None
        """
        
        # Time-based exit
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600  # hours
        if trade_duration > self.max_trade_duration_hours.value:
            return 'time_based_exit'
        
        # Volatility spike exit
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if last_candle['atr'] > self.max_atr_spike.value * last_candle['atr_ma']:
            return 'volatility_spike'
        
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
        # risk_amount = wallet_balance * risk_per_trade
        # position_size = risk_amount / stop_distance_pct
        risk_amount = wallet_balance * self.risk_per_trade.value
        position_size = risk_amount / stop_distance_pct
        
        # Apply maximum position size limit
        max_position = wallet_balance * self.max_position_size_ratio.value
        position_size = min(position_size, max_position)
        
        # Ensure within min/max stake bounds
        if min_stake is not None:
            position_size = max(position_size, min_stake)
        position_size = min(position_size, max_stake)
        
        return position_size
