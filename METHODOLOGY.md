# Climate Arbitrage Bot - Metodología Completa

> **Versión:** 3.1  
> **Fecha:** 2026-02-22  
> **Repo:** https://github.com/TeamBajadaX/climate-arbitrage-bot

---

## 1. Resumen Ejecutivo

El **Climate Arbitrage Bot** es un sistema automatizado de paper trading que busca oportunidades de arbitraje en mercados de predicción de clima de Polymarket.

### Concepto Básico

Polymarket es un mercado de predicción donde puedes operar binarios sobre eventos futuros (ej: "¿Londres tendrá más de 20°C el 15 de marzo?"). 

Nuestra estrategia explota dos tipos de edges:

1. **Spread Arbitrage:** Cuando YES + NO < $1, compramos ambos lados y garantizamos profit
2. **Prediction Edge:** Cuando nuestro forecast (Open-Meteo) dice diferente probabilidad que el mercado

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLIMATE ARBITRAGE BOT                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Polymarket   │───▶│   Prediction │───▶│ Trade Manager │   │
│  │    API       │    │    Engine    │    │              │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                   │                   │                │
│         ▼                   ▼                   ▼                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Markets    │    │  Open-Meteo  │    │   Posiciones │   │
│  │  (temp only) │    │   (forecast) │    │   (paper)   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Componentes

| Componente | Archivo | Descripción |
|------------|--------|-------------|
| Polymarket API | `src/polymarket.py` | Conexión a Polymarket |
| Prediction Engine | `src/prediction.py` | Calcula probabilidades vs mercado |
| Weather Data | `src/weather.py` | Open-Meteo API + históricos |
| Kelly Criterion | `src/kelly.py` | Tamaño de posición |
| Trade Manager | `src/trade_manager.py` | Gestión de reglas de cierre |
| Main Loop | `main.py` | Orquestación |
| Runner | `run_bot.py` | Loop automático |

---

## 3. Obtención de Datos

### 3.1 Markets de Polymarket

**Problema resuelto:** Los markets de temperatura no aparecen en los endpoints estándar de Polymarket.

**Solución:** Usar el tag `103040` (Daily Temperature):

```python
# API endpoint
GET https://gamma-api.polymarket.com/events?tag_id=103040&active=true
```

Esto devuelve ~100 eventos de temperatura con ~900 markets totales.

### 3.2 Filtro de Markets

Solo procesamos markets futuros (fecha >= ahora):

```python
# Filtrado en main.py
for m in markets:
    end_date = m.get('endDate')
    if end > now:
        future_markets.append(m)
```

### 3.3 Datos Climáticos

Usamos **Open-Meteo** (gratuito, sin API key):

```
API: https://api.open-meteo.com/v1/forecast
Límite: 1000 calls/día (gratis)
```

Parámetros solicitados:
- `temperature_2m_max` - Temperatura máxima
- `temperature_2m_min` - Temperatura mínima
- `precipitation_sum` - Precipitación

### 3.4 Cache

Para no agotar el límite de Open-Meteo:

- **Cache TTL:** 1 hora
- **Key:** Ciudad (no ciudad + fecha)
- **Resultado:** ~24 llamadas/día en vez de ~960

---

## 4. Motor de Predicción

### 4.1 Extracción de Datos del Market

El parser extrae de la pregunta:
- Ciudad
- Variable (temperatura, lluvia)
- Threshold (ej: 20°C)
- Operador (">", "<", "=")
- Unidad (°C o °F)

```python
# Ejemplo
"Will the highest temperature in London be 25°C on March 15?"
→ ciudad: "london"
→ threshold: 25
→ operador: ">"
→ unidad: "celsius"
```

### 4.2 Obtención de Forecast

```python
# Open-Meteo devuelve 7 días de forecast
forecast = openmeteo.get_forecast(lat, lon, days=7)

# Resultado:
{
    "forecasts": [
        {"date": "2026-02-23", "max_temp": 15, "min_temp": 8},
        {"date": "2026-02-24", "max_temp": 16, "min_temp": 9},
        ...
    ]
}
```

