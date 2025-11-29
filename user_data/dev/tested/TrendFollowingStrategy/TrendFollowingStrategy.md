# 📈 Trend-Following Strategy – Master Document
Documento completo della strategia Trend-Following + aspetti secondari

---

## 🔷 1. Obiettivo della Strategia

- Tipo: Trend-Following
- Obiettivo: catturare i movimenti direzionali prolungati (bull o bear)
- Mercati: BTC, ETH, principali altcoin
- Timeframe operativo: **1h** (con conferma 4h)
- Timeframe opzionale: 15m per ingressi più precisi
- Stile: semi-lento, orientato a trend chiari

---

## 🔷 2. Indicatori Principali

### 2.1 Trend Direction
- EMA50 (1h)
- EMA200 (1h)

### 2.2 Trend Strength
- ADX(14)

### 2.3 Volatilità
- ATR(14)

### 2.4 Volume
- Volume con media mobile a 20 periodi

---

## 🔷 3. Condizioni per Mercato Trendato (Attivazione Strategia)

La strategia si attiva solo se:

- ADX(14) > 20  
- Distanza tra EMA50 e EMA200 sopra una soglia minima (medie non “incollate”)  
- Per LONG: prezzo sopra EMA50 e EMA200  
- Per SHORT: prezzo sotto EMA50 e EMA200  
- Slope (inclinazione) di EMA50 coerente con la direzione del trend (in salita per long, in discesa per short)

Se queste condizioni **non** sono presenti, la strategia non apre nuove posizioni.

---

## 🔷 4. Logica di Ingresso LONG

### 4.1 Trend Rialzista attivo
- EMA50 > EMA200  
- Prezzo sopra EMA50  
- ADX(14) > 20

### 4.2 Ritracciamento “sano”
- Il prezzo ritraccia verso EMA50 o leggermente sotto  
- Il ritracciamento non deve chiudere sotto EMA200  
- Profondità ritracciamento entro ~1 × ATR sotto EMA50 (parametro ottimizzabile)

### 4.3 Trigger di Entrata LONG
- Dopo il ritracciamento, si forma una candela rialzista che:
  - chiude sopra il massimo della candela precedente
  - preferibilmente con volume ≥ 1.2 × media volume 20 barre
- **Entrata LONG:** sulla rottura del massimo della candela di setup o alla chiusura, in base al modello che verrà implementato.

---

## 🔷 5. Logica di Ingresso SHORT

Simmetrica al LONG.

### 5.1 Trend Ribassista attivo
- EMA50 < EMA200  
- Prezzo sotto EMA50  
- ADX(14) > 20

### 5.2 Ritracciamento “sano”
- Prezzo che ritraccia verso EMA50 o leggermente sopra  
- Nessuna chiusura sopra EMA200  
- Profondità ritracciamento entro ~1 × ATR sopra EMA50

### 5.3 Trigger di Entrata SHORT
- Dopo il ritracciamento, si forma una candela ribassista che:
  - chiude sotto il minimo della candela precedente
  - preferibilmente con volume ≥ 1.2 × media volume 20
- **Entrata SHORT:** sulla rottura del minimo della candela di setup o alla chiusura.

---

## 🔷 6. Stop Loss

Stop dinamico in funzione della volatilità (ATR).

### 6.1 Stop iniziale LONG
- Opzione A: sotto il minimo della candela di ingresso
- Opzione B: `stop = entry_price - (1.5 × ATR(14))`

### 6.2 Stop iniziale SHORT
- Opzione A: sopra il massimo della candela di ingresso
- Opzione B: `stop = entry_price + (1.5 × ATR(14))`

Il moltiplicatore ATR (1.0–1.5–2.0) sarà un parametro da ottimizzare.

---

## 🔷 7. Take Profit & Gestione della Posizione

### 7.1 TP1 – Primo Target
- Obiettivo: **1R** (dove R = rischio iniziale = distanza entry–stop)
- Azioni:
  - Chiudere ad esempio il **50%** della posizione
  - Spostare lo stop a **break-even** (prezzo di ingresso)

### 7.2 TP2 – Secondo Target
- Obiettivo tipico: **2R**
- Azione: chiudere il restante 50% della posizione

### 7.3 Variante con Trailing
- TP1 a 1R (chiusura parziale)
- sul restante 50% attivare un trailing stop:
  - Trailing ATR (es. 2 × ATR(14))
  - oppure trailing su EMA21

La scelta fra TP fisso e trailing sarà oggetto di backtest.

---

## 🔷 8. Filtri Secondari (Qualità dei Segnali)

### 8.1 Filtri Trend
- ADX(14) deve essere > soglia (es. 20)  
- Distanza minima tra EMA50 e EMA200 per evitare fasi di congestione  
- Inclinazione di EMA50:
  - LONG: EMA50 in salita
  - SHORT: EMA50 in discesa

### 8.2 Filtri di Volatilità
- Volatilità minima:
  - ATR(14) > media ATR(14) × 0.8 (parametrizzabile)
- Volatilità massima (per evitare eccessi):
  - nessun ingresso immediato dopo una candela con range > 2.5 × ATR(14)

