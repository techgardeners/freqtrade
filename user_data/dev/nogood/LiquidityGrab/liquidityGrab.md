# 🌀 Liquidity Grab + Micro-Imbalance Reversal Strategy
Strategia NON convenzionale basata su logiche di liquidità, imbalance e microstruttura

---

## 🔷 1. Obiettivo della Strategia

- Non usa indicatori di analisi tecnica classici (EMA, RSI, MACD, BB, ATR…)
- Basata sulla **microstruttura del prezzo**, NON sulla matematica degli indicatori.
- Obiettivo: sfruttare i movimenti manipolativi dove il prezzo:
  1) Pulisce la liquidità (liquidity grab)  
  2) Rivela un imbalance direzionale  
  3) Inverte violentemente verso la direzione opposta

Funziona molto bene sulle crypto, soprattutto in TF bassi (1m/5m/15m), perché:

- mercati fortemente manipolati  
- grandi quantità di stop-loss sopra/sotto livelli chiave  
- movimenti esplosivi dopo la presa di liquidità  

---

## 🔷 2. Concetti Chiave

### 🔸 2.1 Liquidity Grab (Stop Hunt)
Il mercato spesso rompe brevemente:

- un massimo precedente (swing high)
- o un minimo precedente (swing low)

solo per prendere gli stop-loss e poi invertire.

### 🔸 2.2 Imbalance (Micro-FVG)
Una “candela inefficiente” dove:

- apertura → massimo → chiusura  
oppure  
- apertura → minimo → chiusura  

mostra una **forte spinta unidirezionale senza ritorno**.

Quando il prezzo ritorna in quell’area → bounce ad alta probabilità.

### 🔸 2.3 Market Structure Shift (MSS)
Dopo la presa di liquidità, il mercato deve:

- rompere l’ultimo micro-swing a favore dell’inversione

Questo conferma che non è un semplice spike, ma un vero reversal.

---

## 🔷 3. Elementi necessari (NO indicatori classici)

La strategia richiede SOLO:

1. Swing High / Swing Low locali  
2. Identificazione di un Liquidity Grab  
3. Identificazione di Micro-Imbalance (Fair Value Gap)  
4. Break strutturale (Market Structure Shift)  
5. Rientro a testare l’inefficienza → Entry

Nessun EMA. Nessun RSI. Zero indicatori da “retail”.

---

## 🔷 4. Logica di Ingresso LONG

### 4.1 Identificazione Liquidità sopra un massimo
- Identificare un **swing high recente**  
- Il prezzo rompe sopra lo swing **per pochi tick/candele**  
- Chiusura *immediatamente* sotto lo swing → segnale di “grab”  

### 4.2 Imbalance ribassista sulla candela di reversal
La candela che fa il reversal deve avere:

- corpo grande  
- wick minimo  
- range fortemente direzionale  
- struttura tipo “FVG (fair value gap)”:
  - minimo della candela 3 > massimo della candela 1

### 4.3 Market Structure Shift
- Il prezzo rompe il “micro-swing low” interno alla struttura precedente  
→ questo conferma l’inversione.

### 4.4 Entry LONG
L’entry non è sulla rottura, ma sul **ritest dell’area di imbalance**:

- Entry = ritorno del prezzo nella zona FVG  
- Entry limit, non market (precisione massima)

Nessun indicatore necessario.

---

## 🔷 5. Logica di Ingresso SHORT

Simmetrica:

1. Break sotto uno swing low (liquidity grab)  
2. Ritorno immediato sopra → wick di rifiuto  
3. Candela bullish inefficiente (FAIR VALUE GAP verso l’alto)  
4. Break della struttura (MSS)  
5. Entry short sul ritest dell’inefficienza

---

## 🔷 6. Stop Loss

Stop molto chiaro e non arbitrario:

- Per LONG → sopra il massimo che ha preso la liquidità  
- Per SHORT → sotto il minimo che ha preso la liquidità  

Stop è sempre:
- definito strutturalmente  
- mai un valore fisso o indicatoriale  
- non ha bisogno di ATR o simili

---

## 🔷 7. Take Profit

### TP1 (conservativo)
- Ritorno sul lato opposto dell’inefficienza  
- Di solito 0.5R – 1R

### TP2 (principale)
- Target sulla zona di liquidità opposta del range

### TP3 (esteso)
- Target su breakout zone della nuova struttura creata

La strategia ha spesso R:R molto alti:
- 2R / 3R / 5R sono frequenti  
- perché è un “reversal istituzionale”, non casuale

---

## 🔷 8. Filtri secondari

### 🔸 8.1 Evitare trade:
- in mezzo ai range senza liquidità sopra/sotto  
- dopo candele enormi senza inefficienze  
- se il MSS non è chiaro  
- se il prezzo non ritorna al FVG (entry deve essere precisa)

### 🔸 8.2 Preferire:
- consolidamenti stretti → esplosione → grab → inversione  
- orari con volatilità (EU/US)  
- asset liquidi (BTC/ETH/SOL)

---

## 🔷 9. Position Sizing

Nessun cambio rispetto alle best practice:

- rischio per operazione: **0.5%**  
- size =  
  `(Capitale × rischio%) / distanza_entry_stop`

Stop molto chiaro = size molto facile da calcolare.

---

## 🔷 10. Fail Safes

### Se il prezzo:
- non rimbalza sul FVG → no entry  
- chiude oltre il massimo/minimo del grab → trade invalidato  
- ritorna nel range completamente → chiudere

### Dopo 5 trade consecutivi in SL:
- sospendere strategia per 20–30 barre  

---

## 🔷 11. Parametri da Ottimizzare

Non sono indicatori, quindi parametri "strutturali":

- profondità minima dello swing da liquidare  
- lunghezza minima FVG  
- dimensione minima candela di inversione  
- distanza massima per cui accettiamo il ritest  
- R:R minimo accettabile (1.5R / 2R / 3R)  
- distanza massima tra FVG e swing di riferimento  

---

## 🔷 12. Workflow Operativo Completo

1. Identifica swing chiave  
2. Aspetta il liquidity grab  
3. Cerca la candela di inversione con FVG  
4. Conferma MSS (break struttura interna)  
5. Aspetta il ritorno nell’inefficienza  
6. Entry limit nella zona FVG  
7. Stop sul massimo/minimo della presa di liquidità  
8. TP1 sul ritorno all’origine del movimento  
9. TP2 sulla liquidità successiva  
10. TP3 sul breakout finale  
11. Attiva fail-safes  
12. Pausa lineare dopo serie di SL  

---