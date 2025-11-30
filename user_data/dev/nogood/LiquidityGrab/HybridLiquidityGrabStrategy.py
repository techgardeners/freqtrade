# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (IStrategy, IntParameter, DecimalParameter)
from freqtrade.persistence import Trade

import talib.abstract as ta

class HybridLiquidityGrabStrategy(IStrategy):
    """
    Hybrid Liquidity Grab Strategy
    Author: Antigravity
    Version: 2.0.0
    
    Combines:
    - Liquidity Grab detection (from LiquidityGrabStrategy)
    - EMA trend filter (from SimplifiedICT)
    - ROC momentum filter (from SimplifiedICT)
    - FVG pattern recognition
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    minimal_roi = {
        "0": 0.226,
        "37": 0.061,
        "78": 0.018,
        "135": 0
    }
    
    stoploss = -0.314
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
    # Trend filters (from SimplifiedICT)
    ema_fast = IntParameter(8, 20, default=15, space='buy', optimize=True)
    ema_slow = IntParameter(20, 50, default=47, space='buy', optimize=True)
    momentum_threshold = DecimalParameter(0.5, 2.0, default=1.875, space='buy', optimize=True)
    
    # Liquidity Grab parameters
    swing_period = IntParameter(3, 10, default=9, space='buy', optimize=True)
    fvg_lookback = IntParameter(5, 15, default=13, space='buy', optimize=True)
    grab_tolerance = DecimalParameter(0.001, 0.01, default=0.005, space='buy', optimize=True)
    
    # Exit parameters
    target_rr = DecimalParameter(2.0, 4.0, default=2.265, space='sell', optimize=True)
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.005, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Hybrid indicators: trend + price action
        """
        
        # Trend indicators (from SimplifiedICT)
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast.value)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow.value)
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=10)
        
        # Volatility (for stop loss)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Volume
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        
        # Price action (from LiquidityGrab)
        period = self.swing_period.value
        dataframe['swing_high'] = dataframe['high'].rolling(window=period*2+1, center=False).max().shift(period)
        dataframe['swing_low'] = dataframe['low'].rolling(window=period*2+1, center=False).min().shift(period)
        
        # FVG Detection
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        dataframe['fvg_bull_top'] = dataframe['low']
        dataframe['fvg_bull_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bear_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bear_bottom'] = dataframe['high']
        
        # Candle characteristics
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']
        dataframe['is_bearish'] = dataframe['close'] < dataframe['open']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Hybrid entry logic:
        1. EMA trend filter (SimplifiedICT)
        2. ROC momentum filter (SimplifiedICT)
        3. Liquidity Grab detection
        4. FVG formation
        5. Price returns to FVG
        """
        
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        
        lookback = self.fvg_lookback.value
        tolerance = self.grab_tolerance.value
        
        # Track active FVG zones
        dataframe['active_fvg_bull_top'] = 0.0
        dataframe['active_fvg_bull_bottom'] = 0.0
        dataframe['active_fvg_bear_top'] = 0.0
        dataframe['active_fvg_bear_bottom'] = 0.0
        dataframe['grab_high'] = 0.0
        dataframe['grab_low'] = 0.0
        
        for i in range(lookback + 10, len(dataframe)):
            # LONG SETUP
            # Primary: Check trend (SimplifiedICT filter)
            if dataframe['ema_fast'].iloc[i] > dataframe['ema_slow'].iloc[i]:
                # Secondary: Check for FVG (relaxed - no grab required)
                # Look for bearish FVG in recent candles
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bearish'].iloc[j]:
                        # Optional: Check if there was a liquidity grab nearby
                        swing_high = dataframe['swing_high'].iloc[j]
                        grab_detected = False
                        
                        # Check for grab in window around FVG
                        for k in range(max(0, j-3), min(len(dataframe), j+3)):
                            if swing_high > 0:
                                if dataframe['high'].iloc[k] > swing_high * (1 + tolerance):
                                    if dataframe['close'].iloc[k] < swing_high:
                                        grab_detected = True
                                        dataframe.loc[i, 'grab_high'] = swing_high
                                        break
                        
                        # Accept FVG even without grab if momentum is strong
                        if grab_detected or dataframe['roc'].iloc[i] > self.momentum_threshold.value * 1.5:
                            dataframe.loc[i, 'active_fvg_bear_top'] = dataframe['fvg_bear_top'].iloc[j]
                            dataframe.loc[i, 'active_fvg_bear_bottom'] = dataframe['fvg_bear_bottom'].iloc[j]
                            if not grab_detected:
                                dataframe.loc[i, 'grab_high'] = dataframe['swing_high'].iloc[i-1]
                            break
            
            # SHORT SETUP
            # Primary: Check trend (SimplifiedICT filter)
            if dataframe['ema_fast'].iloc[i] < dataframe['ema_slow'].iloc[i]:
                # Secondary: Check for FVG (relaxed - no grab required)
                for j in range(i-1, max(0, i-lookback), -1):
                    if dataframe['fvg_bullish'].iloc[j]:
                        # Optional: Check if there was a liquidity grab nearby
                        swing_low = dataframe['swing_low'].iloc[j]
                        grab_detected = False
                        
                        for k in range(max(0, j-3), min(len(dataframe), j+3)):
                            if swing_low > 0:
                                if dataframe['low'].iloc[k] < swing_low * (1 - tolerance):
                                    if dataframe['close'].iloc[k] > swing_low:
                                        grab_detected = True
                                        dataframe.loc[i, 'grab_low'] = swing_low
                                        break
                        
                        # Accept FVG even without grab if momentum is strong
                        if grab_detected or dataframe['roc'].iloc[i] < -self.momentum_threshold.value * 1.5:
                            dataframe.loc[i, 'active_fvg_bull_top'] = dataframe['fvg_bull_top'].iloc[j]
                            dataframe.loc[i, 'active_fvg_bull_bottom'] = dataframe['fvg_bull_bottom'].iloc[j]
                            if not grab_detected:
                                dataframe.loc[i, 'grab_low'] = dataframe['swing_low'].iloc[i-1]
                            break
            
            # Propagate active FVG zones
            if dataframe['active_fvg_bear_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'active_fvg_bear_top'] = dataframe['active_fvg_bear_top'].iloc[i-1]
                dataframe.loc[i, 'active_fvg_bear_bottom'] = dataframe['active_fvg_bear_bottom'].iloc[i-1]
                dataframe.loc[i, 'grab_high'] = dataframe['grab_high'].iloc[i-1]
                
            if dataframe['active_fvg_bull_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'active_fvg_bull_top'] = dataframe['active_fvg_bull_top'].iloc[i-1]
                dataframe.loc[i, 'active_fvg_bull_bottom'] = dataframe['active_fvg_bull_bottom'].iloc[i-1]
                dataframe.loc[i, 'grab_low'] = dataframe['grab_low'].iloc[i-1]
        
        # Entry conditions
        # LONG: Price rallies into bearish FVG zone (in uptrend)
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &  # Trend filter
                (dataframe['active_fvg_bear_top'] > 0) &
                (dataframe['high'] >= dataframe['active_fvg_bear_bottom']) &
                (dataframe['high'] <= dataframe['active_fvg_bear_top']) &
                (dataframe['is_bullish']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)
            ),
            'enter_long'] = 1
        
        # SHORT: Price dips into bullish FVG zone (in downtrend)
        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) &  # Trend filter
                (dataframe['active_fvg_bull_top'] > 0) &
                (dataframe['low'] <= dataframe['active_fvg_bull_top']) &
                (dataframe['low'] >= dataframe['active_fvg_bull_bottom']) &
                (dataframe['is_bearish']) &
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8)
            ),
            'enter_short'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when trend reverses
        """
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        
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
        Dynamic stoploss based on ATR (from SimplifiedICT)
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