### 8.3 Filtri sulle Candele
- Evitare:
  - candele doji come candela di trigger
  - candele con shadow molto lunga (es. shadow > 60% del range)
  - candele troppo piccole (corpo < soglia minima rispetto ad ATR)

### 8.4 Filtri Volume
- Richiedere che il volume sulla candela di breakout sia:
  - ≥ 1.1–1.2 × media volume 20
- In versione avanzata:
  - volume in crescita nelle ultime 3–4 candele rispetto alle precedenti

---

## 🔷 9. Time Filters (Opzionali)

Per il mercato crypto è meno critico, ma comunque utile:

- Evitare fasce orarie di liquidità molto bassa (es. 02:00–05:00 UTC per alcune altcoin)
- Preferire fasce con alta partecipazione di mercato (es. 13:00–18:00 UTC, overlap EU/US)
- Possibilità di escludere determinate fasce orarie via configurazione.

---

## 🔷 10. Position Sizing (Gestione della Size)

### 10.1 Logica base
- Rischio fisso per trade: **0.5%–1%** del capitale (parametro)
- Dimensione posizione calcolata in funzione dello stop:

`position_size = (Capitale_totale × rischio_per_trade) / distanza_entry_stop`

dove:
- `Capitale_totale` = equity attuale
- `rischio_per_trade` = es. 0.005 (0.5%) o 0.01 (1%)
- `distanza_entry_stop` = |entry_price − stop_price|

### 10.2 Obiettivi
- Mantenere costante il rischio per ogni operazione
- Limitare l’effetto delle piccole perdite frequenti
- Massimizzare il profitto sui trend forti catturati dalla strategia

### 10.3 Limiti addizionali
- Esposizione massima per singolo trade (es. non oltre 10–20% del capitale in notional)
- Esposizione massima totale sul mercato (es. non oltre 50% del capitale totale in posizione).

---

## 🔷 11. Uscite Forzate (Fail-Safes)

### 11.1 Cambio di Trend
- LONG:
  - chiudere il trade se il prezzo chiude sotto EMA200 per N barre consecutive
  - oppure se EMA50 incrocia sotto EMA200
- SHORT:
  - chiudere il trade se il prezzo chiude sopra EMA200 per N barre
  - oppure se EMA50 incrocia sopra EMA200

### 11.2 ADX Debole
- Se ADX(14) scende sotto una soglia (es. 15) per più barre → chiudere il trade, il trend è “morto”.

### 11.3 Time-Based Exit
- Se un trade rimane aperto oltre una certa durata (es. 48 barre sul TF 1h) senza raggiungere TP o SL:
  - chiudere il trade per liberare capitale.

### 11.4 Volatilità Anomala
- Se ATR(14) aumenta bruscamente (es. > 2 × media ATR) in poche barre:
  - chiudere parzialmente (es. 30–50%) o uscire del tutto in base alle regole che verranno decise.

### 11.5 Filtro Consistency (per bloccare serie negative)
- Se la strategia registra 4–5 stop-loss consecutivi:
  - sospendere nuovi ingressi per N barre (es. 24 barre su 1h)
  - questa logica riduce l’impatto dei periodi dove il mercato non è adatto alla strategia.

---

## 🔷 12. Parametri da Ottimizzare

Lista ordinata di variabili chiave:

- EMA50 / EMA200:
  - test alternative: EMA20/EMA100, EMA100/EMA200
- Soglia ADX:
  - da 18 a 25
- Moltiplicatore ATR per lo stop:
  - 1.0 – 1.5 – 2.0
- TP:
  - TP1: 0.8R – 1R – 1.2R
  - TP2: 2R – 3R – solo trailing
- Percentuale da chiudere a TP1:
  - 30% – 50% – 70%
- Soglia volume:
  - 1.1× – 1.2× – 1.5× media 20
- Filtri candele:
  - soglie su dimensione corpo e shadow
- Filtri volatilità:
  - soglia minima e massima di ATR
- Durata massima del trade (time-based exit):
  - N barre (parametro).

---

## 🔷 13. Struttura Operativa Finale (Workflow)

1. Verificare che il mercato sia in trend:
   - EMA50/EMA200 allineate
   - ADX > soglia
2. Controllare la volatilità:
   - ATR in range accettabile
3. Controllare il volume:
   - volume conforme alle regole minime
4. Attendere un ritracciamento verso EMA50:
   - senza rottura strutturale della EMA200
5. Identificare la candela di setup:
   - candela di inversione con struttura pulita
6. Calcolare distanza entry–stop e dimensione posizione:
   - rispettando il rischio fisso per trade
7. Entrare a mercato:
   - solo se tutte le condizioni (trend, volume, volatilità, candela) sono allineate
8. Gestire TP1:
   - chiusura parziale + stop a break-even
9. Gestire TP2 e/o trailing:
   - lasciare correre il trend con trailing (ATR o EMA)
10. Monitorare i fail-safe:
    - cambio trend, collasso ADX, volatilità estrema, serie di SL
11. Applicare eventuali pause operative dopo serie negative.

---