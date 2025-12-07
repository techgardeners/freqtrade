# 📊 Regression Channel Break & Fade – Statistical Scalper (1m/5m)

Strategia quantitativa avanzata basata su:

- Regressione lineare per il trend locale
- Deviazione statistica multipla per identificare estremi inefficaci
- Break + Fade per catturare il ritorno alla media

---

## 1. Obiettivo

- Identificare eccessi estremi rispetto al trend “matematico”
- Scommettere sul ritorno al centro del canale
- Scalping veloce, stop micro, TP sulla media

---

## 2. Indicatori

### 2.1 Regression Channel

- Periodo: 100 barre
- Componenti:
  - linea centrale
  - +-1σ, +-2σ deviazioni

### 2.2 Bollinger Supp. (opzionale)

- Bollinger 20,2 per rafforzare segnali

---

## 3. Regole LONG (Fade al ribasso)

1. **Prezzo rompe sotto -2σ della regressione**
   - Non seguito da forte volume → probabile eccesso temporaneo

2. **Candela successiva chiude sopra -2σ**
   - Rejet statistico

3. **Trigger**
   - Entry sulla rottura del massimo della candela di conferma
   - Oppure entry limit sul 50% della candela

---

## 4. Regole SHORT (Fade al rialzo)

1. **Prezzo rompe sopra +2σ**
2. Candela successiva chiude sotto +2σ
3. Entry su break del minimo o limit al 50%

---

## 5. Stop Loss

- LONG → sotto l’estremo a -2σ
- SHORT → sopra estremo a +2σ
- Stop molto stretti

---

## 6. Take Profit

- TP1 → linea centrale della regressione
- TP2 → lato opposto del canale di regressione
- Tipico R:R: **1:1.5 – 1:3**

---

## 7. Filtri

- Evitare trend-day estremi (prezzo corre lungo un lato del canale)
- No entry durante news
- Migliori condizioni: range day o volatilità moderata

---

## 8. Parametri da ottimizzare

- Periodo regressione: 80–150
- Deviazioni: 1.8σ – 2.0σ – 2.2σ
- Candela conferma: range minimo

---

## 9. Workflow

1. Segui regressione → identifica estremi  
2. Aspetta break e fail (rientro nel canale)  
3. Entry con conferma o limit  
4. SL stretto fuori dal canale  
5. TP sulla media  
