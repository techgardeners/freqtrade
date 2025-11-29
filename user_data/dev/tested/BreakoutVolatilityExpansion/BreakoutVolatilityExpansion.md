# ⚡ Breakout / Volatility Expansion Strategy – Master Document
Documento completo della strategia Breakout + aspetti secondari

---

## 🔷 1. Obiettivo della Strategia

- Tipo: Breakout Momentum
- Obiettivo: catturare l'inizio di un movimento forte dopo una fase di compressione
- Mercati ideali:
  - BTC, ETH per stabilità
  - SOL, AVAX, LINK, MATIC per volatilità
- Timeframe principali: **5m – 15m – 1h**
- Stile: aggressivo, ottimo per bot, punta a prese di profitto su movimenti esplosivi

---

## 🔷 2. Indicatori Principali

### 2.1 Compressione (Squeeze)
- Bollinger Bands (20, 2)
- Keltner Channels (20, 1.5)
- Regola: *BB dentro Keltner = compressione*

### 2.2 Direzione e Momentum
- EMA20
- EMA50
- ATR(14)
- Volume (media 20 periodi)

### 2.3 Trend / direzione
- EMA200 come filtro bias generale

---

## 🔷 3. Identificazione della Fase di Compressione

La strategia opera SOLO dopo una compressione reale.

### Condizioni di compressione:
- Bollinger Bands **dentro** Keltner Channels
- 3–10 candele consec. con range stretto
- ATR(14) più basso del 10–20% rispetto alla sua media
- Volume sotto la media (accumulo silenzioso)
- Prezzo che si muove lateralmente intorno alla EMA20

Più compressione → breakout più forte.

---

## 🔷 4. Logica di Ingresso LONG

### 4.1 Pre-condizioni (compressione)
- BB dentro KC
- ATR basso
- lateralizzazione del prezzo
- volume debole → segnale di accumulo

### 4.2 Segnale di breakout
Una candela di breakout valida deve avere TUTTI questi requisiti:

1. Rottura della **Bollinger superiore**
2. Range candela ≥ **1.5 × ATR**
3. Volume ≥ **1.3 × media 20**
4. Chiusura nella parte superiore del range (> 70%)
5. Prezzo sopra EMA20, idealmente anche sopra EMA50
6. Nessun wick ribassista enorme (indicativo di rigetto)

### 4.3 Trigger di entrata LONG
- Entrare sulla **rottura del massimo** della candela di breakout
- oppure sulla chiusura della candela se non troppo estesa

---

## 🔷 5. Logica di Ingresso SHORT

Simmetrica al LONG.

### Candela di breakout short deve:
- rompere la Bollinger inferiore
- avere range ≥ 1.5 × ATR
- volume ≥ 1.3 × media 20
- chiusura verso il fondo della candela (> 70%)
- EMA20/EMA50 inclinate al ribasso

### Trigger short:
- ingresso sotto il minimo della candela di breakout

---

## 🔷 6. Stop Loss

Stop tecnico ma stretto, perché i breakout falsi vanno tagliati subito.

### LONG
- stop sotto il minimo della candela di breakout  
**oppure**
- stop = entry - (1 × ATR)

### SHORT
- stop sopra la candela di breakout  
**oppure**
- stop = entry + (1 × ATR)

Stop più larghi riducono qualità e profit factor della strategia.

---

## 🔷 7. Take Profit e Gestione Posizione

La parte più importante.

### 7.1 TP1 (Take Profit rapido)
- TP1 = **1R** o **1.2R**
- Azioni:
  - chiudere 25–40%
  - spostare stop a break-even

### 7.2 TP2
- TP2 = **2R**
- chiudere 40–50%

### 7.3 Trailing finale
Sul restante 10–30%:

- trailing ATR (2×ATR)
- oppure trailing swing (swing lows/higher lows)
- oppure trailing EMA20

