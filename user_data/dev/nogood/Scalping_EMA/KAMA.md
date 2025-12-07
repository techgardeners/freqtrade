# ⚡ KAMA + SuperTrend + QQE MOD – Scalping System (1m/5m)

Strategia di scalping avanzata basata su:

- Trend dinamico adattivo (KAMA)
- Direzionalità e volatilità filtrata (SuperTrend)
- Momentum strutturato (QQE MOD)

---

## 1. Obiettivo

- Identificare micro-trend ad alta qualità
- Filtrare tutto il rumore tipico dei timeframe bassi
- Entrare solo quando trend + momentum + volatilità sono allineati
- Uscire rapidamente con stop stretti

---

## 2. Indicatori

### 2.1 KAMA (Kaufman Adaptive Moving Average)

- Periodo: 21 (da ottimizzare: 18–30)
- Funzione: media adattiva che si “accelera” nei trend e rallenta nei range

### 2.2 SuperTrend

- ATR period: 10  
- ATR multiplier: 2.5  
- Funzione: definisce il bias direzionale e agisce quasi da trailing stop

### 2.3 QQE MOD

- Periodo base RSI: 14  
- Funzione: smoothed momentum indicator, più stabile degli oscillatori classici

---

## 3. Regole LONG

1. **Trend rialzista pulito**
   - Candela chiude **sopra KAMA**
   - SuperTrend → verde (trend bullish)

2. **Momentum confermato**
   - QQE MOD: linea fast > linea slow
   - oppure QQE “trend ribbon” diventa verde

3. **Trigger operativo**
   - Entrata sulla rottura del massimo della candela di segnale
   - Oppure entry limit sulla metà della candela di retracement

---

## 4. Regole SHORT

1. **Trend ribassista**
   - Candela chiude **sotto KAMA**
   - SuperTrend → rosso

2. **Momentum ribassista**
   - QQE fast < QQE slow

3. **Trigger**
   - Entry sulla rottura del minimo candela di segnale
   - Entry limit su ritracciamento

---

## 5. Stop Loss

- Stop sotto KAMA (LONG)
- Stop sopra KAMA (SHORT)
- Oppure stop sulla linea SuperTrend (molto sicuro)

---

## 6. Take Profit

Strategia mordi-e-fuggi:

- **TP fisso 1:1.5 o 1:2**
- **TP parziale + trailing su SuperTrend**

---

## 7. Filtri

- No trade se il prezzo taglia KAMA continuamente (range rumoroso)
- No trade con bande di prezzo super compresse
- Evitare news macro

---

## 8. Parametri da ottimizzare

- Periodo KAMA
- ATR SuperTrend (multiplier)
- Soglie QQE
- R:R: 1:1.2 / 1:1.5 / 1:2

---

## 9. Workflow

1. Controlla bias SuperTrend  
2. Controlla prezzo vs KAMA  
3. Controlla momentum QQE  
4. Entra con rottura o retest  
5. SL su KAMA / SuperTrend  
6. TP rapido con trailing  
