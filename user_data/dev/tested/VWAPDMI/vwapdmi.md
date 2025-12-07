# 📈 VWAP + DMI Trend Strategy – Master Document
Strategia basata su Rolling VWAP e DMI/ADX per identificare trend puliti su timeframe 1H

---

## 🔷 1. Obiettivo della Strategia

- Identificare trend puliti e sostenibili su timeframe **1H**
- Usare la VWAP come “fair value volume-based”
- Usare il DMI/ADX per confermare direzione e forza del trend
- Entrare solo quando volume e prezzo sono allineati nella direzione dominante
- Strategia semplice, chiara, robusta, ottima per crypto, forex e index

---

## 🔷 2. Indicatori Utilizzati

### 2.1 Rolling VWAP (Volume Weighted Average Price)
- **Impostazione:** Minimum Window Size = **200**
- Smussa il rumore e mostra il valore equo ponderato sul volume

### 2.2 DMI (Directional Movement Index)
- Impostazione standard: **14**
- Componenti:
  - **+DI** → forza dei compratori
  - **-DI** → forza dei venditori
  - **ADX** → forza del trend (non direzione)

---

## 🔷 3. Logica di Mercato Necessaria

La strategia opera **solo se c’è un trend reale**, non in range.

Condizioni richieste:

1. **Incrocio del prezzo con VWAP**
2. **Dominanza DI corretto (+DI > -DI o viceversa)**
3. **ADX > 20** → trend reale, nessun rumore

Se ADX < 20 → NO trade (mercato laterale).

---

## 🔷 4. Regole di Ingresso LONG

Per aprire una posizione LONG devono essere vere TUTTE le seguenti condizioni:

1. **Prezzo sopra VWAP**
   - Il prezzo attraversa e chiude sopra il VWAP
   - Segnale che gli acquirenti dominano il valore equo

2. **+DI sopra -DI**
   - La forza rialzista supera quella ribassista
   - Conferma del bias bullish

3. **ADX sopra 20**
   - Trend abbastanza forte da rendere i segnali affidabili

### 🎯 Entry:
- Entrare **sulla candela successiva** al segnale completo.

---

## 🔷 5. Regole di Ingresso SHORT

Per aprire una posizione SHORT devono essere vere TUTTE le seguenti condizioni:

1. **Prezzo sotto VWAP**
   - Prezzo chiude sotto la VWAP
   - I venditori controllano il fair value

2. **-DI sopra +DI**
   - Forza ribassista maggiore di quella rialzista

3. **ADX sopra 20**
   - Trend ribassista forte, non range

### 🎯 Entry:
- Entrare **sulla candela successiva** al segnale completo.

---

## 🔷 6. Gestione del Rischio e Posizione

### 6.1 Stop Loss

#### LONG
- Stop = close della candela di segnale **– 2.5 × ATR(14)**

#### SHORT
- Stop = close della candela di segnale **+ 2.5 × ATR(14)**

Ragione:
- ATR identifica la volatilità reale
- 2.5 × ATR garantisce stop ampio ma non eccessivo

---

## 🔷 7. Take Profit

### 7.1 Rapporto R:R fisso
- **Reward / Risk = 3 : 1**

Esempio:
- Se stop è 100$, TP = 300$

Questo evita TP troppo vicini e filtra rumore del mercato.

---

## 🔷 8. Filtri Secondari (Opzionali ma Consigliati)

### 8.1 Filtro volume
- Evitare trade con volume inferiore alla media nelle ultime 20 barre

### 8.2 Evitare orari:
- Notte asiatica → volatilità bassa
- 1h prima o dopo news macro

### 8.3 Filtro volatilità
- Evitare trade quando ATR è insolitamente basso (compressione estrema)

---

## 🔷 9. Indicazioni di Robustezza

- Funziona bene quando il mercato **ha una direzione chiara**
- Evita i range grazie all’ADX
- Il VWAP filtra molto del rumore presente nelle crypto 1H
- Strategia semplice → più difficile da “rompere”

---

## 🔷 10. Parametri da Ottimizzare (per backtest)

- Minimum window VWAP: 150–200–300
- Soglia ADX: 18–20–25
- Moltiplicatore ATR: 2.0 – 2.5 – 3.0
- Rapporto R:R: 3:1 – 2.5:1 – 4:1
- DI smoothing: 14 / 10 / 20

---

## 🔷 11. Workflow Operativo Completo

1. Autorizzare trading solo in HTF pulito  
2. Attendere incrocio del prezzo con VWAP  
3. Controllare DI dominance (+DI / -DI)  
4. Verificare ADX > 20  
5. Segnale completo → entry candela successiva  
6. SL = entry +/- (2.5 × ATR)  
7. TP = 3 × rischio  
8. Continuare fino a chiusura  
9. Evitare range, news e volume basso  
10. Ripetere solo con condizioni pulite  

---