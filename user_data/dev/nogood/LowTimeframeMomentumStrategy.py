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

class LowTimeframeMomentumStrategy(IStrategy):
    """
    Low Timeframe Momentum Micro-Pullback Strategy
    Author: Antigravity
    Version: 1.0.0
    
    Timeframe: 1m / 5m / 15m
    Target: Crypto (BTC, ETH, SOL, AVAX, etc.)
    """
    
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = '5m'

    # Can this strategy go short?
    can_short = True

    # Minimal ROI designed for the strategy.
    # Since we use custom exit logic, we set this to a high value to avoid default ROI exits
    # unless we want a safety net.
    minimal_roi = {
        "0": 0.117,
        "22": 0.027,
        "62": 0.014,
        "176": 0
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.2  # We use custom_stoploss

    # Trailing stoploss
    trailing_stop = False

    # Run "populate_indicators" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Order time in force.
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }
    
    # Hyperopt Parameters
    # -------------------
    # ADX Threshold
    buy_adx = IntParameter(15, 25, default=25, space='buy', optimize=True)
    
    # ATR Multiplier for Stop Loss
    sl_atr_multiplier = DecimalParameter(0.8, 1.5, default=1.215, space='sell', optimize=True)
    
    # Take Profit 1 (Risk Reward)
    tp1_rr = DecimalParameter(0.8, 1.5, default=1.291, space='sell', optimize=True)
    
    # Take Profit 2 (Risk Reward)
    tp2_rr = DecimalParameter(2.0, 3.5, default=2.371, space='sell', optimize=True)
    
    # Volume Threshold Multiplier
    volume_multiplier = DecimalParameter(1.0, 2.0, default=1.899, space='buy', optimize=True)

    # Risk per trade (0.3% - 0.6%)
    risk_per_trade = DecimalParameter(0.003, 0.006, default=0.004, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Generate all indicators used by the strategy
        """
        
        # 3.1 Trend Indicators
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        
        # 3.2 Momentum Indicators
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=7) # Using 7 as per doc suggestion
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=9)
        
        # 3.3 Volatility Indicators
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        
        # 3.4 Volume Indicators
        dataframe['volume_mean_20'] = dataframe['volume'].rolling(window=20).mean()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        """
        
        # ----------------------------------------------------------------------
        # LONG CONDITIONS
        # ----------------------------------------------------------------------
        # 1. Trend: EMA20 > EMA50 > EMA200
        trend_long = (
            (dataframe['ema_20'] > dataframe['ema_50']) &
            (dataframe['ema_50'] > dataframe['ema_200'])
        )
        
        # 2. Momentum: ADX > Threshold & ROC > 0
        momentum_long = (
            (dataframe['adx'] > self.buy_adx.value) &
            (dataframe['roc'] > 0)
        )
        
        # 3. Pullback Condition (Looking at previous candle or current?)
        # Strategy says: "During the pullback... Price touches EMA20 but NOT EMA50"
        # And "Trigger: Bullish candle closing above prev high"
        # Implementation:
        # We need to look at the *previous* candle(s) for the pullback, and the *current* candle for the trigger.
        # Or, strictly speaking, if we are calculating on 'current' candle as the trigger candle:
        #   - Current candle is green (close > open)
        #   - Current close > Previous High
        #   - Previous candle (or recent candles) touched EMA20
        #   - Previous candle did NOT touch EMA50
        
        # Let's define "Pullback occurred recently"
        # We check if Low <= EMA20 and Low > EMA50 in the last 1-2 candles.
        # Using .shift(1) to check previous candle
        
        prev_low = dataframe['low'].shift(1)
        prev_ema20 = dataframe['ema_20'].shift(1)
        prev_ema50 = dataframe['ema_50'].shift(1)
        
        pullback_long = (
            (prev_low <= prev_ema20) &
            (prev_low > prev_ema50)
        )
        
        # 4. Trigger Candle
        # - Close > Previous High
        # - Volume > Multiplier * Avg Volume
        # - Close < BB Upper (No FOMO)
        
        trigger_long = (
            (dataframe['close'] > dataframe['high'].shift(1)) &
            (dataframe['volume'] > (dataframe['volume_mean_20'] * self.volume_multiplier.value)) &
            (dataframe['close'] < dataframe['bb_upper'])
        )
        
        dataframe.loc[
            (trend_long) &
            (momentum_long) &
            (pullback_long) &
            (trigger_long),
            'enter_long'] = 1

        # ----------------------------------------------------------------------
        # SHORT CONDITIONS
        # ----------------------------------------------------------------------
        # 1. Trend: EMA20 < EMA50 < EMA200
        trend_short = (
            (dataframe['ema_20'] < dataframe['ema_50']) &
            (dataframe['ema_50'] < dataframe['ema_200'])
        )
        
        # 2. Momentum: ADX > Threshold & ROC < 0
        momentum_short = (
            (dataframe['adx'] > self.buy_adx.value) &
            (dataframe['roc'] < 0)
        )
        
        # 3. Pullback Condition
        # High >= EMA20 and High < EMA50
        prev_high = dataframe['high'].shift(1)
        
        pullback_short = (
            (prev_high >= prev_ema20) &
            (prev_high < prev_ema50)
        )
        
        # 4. Trigger Candle
        # - Close < Previous Low
        # - Volume > Multiplier * Avg Volume
        # - Close > BB Lower
        
        trigger_short = (
            (dataframe['close'] < dataframe['low'].shift(1)) &
            (dataframe['volume'] > (dataframe['volume_mean_20'] * self.volume_multiplier.value)) &
            (dataframe['close'] > dataframe['bb_lower'])
        )
        
        dataframe.loc[
            (trend_short) &
            (momentum_short) &
            (pullback_short) &
            (trigger_short),
            'enter_short'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        """
        # Fail-safes based on strategy
        
        # 12.1 Immediate return to pullback (Fail)
        # If candle closes below EMA20 (Long) -> Exit
        # This is hard to model in vectorised 'populate_exit_trend' because it depends on being in a trade.
        # But we can set a general signal: if Close < EMA20 and we are long... 
        # But we only want to exit if we JUST entered. 
        # Standard Freqtrade handles exits if the condition is met.
        # If we put 'exit_long = close < ema_20', it will exit ANY long trade that drops below EMA20.
        # The strategy says: "Se la candela successiva chiude sotto EMA20 (LONG) -> uscita"
        # This implies a trailing stop or a condition.
        # Let's implement a strict exit if trend breaks.
        
        dataframe.loc[
            (dataframe['close'] < dataframe['ema_20']),
            'exit_long'] = 1
            
        dataframe.loc[
            (dataframe['close'] > dataframe['ema_20']),
            'exit_short'] = 1
            
        # 12.2 Volatility Spike
        # If ATR increases > 2x in 3 bars -> Exit
        # atr_change = dataframe['atr'] / dataframe['atr'].shift(3)
        # dataframe.loc[atr_change > 2.0, 'exit_long'] = 1
        # dataframe.loc[atr_change > 2.0, 'exit_short'] = 1
        
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss logic based on ATR
        """
        # Calculate SL based on ATR at entry
        # We need to access the dataframe or store the ATR at entry.
        # Freqtrade 'trade' object doesn't store custom data easily without custom_info, 
        # but we can re-calculate or look up.
        # However, looking up dataframe in custom_stoploss is expensive/complex.
        # Simplified approach: Use a fixed percentage fallback or try to get ATR.
        
        # Better approach for Freqtrade: Calculate SL distance at entry and store it?
        # Or just use the 'stoploss' parameter if it was dynamic?
        # Since we can't easily access the DataFrame here efficiently for backtesting speed,
        # we will use a workaround or assume the user accepts a percentage approximation if not using
        # the 'custom_entry_price' to set stoploss.
        
        # Actually, the strategy says: SL = entry - (1 x ATR).
        # This is a fixed distance at entry.
        # We can set this in `custom_entry_price`? No, that's for limit orders.
        
        # We can use `populate_entry_trend` to calculate the SL price and store it in a column,
        # but `trade` object won't have it.
        
        # Let's use a dynamic stoploss based on current volatility if possible, 
        # or rely on the initial stoploss being set.
        
        # For this implementation, I will use a fixed percentage as a proxy if I can't get ATR,
        # BUT I can try to fetch the dataframe.
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # This is not ideal for backtesting (lookahead bias if using current candle for past trade).
        # Correct way in Freqtrade:
        # Use absolute stoploss.
        
        # If we want to be precise:
        # We can't easily set per-trade absolute stoploss in standard Freqtrade without `custom_stoploss` 
        # returning a percentage relative to CURRENT price or INITIAL price.
        
        # Strategy: SL = Entry - 1*ATR
        # Stoploss % = (Entry - (Entry - ATR)) / Entry = ATR / Entry
        
        # We can calculate this percentage at entry time?
        # No, custom_stoploss is called every tick/candle.
        
        # Let's try to find the ATR of the open candle.
        open_date = trade.open_date_utc
        # Find candle corresponding to open_date
        entry_candle = dataframe.loc[dataframe['date'] == open_date]
        
        if not entry_candle.empty:
            atr = entry_candle['atr'].values[0]
            # Calculate SL percentage
            # SL Price = Open Rate - (Multiplier * ATR)
            # We want to return the stoploss as a percentage from the OPEN price (initial stoploss)
            # or current price (trailing).
            # Freqtrade expects return value as % of current price (negative).
            # Or absolute price if using stoploss_on_exchange? No, always %.
            
            # Wait, custom_stoploss return value:
            # "return a value to be used as the new stoploss value (as a ratio of the current price)."
            # If we want a fixed SL at (Entry - ATR), we calculate:
            # Target_SL_Price = Trade_Open_Rate - (Multiplier * ATR)
            # New_SL_Ratio = (Target_SL_Price - Current_Rate) / Current_Rate
            
            if trade.is_short:
                 target_sl_price = trade.open_rate + (atr * self.sl_atr_multiplier.value)
            else:
                 target_sl_price = trade.open_rate - (atr * self.sl_atr_multiplier.value)
            
            # Ensure SL is below current price for Long, above for Short
            if trade.is_short:
                if target_sl_price < current_rate:
                    return -0.01 # Safety, should be above
            else:
                if target_sl_price > current_rate:
                    return -0.01 # Safety
            
            # Calculate ratio
            # For Freqtrade, stoploss is relative to current_rate.
            # stoploss = (stop_price - current_price) / current_price
            
            sl_ratio = (target_sl_price - current_rate) / current_rate
            return sl_ratio
            
        return -0.05 # Fallback

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        # Strategy: Risk per trade = 0.3-0.6% of capital
        # Size = (Capital * risk%) / distance_entry_stop
        
        # We need the ATR to calculate distance_entry_stop.
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle['atr']
        
        if atr == 0:
            return proposed_stake
            
        risk_per_trade = self.risk_per_trade.value # e.g. 0.005 (0.5%)
        capital = self.wallets.get_total_stake_amount()
        
        risk_amount = capital * risk_per_trade
        
        # Distance to stop
        # Stop distance = ATR * Multiplier
        stop_distance = atr * self.sl_atr_multiplier.value
        
        # Size = Risk Amount / Stop Distance (in price terms)
        # This gives amount in COIN.
        # We need amount in STAKE (USDT).
        # Size_Coin = Risk_Amount / Stop_Distance
        # Size_Stake = Size_Coin * Current_Rate
        
        if stop_distance == 0:
            return proposed_stake
            
        size_coin = risk_amount / stop_distance
        size_stake = size_coin * current_rate
        
        # Apply limits
        if size_stake > max_stake:
            size_stake = max_stake
        if size_stake < min_stake:
            size_stake = min_stake
            
        return size_stake

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float, max_stake: float,
                              **kwargs) -> Union[Optional[float], tuple[Optional[float], Optional[str]]]:
        """
        Manage TP1 (Close 50%)
        """
        # TP1 = 1R
        # R = ATR * Multiplier (at entry)
        # We need to reconstruct R.
        
        # If we already partially exited, don't do it again.
        # We can check trade.orders to see if we have a sell order?
        # Or check if trade.amount is less than initial amount?
        
        # Simplified check: if we haven't reduced position yet.
        # Freqtrade doesn't easily track "TP1 hit" state persistently across reloads without custom data,
        # but we can check if current_profit > TP1_RR * (Risk%)?
        # No, R is price distance.
        
        # Let's try to get ATR from entry time again (expensive but necessary for logic consistency)
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        entry_candle = dataframe.loc[dataframe['date'] == trade.open_date_utc]
        
        if entry_candle.empty:
            return None
            
        atr = entry_candle['atr'].values[0]
        risk_distance_pct = (atr * self.sl_atr_multiplier.value) / trade.open_rate
        
        # TP1 Target Profit % = Risk Distance % * TP1_RR
        tp1_profit_pct = risk_distance_pct * self.tp1_rr.value
        
        # TP2 Target Profit % = Risk Distance % * TP2_RR
        tp2_profit_pct = risk_distance_pct * self.tp2_rr.value
        
        # Check if TP1 hit
        if current_profit >= tp1_profit_pct:
            # Check if we already sold 50%
            # If current amount is roughly 50% of initial amount?
            # trade.amount is current amount. trade.initial_amount (if available?)
            # Freqtrade `Trade` object has `amount`.
            # We can't easily know initial amount if we don't store it.
            # But we can check if we have any sell orders.
            
            # If we haven't sold yet, sell 50%.
            # How to check? count sell orders.
            sell_orders = [o for o in trade.orders if o.side == 'sell' or o.side == 'short_exit'] # short_exit for shorts?
            # Actually side is 'sell' for spot, 'buy' for short exit?
            # Let's just check `trade.nr_of_successful_exits` if it exists or similar.
            
            # Simplest way: use a tag.
            # If 'tp1_exit' not in trade.exit_reason (if we can see past reasons? No)
            
            # We can use `trade.orders` to see if there is a filled order with 'tp1' in custom_data?
            # Not easily.
            
            # Let's assume if we are above TP1 and we have full position, we sell half.
            # How to know "full position"? 
            # We can't.
            
            # Alternative: Just return the adjustment. Freqtrade will execute it.
            # We need to ensure we don't do it repeatedly.
            # We can use `trade.set_custom_data` / `get_custom_data` if available in this version?
            # It is available in recent versions.
            
            # Let's try to use a class attribute dict to track trades? 
            # Unsafe across restarts.
            
            # If we can't reliably track partial exit, we might skip it or just do a full exit at TP2
            # and maybe a full exit at TP1?
            # The user asked for "Chiudere 50%".
            
            # Let's try to use `trade.get_custom_data`.
            try:
                tp1_hit = trade.get_custom_data(key='tp1_hit')
            except:
                tp1_hit = None
            
            if not tp1_hit:
                # Sell 50%
                # Stake to sell = current_stake * 0.5
                # Return negative value to reduce position
                
                # Mark as hit
                trade.set_custom_data(key='tp1_hit', value=True)
                
                return -(trade.amount * 0.5), 'tp1_exit'
        
        # Check if TP2 hit -> Full Exit
        if current_profit >= tp2_profit_pct:
            return -trade.amount, 'tp2_exit'
            
        return None