### 4.3 Cálculo de Probabilidad

Usamos el rango de temperatura + varianza histórica:

```python
# Pseudocódigo
variance = 3  # grados de varianza

if threshold < min_temp - variance:
    probability = 1.0  # Siempre va a estar arriba
elif threshold > max_temp + variance:
    probability = 0.0  # Nunca va a llegar
else:
    # Interpolación lineal
    probability = 1 - (threshold - min_temp) / (max_temp - min_temp)
```

### 4.4 Comparación con Mercado

```
edge = P_nuestra - P_mercado

Si |edge| > threshold (15%):
    → OPORTUNIDAD DETECTADA
```

---

## 5. Gestión de Posiciones

### 5.1 Apertura de Posición

**Criterios para abrir:**
- Confianza >= 1.5 (threshold configurable)
- Edge >= 10%
- No tener posición existente en ese market

**Tamaño de posición (Kelly Criterion):**

```python
kelly = (b * p - q) / b
# donde:
#   p = probabilidad de acierto
#   q = 1 - p
#   b = odds - 1

# Kelly capped al 25% (risk management)
kelly_cap = kelly * 0.25

# Tamaño final
position_size = min(bankroll * kelly_cap, max_bet)
```

### 5.2 Reglas de Cierre (6 implementadas)

| Regla | Condición | Acción |
|-------|-----------|--------|
| **HOLD** | Siempre | Mantener hasta resolución |
| **STOP_LOSS** | Pérdida > 10% | Vender |
| **PROFIT_TAKE** | Ganancia > 30% | Asegurar ganancias |
| **TRAILING_STOP** | Caída 15% desde máximo | Proteger ganancias |
| **TIME_BASED** | < 1 hora para resolución | Cerrar antes |
| **EDGE_LOSS** | Edge baja > 2% | Salir si edge desaparece |

### 5.3 Tracking de Performance

Cada posición registra:

```python
position = {
    "market_id": "...",
    "side": "YES",  # o NO
    "amount": 15.0,
    "price_entry": 0.65,
    "price_highest": 0.70,
    "price_lowest": 0.60,
    "profit_pct": 0.0,  # se actualiza en cada scan
    "close_reasons": {
        "hold": {"triggered": False},
        "stop_loss": {"triggered": False},
        ...
    }
}
```

---

## 6. Logging y Métricas

### 6.1 Archivos de Log

```
logs/
├── bot_loop.log       # Output del runner
├── scan_YYYYMMDD_HHMM.json  # Cada scan
├── positions_YYYYMMDD.json   # Estado de posiciones
└── daily_YYYYMMDD.json       # Report diario
```

### 6.2 Métricas por Scan

```json
{
  "timestamp": "2026-02-22T17:37:00Z",
  "markets_checked": 549,
  "spread_opportunities": 0,
  "prediction_opportunities": 221,
  "new_positions": 84,
  "closed_positions": 0
}
```

### 6.3 Métricas por Posición

```json
{
  "market_id": "1401734",
  "question": "Will the highest temperature in London be 20°C on March 15?",
  "side": "YES",
  "amount": 15.0,
  "price_entry": 0.65,
  "profit_pct": 0.15,
  "close_reasons": {
    "hold": {"triggered": false},
    "stop_loss": {"triggered": false, "reason": "profit -15% < -10%"}
  }
}
```

---

## 7. Parámetros de Configuración

### 7.1 Archivo: `config.yaml`

```yaml
polymarket:
  api_key: ""  # Vacío = solo lectura

trading:
  mode: "paper"      # paper o live
  bankroll: 300     # USD
  kelly_fraction: 0.25
  min_bet: 5
  max_bet: 50
  max_position_pct: 0.15

# Thresholds
spread_threshold: 0.95      # Spread < 95% = arbitraje
prediction_threshold: 0.15    # Edge > 15% para considerar
min_confidence: 1.5          # Mínima confianza
min_edge: 0.10               # Edge mínimo 10%

# Reglas de cierre
stop_loss_pct: 0.10          # 10%
profit_take_pct: 0.30         # 30%
trailing_stop_pct: 0.15       # 15%
hours_before_close: 1          # 1 hora antes
edge_loss_threshold: 0.02     # 2%
```

