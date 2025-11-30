# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (IStrategy, IntParameter, DecimalParameter, informative, merge_informative_pair)
from freqtrade.persistence import Trade

import talib.abstract as ta

class ICTMTFStrategy(IStrategy):
    """
    ICT Multi-TimeFrame Strategy
    Author: Antigravity
    Version: 1.0.0
    
    Multi-Timeframe approach:
    - HTF (15m): Bias detection (EMA trend) + FVG zones
    - LTF (5m): Precise entry on FVG retest
    
    Based on SimplifiedICT proven logic with MTF enhancement
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    minimal_roi = {
        "0": 0.123,
        "35": 0.074,
        "84": 0.022,
        "183": 0
    }
    
    stoploss = -0.327
    trailing_stop = False
    process_only_new_candles = True
    
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    startup_candle_count: int = 100
    
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
    # HTF parameters
    htf_ema_fast = IntParameter(8, 20, default=15, space='buy', optimize=True)
    htf_ema_slow = IntParameter(20, 50, default=40, space='buy', optimize=True)
    
    # LTF parameters
    ltf_momentum_threshold = DecimalParameter(0.5, 2.0, default=1.356, space='buy', optimize=True)
    fvg_lookback = IntParameter(5, 15, default=10, space='buy', optimize=True)
    
    # Exit parameters
    target_rr = DecimalParameter(2.0, 4.0, default=2.895, space='sell', optimize=True)
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.007, space='buy', optimize=True)

    @informative('15m')
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        HTF (15m) indicators for bias detection
        """
        # Trend indicators
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.htf_ema_fast.value)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.htf_ema_slow.value)
        
        # FVG Detection
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        # FVG zones
        dataframe['fvg_bull_top'] = dataframe['low']
        dataframe['fvg_bull_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bear_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bear_bottom'] = dataframe['high']
        
        # Trend direction
        dataframe['htf_bullish'] = dataframe['ema_fast'] > dataframe['ema_slow']
        dataframe['htf_bearish'] = dataframe['ema_fast'] < dataframe['ema_slow']
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        LTF (5m) indicators for entry execution
        """
        # Momentum
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=10)
        
        # Volatility
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        
        # FVG Detection (LTF)
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        dataframe['fvg_bull_top'] = dataframe['low']
        dataframe['fvg_bull_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bear_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bear_bottom'] = dataframe['high']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        MTF Entry logic:
        1. HTF bias (EMA trend)
        2. HTF FVG zone identified
        3. LTF entry when price returns to HTF FVG
        """
        
        # Check if FVG formed in last N candles (HTF)
        lookback = self.fvg_lookback.value
        dataframe['htf_recent_fvg_bull'] = dataframe['fvg_bullish_15m'].rolling(window=lookback).max()
        dataframe['htf_recent_fvg_bear'] = dataframe['fvg_bearish_15m'].rolling(window=lookback).max()
        
        # Track active HTF FVG zones
        dataframe['htf_active_fvg_bull_top'] = 0.0
        dataframe['htf_active_fvg_bull_bottom'] = 0.0
        dataframe['htf_active_fvg_bear_top'] = 0.0
        dataframe['htf_active_fvg_bear_bottom'] = 0.0
        
        # Find most recent HTF FVG
        for i in range(lookback, len(dataframe)):
            # Bullish HTF FVG
            if dataframe['htf_recent_fvg_bull'].iloc[i] > 0:
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bullish_15m'].iloc[j]:
                        dataframe.loc[i, 'htf_active_fvg_bull_top'] = dataframe['fvg_bull_top_15m'].iloc[j]
                        dataframe.loc[i, 'htf_active_fvg_bull_bottom'] = dataframe['fvg_bull_bottom_15m'].iloc[j]
                        break
            
            # Bearish HTF FVG
            if dataframe['htf_recent_fvg_bear'].iloc[i] > 0:
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bearish_15m'].iloc[j]:
                        dataframe.loc[i, 'htf_active_fvg_bear_top'] = dataframe['fvg_bear_top_15m'].iloc[j]
                        dataframe.loc[i, 'htf_active_fvg_bear_bottom'] = dataframe['fvg_bear_bottom_15m'].iloc[j]
                        break
            
            # Propagate forward
            if dataframe['htf_active_fvg_bull_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'htf_active_fvg_bull_top'] = dataframe['htf_active_fvg_bull_top'].iloc[i-1]
                dataframe.loc[i, 'htf_active_fvg_bull_bottom'] = dataframe['htf_active_fvg_bull_bottom'].iloc[i-1]
                
            if dataframe['htf_active_fvg_bear_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'htf_active_fvg_bear_top'] = dataframe['htf_active_fvg_bear_top'].iloc[i-1]
                dataframe.loc[i, 'htf_active_fvg_bear_bottom'] = dataframe['htf_active_fvg_bear_bottom'].iloc[i-1]
        
        # Entry conditions
        # LONG: HTF bullish + price dips into HTF bearish FVG (discount)
        dataframe.loc[
            (
                (dataframe['htf_bullish_15m']) &  # HTF bias
                (dataframe['roc'] > self.ltf_momentum_threshold.value) &  # LTF momentum
                (dataframe['htf_active_fvg_bear_top'] > 0) &  # HTF FVG exists
                (dataframe['low'] <= dataframe['htf_active_fvg_bear_top']) &  # Price in zone
                (dataframe['low'] >= dataframe['htf_active_fvg_bear_bottom']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)
            ),
            'enter_long'] = 1
        
        # SHORT: HTF bearish + price rallies into HTF bullish FVG (premium)
        dataframe.loc[
            (
                (dataframe['htf_bearish_15m']) &  # HTF bias
                (dataframe['roc'] < -self.ltf_momentum_threshold.value) &  # LTF momentum
                (dataframe['htf_active_fvg_bull_top'] > 0) &  # HTF FVG exists
                (dataframe['high'] >= dataframe['htf_active_fvg_bull_bottom']) &  # Price in zone
                (dataframe['high'] <= dataframe['htf_active_fvg_bull_top']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)
            ),
            'enter_short'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when HTF trend reverses
        """
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        
        # Exit long when HTF trend reverses
        dataframe.loc[
            (dataframe['htf_bearish_15m']),
            'exit_long'] = 1
        
        # Exit short when HTF trend reverses
        dataframe.loc[
            (dataframe['htf_bullish_15m']),
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
            sl_price = trade.open_rate + (atr * 1.5)
            return (sl_price - current_rate) / current_rate
        else:
            sl_price = trade.open_rate - (atr * 1.5)
            return (sl_price - current_rate) / current_rate

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        Take profit at target R:R
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        atr = last_candle['atr']
        
        risk = atr * 1.5
        
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
        
        stop_distance = atr * 1.5
        
        if stop_distance == 0:
            return proposed_stake
        
        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate
        
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake
        
        return size_stake
