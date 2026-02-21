# Climate Arbitrage Bot

Bot para explotar mercados de clima en Polymarket usando arbitraje de spreads binarios.

## Estrategia

- Comparar forecasts de NOAA vs precios de Polymarket
- Cuando el spread (YES + NO) < $1, hay arbitraje seguro
- Comprar ambos lados y ganar sin importar el resultado

## Requisitos

- Python 3.9+
- Polymarket API
- NOAA/Weather API
- keys de Polymarket

## Setup

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Editar config.yaml con tus API keys
python main.py
```

## Estructura

```
├── main.py           # Entry point
├── config.yaml       # Config (no commitear)
├── config.example.yaml
├── src/
│   ├── polymarket.py  # API de Polymarket
│   ├── weather.py     # APIs de clima (NOAA, Wunderground)
│   ├── arbitrage.py   # Lógica de arbitraje
│   └── trader.py      # Ejecución de trades
└── requirements.txt
```

## Disclaimer

Este código es para fines educativos. Operar con precaución.
