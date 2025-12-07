# 🧠 CVD + VWAP Bands + Microstructure – Scalping System (1m/5m)

Strategia avanzata basata su:

- Volume delta (CVD)
- VWAP Bands istituzionali
- Micro-structure reversal per entry chirurgiche

---

## 1. Obiettivo

- Identificare squilibri reali tra acquirenti e venditori
- Usare la VWAP come magnete istituzionale
- Entrare con micro-pattern strutturali a stop ridottissimi

---

## 2. Indicatori e Strumenti

### 2.1 CVD (Cumulative Volume Delta)

- Mostra se il flusso ordini è dominato da buyers o sellers

### 2.2 VWAP Bands

- VWAP centrale
- Deviazioni: 0.5σ – 1σ – 2σ
- Usate come zone di:
  - fair value
  - premium / discount
  - rimbalzi probabilistici

### 2.3 Micro-Structure Pattern

- BOS (micro-break)
- Mini-orderblock
- Liquidity micro-grabs

---

## 3. Regole LONG

1. **CVD Divergence Bullish**
   - Prezzo fa un nuovo minimo
   - CVD NON fa un nuovo minimo → divergenza buy

2. **Prezzo in Discount VWAP**
   - Il prezzo tocca banda -1σ o -2σ

3. **Micro BOS rialzista**
   - rottura dell’ultimo micro-swing high

4. **Entry**
   - Entry limit sul mini-orderblock creato dopo il BOS
   - Oppure sulla parte bassa della candela di displacement

---

## 4. Regole SHORT

1. Divergenza ribassista CVD:
   - Prezzo nuovo massimo
   - CVD non conferma

2. Prezzo in Premium VWAP:
   - sopra +1σ o +2σ

3. Micro BOS ribassista

4. Entry:
   - limit nel mini-OB ribassista

---

## 5. Stop Loss

- Stop sotto il micro-OB (LONG)
- Sopra micro-OB (SHORT)
- Stop molto piccoli: 0.05–0.20% tipici

---

## 6. Take Profit

- TP1: ritorno verso VWAP
- TP2: VWAP centrale
- TP3 (runner): banda opposta

---

## 7. Filtri

- No trade se CVD è piatto
- No trade se prezzo cammina su VWAP senza direzione
- Evitare orbite post-news

---

## 8. Parametri da ottimizzare

- Deviazioni VWAP
- Range minimo per micro-OB
- Tempo max per retest OB
- Divergenza CVD minima (X%)

---

## 9. Workflow

1. Controlla divergente CVD  
2. Identifica premium/discount via VWAP  
3. Cerca microstructure BOS  
4. Entry limit  
5. SL micro, TP veloce  
