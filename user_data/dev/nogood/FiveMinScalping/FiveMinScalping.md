# ⚡ 5-Minute Scalping Strategy – Master Document

High-probability trend-following scalping system for the 5-minute timeframe.

---

## 1. Strategy Overview

This is a **trend-following scalping strategy** designed for the **5-minute timeframe**, using a multi-confirmation approach to reduce false breakouts and filter market noise.

The strategy enters trades *only* in the direction of the dominant trend and requires alignment between trend, momentum, and price action.

---

## 2. Indicators Setup

Add the following indicators to your chart (TradingView, MT4, MT5, etc.):

### 2.1 EMA 200 (Exponential Moving Average)

- Function: Determines long-term trend direction.
- Rule: **Only trade in the direction of the 200 EMA.**

### 2.2 EMA 55

- Function: Medium-term dynamic support/resistance.
- Acts as an important trend filter.

### 2.3 EMA 9

- Function: Fast EMA used as the entry trigger reference.
- Measures short-term momentum shifts.

### 2.4 MACD (12, 26, 9)

- Modification:
  - Disable / hide the **MACD Line** and **Signal Line**.
  - Only the **MACD Histogram** is used.
- Function: Momentum trigger (green = bullish, red = bearish).

### 2.5 RSI (Relative Strength Index)

- Settings: 14-period RSI.
- Modification:
  - Draw a horizontal line at **50**.
- Function: Confirms directional strength.

---

## 3. Long (Buy) Entry Rules

All conditions must be met before entering a BUY trade:

### 3.1 Trend Filter

- Price must be **above the 200 EMA**.

### 3.2 EMA Alignment

- **EMA 9 > EMA 55**
  - Confirms bullish short-term momentum aligned with the trend.

### 3.3 Price Action Pullback

- Wait for the price to **pull back toward the EMAs**.
- Price **must not close below the 55 EMA**.

### 3.4 RSI Confirmation

- RSI must be **above the 50 level**.
  - Indicates bullish market strength.

### 3.5 MACD Momentum Trigger

- MACD Histogram must show **green bars**.
- Preferably:
  - A flip from red → green  
  - Or increasing green bars (building momentum)

### 3.6 Entry Execution

- Enter after all conditions align at the close of the signal candle.

### 3.7 Stop Loss

- Place SL **below the most recent swing low**,  
  or  
- Below the **55 EMA** if swing low is too far.

### 3.8 Take Profit

- Use a **1 : 1.5 Risk-to-Reward** target.
- Example:
  - Risk = 10 pips → TP = 15 pips.

---

## 4. Short (Sell) Entry Rules

Mirror the long rules:

### 4.1 Trend Filter

- Price must be **below the 200 EMA**.

### 4.2 EMA Alignment

- **EMA 9 < EMA 55**

### 4.3 Price Action Pullback

- Wait for a pullback toward the EMAs.

### 4.4 RSI Confirmation

- RSI must be **below 50**.

### 4.5 MACD Momentum Trigger

- MACD Histogram must show **red bars**.

### 4.6 Entry Execution

- Enter at the close of the signal candle.

### 4.7 Stop Loss

- Place SL **above the most recent swing high**.

### 4.8 Take Profit

- Use **1 : 1.5 RR**.

---

## 5. Important Rules & Tips

### 5.1 Avoid Ranging Markets

Do NOT trade if:

- EMAs (9, 55, 200) are flat and overlapping,
- Price oscillates between the EMAs,
- The market shows “choppy” behavior.

### 5.2 Avoid High-Impact News

Skip trades during:

- NFP  
- FOMC  
- CPI  
- Any major red-folder economic event

Volatility becomes unpredictable.

### 5.3 All Conditions Must Align

If even **one** rule disagrees:

- Example: Price above 200 EMA, EMA alignment good, MACD good…  
  but RSI below 50 → **NO TRADE**

Discipline ensures high win rate.

### 5.4 Best Instruments

- Crypto pairs (BTC, ETH, SOL, BNB)
- Forex majors
- Indices (NASDAQ, SPX, DAX)

---

## 6. Optimization Parameters

Recommended variables to backtest:

- EMA 9 → EMA 8 or 10  
- EMA 55 → 50 or 60  
- RSI threshold → 48 / 50 / 52  
- MACD histogram smoothing → default or 2-bar smooth  
- Stop placement:
  - Swing low vs EMA-based  
- RR targets:
  - 1:1  
  - 1:1.5  
  - 1:2  

---

## 7. Workflow Summary

1. Check price direction vs 200 EMA  
2. Confirm EMA 9 vs EMA 55 alignment  
3. Wait for controlled pullback  
4. Confirm RSI position (above/below 50)  
5. Check MACD histogram color and momentum  
6. Enter at candle close  
7. Set SL below/above swing  
8. Set TP at 1:1.5  
9. Avoid ranges and news events  
10. Repeat only in clean trend conditions  

---
