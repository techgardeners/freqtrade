# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (IStrategy, IntParameter, DecimalParameter, CategoricalParameter)
from freqtrade.persistence import Trade

import talib.abstract as ta
import pandas_ta as pta

class SimplifiedICTStrategy(IStrategy):
    """
    Simplified ICT-Inspired Strategy
    Author: Antigravity
    Version: 1.0.0
    
    Simplified approach focusing on:
    - FVG (Fair Value Gaps)
    - Momentum shifts
    - Dynamic stop loss
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    minimal_roi = {
        "0": 0.229,
        "24": 0.106,
        "64": 0.04,
        "115": 0
    }
    
    stoploss = -0.24
    trailing_stop = False
    process_only_new_candles = True
    
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    startup_candle_count: int = 50
    
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }
    
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }
    
    # Hyperopt Parameters (Optimized)
    ema_fast = IntParameter(8, 20, default=16, space='buy', optimize=True)
    ema_slow = IntParameter(20, 50, default=26, space='buy', optimize=True)
    
    # FVG minimum size (as % of ATR)
    fvg_min_size = DecimalParameter(0.3, 1.0, default=0.725, space='buy', optimize=True)
    
    # Momentum threshold (ROC)
    momentum_threshold = DecimalParameter(0.5, 2.0, default=1.347, space='buy', optimize=True)
    
    # Risk Reward
    target_rr = DecimalParameter(2.0, 4.0, default=3.407, space='sell', optimize=True)
    
    # Risk per trade
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.014, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simplified indicators focusing on momentum and gaps
        """
        
        # Trend indicators
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast.value)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow.value)
        
        # Momentum
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=10)
        
        # Volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        
        # Fair Value Gaps (Simplified)
        # Bullish FVG: Low[i] > High[i-2] (gap up)
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        # FVG size
        dataframe['fvg_bull_size'] = dataframe['low'] - dataframe['high'].shift(2)
        dataframe['fvg_bear_size'] = dataframe['low'].shift(2) - dataframe['high']
        
        # FVG levels (for entry)
        dataframe['fvg_bull_top'] = dataframe['low']
        dataframe['fvg_bull_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bear_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bear_bottom'] = dataframe['high']
        
        # Swing highs/lows (simplified using rolling)
        swing_period = 5
        dataframe['swing_high'] = dataframe['high'].rolling(window=swing_period*2+1, center=False).max().shift(swing_period)
        dataframe['swing_low'] = dataframe['low'].rolling(window=swing_period*2+1, center=False).min().shift(swing_period)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Simplified entry logic:
        1. FVG formed
        2. Momentum in direction
        3. Price returns to FVG zone
        """
        
        # Long conditions
        # 1. Bullish FVG formed recently (within last 10 candles)
        # 2. EMA trend is bullish
        # 3. Strong momentum (ROC > threshold)
        # 4. Price dips into FVG zone
        
        # Check if FVG formed in last N candles
        lookback = 10
        dataframe['recent_fvg_bull'] = dataframe['fvg_bullish'].rolling(window=lookback).max()
        dataframe['recent_fvg_bear'] = dataframe['fvg_bearish'].rolling(window=lookback).max()
        
        # Get the most recent FVG levels
        # For simplicity, use the last FVG levels if any FVG occurred recently
        for i in range(lookback, len(dataframe)):
            # Long: Find most recent bullish FVG
            if dataframe['recent_fvg_bull'].iloc[i] > 0:
                # Look back for the actual FVG
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bullish'].iloc[j]:
                        dataframe.loc[i, 'active_fvg_bull_top'] = dataframe['fvg_bull_top'].iloc[j]
                        dataframe.loc[i, 'active_fvg_bull_bottom'] = dataframe['fvg_bull_bottom'].iloc[j]
                        break
            
            # Short: Find most recent bearish FVG
            if dataframe['recent_fvg_bear'].iloc[i] > 0:
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bearish'].iloc[j]:
                        dataframe.loc[i, 'active_fvg_bear_top'] = dataframe['fvg_bear_top'].iloc[j]
                        dataframe.loc[i, 'active_fvg_bear_bottom'] = dataframe['fvg_bear_bottom'].iloc[j]
                        break
        
        # Fill NaN with 0
        dataframe['active_fvg_bull_top'] = dataframe['active_fvg_bull_top'].fillna(0)
        dataframe['active_fvg_bull_bottom'] = dataframe['active_fvg_bull_bottom'].fillna(0)
        dataframe['active_fvg_bear_top'] = dataframe['active_fvg_bear_top'].fillna(0)
        dataframe['active_fvg_bear_bottom'] = dataframe['active_fvg_bear_bottom'].fillna(0)
        
        # Entry conditions
        # Long: Price dips into bullish FVG zone
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # Trend
                (dataframe['roc'] > self.momentum_threshold.value) &  # Momentum
                (dataframe['active_fvg_bull_top'] > 0) &  # Active FVG exists
                (dataframe['low'] <= dataframe['active_fvg_bull_top']) &  # Price touches FVG
                (dataframe['low'] >= dataframe['active_fvg_bull_bottom']) &  # Within FVG zone
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)  # Volume check
            ),
            'enter_long'] = 1
        
        # Short: Price rallies into bearish FVG zone
        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) &  # Trend
                (dataframe['roc'] < -self.momentum_threshold.value) &  # Momentum
                (dataframe['active_fvg_bear_bottom'] > 0) &  # Active FVG exists
                (dataframe['high'] >= dataframe['active_fvg_bear_bottom']) &  # Price touches FVG
                (dataframe['high'] <= dataframe['active_fvg_bear_top']) &  # Within FVG zone
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)  # Volume check
            ),
            'enter_short'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when trend reverses
        """
        # Exit long when EMA crosses down
        dataframe.loc[
            (dataframe['ema_fast'] < dataframe['ema_slow']),
            'exit_long'] = 1
        
        # Exit short when EMA crosses up
        dataframe.loc[
            (dataframe['ema_fast'] > dataframe['ema_slow']),
            'exit_short'] = 1
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Dynamic stoploss based on ATR
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        atr = last_candle['atr']
        
        if trade.is_short:
            # Short: SL above entry
            sl_price = trade.open_rate + (atr * 1.5)
            return (sl_price - current_rate) / current_rate
        else:
            # Long: SL below entry
            sl_price = trade.open_rate - (atr * 1.5)
            return (sl_price - current_rate) / current_rate

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        Take profit at target R:R
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        # Find entry candle ATR
        # Approximate with current ATR
        last_candle = dataframe.iloc[-1]
        atr = last_candle['atr']
        
        risk = atr * 1.5  # Same as SL distance
        
        if risk == 0:
            return None
        
        profit_amount = (current_rate - trade.open_rate) if not trade.is_short else (trade.open_rate - current_rate)
        r_multiple = profit_amount / risk
        
        if r_multiple >= self.target_rr.value:
            return "target_rr_reached"
        
        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        """
        Position sizing based on risk
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        atr = last_candle['atr']
        if atr == 0:
            return proposed_stake
        
        capital = self.wallets.get_total_stake_amount()
        risk_amount = capital * self.risk_per_trade.value
        
        # Stop distance = 1.5 * ATR
        stop_distance = atr * 1.5
        
        if stop_distance == 0:
            return proposed_stake
        
        # Size in coins
        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate
        
        # Apply limits
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake
        
        return size_stake
