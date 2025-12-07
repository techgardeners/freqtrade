# 📈 Scalping Momentum EMA + RSI – Master Document

Strategia di scalping per timeframe 1m / 5m basata su trend + momentum

---

## 1. Obiettivo della Strategia

- Tipo: Scalping direzionale (trend-following di brevissimo termine)
- Timeframe: 1 minuto e 5 minuti
- Mercati: Crypto liquide (BTC, ETH, SOL, ecc.)
- Obiettivo: cogliere micro-impulsi nella direzione del trend con
  stop stretti e target rapidi (“mordi e fuggi”)

---

## 2. Indicatori Utilizzati

### 2.1 Medie Mobili

- EMA veloce: **EMA 10**
- EMA lenta: **EMA 50**
- Funzione:
  - EMA10 → direzione e micro-trend
  - EMA50 → bias di fondo e filtro di trend
  - EMA10 sopra EMA50 → bias rialzista
  - EMA10 sotto EMA50 → bias ribassista

### 2.2 RSI (Relative Strength Index)

- RSI periodo: **14** (da ottimizzare, vedi parametri)
- Livelli chiave:
  - 30 → ipervenduto
  - 70 → ipercomprato
  - 50 → spartiacque momentum (sopra bullish, sotto bearish)

*(Opzionale)*: Stochastic (es. 14,3,3) per conferma, non obbligatorio.

---

## 3. Condizioni di Mercato Richieste

La strategia opera solo se:

- Il prezzo non è in range super stretto (poca volatilità)
- Non ci sono news macro ad altissimo impatto imminenti/ appena uscite
- C’è un minimo di direzionalità visibile (EMA50 non completamente piatta)

---

## 4. Regole di Ingresso LONG (Buy)

1. **Trend rialzista di base**
   - Prezzo sopra **EMA50**
   - EMA10 ≥ EMA50 (o sta incrociando al rialzo)

2. **Pullback + RSI in ipervenduto**
   - Il prezzo effettua un piccolo ritracciamento verso EMA10 / EMA50
   - RSI scende **sotto 30** e poi risale **sopra 30**
     (uscita dall’ipervenduto = fine della mini-correzione)

3. **Conferma di ripartenza**
   - Candela bullish che chiude sopra la chiusura della candela precedente
   - Possibilmente il prezzo torna sopra EMA10

4. **Trigger di ingresso**
   - Entrata **LONG**:
     - alla chiusura della candela di conferma
     - oppure sulla rottura del massimo della candela di conferma

---

## 5. Regole di Ingresso SHORT (Sell)

1. **Trend ribassista di base**
   - Prezzo sotto **EMA50**
   - EMA10 ≤ EMA50 (o sta incrociando al ribasso)

2. **Pullback + RSI in ipercomprato**
   - Il prezzo rimbalza verso EMA10 / EMA50
   - RSI sale **sopra 70** e poi scende **sotto 70**
     (uscita dall’ipercomprato = fine del mini-rimbalzo)

3. **Conferma di ripartenza ribassista**
   - Candela bearish che chiude sotto la chiusura della candela precedente
   - Preferibilmente prezzo di nuovo sotto EMA10

4. **Trigger di ingresso**
   - Entrata **SHORT**:
     - alla chiusura della candela di conferma
     - oppure sulla rottura del minimo della candela di conferma

---

## 6. Stop Loss

- **LONG**:
  - Stop sotto il **minimo locale** del pullback
  - oppure sotto il minimo della candela di conferma
- **SHORT**:
  - Stop sopra il **massimo locale** del rimbalzo
  - oppure sopra il massimo della candela di conferma

In entrambi i casi:

- distanza stop tipicamente molto piccola (0.1–0.3% su crypto, da adattare)
- NON allargare lo stop se viene quasi colpito: se il segnale fallisce, si accetta la perdita.

---

## 7. Take Profit

Strategia “mordi e fuggi” → target rapidi.

### Variante A – R:R fisso

- Rischio/Reward tipico: **1:1.5** o **1:2**
- Esempio:
  - stop 0.2% → TP1 a 0.3–0.4%

### Variante B – Livelli tecnici

- Per LONG:
  - TP su **massimo locale precedente** o piccola resistenza vicina
- Per SHORT:
  - TP su **minimo locale precedente** o piccolo supporto

### Gestione parziale (consigliata)

- Chiudere **50%** posizione a TP1
- Spostare stop a **break-even**
- Lasciare correre il restante 50% verso un target un po’ più ambizioso (2R)

---

## 8. Filtri Operativi / Orari

- Evitare:
  - minuti immediatamente successivi a news macro importanti
  - sessioni ultra-piatte (volume molto basso)
- Preferire:
  - Fasce con buona liquidità (sovrapposizione EU/US per crypto)
- Facoltativo:
  - Operare solo a favore del trend visibile su TF superiore (15m / 1H)

---

## 9. Parametri da Ottimizzare

- Periodo RSI: **7 / 9 / 14**
- Soglie RSI:
  - ipervenduto: 20–30
  - ipercomprato: 70–80
- Periodi medie:
  - EMA veloce: 8 / 10 / 13
  - EMA lenta: 34 / 50 / 55
- R:R:
  - 1:1.2 / 1:1.5 / 1:2
- Filtro orario:
  - solo alcune fasce (es. 09:00–12:00, 14:00–18:00)

---

## 10. Workflow Operativo

1. Identifica il trend (prezzo vs EMA50, posizione EMA10)
2. Attendi un pullback (contro-trend locale)
3. Controlla RSI in ipercomprato/ipervenduto e rientro dalla zona estrema
4. Aspetta candela di conferma a favore del trend
5. Calcola distanza entry–stop e dimensione posizione
6. Entra, imposta subito stop e TP
7. Gestisci TP parziale e sposta stop a BE dopo il primo target
8. Non forzare trade fuori dalle condizioni sopra
