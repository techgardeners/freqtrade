# ⚡ Low Timeframe Momentum Micro-Pullback Strategy – Master Document
Strategia ottimizzata per crypto, timeframe 1m / 5m / 15m

---

## 🔷 1. Obiettivo della Strategia

- Tipo: Momentum + Pullback breve (trend-following di breve termine)
- Mercati ideali: tutte le crypto liquide, soprattutto BTC, ETH, SOL, AVAX
- Timeframe: **1m / 5m / 15m**
- Obiettivo: sfruttare piccole onde direzionali con ritracciamenti minimi
- Stile: alta frequenza, operazioni rapide, take profit ridotti ma ricorrenti
- Evita completamente il comportamento mean reversion classico (non profittevole su crypto)

---

## 🔷 2. Logica Principale della Strategia

La strategia opera solo quando:

1. C’è un **micro-trend chiaro**  
2. Avviene un **piccolo ritracciamento controllato**  
3. Arriva un **segnale di ripartenza con volume in aumento**

È una struttura molto efficace su timeframe bassi perché:

- segue il momentum naturale delle crypto
- evita il rumore e gli squeeze laterali
- entra solo in condizioni di qualità
- massimizza il profitto su movimenti veloci

---

## 🔷 3. Indicatori Principali

### 3.1 Direzione del micro-trend
- EMA20
- EMA50
- EMA200 (bias generale)

### 3.2 Forza del movimento
- ADX(7) o ADX(14)
- Rate of Change (ROC 9–14)

### 3.3 Volatilità
- ATR(14)
- Bollinger Bands (20, 2) per filtrare eccessi

### 3.4 Volume
- Volume con media 20 periodi
- Volume delta (opzionale)

---

## 🔷 4. Condizioni per Attivare la Strategia

La strategia opera solo se:

1. **EMA20 > EMA50** (long) o **EMA20 < EMA50** (short)  
2. EMA50 > EMA200 per long, EMA50 < EMA200 per short  
3. **ADX(7) > 15–18** (trend anche piccolo ma reale)  
4. Volume non in collasso (volume > media 20 × 0.8)  
5. Nessun squeeze estremo (Bollinger non ultra-strette)

Se una di queste manca → non si opera.

---

## 🔷 5. Logica di Ingresso LONG

### 5.1 Condizioni preliminari di trend rialzista

- EMA20 > EMA50 > EMA200  
- Tutte inclinate verso l'alto  
- ADX(7) > 15  
- ROC positivo (momentum)

### 5.2 Il Ritracciamento Perfetto (micro-pullback)

Durante il pullback:

- Il prezzo tocca o leggermente penetra **EMA20**  
- MA NON tocca EMA50 (segno che il trend è ancora forte)
- La candela di pullback deve essere piccola (range < 1.2 × ATR)
- No candele con shadow superiore enorme (rifiuto)

### 5.3 Il Segnale di Ripartenza

Il trigger ufficiale:

- Una candela rialzista che chiude sopra il massimo della candela precedente  
- Volume ≥ 1.1–1.2 × media 20  
- Scanner BB: prezzo NON deve chiudere sopra la BB superiore nella candela di entrata (evita FOMO)

### 5.4 Entry LONG

- Entry = rottura del massimo della candela di trigger  
oppure
- Entry a market alla chiusura della candela di trigger

---

## 🔷 6. Logica di Ingresso SHORT

Simmetrica:

- EMA20 < EMA50 < EMA200  
- Pullback verso EMA20  
- Nessuna chiusura sopra EMA50  
- Candela di ripresa ribassista  
- Volume ≥ soglia  
- Entry = rottura del minimo

---

## 🔷 7. Stop Loss

Stop assolutamente serrato (molto importante in TF bassi).

### Opzioni:

1. Stop = minimo del pullback (LONG)
2. Stop = entry - (0.8 × ATR) (LONG)
3. Opposto per SHORT

Il valore consigliato:

