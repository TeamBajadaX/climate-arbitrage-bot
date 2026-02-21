#!/usr/bin/env python3
"""
Climate Arbitrage Bot - Main Entry Point v2.0
Soporta:
1. Spread Arbitrage (YES + NO < $1)
2. Prediction Edge (NOAA vs Market)
"""
import argparse
import logging
import yaml
import time
import json
from pathlib import Path
from datetime import datetime

from polymarket import PolymarketClient, get_weather_markets, calculate_spread, is_arbitrage_opportunity
from weather import NOAAClient, get_coords_for_city
from arbitrage import estimate_profit
from prediction import PredictionEngine
from kelly import capped_kelly, position_size

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_all_weather_markets(pm_client: PolymarketClient) -> list:
    """Get ALL weather markets from Polymarket"""
    logger.info("Fetching ALL markets from Polymarket...")
    
    all_markets = []
    cursor = None
    
    while True:
        page = pm_client.get_markets(cursor=cursor, limit=200)
        if not page or "markets" not in page:
            break
        
        markets = page["markets"]
        all_markets.extend(markets)
        
        cursor = page.get("nextCursor")
        if not cursor:
            break
    
    # Filter for weather
    weather = get_weather_markets(all_markets)
    logger.info(f"Found {len(weather)} weather markets")
    
    return weather


def analyze_spread_arbitrage(market: dict) -> dict:
    """Check if market has spread arbitrage opportunity"""
    # Simplified - need to fetch actual order book
    yes_price = market.get("yes_price", 0)
    no_price = market.get("no_price", 0)
    
    if yes_price == 0 or no_price == 0:
        # Try to get from description or other fields
        return None
    
    spread = calculate_spread(yes_price, no_price)
    
    if is_arbitrage_opportunity(yes_price, no_price, threshold=0.95):
        profit_info = estimate_profit(yes_price, no_price, 100)
        return {
            "strategy": "SPREAD",
            "market_id": market.get("id"),
            "question": market.get("question"),
            "yes_price": yes_price,
            "no_price": no_price,
            "spread": spread,
            "profit_pct": profit_info.get("profit_pct", 0),
            "action": "BUY_BOTH",
            "profit_per_100": profit_info.get("profit", 0)
        }
    
    return None


def analyze_prediction_edge(market: dict, engine: PredictionEngine, config: dict) -> dict:
    """Check if market has prediction edge vs NOAA"""
    # Por ahora es placeholder - necesita implementar NOAA API real
    return None


def run_scan(pm_client: PolymarketClient, config: dict):
    """Run one scan cycle"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "spread_opportunities": [],
        "prediction_opportunities": [],
        "markets_checked": 0
    }
    
    markets = get_all_weather_markets(pm_client)
    results["markets_checked"] = len(markets)
    
    engine = PredictionEngine(threshold=config.get("prediction_threshold", 0.08))
    
    # Analyze each market
    for market in markets:
        # Spread arbitrage
        spread_result = analyze_spread_arbitrage(market)
        if spread_result:
            results["spread_opportunities"].append(spread_result)
        
        # Prediction edge
        pred_result = analyze_prediction_edge(market, engine, config)
        if pred_result:
            results["prediction_opportunities"].append(pred_result)
    
    # Log results
    logger.info(f"Scanned {results['markets_checked']} markets")
    
    if results["spread_opportunities"]:
        logger.info(f"Found {len(results['spread_opportunities'])} SPREAD opportunities:")
        for opp in results["spread_opportunities"][:5]:
            logger.info(f"  - {opp['question'][:60]}... Spread: ${opp['spread']:.2f}")
    
    if results["prediction_opportunities"]:
        logger.info(f"Found {len(results['prediction_opportunities'])} PREDICTION opportunities:")
        for opp in results["prediction_opportunities"][:5]:
            logger.info(f"  - {opp['question'][:60]}...")
    
    # Save to log file
    log_file = Path("logs") / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_file.parent.mkdir(exist_ok=True)
    with open(log_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Climate Arbitrage Bot v2.0")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper", help="Trading mode")
    parser.add_argument("--loop", action="store_true", help="Run in loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    parser.add_argument("--cities", nargs="+", help="Filter by cities")
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.info("Copy config.example.yaml to config.yaml")
        return
    
    config = load_config(config_path)
    config["mode"] = args.mode
    
    # Initialize clients
    pm_client = PolymarketClient(
        api_key=config.get("polymarket", {}).get("api_key")
    )
    
    weather_client = NOAAClient()
    
    logger.info(f"Starting Climate Arbitrage Bot (mode: {args.mode})")
    
    def scan_once():
        try:
            return run_scan(pm_client, config)
        except Exception as e:
            logger.error(f"Error in scan: {e}")
            return None
    
    if args.loop:
        logger.info(f"Running in loop (interval: {args.interval}s)")
        while True:
            try:
                scan_once()
                time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(args.interval)
    else:
        scan_once()


if __name__ == "__main__":
    main()
