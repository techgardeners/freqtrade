# 🧠 ICT Order Block Momentum Strategy – Master Document
Strategia basata sulla teoria ICT: Order Blocks, Liquidity, FVG, BOS, MSS

---

## 🔷 1. Obiettivo della Strategia

- Strategia basata al 100% sui concetti ICT reali, non indicatori.
- Funziona nei timeframe **1m / 5m / 15m**.
- Si basa su:
  - identificare zone di liquidità  
  - attendere uno spostamento istituzionale (displacement)  
  - tracciare l’Order Block corretto  
  - entrare sul ritorno del prezzo a quella zona  

Obiettivo:
👉 Catturare movimenti istituzionali con R:R molto elevati (3R–8R tipici).

---

## 🔷 2. Concetti ICT utilizzati

### 🔸 2.1 Order Block (OB)
L’ultima candela rialzista prima di un forte movimento ribassista (per short)  
o  
l’ultima candela ribassista prima di un forte movimento rialzista (per long).

### 🔸 2.2 Break of Structure (BOS)
La rottura del massimo/minimo strutturale che conferma un cambio di trend.

### 🔸 2.3 Market Structure Shift (MSS)
Il primo segnale che le “mani forti” hanno cambiato direzione.

### 🔸 2.4 Fair Value Gap (FVG)
Imbalance di tre candele:
- massimo candela 1 < minimo candela 3 → FVG rialzista  
- minimo candela 1 > massimo candela 3 → FVG ribassista  

### 🔸 2.5 Liquidity Pools
Zone chiave dove sono raccolti:
- stop-loss  
- ordini pendenti  
- breakout traders  

Es:
- swing high / swing low  
- equal highs / equal lows  
- livelli psicologici (00/25/50/75)  

### 🔸 2.6 Premium / Discount
- In un trend rialzista: si compra in **discount**  
- In un trend ribassista: si vende in **premium**

---

## 🔷 3. Condizioni preliminari per attivare la strategia

La strategia opera solo se:

1. È avvenuto **un grab di liquidità** sopra o sotto uno swing chiave  
2. Dopo il grab avviene un **displacement forte** (candela impulsiva)  
3. Viene creato un **Order Block valido** dietro al movimento  
4. C’è un **BOS/MSS chiaro**  
5. Il ritorno al OB avviene in modo ordinato (senza spike caotici)

Se uno di questi elementi manca → NO trade.

---

## 🔷 4. Logica di Ingresso LONG (ICT Order Block BUY)

### 4.1 Identificare un Liquidity Grab
- Identificare un **swing low importante**  
- Il prezzo lo rompe leggermente  
- La candela successiva rientra sopra il livello → wick di rifiuto  

### 4.2 Displacement rialzista
Dopo il grab, serve una prova di forza istituzionale:

- 1–3 candele bullish ad alta velocità  
- FVG creato nella salita  
- volume crescente (opzionale, non necessario in ICT puro)

### 4.3 Creazione dell’Order Block
Il BUY order block è:

👉 **l’ultima candela ribassista prima del movimento rialzista impulsivo**

Condizioni importanti:
- corpo chiaro (non doji)
- range non troppo grande
- preferibile se coincide con un FVG parziale

### 4.4 Break of Structure / MSS
Il prezzo deve:
- rompere almeno **uno swing high interno**  
- idealmente rompere il massimo principale formato prima della discesa

Senza BOS/MSS → trade invalidato.

### 4.5 Entry LONG
L’entry avviene SOLO al ritorno del prezzo sull’Order Block:

- Entry = nella porzione **superiore del corpo** dell’OB  
- Entry limit (non market)  
- Richiesto un ritorno ordinato, non impulsivo

Opzione avanzata:
- Entry nella "mità del corpo dell’OB" (50% OB)

### 4.6 Stop Loss
- sotto il minimo del liquidity grab originale  
- oppure sotto il minimo dell’OB (entry più conservativa)

### 4.7 Take Profit
TP principali:

#### TP1 (conservativo)
- High che ha originato la struttura (1R–2R)

#### TP2 (principale)
- Liquidity pool superiore

#### TP3 (esteso)
- Imbalance non ancora chiuso  
- oppure massimo HTF (5m/15m)

---

## 🔷 5. Logica di Ingresso SHORT (ICT Order Block SELL)

Simmetria perfetta:

1. Liquidity grab sopra uno swing high  
2. Displacement ribassista con FVG  
3. Creazione dell’ultima candela bullish prima del dump → Order Block SELL  
4. BOS/MSS verso il basso  
5. Ritorno al OB → entry sell limit  
6. Stop sopra il massimo del liquidity grab  
7. TP su livelli inferiori di liquidità

---

## 🔷 6. Filtri Secondari

### 🔸 6.1 Evitare trade se:
- L’Order Block è troppo grande  
- Non c’è vero displacement (movimento lento = retail, non istituzionale)  
- Il ritorno al OB è troppo impulsivo  
- BOS/MSS non è netto  
- Il prezzo non ha creato nessun FVG  

### 🔸 6.2 Preferire trade se:
- Il FVG coincide con l’Order Block  
- Ci sono equal highs/lows come target chiaro  
- OB è piccolo e ben definito  
- Il grab ha preso sia swing che equal lows/highs (doppia liquidità)  

---

## 🔷 7. Position Sizing

Rischio consigliato:
- 0.5%–1% del capitale  
- size =  
  `(capitale × rischio%) / distanza_entry_stop`

L’RR tipico è 1:3 – 1:8.

---

## 🔷 8. Fail Safes

- Se il prezzo supera il massimo/minimo del liquidity grab → trade invalidato  
- Se non ritorna all’OB entro N candele → invalidazione  
- Se BOS non è chiaro → zero operazioni  
- STOP ALWAYS HARD STOP  
- Dopo 5 SL → pausa di 30–50 barre  

---

## 🔷 9. Parametri da Ottimizzare

- lunghezza minima dello swing  
- dimensione massima OB  
- distanza massima per ritest OB  
- tempo massimo per ritest  
- FVG size minima  
- TP ottimali (1.5R, 2R, 3R, 5R…)  

---

## 🔷 10. Workflow Operativo Completo

1. Identifica un’area di liquidità (swing high/low)  
2. Aspetta il liquidity grab  
3. Cerca displacement con FVG  
4. Segnati l’Order Block creato  
5. Conferma BOS/MSS  
6. Attendi ritorno all’OB  
7. Entry limit precisa  
8. SL sotto/ sopra il liquidity grab  
9. TP su zone di liquidità opposte  
10. Gestione multilivello TP  
11. pause dopo serie negative  
12. Continua solo in condizioni di qualità  

---