👉 `SL = entry - (1 × ATR)` nel caso in cui il pullback sia piccolo.

Stop troppo larghi distruggono la strategia su TF bassi.

---

## 🔷 8. Take Profit & Gestione della Posizione

### 8.1 TP rapido (fondamentale)

- TP1 = **1R**  
- Chiudere 50%
- Spostare stop a Break-Even

### 8.2 TP finale

Opzioni consigliate:

- TP2 = entry + **2R**  
oppure
- Trailing Stop basato su EMA20 (solo in trend molto forti)
oppure
- Trailing ATR molto stretto (1.5 × ATR)

Strategia ideale:  
👉 TP1 = rapido  
👉 TP2 = movimento esteso con trailing

---

## 🔷 9. Filtri Secondari (qualità segnali)

### 9.1 Filtro candele
Evitare trade se:

- pullback con shadow lunghissima  
- candela trigger troppo piccola  
- candela trigger troppo grande (> 2.2 × ATR)

### 9.2 Filtro volume
- Volume del breakout deve essere superiore alla media  
- Evitare segnali con volume in contrazione

### 9.3 Filtro volatilità
- Evitare ingressi in compressione (range ultra-stretto)
- Evitare ingressi dopo una spike troppo violenta

### 9.4 Trend filter avanzato
- distanza EMA20–EMA50 deve crescere leggermente  
→ segno che il trend si sta rafforzando

---

## 🔷 10. Time Filters

Consigliati:

- Evitare trading nella notte asiatica su altcoin  
- Timeframe ottimali:
  - 13:00–18:00 UTC (EU+US overlap)
  - 08:00–11:00 UTC (pre-EU)

---

## 🔷 11. Position Sizing

### Logica:

- Rischio per trade: **0.3–0.6%** del capitale (TF bassi = rischio ridotto)
- Size =  
  `(Capitale × rischio%) / distanza_entry_stop`

### Regole di sicurezza:

- Max esposizione: 8–12% del capitale su BTC/ETH  
- Max esposizione: 5–8% su altcoin  
- Non aprire più di 2 trade simultanei sullo stesso asset

---

## 🔷 12. Uscite di Sicurezza (Fail-Safes)

### 12.1 Ritorno immediato nel pullback
- Se la candela successiva chiude sotto EMA20 (LONG) → uscita

### 12.2 Volatilità improvvisa
- Se ATR aumenta > 2× in 3 barre → uscita totalitaria

### 12.3 Stop time-based
- Se trade non raggiunge TP1 entro 6–10 barre → chiusura

### 12.4 Serie di SL
- 5 stop consecutivi → pausa strategia per 30–50 barre

---

## 🔷 13. Parametri da Ottimizzare

- Periodi EMA: 20/50/200 (alternativa: 13/34/200)
- ADX soglia: 12 / 15 / 18 / 20
- ATR multipliers: 0.7 / 1.0 / 1.2
- TP1: 0.8R / 1.0R / 1.2R
- TP2: 2R / 2.5R / trailing
- Volume threshold: 1.1× / 1.2× / 1.5× media 20
- Validità pullback: profondità vs. ATR
- Time-based exit: 6 / 8 / 10 barre

---

## 🔷 14. Workflow Operativo Completo

1. Identificare micro-trend (EMA20>EMA50>EMA200)
2. Confermare momentum (ADX + ROC)
3. Attendere un micro-pullback verso EMA20
4. Assicurarsi che non raggiunga EMA50
5. Validare che il pullback sia piccolo e pulito
6. Identificare candela di ripartenza con volume
7. Calcolare l’entry
8. Calcolare SL e size (risk-based)
9. Entrare solo se tutti i filtri sono rispettati
10. Gestire TP1 (chiusura parziale + BE)
11. Gestire TP2 (TP o trailing)
12. Gestire fail-safes (volatilità, tempo, trend)
13. Pausa dopo serie di loss
14. Ritorno in strategia solo in condizioni ottimali

---