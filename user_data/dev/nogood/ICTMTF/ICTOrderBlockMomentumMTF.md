# 🧠 ICT Order Block Momentum – Versione Avanzata Multi-Timeframe (HTF + LTF)

Strategia ICT professionale basata su:
- HTF (Higher Timeframe: 15m / 1h / 4h)
- LTF (Lower Timeframe: 1m / 5m)

L'obiettivo è sfruttare la liquidità e gli order block istituzionali del timeframe superiore,  
ed eseguire l’ingresso preciso sul timeframe basso con R:R molto elevato.

---

## 🔷 1. Obiettivo della Strategia

- Identificare la *direzione istituzionale* sul timeframe alto (HTF)
- Cercare liquidity grab + displacement + order block sul HTF
- Usare il LTF per entrare con alta precisione e stop minimi
- Perfetta per BTC, ETH, SOL, AVAX nei TF:
  - HTF: 15m, 1h, 4h
  - LTF: 1m, 3m, 5m

---

## 🔷 2. Struttura Multi-Timeframe

### HTF → Direzione + Zone istituzionali  
### LTF → Entrata precisa

---

## 🔷 3. Fase HTF – Identificazione del Bias

Il timeframe superiore serve a identificare:

### 3.1 Trend istituzionale (Bias)
- Se il prezzo è in **premium** → preferire SHORT
- Se è in **discount** → preferire LONG

### 3.2 Zone di interesse (HTF Kill Zones)
- Order Blocks (OB)
- Fair Value Gaps (FVG)
- Imbalance
- Liquidity pools:
  - Equal highs / lows
  - Swing high / swing low
  - Round numbers (00/25/50/75)

### 3.3 Requisito fondamentale
HTF deve mostrare un:
- Liquidity grab  
- BOS (Break of Structure) verso la direzione opposta  
- Creazione di un Order Block HTF valido  

Solo allora si passa al LTF.

---

## 🔷 4. Fase LTF – Setup di Entrata

Una volta confermato il bias sul HTF:

### Requisiti:

1. LTF deve replicare:
   - Grab locale  
   - Micro-displacement  
   - LTF BOS / MSS

2. L’Order Block LTF deve **allinearsi** con:
   - OB HTF  
   - FVG HTF  
   - Mitigation Block HTF

3. L’ingresso va eseguito esclusivamente in:
   - discount zone (per BUY)
   - premium zone (per SELL)

---

## 🔷 5. Logica di Ingresso LONG

### 5.1 Su HTF:
- Swing low preso (liquidity grab)
- Displacement forte verso l’alto
- Creazione OB (ultima candela ribassista)
- BOS confermato

### 5.2 Su LTF:
- Ripetizione dello stesso pattern in piccolo:
  - Grab su micro-swing  
  - LTF FVG  
  - LTF BOS/MSS  
  - Ritorno al LTF OB *che coincide* con il bordo dell’OB HTF

### 5.3 Entry:
- Entry limit nella parte superiore del corpo dell’OB LTF
- SL sotto il minimo del grab HTF (o LTF per entry più aggressiva)
- TP:
  - TP1: lato opposto del LTF FVG
  - TP2: liquidity pool HTF
  - TP3: massimo/inefficienza HTF

R:R tipico: **1:4 → 1:12**

---

## 🔷 6. Logica SHORT

Simmetrica:
- HTF liquidity grab sopra uno swing
- HTF displacement ribassista
- OB vendite HTF
- LTF entry sul micro-OB in premium zone
- SL sopra il massimo HTF grab
- TP su liquidity inferiore

---

## 🔷 7. Filtri di Qualità (Essenziali)

- NO trade se OB HTF è enorme
- NO trade se non esiste displacement chiaro
- NO trade se il prezzo non ritorna in modo ordinato
- NO trade se il LTF BOS non è netto
- NO trade in orari illiquidi

---

## 🔷 8. Fail Safe

- Se BOS HTF viene invalidato → annullare strategia
- Se il prezzo non ritorna al LTF OB entro X barre → ignorare
- Dopo 5 SL consecutivi → stop 50 barre

---

## 🔷 9. Workflow Multi-Timeframe Finale

1. Identifica bias su HTF  
2. Localizza OB/FVG/Imbalance HTF  
3. Attendi grab + displacement HTF  
4. Passa al LTF  
5. Cerca pattern identico in piccolo  
6. Conferma MSS LTF  
7. Entry limit su OB LTF  
8. Gestione TP multi-livello  
9. Monitoraggio fail-safes  