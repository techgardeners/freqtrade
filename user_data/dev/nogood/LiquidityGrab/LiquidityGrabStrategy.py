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

class LiquidityGrabStrategy(IStrategy):
    """
    Liquidity Grab + Micro-Imbalance Reversal Strategy
    Author: Antigravity
    Version: 1.0.0
    
    Pure price action strategy:
    - NO traditional indicators (EMA, RSI, MACD, BB, ATR)
    - Based on market microstructure
    - Liquidity grabs + FVG + MSS
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    minimal_roi = {
        "0": 0.118,
        "26": 0.083,
        "62": 0.023,
        "176": 0
    }
    
    stoploss = -0.208
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
    swing_period = IntParameter(3, 10, default=4, space='buy', optimize=True)
    fvg_lookback = IntParameter(5, 15, default=15, space='buy', optimize=True)
    grab_tolerance = DecimalParameter(0.001, 0.01, default=0.007, space='buy', optimize=True)
    target_rr = DecimalParameter(1.5, 4.0, default=3.56, space='sell', optimize=True)
    risk_per_trade = DecimalParameter(0.005, 0.015, default=0.006, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Pure price action - minimal indicators
        """
        
        # Swing highs/lows detection
        period = self.swing_period.value
        dataframe['swing_high'] = dataframe['high'].rolling(window=period*2+1, center=False).max().shift(period)
        dataframe['swing_low'] = dataframe['low'].rolling(window=period*2+1, center=False).min().shift(period)
        
        # FVG Detection (vectorized)
        # Bullish FVG: Low[i] > High[i-2]
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        # FVG zones
        dataframe['fvg_bull_top'] = dataframe['low']
        dataframe['fvg_bull_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bear_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bear_bottom'] = dataframe['high']
        
        # Candle characteristics for reversal detection
        dataframe['body_size'] = abs(dataframe['close'] - dataframe['open'])
        dataframe['range_size'] = dataframe['high'] - dataframe['low']
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']
        dataframe['is_bearish'] = dataframe['close'] < dataframe['open']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic:
        1. Liquidity Grab (break swing then reverse)
        2. FVG formation
        3. Price returns to FVG
        """
        
        # Initialize
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
            # 1. Check for liquidity grab (break swing high then close below)
            swing_high = dataframe['swing_high'].iloc[i-1]
            
            if swing_high > 0:
                # Did we break above swing high?
                if dataframe['high'].iloc[i-1] > swing_high * (1 + tolerance):
                    # Did we close back below? (Rejection)
                    if dataframe['close'].iloc[i-1] < swing_high:
                        # Liquidity grab detected!
                        # Now look for bearish FVG in recent candles
                        for j in range(i-1, max(0, i-lookback), -1):
                            if dataframe['fvg_bearish'].iloc[j]:
                                # Found FVG after grab
                                dataframe.loc[i, 'active_fvg_bear_top'] = dataframe['fvg_bear_top'].iloc[j]
                                dataframe.loc[i, 'active_fvg_bear_bottom'] = dataframe['fvg_bear_bottom'].iloc[j]
                                dataframe.loc[i, 'grab_high'] = swing_high
                                break
            
            # SHORT SETUP
            # 1. Check for liquidity grab (break swing low then close above)
            swing_low = dataframe['swing_low'].iloc[i-1]
            
            if swing_low > 0:
                # Did we break below swing low?
                if dataframe['low'].iloc[i-1] < swing_low * (1 - tolerance):
                    # Did we close back above? (Rejection)
                    if dataframe['close'].iloc[i-1] > swing_low:
                        # Liquidity grab detected!
                        # Now look for bullish FVG in recent candles
                        for j in range(i-1, max(0, i-lookback), -1):
                            if dataframe['fvg_bullish'].iloc[j]:
                                # Found FVG after grab
                                dataframe.loc[i, 'active_fvg_bull_top'] = dataframe['fvg_bull_top'].iloc[j]
                                dataframe.loc[i, 'active_fvg_bull_bottom'] = dataframe['fvg_bull_bottom'].iloc[j]
                                dataframe.loc[i, 'grab_low'] = swing_low
                                break
            
            # Propagate active FVG zones forward
            if dataframe['active_fvg_bear_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'active_fvg_bear_top'] = dataframe['active_fvg_bear_top'].iloc[i-1]
                dataframe.loc[i, 'active_fvg_bear_bottom'] = dataframe['active_fvg_bear_bottom'].iloc[i-1]
                dataframe.loc[i, 'grab_high'] = dataframe['grab_high'].iloc[i-1]
                
            if dataframe['active_fvg_bull_top'].iloc[i] == 0 and i > 0:
                dataframe.loc[i, 'active_fvg_bull_top'] = dataframe['active_fvg_bull_top'].iloc[i-1]
                dataframe.loc[i, 'active_fvg_bull_bottom'] = dataframe['active_fvg_bull_bottom'].iloc[i-1]
                dataframe.loc[i, 'grab_low'] = dataframe['grab_low'].iloc[i-1]
        
        # Entry conditions
        # LONG: Price rallies into bearish FVG zone (after grab high)
        dataframe.loc[
            (
                (dataframe['active_fvg_bear_top'] > 0) &
                (dataframe['grab_high'] > 0) &
                (dataframe['high'] >= dataframe['active_fvg_bear_bottom']) &
                (dataframe['high'] <= dataframe['active_fvg_bear_top']) &
                (dataframe['is_bullish'])  # Bullish candle entering FVG
            ),
            'enter_long'] = 1
        
        # SHORT: Price dips into bullish FVG zone (after grab low)
        dataframe.loc[
            (
                (dataframe['active_fvg_bull_top'] > 0) &
                (dataframe['grab_low'] > 0) &
                (dataframe['low'] <= dataframe['active_fvg_bull_top']) &
                (dataframe['low'] >= dataframe['active_fvg_bull_bottom']) &
                (dataframe['is_bearish'])  # Bearish candle entering FVG
            ),
            'enter_short'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit when structure breaks
        """
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        
        # Exit long if price breaks below recent swing low
        dataframe.loc[
            (dataframe['close'] < dataframe['swing_low']),
            'exit_long'] = 1
        
        # Exit short if price breaks above recent swing high
        dataframe.loc[
            (dataframe['close'] > dataframe['swing_high']),
            'exit_short'] = 1
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Stop loss at liquidity grab level
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        # Find entry candle
        entry_candle = dataframe[dataframe['date'] == trade.open_date_utc]
        
        if entry_candle.empty:
            return self.stoploss
        
        if trade.is_short:
            # Short: SL above grab low
            grab_level = entry_candle['grab_low'].values[0]
            if grab_level > 0:
                sl_price = grab_level * 1.01  # Slightly above
                return (sl_price - current_rate) / current_rate
        else:
            # Long: SL below grab high
            grab_level = entry_candle['grab_high'].values[0]
            if grab_level > 0:
                sl_price = grab_level * 0.99  # Slightly below
                return (sl_price - current_rate) / current_rate
        
        return self.stoploss

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        Take profit at target R:R
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        # Find entry candle
        entry_candle = dataframe[dataframe['date'] == trade.open_date_utc]
        
        if entry_candle.empty:
            return None
        
        # Calculate risk
        if trade.is_short:
            grab_level = entry_candle['grab_low'].values[0]
            if grab_level > 0:
                risk = abs(trade.open_rate - grab_level * 1.01)
            else:
                return None
        else:
            grab_level = entry_candle['grab_high'].values[0]
            if grab_level > 0:
                risk = abs(trade.open_rate - grab_level * 0.99)
            else:
                return None
        
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
        
        # Get grab level for stop calculation
        if side == 'long':
            grab_level = last_candle['grab_high']
            if grab_level == 0:
                return proposed_stake
            stop_distance = abs(current_rate - grab_level * 0.99)
        else:
            grab_level = last_candle['grab_low']
            if grab_level == 0:
                return proposed_stake
            stop_distance = abs(current_rate - grab_level * 1.01)
        
        if stop_distance == 0:
            return proposed_stake
        
        capital = self.wallets.get_total_stake_amount()
        risk_amount = capital * self.risk_per_trade.value
        
        # Size in coins
        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate
        
        # Apply limits
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake
        
        return size_stake
