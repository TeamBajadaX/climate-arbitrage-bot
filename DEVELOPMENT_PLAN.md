# Climate Arbitrage Bot - Development Plan

> **Versión 2.0** - Incluye Kelly Criterion + Prediction Edge

## Overview

Este documento define el plan de desarrollo y testing para el Climate Arbitrage Bot.

## Dos Estrategias

### 1. Spread Arbitrage
- Cuando `YES + NO < $1`, comprar ambos lados
- Profit = $1 - (YES + NO) × amount
- Sin riesgo, solo depende del spread

### 2. Prediction Edge (Main Strategy)
- Comparar forecast de NOAA vs precio de mercado
- Si `P_NOAA > P_market + threshold`, comprar YES
- Si `P_NOAA < P_market - threshold`, comprar NO
- **Kelly Criterion** para sizing: `K% = (b × p - q) / b`
  - Donde: p = probabilidad de acierto, q = 1-p, b = odds - 1
  - **CAPEADO al 25%** del tamaño sugerido para reducir riesgo

## Métricas a Medir

Por cada ciudad/mercado:
- ✅ Oportunidades detectadas
- ✅ Win rate (predicciones correctas vs incorrectas)
- ✅ Profit/pérdida por trade
- ✅ ROI por ciudad
- ✅ Volumen operado

Por estrategia:
- ✅ Spread vs Prediction edge: ¿cuál genera más profit?
- ✅ ROI por estrategia
- ✅ Drawdown máximo

## Markets Objetivo (TODOS los disponibles)

### Tier 1 - Alta Liquidez (>100k volume)
- London, New York, Paris, Tokyo, Sydney

### Tier 2 - Media Liquidez (10k-100k)
- Miami, Chicago, Seoul, Berlin, Madrid, Rome

### Tier 3 - Baja Liquidez (<10k)
- Otras ciudades con markets de temperatura, lluvia, nieve

**Objetivo:** Testear TODOS para determinar cuáles tienen más edge.

## Parámetros

### Kelly Criterion
```
Kelly % = (win_rate - (1 - win_rate) / odds)
Kelly cap = Kelly % × 0.25
```

Ejemplo:
- win_rate = 60%
- odds = 2.0 (si aciertas ganas 2x)
- Kelly = (0.6 - 0.4 / 2.0) = 0.4 = 40%
- Kelly cap = 40% × 0.25 = 10% del bankroll

### Thresholds
- Prediction threshold: 0.05-0.15 (ajustar por ciudad)
- Spread threshold: 0.95 (arbitrage seguro)

### Configuración inicial
```yaml
kelly_fraction: 0.25  # 25% del Kelly sugerido
min_confidence: 0.55  # Mínimo 55% de confianza
max_position_pct: 0.10  # Máximo 10% del bankroll por trade
base_bet: 10  # USD mínimo

# Thresholds por estrategia
spread_threshold: 0.95  # Arbitrage
prediction_threshold: 0.08  # Edge detection
```

## Plan de Testing (1 Semana)

### Día 1-2: Setup
- [ ] Obtener API keys de Polymarket
- [ ] Configurar logging completo
- [ ] Implementar Kelly criterion
- [ ] Integrar NOAA API

### Día 3-4: Paper Trading - todos los markets
- [ ] Correr en modo paper (sin dinero real)
- [ ] Operar TODOS los mercados de clima
- [ ] Logging detallado de cada decisión

### Día 5-7: Análisis
- [ ] Calcular métricas por ciudad
- [ ] Calcular métricas por estrategia
- [ ] Identificar mejores markets
- [ ] Ajustar thresholds

### Fin de Semana 1
Reporte con:
- Top 5 ciudades por ROI
- Spread vs Prediction: ¿cuál mejor?
- Win rate real
- ¿Pasar a live trading?

## Criterios de Éxito

| Métrica | Mínimo | Target |
|---------|--------|--------|
| Win rate | 50% | 60% |
| Profit semanal | >$0 | >$50 |
| Drawdown máx | <20% | <10% |

## Arquitectura del Bot

```
src/
├── polymarket.py      # API de Polymarket
├── weather.py         # NOAA + others
├── arbitrage.py       # Spread detection
├── prediction.py      # NOAA vs Market comparison
├── kelly.py          # Kelly criterion calculator
├── trader.py         # Paper/Live trading
├── metrics.py        # Métricas y logging
└── main.py           # Loop principal
```

## Tech Stack

- Python 3.9+
- Polymarket API
- NOAA Weather API (free)
- SQLite (logging de trades)
- Telegram (alertas)

## Notas

- **Paper trading:** Todos los trades se registran pero NO se ejecutan
- **Live trading:** Requiere aprobación manual después de fase 1
- **Bankroll inicial recomendado:** $100-500 para testing

---

*Actualizado: 2026-02-21*
