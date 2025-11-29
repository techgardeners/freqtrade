# 📉 Mean Reversion Strategy – Master Document
Documento completo della strategia Mean Reversion + aspetti secondari

---

## 🔷 1. Obiettivo della Strategia

- Tipo: Mean Reversion (contrarian)
- Obiettivo: acquistare gli eccessi al ribasso e vendere gli eccessi al rialzo
- Funziona SOLO in mercati laterali / privi di trend
- Mercati: BTC, ETH, altcoin liquide
- Timeframe consigliati: **5m – 15m – 30m**
- Stile: frequenza operativa medio-alta, target piccoli ma ripetuti

---

## 🔷 2. Indicatori Principali

### 2.1 Oscillatori di Eccesso
- RSI(14)
- Stochastic RSI
- Z-Score della deviazione da SMA20

### 2.2 Bande di Volatilità
- Bollinger Bands (20, 2)
- Keltner Channels (20, 1.5)
- Indicatore logico “Squeeze”

### 2.3 Trend Filter
- ADX(14)
- EMA200 (trend bias generale)

---

## 🔷 3. Condizioni per Mercato Laterale (Attivazione Strategia)

La strategia è attiva solo se:

- ADX(14) < 20 (o soglia simile 18–22)
- EMA50 e EMA200 hanno slope quasi piatto
- Distanza tra le due medie stabile, senza divergenza
- Bollinger Bands non troppo espanse (volatilità contenuta)
- Prezzo vicino alla SMA20

Se il mercato è in trend forte → **la strategia si disattiva**.

---

## 🔷 4. Logica di Ingresso LONG

### 4.1 Condizioni di Contesto
- ADX < 20 (trend debole)
- Prezzo vicino o sotto la Bollinger inferiore
- Prezzo vicino alla SMA20 o leggermente sotto
- No trend ribassista strutturato (prezzo sopra EMA200 preferibile)

### 4.2 Segnali di Eccesso (almeno 2 richiesti)
- RSI < 30 (o < 25 per segnali più puliti)
- Stoch RSI < 20
- Prezzo **sotto** Bollinger inferiore
- Z-score < -1.25 / -1.5

### 4.3 Trigger di Ingresso LONG
- Prima candela che mostra inversione:
  - chiusura sopra il massimo della candela precedente
  - oppure RSI che risale sopra 30
  - oppure cross long dello Stoch RSI

**Entrata LONG:** sulla rottura del massimo della candela di setup.

---

## 🔷 5. Logica di Ingresso SHORT

Simmetrica al LONG.

### 5.1 Condizioni di Contesto
- ADX < 20
- Prezzo vicino o sopra la Bollinger superiore
- Mercato non in forte trend rialzista

### 5.2 Segnali di Eccesso (almeno 2 richiesti)
- RSI > 70–75
- Stoch RSI > 80
- Prezzo sopra Bollinger superiore
- Z-score > +1.25 / +1.5

### 5.3 Trigger SHORT
- Candela ribassista che chiude sotto il minimo della precedente
- oppure RSI che scende sotto 70
- oppure cross short dello Stoch RSI

**Entrata SHORT:** sulla rottura del minimo della candela di setup.

---

## 🔷 6. Stop Loss

Stop sempre **stretto**, perché i falsi segnali costano poco e gli sbagli vanno tagliati presto.

### Tipi di Stop
- Stop fisso tra 0.5% e 1% (dipende dal TF)
- Stop basato su ATR:
  - Stop = 1 × ATR(14)
- Stop tecnico:
  - LONG → sotto il minimo dello swing del segnale
  - SHORT → sopra il massimo dello swing

La versione consigliata a livello operativo:
👉 **Stop = 1 × ATR(14)**

---

## 🔷 7. Take Profit e Gestione Posizione

La Mean Reversion vuole trarre profitto dal ritorno verso la media.

### 7.1 TP Principale
- Target LONG = SMA20 (media centrale)
- Target SHORT = SMA20 (dall’alto)

