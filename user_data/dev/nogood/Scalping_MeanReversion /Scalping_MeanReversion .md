# 🧠 ICT Scalping – Liquidity Grab + Fair Value Gap – Master Document

Strategia di scalping ICT per timeframe 1m / 5m basata su liquidità e inefficienze

---

## 1. Obiettivo della Strategia

- Tipo: Price Action avanzata (ICT / Smart Money)
- Timeframe: 1 minuto e 5 minuti
- Mercati: Crypto liquide
- Obiettivo: entrare dopo **liquidity grab** + **displacement** +
  **ritorno in Fair Value Gap (FVG)** con stop molto stretti e R:R elevato

---

## 2. Concetti Chiave (ICT)

- **Liquidity Pool**:
  - zone con molti stop-order (swing high/low, massimi/minimi di sessione)
- **Liquidity Grab / Stop Hunt**:
  - rottura veloce di un massimo/minimo chiave e immediato rientro
- **Fair Value Gap (FVG)**:
  - sequenza di 3 candele in cui la candela centrale è impulsiva
  - esempio rialzista:
    - massimo candela 1 < minimo candela 3 → spazio “vuoto” = FVG
- **Break of Structure (BOS) / Market Structure Shift (MSS)**:
  - rottura di un piccolo swing a favore della nuova direzione
  - conferma che non è un rimbalzo casuale ma un’inversione reale

---

## 3. Setup LONG (dopo grab ribassista)

### 3.1 Liquidity Grab

1. Identifica un **supporto chiave**:
   - minimo della sessione
   - minimo precedente evidente
2. Aspetta che il prezzo:
   - scenda **sotto quel minimo**, facendo uno spike
   - e poi **rientri subito sopra** (candela con lunga shadow inferiore)

### 3.2 Displacement + BOS

3. Dopo il grab, il prezzo deve:
   - iniziare un **impulso rialzista forte** (1–3 candele verdi)
   - rompere un **piccolo swing high** interno: questo è il BOS/MSS rialzista

### 3.3 Identificazione del FVG rialzista

4. Sull’impulso che ha causato il BOS, cerca un **FVG rialzista**:
   - consideri 3 candele: 1 → impulsiva → 3
   - se **minimo candela 3 > massimo candela 1**
   - l’area tra massimo candela 1 e minimo candela 3 è il FVG

### 3.4 Entrata LONG

5. Piazza un **ordine BUY limit**:
   - **dentro il FVG**, preferibilmente sulla parte bassa del gap
   - in alternativa, entry a mercato quando la candela ritraccia nel gap

### 3.5 Stop Loss e Take Profit

- **Stop Loss LONG**:
  - appena **sotto il minimo del liquidity grab**
  - oppure appena sotto il limite inferiore del FVG (se molto vicino)

- **Take Profit LONG**:
  - TP1: chiusura completa del FVG (ritorno al massimo candela 1)
  - TP2: swing high precedente o livello di resistenza vicino
  - R:R target: minimo **1:2**, ideale 1:3+

---

## 4. Setup SHORT (dopo grab rialzista)

### 4.1 Liquidity Grab

1. Identifica una **resistenza chiave**:
   - massimo della sessione
   - massimo precedente evidente
2. Aspetta che il prezzo:
   - salga **sopra quel massimo** con uno spike
   - e poi **rientri subito sotto** (shadow superiore lunga)

### 4.2 Displacement + BOS ribassista

3. Dopo il grab, il prezzo deve:
   - generare un **impulso ribassista forte**
   - rompere un **piccolo swing low** interno (BOS/MSS bearish)

### 4.3 Identificazione del FVG ribassista

4. Sull’impulso, trova un **FVG ribassista**:
   - minimo candela 1 > massimo candela 3
   - zona tra minimo candela 1 e massimo candela 3 = FVG

### 4.4 Entrata SHORT

5. Piazza un **ordine SELL limit**:
   - **dentro il FVG**, preferibilmente verso la parte alta del gap
   - oppure entra a mercato alla prima reazione nella zona del gap

### 4.5 Stop Loss e Take Profit

- **Stop Loss SHORT**:
  - appena **sopra il massimo del liquidity grab**
  - oppure poco sopra il limite superiore del FVG

- **Take Profit SHORT**:
  - TP1: fill completo del FVG (ritorno al minimo candela 1)
  - TP2: swing low precedente o supporto successivo
  - R:R target: minimo **1:2**, meglio se 1:3+

---

## 5. Filtri Operativi

- Evitare:
  - trend days estremi (price unidirezionale senza vere inversioni)
  - orari con volatilità da news
- Preferire:
  - momenti di alta liquidità (apertura Europa/USA)
  - livelli di liquidity chiari (massimi/minimi di sessione)
- Bonus:
  - allineare i trade alla direzione del TF superiore (es. 15m/1H)

---

## 6. Gestione del Rischio

- Rischio per trade: **0.25% – 0.5%** del capitale (scalping)
- Dimensione posizione:
  - position_size = (capitale × rischio) / (distanza entry–stop)
- Niente martingale, niente “mediare al ribasso”: ogni trade è indipendente

---

## 7. Parametri da Ottimizzare

- Dimensione minima FVG:
  - in % del prezzo (es. 0.05% / 0.1% / 0.2%)
- Tipo di livelli di liquidità:
  - solo high/low di giornata
  - anche swing minori (high/low ultime N barre)
- Richiesta BOS obbligatoria o no:
  - testare con e senza condizione di break di struttura
- Numero massimo di candele per il ritorno nel FVG:
  - se il prezzo non ritorna nel gap entro X barre → setup invalidato

---

## 8. Workflow Operativo

1. Segna sul grafico i livelli di liquidità (swing high/low importanti)
2. Aspetta un **grab** (spike oltre il livello e rientro rapido)
3. Attendi un **impulso forte** opposto con BOS/MSS
4. Individua il **FVG** sull’impulso
5. Piazza ordine limit nel FVG (buy o sell)
6. Imposta subito stop oltre il grab
7. Imposta TP1/TP2 (almeno 1:2)
8. Applica la stessa logica solo in contesti “puliti”, non forzare
