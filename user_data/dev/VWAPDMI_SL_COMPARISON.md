# VWAPDMIS Stop Loss Comparison Report

## 📊 Test Results (3 months: Sept-Nov 2025)

| Version | ATR Mult | Max SL Cap | Profit | Drawdown | Trades | Win Rate | Worst Trade | Status |
|---------|----------|------------|--------|----------|--------|----------|-------------|--------|
| **V1 Original** | 2.04 | ❌ None | **+24.63%** | 7.27% | 75 | 85.3% | -24.96% | ⚠️ Risky |
| **V2 MaxSL** | 2.04 | ✅ 5% | **+24.63%** | 7.27% | 75 | 85.3% | -24.96% | ⚠️ Cap ineffective |
| **V3 TightSL** | **1.5** | ✅ 5% | **+29.93%** | 9.94% | 75 | 84.0% | -24.96% | ✅ **Best** |

---

## 🔍 Analisi Dettagliata

### V1 - Original (Baseline)

- **Profitto**: +2,463 USDT (+24.63%)
- **Drawdown**: 977 USDT (7.27%)
- **Stop Loss**: 1 trade al -24.96% (SOL)
- **Problema**: Può aprire trade con SL al 25%+

### V2 - Con Max SL Cap (5%)

- **Profitto**: +2,463 USDT (+24.63%) - **IDENTICO a V1**
- **Drawdown**: 977 USDT (7.27%)
- **Stop Loss**: 1 trade al -24.96% (SOL) - **CAP NON HA FUNZIONATO**
- **Problema**: Il cap viene applicato DOPO l'apertura del trade, non impedisce l'ingresso

### V3 - ATR Ridotto + Cap

- **Profitto**: +2,993 USDT (+29.93%) - **+21% meglio di V1**
- **Drawdown**: 1,434 USDT (9.94%) - **Peggiore**
- **Stop Loss**: 1 trade al -24.96% (SOL) - **Stesso problema**
- **Vantaggio**: Più TP raggiunti (12 vs 1) grazie a stop più stretti

---

## ⚠️ Il Problema Fondamentale

**Tutti e tre hanno ancora il trade SOL con -24.96% SL!**

### Perché il Cap Non Funziona?

Il `max_stoploss_pct` viene applicato in `custom_stoploss()`, che è chiamato **DOPO** che il trade è già aperto.

**Il vero problema è nel `custom_stake_amount()`**:

```python
# Se ATR è enorme (es. 10,000 USDT su BTC volatile)
stop_distance = atr * 2.04  # = 20,400 USDT
size_stake = (80 / 20,400) * 86,433 = 339 USDT  # Piccolo!

# Ma lo SL % è:
sl_pct = 20,400 / 86,433 = 23.6%  # ENORME!
```

La strategia **non controlla** se lo SL % è accettabile **prima** di aprire il trade.

---

## ✅ Raccomandazione

### Opzione A: Usa V3 (Migliore Performance)

- **+29.93%** profit
- Stop più stretti (1.5x ATR) = più TP raggiunti
- **MA** ancora rischio di SL al 25% in condizioni estreme

### Opzione B: Aggiungi Filtro Pre-Entry

Modificare `custom_stake_amount()` per **rifiutare** il trade se:

```python
sl_pct = (atr * atr_multiplier) / current_rate
if sl_pct > 0.05:  # Se SL > 5%
    return 0  # NON aprire il trade
```

### Opzione C: Usa VWAPDMISSafe

- Ha `max_stake_ratio = 0.3` (30% max per trade)
- Limita l'esposizione totale
- **MA** non risolve il problema dello SL al 25%

---

## 🎯 La Mia Raccomandazione Finale

**Implementare Opzione B su V3**:

1. Usa ATR ridotto (1.5x) per stop più stretti
2. Aggiungi filtro pre-entry per rifiutare trade con SL > 5%
3. Questo **previene** completamente il problema

Vuoi che implementi questa soluzione?
