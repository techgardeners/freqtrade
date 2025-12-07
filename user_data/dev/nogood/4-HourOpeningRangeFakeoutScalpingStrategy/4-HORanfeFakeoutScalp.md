# ⚡ 4-Hour Opening Range Fakeout Scalping Strategy – Master Document

Price-action-based scalping system using the New York 4-hour opening range.

This strategy requires **no indicators**, only clean market structure.

---

## 1. Strategy Overview

This is a scalping strategy built around the concept of the **first 4-hour candle of the trading day (New York time)**.

It looks for:

- A breakout of the 4H range,
- Followed by a **re-entry back inside** the range,
- And then takes a reversal trade targeting a 1:2 RR.

Works on:

- **Analysis timeframe:** 4H  
- **Execution timeframe:** 5 minutes  
- **Timezone:** New York  

---

## 2. Chart Setup

### 2.1 Timeframes

- Higher timeframe for structure: **4H**
- Execution timeframe: **5m**

### 2.2 Timezone

- Set chart to **New York time**.

---

## 3. Step 1 – Identify the 4-Hour Opening Range

1. Go to the **4H timeframe**.
2. Identify the **first 4-hour candle of the new trading day**.
3. Wait for this candle to **fully close**.
4. Draw two horizontal lines:
   - One at the **High**
   - One at the **Low**
5. Extend these lines across the entire trading day.

This defines the **4-Hour Opening Range (OR)**.

---

## 4. Step 2 – Breakout & Re-Entry Setup

Switch to the **5-minute chart**.

You now wait for a specific sequence:

### 4.1 Breakout Condition

A valid breakout requires:

- A **5m candle closes fully OUTSIDE** the 4H range  
  (body must close outside; wick-only break does NOT count)

Breakout of the HIGH → potential SHORT  
Breakout of the LOW → potential LONG

### 4.2 Re-Entry Condition

After a valid breakout:

- Wait for price to **close back INSIDE** the 4H range.

This MUST happen on the same day.

When the re-entry candle closes inside the range, a trade setup is formed.

---

## 5. Step 3 – Entry Rules

### 5.1 Long Entry (Buy)

Conditions:

- Price breaks **below** the 4H Low  
- Then **re-enters** and closes inside the range

Entry:

- Enter long at the close of the re-entry candle.

### 5.2 Short Entry (Sell)

Conditions:

- Price breaks **above** the 4H High  
- Then **re-enters** and closes inside the range

Entry:

- Enter short at the close of the re-entry candle.

The logic:  
You are trading a **failed breakout** (fakeout) and capturing the move back inside the range.

---

## 6. Stop Loss Placement

### 6.1 Default Stop Loss Rule

Place SL at the **extreme of the breakout wick**:

- LONG → SL goes **below the breakout wick low**
- SHORT → SL goes **above the breakout wick high**

### 6.2 Special Case: Breakout is too large

If the breakout wick is huge (SL becomes unreasonably wide):

→ Find the nearest logical structure level:

- Local support/resistance  
- Minor swing  
- Order block  
- Micro-demand/supply zone  

Place the stop behind that level.

---

## 7. Take Profit

- Target at least a **1 : 2 Risk-to-Reward ratio**.
- You may scale out or trail the stop once 1R is reached.

Recommended:

- TP1 = 1R  
- TP2 = 2R  
- Optional: Runner toward opposite side of the range  

---

## 8. Key Rules & Notes

### 8.1 Only trade the SAME DAY

If a breakout happens the next day → it is invalid.

### 8.2 Candle body matters

Breakouts require a **full candle close outside the range**.

Wick-only violations are ignored.

### 8.3 Avoid trading

- During major news (NFP, CPI, FOMC)
- If price stays inside the range the whole day
- If breakout and re-entry happen on extremely low volume

### 8.4 Best market types

- Markets with high liquidity (BTC, ETH, majors, indices)
- Trending days with opening volatility
- Days with early manipulation then mean reversion

---

## 9. Optimization Suggestions

- Stop-loss source:
  - Breakout wick  
  - Nearest structural zone  
- RR:
  - 1:1.5  
  - 1:2  
  - 1:3  
- Entry refinements:
  - Enter on re-entry candle close  
  - Enter on wick retracement into the candle midpoint  
- Only trade during New York morning session  

---

## 10. Workflow Summary

1. Mark the first 4H candle of the day (NY time)  
2. Draw High and Low → Opening Range  
3. Go to 5m chart  
4. Wait for:
   - Breakout candle close outside the range  
   - Re-entry candle close inside the range  
5. Enter LONG/SHORT depending on direction  
6. Set SL beyond breakout wick  
7. Set TP 1:2 RR  
8. Only trade same-day signals  
9. Avoid news and low-volume conditions  

---
