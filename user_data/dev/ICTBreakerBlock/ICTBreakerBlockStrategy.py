"""
ICT Breaker Block Reversal Strategy

This strategy implements ICT (Inner Circle Trader) concepts focusing on Breaker Blocks:
violated Order Blocks that signal powerful reversals in crypto markets.

Core ICT Concepts:
- Order Block (OB): Strong candle with wicks indicating institutional orders
- Breaker Block: An OB that has been violated (liquidity grab) and becomes reversal zone
- Fair Value Gap (FVG): Price inefficiency (gap between candles)
- Break of Structure (BOS): Price breaking previous swing highs/lows
- Displacement: Strong directional move after liquidity grab

Entry Logic (LONG):
1. Detect bearish Order Block
2. Price breaks above OB (liquidity grab)
3. Displacement upward with FVG
4. Bullish BOS confirmed
5. Price returns to violated OB (now Breaker Block)
6. Enter long in upper part of breaker block

Entry Logic (SHORT):
1. Detect bullish Order Block
2. Price breaks below OB (liquidity grab)
3. Displacement downward with FVG
4. Bearish BOS confirmed
5. Price returns to violated OB (now Breaker Block)
6. Enter short in lower part of breaker block

Author: AI Assistant
Version: 1.0.0
"""

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class ICTBreakerBlockStrategy(IStrategy):
    """
    ICT Breaker Block Reversal Strategy
    
    Captures powerful reversals by identifying violated Order Blocks
    that become Breaker Blocks after liquidity grabs.
    """
    
    STRATEGY_VERSION = "1.0.0"
    
    # Strategy settings
    timeframe = '5m'
    can_short = True
    
    # ROI table - Optimized for better profit capture
    minimal_roi = {
        "0": 0.05,   # 5% TP1
        "30": 0.03,  # 3% TP2 after 30 min
        "60": 0.02   # 2% TP3 after 1 hour
    }
    
    # Stoploss
    stoploss = -0.02  # 2% - will be managed by custom_stoploss
    
    # Trailing stop
    trailing_stop = False
    
    # Protections
    protections = [
        {
            "method": "CooldownPeriod",
            "stop_duration_candles": 3
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 24,
            "trade_limit": 2,
            "stop_duration_candles": 12,
            "max_allowed_drawdown": 0.15
        }
    ]
    
    # Hyperopt parameters
    
    # Order Block detection
    ob_lookback = IntParameter(10, 30, default=20, space='buy', optimize=True)
    ob_wick_ratio = DecimalParameter(0.3, 0.7, default=0.5, space='buy', optimize=True)
    
    # Breaker Block confirmation
    bb_confirmation_candles = IntParameter(1, 5, default=2, space='buy', optimize=True)
    bb_return_threshold = DecimalParameter(0.2, 0.8, default=0.4, space='buy', optimize=True)
    
    # Fair Value Gap (FVG)
    fvg_min_gap = DecimalParameter(0.0005, 0.005, default=0.001, space='buy', optimize=True)
    fvg_required = IntParameter(0, 1, default=0, space='buy', optimize=True)  # 0=optional, 1=required
    
    # Break of Structure (BOS)
    bos_lookback = IntParameter(3, 15, default=7, space='buy', optimize=True)
    bos_threshold = DecimalParameter(0.0005, 0.003, default=0.001, space='buy', optimize=True)
    
    # Displacement
    displacement_strength = DecimalParameter(0.005, 0.03, default=0.01, space='buy', optimize=True)
    displacement_candles = IntParameter(2, 5, default=2, space='buy', optimize=True)
    
    # Trend Filter
    use_trend_filter = IntParameter(0, 1, default=1, space='buy', optimize=True)  # 0=off, 1=on
    
    # Momentum Filter
    use_rsi_filter = IntParameter(0, 1, default=1, space='buy', optimize=True)  # 0=off, 1=on
    rsi_min = IntParameter(25, 45, default=30, space='buy', optimize=True)
    rsi_max = IntParameter(55, 75, default=70, space='buy', optimize=True)
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all ICT indicators
        """
        
        # Basic price action
        dataframe['hl2'] = (dataframe['high'] + dataframe['low']) / 2
        dataframe['body'] = abs(dataframe['close'] - dataframe['open'])
        dataframe['range'] = dataframe['high'] - dataframe['low']
        
        # Calculate upper and lower wicks
        dataframe['upper_wick'] = np.where(
            dataframe['close'] > dataframe['open'],
            dataframe['high'] - dataframe['close'],
            dataframe['high'] - dataframe['open']
        )
        dataframe['lower_wick'] = np.where(
            dataframe['close'] > dataframe['open'],
            dataframe['open'] - dataframe['low'],
            dataframe['close'] - dataframe['low']
        )
        
        # Volume confirmation - calculate BEFORE Order Block detection
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # ATR for dynamic stops
        dataframe['atr_14'] = ta.ATR(dataframe, timeperiod=14)
        
        # Trend Filter: EMA 50/200
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['trend_up'] = dataframe['ema_50'] > dataframe['ema_200']
        dataframe['trend_down'] = dataframe['ema_50'] < dataframe['ema_200']
        
        # Momentum Filter: RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Order Block Detection
        dataframe = self._detect_order_blocks(dataframe)
        
        # Fair Value Gap Detection
        dataframe = self._detect_fvg(dataframe)
        
        # Break of Structure Detection
        dataframe = self._detect_bos(dataframe)
        
        # Displacement Detection
        dataframe = self._detect_displacement(dataframe)
        
        # Breaker Block Detection
        dataframe = self._detect_breaker_blocks(dataframe)
        
        return dataframe
    
    def _detect_order_blocks(self, dataframe: DataFrame) -> DataFrame:
        """
        Detect bullish and bearish Order Blocks
        
        OB characteristics:
        - Strong body (bullish or bearish)
        - Significant wick on one side
        - Represents institutional order zone
        """
        lookback = self.ob_lookback.value
        wick_ratio = self.ob_wick_ratio.value
        
        # Bullish Order Block: strong bullish candle with lower wick
        dataframe['is_bullish_ob'] = (
            (dataframe['close'] > dataframe['open']) &  # Bullish candle
            (dataframe['body'] > dataframe['range'] * 0.5) &  # Strong body
            (dataframe['lower_wick'] > dataframe['body'] * wick_ratio) &  # Significant lower wick
            (dataframe['volume_ratio'] > 1.2)  # Above average volume
        )
        
        # Bearish Order Block: strong bearish candle with upper wick
        dataframe['is_bearish_ob'] = (
            (dataframe['close'] < dataframe['open']) &  # Bearish candle
            (dataframe['body'] > dataframe['range'] * 0.5) &  # Strong body
            (dataframe['upper_wick'] > dataframe['body'] * wick_ratio) &  # Significant upper wick
            (dataframe['volume_ratio'] > 1.2)  # Above average volume
        )
        
        # Store OB levels
        dataframe['bullish_ob_low'] = np.where(dataframe['is_bullish_ob'], dataframe['low'], np.nan)
        dataframe['bullish_ob_high'] = np.where(dataframe['is_bullish_ob'], dataframe['high'], np.nan)
        dataframe['bearish_ob_low'] = np.where(dataframe['is_bearish_ob'], dataframe['low'], np.nan)
        dataframe['bearish_ob_high'] = np.where(dataframe['is_bearish_ob'], dataframe['high'], np.nan)
        
        # Forward fill OB levels for lookback period
        dataframe['bullish_ob_low'] = dataframe['bullish_ob_low'].fillna(method='ffill', limit=lookback)
        dataframe['bullish_ob_high'] = dataframe['bullish_ob_high'].fillna(method='ffill', limit=lookback)
        dataframe['bearish_ob_low'] = dataframe['bearish_ob_low'].fillna(method='ffill', limit=lookback)
        dataframe['bearish_ob_high'] = dataframe['bearish_ob_high'].fillna(method='ffill', limit=lookback)
        
        return dataframe
    
    def _detect_fvg(self, dataframe: DataFrame) -> DataFrame:
        """
        Detect Fair Value Gaps (FVG)
        
        FVG = price inefficiency where there's a gap between candles
        Bullish FVG: gap between candle[i-2].high and candle[i].low
        Bearish FVG: gap between candle[i-2].low and candle[i].high
        """
        min_gap = self.fvg_min_gap.value
        
        # Bullish FVG: current low > 2 candles ago high
        dataframe['bullish_fvg'] = (
            (dataframe['low'] - dataframe['high'].shift(2)) / dataframe['close'] > min_gap
        )
        
        # Bearish FVG: current high < 2 candles ago low
        dataframe['bearish_fvg'] = (
            (dataframe['low'].shift(2) - dataframe['high']) / dataframe['close'] > min_gap
        )
        
        # Store FVG levels
        dataframe['bullish_fvg_low'] = np.where(
            dataframe['bullish_fvg'],
            dataframe['high'].shift(2),
            np.nan
        )
        dataframe['bullish_fvg_high'] = np.where(
            dataframe['bullish_fvg'],
            dataframe['low'],
            np.nan
        )
        
        dataframe['bearish_fvg_low'] = np.where(
            dataframe['bearish_fvg'],
            dataframe['high'],
            np.nan
        )
        dataframe['bearish_fvg_high'] = np.where(
            dataframe['bearish_fvg'],
            dataframe['low'].shift(2),
            np.nan
        )
        
        return dataframe
    
    def _detect_bos(self, dataframe: DataFrame) -> DataFrame:
        """
        Detect Break of Structure (BOS)
        
        Bullish BOS: price breaks above recent swing high
        Bearish BOS: price breaks below recent swing low
        """
        lookback = self.bos_lookback.value
        threshold = self.bos_threshold.value
        
        # Calculate swing highs and lows
        dataframe['swing_high'] = dataframe['high'].rolling(window=lookback).max()
        dataframe['swing_low'] = dataframe['low'].rolling(window=lookback).min()
        
        # Bullish BOS: close breaks above previous swing high
        dataframe['bullish_bos'] = (
            (dataframe['close'] > dataframe['swing_high'].shift(1)) &
            ((dataframe['close'] - dataframe['swing_high'].shift(1)) / dataframe['close'] > threshold)
        )
        
        # Bearish BOS: close breaks below previous swing low
        dataframe['bearish_bos'] = (
            (dataframe['close'] < dataframe['swing_low'].shift(1)) &
            ((dataframe['swing_low'].shift(1) - dataframe['close']) / dataframe['close'] > threshold)
        )
        
        return dataframe
    
    def _detect_displacement(self, dataframe: DataFrame) -> DataFrame:
        """
        Detect Displacement: strong directional move
        
        Displacement characteristics:
        - Multiple consecutive candles in same direction
        - Strong momentum
        - Often accompanied by FVG
        """
        strength = self.displacement_strength.value
        candles = self.displacement_candles.value
        
        # Calculate price change over displacement period
        dataframe['price_change'] = (
            (dataframe['close'] - dataframe['close'].shift(candles)) / dataframe['close'].shift(candles)
        )
        
        # Bullish displacement: strong upward move
        dataframe['bullish_displacement'] = (
            (dataframe['price_change'] > strength) &
            (dataframe['close'] > dataframe['open']) &  # Current candle bullish
            (dataframe['close'].shift(1) > dataframe['open'].shift(1))  # Previous candle bullish
        )
        
        # Bearish displacement: strong downward move
        dataframe['bearish_displacement'] = (
            (dataframe['price_change'] < -strength) &
            (dataframe['close'] < dataframe['open']) &  # Current candle bearish
            (dataframe['close'].shift(1) < dataframe['open'].shift(1))  # Previous candle bearish
        )
        
        return dataframe
    
    def _detect_breaker_blocks(self, dataframe: DataFrame) -> DataFrame:
        """
        Detect Breaker Blocks: violated Order Blocks that become reversal zones
        
        Bullish Breaker Block (for LONG):
        1. Bearish OB exists
        2. Price breaks above OB (liquidity grab)
        3. Bullish displacement with FVG
        4. Bullish BOS
        5. Price returns to violated OB zone
        
        Bearish Breaker Block (for SHORT):
        1. Bullish OB exists
        2. Price breaks below OB (liquidity grab)
        3. Bearish displacement with FVG
        4. Bearish BOS
        5. Price returns to violated OB zone
        """
        confirmation = self.bb_confirmation_candles.value
        return_threshold = self.bb_return_threshold.value
        
        # Bullish Breaker Block detection
        # Check if bearish OB was violated upward
        dataframe['ob_violated_up'] = (
            dataframe['bearish_ob_high'].notna() &
            (dataframe['close'] > dataframe['bearish_ob_high'])
        )
        
        # Check if price is returning to violated OB zone
        dataframe['returning_to_bearish_ob'] = (
            dataframe['bearish_ob_low'].notna() &
            dataframe['bearish_ob_high'].notna() &
            (dataframe['low'] <= dataframe['bearish_ob_high']) &
            (dataframe['close'] >= dataframe['bearish_ob_low'])
        )
        
        # Bullish Breaker Block confirmed
        # FVG is optional based on hyperopt parameter
        fvg_condition_long = (
            (self.fvg_required.value == 0) |  # FVG not required
            (dataframe['bullish_fvg'].shift(1))  # FVG present
        )
        
        dataframe['bullish_breaker_block'] = (
            dataframe['ob_violated_up'].shift(confirmation) &  # OB was violated
            dataframe['bullish_displacement'].shift(1) &  # Displacement occurred
            fvg_condition_long &  # FVG optional
            dataframe['bullish_bos'].shift(1) &  # BOS confirmed
            dataframe['returning_to_bearish_ob']  # Price returning to OB zone
        )
        
        # Bearish Breaker Block detection
        # Check if bullish OB was violated downward
        dataframe['ob_violated_down'] = (
            dataframe['bullish_ob_low'].notna() &
            (dataframe['close'] < dataframe['bullish_ob_low'])
        )
        
        # Check if price is returning to violated OB zone
        dataframe['returning_to_bullish_ob'] = (
            dataframe['bullish_ob_low'].notna() &
            dataframe['bullish_ob_high'].notna() &
            (dataframe['high'] >= dataframe['bullish_ob_low']) &
            (dataframe['close'] <= dataframe['bullish_ob_high'])
        )
        
        # Bearish Breaker Block confirmed
        # FVG is optional based on hyperopt parameter
        fvg_condition_short = (
            (self.fvg_required.value == 0) |  # FVG not required
            (dataframe['bearish_fvg'].shift(1))  # FVG present
        )
        
        dataframe['bearish_breaker_block'] = (
            dataframe['ob_violated_down'].shift(confirmation) &  # OB was violated
            dataframe['bearish_displacement'].shift(1) &  # Displacement occurred
            fvg_condition_short &  # FVG optional
            dataframe['bearish_bos'].shift(1) &  # BOS confirmed
            dataframe['returning_to_bullish_ob']  # Price returning to OB zone
        )
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions for long and short positions
        """
        
        # Trend filter conditions
        trend_ok_long = (
            (self.use_trend_filter.value == 0) |  # Filter disabled
            (dataframe['trend_up'])  # Uptrend
        )
        trend_ok_short = (
            (self.use_trend_filter.value == 0) |  # Filter disabled
            (dataframe['trend_down'])  # Downtrend
        )
        
        # RSI filter conditions
        rsi_ok_long = (
            (self.use_rsi_filter.value == 0) |  # Filter disabled
            ((dataframe['rsi'] > self.rsi_min.value) & (dataframe['rsi'] < self.rsi_max.value))
        )
        rsi_ok_short = (
            (self.use_rsi_filter.value == 0) |  # Filter disabled
            ((dataframe['rsi'] > self.rsi_min.value) & (dataframe['rsi'] < self.rsi_max.value))
        )
        
        # LONG Entry: Bullish Breaker Block setup with filters
        long_conditions = (
            dataframe['bullish_breaker_block'] &
            (dataframe['volume_ratio'] > 0.5) &  # Volume requirement
            trend_ok_long &  # Trend filter
            rsi_ok_long  # RSI filter
        )
        
        dataframe.loc[long_conditions, 'enter_long'] = 1
        
        # SHORT Entry: Bearish Breaker Block setup with filters
        short_conditions = (
            dataframe['bearish_breaker_block'] &
            (dataframe['volume_ratio'] > 0.5) &  # Volume requirement
            trend_ok_short &  # Trend filter
            rsi_ok_short  # RSI filter
        )
        
        dataframe.loc[short_conditions, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit conditions
        
        Exit when:
        - Opposite breaker block forms
        - Strong counter-trend displacement
        """
        
        # Exit LONG
        exit_long_conditions = (
            dataframe['bearish_breaker_block'] |
            dataframe['bearish_displacement']
        )
        
        dataframe.loc[exit_long_conditions, 'exit_long'] = 1
        
        # Exit SHORT
        exit_short_conditions = (
            dataframe['bullish_breaker_block'] |
            dataframe['bullish_displacement']
        )
        
        dataframe.loc[exit_short_conditions, 'exit_short'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss based on ATR and breaker block levels
        
        Initial stop: below/above breaker block
        Trailing: move to breakeven after 1.5% profit
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # Get ATR for dynamic stop
        atr = last_candle['atr_14']
        
        if trade.is_short:
            # For shorts: stop above breaker block
            if current_profit > 0.015:  # 1.5% profit
                # Move to breakeven
                return 0.001
            else:
                # Initial stop: 1.5 * ATR above entry
                return -(1.5 * atr / current_rate)
        else:
            # For longs: stop below breaker block
            if current_profit > 0.015:  # 1.5% profit
                # Move to breakeven
                return 0.001
            else:
                # Initial stop: 1.5 * ATR below entry
                return -(1.5 * atr / current_rate)