Per BTC/ETH funziona estremamente bene.

### 7.2 TP Multipli
Opzione avanzata:

- TP1: SMA20 → chiudere 50%
- TP2: banda opposta di Bollinger

Questo permette di sfruttare oscillazioni più ampie.

### 7.3 Time-based Exit
Se il prezzo non ritorna verso la media entro X barre:
- uscire dal trade
- valore tipico: 10–20 barre

---

## 🔷 8. Filtri Secondari

### 8.1 Filtro ADX
- NO trade se ADX > 20 (o se sale per 3 barre)

### 8.2 Filtro volatilità estrema
- Evitare segnali se una candela ha range > 1.5–2 × ATR

### 8.3 Filtro shadow lunga
- Candela di inversione deve avere corpo “pulito”, non shadow eccessive

### 8.4 Filtro rottura banda
Evitare trade se:
- una candela rompe la banda inferiore/superiore con chiusura violenta, perché potrebbe essere inizio trend.

---

## 🔷 9. Time Filters (Opzionali)

Molto utili per evitare falsi segnali:

- evitare trading in momenti di volatilità estremamente bassa (notte asiatica)
- evitare trading 15–30 min prima/dopo news macro (logico/non automatizzabile)
- preferire sessioni EU/US

---

## 🔷 10. Position Sizing

### Logica
- Rischio per trade: **0.5–1%** del capitale
- Size =  
  `(Capitale_totale × rischio%) / distanza_entry_stop`

dove:
- distanza_entry_stop è molto piccola (tipico per mean reversion)
- di conseguenza la size può risultare più grande → controllare esposizione massima

### Esposizione massima consigliata
- max 10–15% del capitale per trade su altcoin  
- max 20–25% su BTC/ETH (più sicure)

---

## 🔷 11. Uscite di Sicurezza (Fail-Safes)

### 11.1 Rottura del Range
Se il prezzo rompe e chiude fuori dal range:
- LONG: chiudere se prezzo chiude sotto la banda inferiore per 2 barre
- SHORT: chiudere se prezzo chiude sopra la banda superiore per 2 barre

### 11.2 Attivazione Trend
- Se ADX sale sopra 22–25 → chiudere trade

### 11.3 Time-based exit
- Se trade dura > X barre (es. 15 barre 15m) → uscire

### 11.4 Volatilità improvvisa
- Se ATR aumenta > 2× in poche barre → chiudere o ridurre posizione

### 11.5 Serie di Perdite
- 4–5 SL consecutivi → stop strategia per N barre (es. 20 barre)

---

## 🔷 12. Parametri da Ottimizzare

Tabella dei parametri chiave:

- RSI:
  - periodo: 9–14–21
  - threshold: 25 / 30 / 35
- Stoch RSI:
  - K/D 14/14/3 o varianti
- Z-score threshold:
  - -1.0 / -1.25 / -1.5
- Deviations Bollinger:
  - 1.8 / 2.0 / 2.5
- ATR multipliers:
  - 0.7 / 1 / 1.2
- TP:
  - solo SMA20
  - SMA20 + BB opposta
- Time-based exit:
  - 10 / 15 / 20 barre
- Min. ADX:
  - 15 / 18 / 20
- Max shadow percent:
  - 40% / 50% / 60%

---

## 🔷 13. Workflow Operativo Completo

1. Controllare ADX → se < 20, potenzialmente range  
2. Analizzare Bande di Bollinger → se strette → ok  
3. Cercare eccessi (RSI, Stoch RSI, Z-score)  
4. Confermare che non è in corso un breakout  
5. Attendere la candela di inversione  
6. Calcolare distanza entry-stop  
7. Calcolare posizionamento con rischi fissi  
8. Entrare al trigger  
9. TP su SMA20  
10. Gestire trailing verso Bollinger opposta (opzionale)  
11. Applicare time-based exit  
12. Attivare fail-safe per rotture o volatilità anomala  
13. Pausa dopo serie di SL

---