---

## 8. Flujo de Ejecución

### 8.1 Loop Principal (run_bot.py)

```
1. Iniciar loop infinito (cada 15 min)
   │
   ├─→ 2. Fetch temperature events de Polymarket
   │       └─→ ~100 eventos, ~900 markets
   │
   ├─→ 3. Filtrar markets futuros (queda ~500)
   │
   ├─→ 4. Para cada market:
   │       │
   │       ├─→ 4.1 Parsear pregunta
   │       │       └─→ ciudad, threshold, operador, unidad
   │       │
   │       ├─→ 4.2 Si ciudad no está en cache (1h):
   │       │       └─→ Llamar Open-Meteo
   │       │
   │       ├─→ 4.3 Calcular probabilidad
   │       │       └─→ vs precio de mercado
   │       │
   │       └─→ 4.4 Si edge > threshold:
   │               └─→ Abrir posición (paper)
   │
   ├─→ 5. Actualizar posiciones existentes
   │       └─→ Aplicar reglas de cierre
   │
   ├─→ 6. Guardar logs
   │
   └─→ 7. Dormir 15 min
```

### 8.2 Primera Corrida vs Subsiguientes

| Corrida | Acción |
|---------|--------|
| **Primera** | Fetch Open-Meteo para todas las ciudades (~40 llamadas) |
| **Siguientes (1h)** | Usar cache (0 llamadas a API) |
| **Después de 1h** | Refresh cache (~40 llamadas) |

---

## 9. Roadmap de Mejoras

### 9.1 Mejoras Inmediatas

| Prioridad | Mejora | Impacto |
|-----------|--------|---------|
| Alta | Mejorar modelo de probabilidad | Más signals |
| Alta | Añadir más ciudades | Más markets |
| Media | Integrar más fuentes de weather | Mejor forecast |
| Baja | Live trading | Dinero real |

### 9.2 Datos Históricos

**Problema:** Necesitamos saber qué predijo bien vs qué no.

**Solución:** Recolectar datos de markets resueltos y calcular:
- Win rate por ciudad
- Win rate por rango de temperatura
- Sesgos被发现

### 9.3 Modelo de Machine Learning

Futuro: Entrenar modelo que prediga mejor que el mercado usando:
- Forecast de múltiples fuentes
- Datos históricos de markets
- Variables económicas

---

## 10. Disclaimer

**Este código es para fines educativos.**

- Paper trading: simulamos trades sin dinero real
- Live trading: requiere API key y fondos reales
- Riesgo: los mercados de predicción son altamente volátiles
- Sin garantías: este sistema NO garantiza profits

---

## 11. FAQ

### ¿Por qué paper trading?

Para validar la estrategia sin riesgo real antes de comprometer capital.

### ¿Cuánto tiempo de testing?

Recomendado: 1-2 semanas de paper trading antes de live.

### ¿Cuánto puedo ganar?

Depende del edge real vs mercado. Con 55%+ win rate y gestión de riesgo, el potencial es positivo. No hay garantías.

### ¿Qué pasa si el mercado se mueve en mi contra?

Las reglas de cierre (stop loss, trailing stop) limitan pérdidas.

### ¿Puedo usar esto para otros mercados?

El código es genérico. Solo cambiaría el filtro de markets (no solo temperatura).

---

## 12. Referencias

- **Polymarket API:** https://docs.polymarket.com/
- **Open-Meteo:** https://open-meteo.com/
- **Kelly Criterion:** https://en.wikipedia.org/wiki/Kelly_criterion

---

*Documento generado automáticamente*
