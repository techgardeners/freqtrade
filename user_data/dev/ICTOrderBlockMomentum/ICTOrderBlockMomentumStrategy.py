# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: disable=F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (IStrategy, IntParameter, DecimalParameter, CategoricalParameter)
from freqtrade.persistence import Trade

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from freqtrade.exchange import timeframe_to_minutes

class ICTOrderBlockMomentumStrategy(IStrategy):
    """
    ICT Order Block Momentum Strategy
    Author: Antigravity
    Version: 1.0.0
    
    Timeframe: 1m / 5m / 15m
    Target: Crypto (BTC, ETH, SOL, AVAX, etc.)
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    can_short = True
    
    # ROI (High to rely on custom exit)
    minimal_roi = {
        "0": 100
    }
    
    stoploss = -0.99 # Custom stoploss used
    trailing_stop = False
    process_only_new_candles = True
    
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    startup_candle_count: int = 200
    
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
    
    # Hyperopt Parameters
    # -------------------
    # Swing Period (Lookback for Highs/Lows)
    swing_period = IntParameter(3, 10, default=3, space='buy', optimize=True)
    
    # FVG Threshold (Min size of gap as % of price)
    fvg_threshold = DecimalParameter(0.001, 0.005, default=0.001, space='buy', optimize=True)
    
    # Order Block Lookback (How far back to look for the OB candle)
    ob_lookback = IntParameter(3, 10, default=10, space='buy', optimize=True)
    
    # Risk Reward
    target_rr = DecimalParameter(2.0, 5.0, default=3.0, space='sell', optimize=True)
    
    # Risk per trade
    risk_per_trade = DecimalParameter(0.005, 0.01, default=0.01, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Generate indicators. 
        Note: This strategy relies on Price Action, so we calculate Swings, FVGs, and OBs here.
        """
        
        # 1. Identify Swing Highs and Lows
        # Using rolling max/min with center=True would be lookahead, so we use lagging swings.
        # A swing high is a high surrounded by lower highs.
        # We can't easily vectorise "surrounded by" without lookahead for the *current* candle,
        # but we can detect PAST swings.
        
        period = self.swing_period.value
        
        # Pivot High/Low (Fractals)
        # High[i] > High[i-1] ... High[i-period] AND High[i] > High[i+1] ... (Lookahead!)
        # For backtesting/live, we can only know a swing high formed 'period' bars ago.
        
        # We will use a rolling max to detect if a high was the highest in the last N bars.
        # And check if the subsequent bars were lower.
        
        # Simplified Swing detection for vectorization:
        # Highest High in last N bars
        dataframe['high_max'] = dataframe['high'].rolling(window=period*2+1).max()
        dataframe['low_min'] = dataframe['low'].rolling(window=period*2+1).min()
        
        # This is not quite right for "Swing Points".
        # Let's do a custom apply or loop? No, too slow.
        # Let's use argrelextrema from scipy? Or just shift logic.
        
        # We need to identify specific price levels that are "Liquidity Pools".
        # These are previous Swing Highs/Lows.
        
        # Let's define a Swing High as: High[i-2] > High[i-3], High[i-2] > High[i-1], High[i-2] > High[i] (if period=2)
        # We can implement this by shifting.
        
        # For period=3 (default 5 in param, let's use 3 for code simplicity or use param)
        # We need to re-calculate this in `populate_entry_trend` if we want dynamic params?
        # No, populate_indicators runs once. We can use a fixed reasonable period or the default.
        
        # Let's use a fixed period of 5 for indicators.
        p = 5
        
        # Is High[i-p] the highest in window [i-2p, i]?
        # This means it was a swing high p bars ago.
        
        # We'll use a custom function to find these levels and propagate them forward.
        # But for vectorization, we can just mark the candles that ARE swing points.
        
        # 2. Fair Value Gaps (FVG)
        # Bullish FVG: Low[i] > High[i-2]
        # Bearish FVG: High[i] < Low[i-2]
        
        dataframe['fvg_bullish'] = (dataframe['low'] > dataframe['high'].shift(2))
        dataframe['fvg_bearish'] = (dataframe['high'] < dataframe['low'].shift(2))
        
        # Calculate FVG size
        dataframe['fvg_bullish_top'] = dataframe['low']
        dataframe['fvg_bullish_bottom'] = dataframe['high'].shift(2)
        dataframe['fvg_bearish_top'] = dataframe['low'].shift(2)
        dataframe['fvg_bearish_bottom'] = dataframe['high']
        
        # 3. Order Blocks (OB)
        # This is complex to vectorise fully because an OB is valid until mitigated.
        # We will handle OB identification in `populate_entry_trend` or a helper loop if needed.
        # But we can mark potential OB candles.
        
        # Bullish OB: Last Red Candle before a Bullish FVG/Displacement
        # Bearish OB: Last Green Candle before a Bearish FVG/Displacement
        
        dataframe['is_green'] = dataframe['close'] > dataframe['open']
        dataframe['is_red'] = dataframe['close'] < dataframe['open']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry Logic:
        1. Identify Liquidity Grab (Price breaks recent Swing, then reverses)
        2. Identify Displacement (FVG)
        3. Identify OB
        4. Set Entry Signal
        """
        
        # We need to iterate or use advanced vectorization. 
        # Since Freqtrade expects vectorised operations for speed, we will try to vectorise 
        # the "recent event" logic.
        
        # However, "Waiting for return to OB" implies state.
        # Freqtrade's `populate_entry_trend` is stateless per candle (mostly).
        # But we can look back.
        
        # Let's try a loop for the logic, as it's complex pattern recognition.
        # Iterating over the last N candles (e.g. 500) is fast enough in Python if done carefully.
        # But `populate_entry_trend` is called with the full dataframe.
        # We should use `.apply` or just iterate.
        
        # For this implementation, to be robust, I will use a loop over the dataframe 
        # to identify the setup and mark the entry candle.
        # This might be slower but accurate for ICT concepts.
        
        # Initialize columns
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        dataframe['stop_loss'] = np.nan
        dataframe['take_profit'] = np.nan
        dataframe['entry_price'] = np.nan
        
        # We need to keep track of active Swing Points and OBs.
        
        # Parameters
        swing_period = self.swing_period.value
        
        # We can pre-calculate Swing Points
        # Swing High: High is max of +/- swing_period
        # This is a "Fractal".
        # We can use rolling max/min to find them.
        
        # To avoid lookahead bias in backtesting, we only know a swing formed after 'swing_period' candles.
        # So at index `i`, we check if `i - swing_period` was a swing.
        
        # Rolling max of (2*period + 1) centered at i-period.
        # i.e. rolling max of last (2*period + 1) candles, check if it equals High[i-period].
        # Wait, standard rolling is looking back.
        # Max(High[i-2p]...High[i]) == High[i-p]
        
        window = swing_period * 2 + 1
        dataframe['rolling_max'] = dataframe['high'].rolling(window=window).max()
        dataframe['rolling_min'] = dataframe['low'].rolling(window=window).min()
        
        # Shift rolling back by 'swing_period' to align with the potential swing candle?
        # No, if High[i-period] == RollingMax[i], then i-period is a Swing High.
        # But we only know this at index `i`.
        
        # Let's iterate.
        # We will maintain a list of recent Swing Highs and Lows.
        
        swings_high = [] # (index, price)
        swings_low = [] # (index, price)
        
        # Active Order Blocks
        active_ob_bullish = [] # (index, top, bottom, swing_low_price)
        active_ob_bearish = [] # (index, top, bottom, swing_high_price)
        
        # We iterate through the dataframe.
        # Note: This is slow for very large dataframes (years of 1m data).
        # But for backtesting chunks it's okay.
        
        # Optimization: Only iterate if we need to?
        # Or use a generator?
        
        # Let's try to be efficient.
        # We can't easily vectorise "Liquidity Grab + Reversal + FVG + Return to OB".
        
        # We will iterate.
        for i in range(window, len(dataframe)):
            # 1. Detect Swings (confirmed at i)
            # Potential swing is at i - swing_period
            swing_idx = i - swing_period
            
            # Check if swing_idx was a High
            # It is a high if it's the max of the window ending at i
            if dataframe['high'].iloc[swing_idx] == dataframe['rolling_max'].iloc[i]:
                swings_high.append((swing_idx, dataframe['high'].iloc[swing_idx]))
                # Keep only recent swings?
                if len(swings_high) > 5: swings_high.pop(0)
                
            # Check if swing_idx was a Low
            if dataframe['low'].iloc[swing_idx] == dataframe['rolling_min'].iloc[i]:
                swings_low.append((swing_idx, dataframe['low'].iloc[swing_idx]))
                if len(swings_low) > 5: swings_low.pop(0)
                
            # 2. Detect Setup (Long)
            # A. Liquidity Grab: Price went below a recent Swing Low
            # B. Displacement: Bullish FVG formed recently
            # C. OB: Red candle before the move
            
            # Check for Bullish FVG at i (formed by i, i-1, i-2)
            if dataframe['fvg_bullish'].iloc[i]:
                # We have a displacement.
                # Did we grab liquidity recently?
                # Look at the move that caused this FVG.
                # The move started from a low.
                # Find the lowest low before this FVG (within lookback).
                
                # Lookback for "move origin"
                origin_lookback = 10
                slice_lows = dataframe['low'].iloc[max(0, i-origin_lookback):i]
                
                # Safety check for empty slice
                if len(slice_lows) == 0:
                    continue
                    
                local_min = slice_lows.min()
                local_min_idx = slice_lows.idxmin()
                
                # Check if this local_min grabbed a Swing Low
                grabbed_swing = None
                for s_idx, s_price in swings_low:
                    if s_idx < local_min_idx and local_min < s_price:
                        # Grabbed liquidity!
                        grabbed_swing = (s_idx, s_price)
                        break # Found one
                
                if grabbed_swing:
                    # We have a Grab + Displacement (FVG).
                    # Identify OB.
                    # OB is the last Red candle before the local_min (or the candle containing local_min if red).
                    # Usually the last down candle before the up move.
                    
                    # Search backwards from FVG start (i-2) to local_min
                    # Find the last Red candle.
                    ob_idx = None
                    for k in range(i-2, local_min_idx-1, -1):
                        if dataframe['is_red'].iloc[k]:
                            ob_idx = k
                            break
                    
                    # If not found, maybe the local_min candle itself?
                    if ob_idx is None:
                        if dataframe['is_red'].iloc[local_min_idx]:
                            ob_idx = local_min_idx
                            
                    if ob_idx:
                        # Found OB.
                        ob_top = dataframe['high'].iloc[ob_idx] # Or Body Top? ICT usually Body or High. Let's use High for safety/fill.
                        ob_bottom = dataframe['low'].iloc[ob_idx]
                        
                        # Store this OB as active
                        active_ob_bullish.append({
                            'index': ob_idx,
                            'top': ob_top,
                            'bottom': ob_bottom,
                            'stop_loss': local_min, # Stop below the grab low
                            'created_at': i
                        })
            
            # 3. Check for Entry (Long)
            # If price dips into an active OB
            current_low = dataframe['low'].iloc[i]
            current_high = dataframe['high'].iloc[i]
            
            # Iterate active OBs
            for ob in active_ob_bullish[:]: # Copy to remove
                # If OB is too old?
                if i - ob['created_at'] > 50:
                    active_ob_bullish.remove(ob)
                    continue
                
                # If price broke below OB bottom (Failed OB)
                if current_low < ob['bottom']:
                    active_ob_bullish.remove(ob)
                    continue
                
                # If price touches OB Top (Mitigation/Entry)
                # And we are not the candle that created it (i > ob['created_at'])
                if i > ob['created_at'] and current_low <= ob['top']:
                    # ENTRY SIGNAL
                    dataframe.loc[i, 'enter_long'] = 1
                    dataframe.loc[i, 'entry_price'] = ob['top'] # Limit price
                    dataframe.loc[i, 'stop_loss'] = ob['stop_loss']
                    
                    # Remove OB after use (one-shot)
                    active_ob_bullish.remove(ob)
                    break # Only one entry per candle
            
            # -------------------------------------------------------
            # Short Logic (Symmetric)
            # -------------------------------------------------------
            if dataframe['fvg_bearish'].iloc[i]:
                # Lookback for "move origin" (High)
                origin_lookback = 10
                slice_highs = dataframe['high'].iloc[max(0, i-origin_lookback):i]
                
                # Safety check for empty slice
                if len(slice_highs) == 0:
                    continue
                    
                local_max = slice_highs.max()
                local_max_idx = slice_highs.idxmax()
                
                # Check if this local_max grabbed a Swing High
                grabbed_swing = None
                for s_idx, s_price in swings_high:
                    if s_idx < local_max_idx and local_max > s_price:
                        grabbed_swing = (s_idx, s_price)
                        break
                
                if grabbed_swing:
                    # Identify OB (Last Green Candle)
                    ob_idx = None
                    for k in range(i-2, local_max_idx-1, -1):
                        if dataframe['is_green'].iloc[k]:
                            ob_idx = k
                            break
                    
                    if ob_idx is None:
                        if dataframe['is_green'].iloc[local_max_idx]:
                            ob_idx = local_max_idx
                            
                    if ob_idx:
                        ob_bottom = dataframe['low'].iloc[ob_idx]
                        ob_top = dataframe['high'].iloc[ob_idx]
                        
                        active_ob_bearish.append({
                            'index': ob_idx,
                            'top': ob_top,
                            'bottom': ob_bottom,
                            'stop_loss': local_max,
                            'created_at': i
                        })
            
            # Check for Entry (Short)
            for ob in active_ob_bearish[:]:
                if i - ob['created_at'] > 50:
                    active_ob_bearish.remove(ob)
                    continue
                
                if current_high > ob['top']: # Failed OB
                    active_ob_bearish.remove(ob)
                    continue
                
                if i > ob['created_at'] and current_high >= ob['bottom']:
                    dataframe.loc[i, 'enter_short'] = 1
                    dataframe.loc[i, 'entry_price'] = ob['bottom']
                    dataframe.loc[i, 'stop_loss'] = ob['stop_loss']
                    active_ob_bearish.remove(ob)
                    break

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic is handled by custom_stoploss and custom_exit mostly.
        But we can define standard exit signals if needed.
        """
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Use the stoploss calculated at entry.
        """
        # We need to retrieve the stoploss price stored in custom_data or calculate it.
        # Since we calculated it in populate_entry_trend, we can try to access it?
        # No, populate_entry_trend results are in the dataframe, not passed here easily per trade
        # unless we store it in custom_data during entry.
        
        # Freqtrade doesn't support passing data from populate_entry to custom_stoploss easily
        # EXCEPT via `custom_entry_price` (which we use) or `confirm_trade_entry`.
        
        # We will use `confirm_trade_entry` to store the SL in custom_data.
        
        if trade.custom_data and 'stop_loss' in trade.custom_data:
            stop_loss_price = trade.custom_data['stop_loss']
            
            # Calculate ratio
            if trade.is_short:
                # Short: SL is above entry. Ratio = (SL - Current) / Current ?
                # Freqtrade expects negative ratio relative to current price?
                # No, relative to open_rate usually?
                # "return a value to be used as the new stoploss value (as a ratio of the current price)."
                # SL_Ratio = (Stop_Price - Current_Price) / Current_Price
                
                # Example: Short at 100, SL at 110. Current 105.
                # Ratio = (110 - 105) / 105 = 5/105 = +0.047
                # Wait, stoploss must be negative?
                # "The returned value should be negative (e.g. -0.05 for 5% stoploss)."
                # If I return positive, it might be treated as Take Profit?
                # No, custom_stoploss is for STOP LOSS.
                
                # If I want to set absolute price 110.
                # Freqtrade calculates: stop_loss_price = current_rate * (1 + stoploss)
                # So 110 = 105 * (1 + x) -> 1.047 = 1+x -> x = 0.047
                
                # For shorts, stoploss is ABOVE price.
                # Freqtrade documentation says:
                # "Positive values are supported for shorts (stoploss above current price)."
                
                return (stop_loss_price - current_rate) / current_rate
            else:
                # Long: SL is below entry.
                # Example: Long at 100, SL at 90. Current 95.
                # Ratio = (90 - 95) / 95 = -5/95 = -0.052
                return (stop_loss_price - current_rate) / current_rate
                
        return self.stoploss # Fallback

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Called right before placing the entry order.
        We can use this to store the Stop Loss in the trade object.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        # We need the candle that triggered the signal.
        # This function is called at the end of the candle (or start of next).
        # The signal is on the last closed candle.
        
        if 'stop_loss' in last_candle and not pd.isna(last_candle['stop_loss']):
            self.custom_trade_info[pair] = {'stop_loss': last_candle['stop_loss']}
            # We can't access `trade` object here yet, it's not created.
            # We have to use `custom_trade_info` dict to pass to `confirm_trade_exit`?
            # No, we need it in `custom_stoploss`.
            
            # Actually, `confirm_trade_entry` returns bool.
            # We can't modify the trade here.
            
            # Use `custom_entry_price`?
            pass
            
        return True

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime,
                           proposed_rate: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        """
        Set the entry price to the OB level (Limit Order).
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        
        # If we have a signal, we should have an entry price in the dataframe
        if side == 'long' and last_candle['enter_long'] == 1:
            entry_price = last_candle['entry_price']
            # Store SL for later usage?
            # We can't store in 'trade' because it's None for new trades.
            # But we can store in a class attribute dictionary keyed by pair.
            self.custom_trade_info[pair] = {'stop_loss': last_candle['stop_loss']}
            return entry_price
            
        if side == 'short' and last_candle['enter_short'] == 1:
            entry_price = last_candle['entry_price']
            self.custom_trade_info[pair] = {'stop_loss': last_candle['stop_loss']}
            return entry_price
            
        return proposed_rate

    # Helper to store custom info
    custom_trade_info = {}

    def check_entry_timeout(self, pair: str, trade: Trade, order: dict, **kwargs) -> bool:
        # Cancel limit order if not filled quickly?
        # Strategy says "Wait for return".
        # If we placed the order, we are waiting.
        # Default config handles timeout.
        return False

    def check_trade_conformance(self, pair: str, trade: Trade, **kwargs) -> bool:
        # Inject custom data into trade object after creation
        if pair in self.custom_trade_info:
            trade.set_custom_data('stop_loss', self.custom_trade_info[pair]['stop_loss'])
            # Clean up
            # del self.custom_trade_info[pair] # Keep it just in case?
        return True

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        Take Profit Logic
        """
        # TP1: 3R
        # TP2: 5R
        # We can implement partial exits here or just a simple R:R exit.
        
        # Calculate R (Risk)
        # R = |Entry - SL|
        if trade.custom_data and 'stop_loss' in trade.custom_data:
            stop_loss = trade.custom_data['stop_loss']
            risk = abs(trade.open_rate - stop_loss)
            
            if risk == 0: return None
            
            profit_amount = (current_rate - trade.open_rate) if not trade.is_short else (trade.open_rate - current_rate)
            r_multiple = profit_amount / risk
            
            if r_multiple >= self.target_rr.value:
                return "target_rr_reached"
                
        return None