Dipende dal mercato:
- Crypto molto volatili → trailing ATR  
- BTC/ETH → trailing EMA20

---

## 🔷 8. Filtri Secondari (anti-false breakout)

Il 70% dei peggiori breakout è un *fakeout*.  
Questi filtri riducono enormemente le perdite.

### 8.1 Filtro Candela e Volume
- NO ingresso se la candela è troppo grande (> 3×ATR)
- NO ingresso se volume non supera 1.3× media 20
- NO ingresso se la chiusura della candela è sotto il 60% del range

### 8.2 Filtro Volatilità
- Nessun trade se ATR è troppo alto → breakout già avvenuto

### 8.3 Filtro Direzione
- Entrare solo se EMA20 e EMA50 sono nella stessa direzione
- NO ingresso contro EMA200 se troppo vicina

### 8.4 Filtro Squeeze incompleto
- Se BB non rientrano completamente nei KC → compressione debole

### 8.5 Filtri orari (opzionali)
- evitare orari illiquidi che producono fakeout
- evitare pre-news

---

## 🔷 9. Time Filters

Opzionali, ma migliorano molto:

- Evitare trade durante bassa liquidità (02:00–05:00 UTC)
- Preferire sessione USA (13:00–18:00 UTC)
- Evitare 10–20 minuti prima e dopo news macro (solo se monitorate)

---

## 🔷 10. Position Sizing

### 10.1 Logica di risk management
- Rischio per trade: **0.5%–1%** del capitale
- Size calcolata su base dello stop:

`position_size = (Capitale_totale × rischio%) / distanza_entry_stop`

Note:
- stop stretto → size più grande
- stop largo → size più piccola
- ESSENZIALE controllare l’esposizione massima

### 10.2 Limiti consigliati
- max 10% del capitale su altcoin
- max 20% su BTC/ETH
- max 50% esposizione totale (se multi-asset)

---

## 🔷 11. Uscite di Sicurezza (Fail-Safes)

### 11.1 Reversal immediato
- Se la candela successiva al breakout annulla più del 50% del breakout → chiudere

### 11.2 Entrata e ritorno nel range
- Se il prezzo rientra nella zona di compressione → uscire

### 11.3 ADX debole
- Se ADX < 20 per diverse barre dopo il breakout → non è un vero trend → chiudere

### 11.4 Volatilità improvvisa opposta
- Se ATR esplode in direzione contraria → uscita parziale o totale

### 11.5 Time-based exit
- Se un trade non raggiunge TP1 entro 10–15 barre → chiuderlo

### 11.6 Serie di perdite
- dopo 4–5 SL consecutivi → disattivare la strategia per N barre

---

## 🔷 12. Parametri da Ottimizzare

Lista completa dei parametri più sensibili:

- Periodo Bollinger: 20 / 21 / 18
- Deviazioni Bollinger: 2 / 2.2
- Keltner factor: 1.5 / 1.8
- Min durata compressione: 3–10 barre
- ATR soglia per breakout: 1.5× / 1.7× / 2×
- Volume soglia: 1.2× / 1.3× / 1.5× media 20
- TP1: 1R / 1.2R / 1.5R
- TP2: 2R / 2.5R / trailing only
- Trailing: ATR2, ATR3, EMA20
- Time-based exit: 8 / 10 / 15 barre
- Max shadow percent: 40% / 50% / 60%

---

## 🔷 13. Workflow Operativo Completo

1. Identificare compressione (BB dentro KC)
2. Confermare che ATR è basso
3. Verificare volumi in contrazione
4. Aspettare il breakout reale
5. Validare candela (range, volume, chiusura)
6. Calcolare distanza entry–stop
7. Dimensione posizione in base al rischio
8. Entrata su breakout
9. TP1 → chiusura parziale + stop a break-even
10. TP2 → chiusura ulteriore o trailing
11. Monitorare possibili fakeout
12. Applicare fail-safes
13. Pausa strategia dopo serie di perdite

---