#!/usr/bin/env python3
"""
Climate Arbitrage Bot - Main Entry Point v2.1
Soporta:
1. Spread Arbitrage (YES + NO < $1)
2. Prediction Edge (NOAA vs Market) - NOW WITH REAL NOAA DATA
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
        try:
            page = pm_client.get_markets(cursor=cursor, limit=200)
            if not page or "markets" not in page:
                break
            
            markets = page["markets"]
            all_markets.extend(markets)
            
            cursor = page.get("nextCursor")
            if not cursor:
                break
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            break
    
    # Filter for weather
    weather = get_weather_markets(all_markets)
    logger.info(f"Found {len(weather)} weather markets")
    logger.info(f"Total markets checked: {len(all_markets)}")
    
    return weather


def analyze_spread_arbitrage(market: dict, threshold: float = 0.95) -> dict:
    """Check if market has spread arbitrage opportunity"""
    # Get prices from different possible fields
    yes_price = market.get("yes_price") or market.get("outcomePrices", [0, 1])[0]
    no_price = market.get("no_price") or market.get("outcomePrices", [0, 1])[1]
    
    # Handle string prices
    if isinstance(yes_price, str):
        try:
            yes_price = float(yes_price)
            no_price = float(no_price)
        except:
            return None
    
    if yes_price is None or no_price is None or yes_price == 0:
        return None
    
    spread = calculate_spread(yes_price, no_price)
    
    if is_arbitrage_opportunity(yes_price, no_price, threshold):
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
    try:
        analysis = engine.analyze_market(market)
        
        if analysis.get("trade_recommendation"):
            rec = analysis["trade_recommendation"]
            parsed = analysis["parsed"]
            noaa = analysis.get("noaa_data", {})
            
            return {
                "strategy": "PREDICTION",
                "market_id": market.get("id"),
                "question": market.get("question"),
                "city": parsed.get("city"),
                "variable": parsed.get("variable"),
                "threshold": parsed.get("threshold"),
                "operator": parsed.get("operator"),
                "market_price_yes": analysis["market_price_yes"],
                "noaa_probability": noaa.get("probability"),
                "edge": rec.get("edge"),
                "action": rec.get("action"),
                "reason": rec.get("reason"),
                "confidence": rec.get("confidence", 0)
            }
    except Exception as e:
        logger.debug(f"Error analyzing prediction: {e}")
    
    return None


def run_scan(pm_client: PolymarketClient, config: dict):
    """Run one scan cycle"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "spread_opportunities": [],
        "prediction_opportunities": [],
        "markets_checked": 0,
        "markets_with_error": 0
    }
    
    markets = get_all_weather_markets(pm_client)
    results["markets_checked"] = len(markets)
    
    # Initialize prediction engine
    engine = PredictionEngine(
        threshold=config.get("prediction_threshold", 0.08),
        use_cache=True
    )
    
    spread_threshold = config.get("spread_threshold", 0.95)
    
    # Analyze each market
    for i, market in enumerate(markets):
        if i % 50 == 0:
            logger.info(f"Progress: {i}/{len(markets)}")
        
        try:
            # Spread arbitrage
            spread_result = analyze_spread_arbitrage(market, spread_threshold)
            if spread_result:
                results["spread_opportunities"].append(spread_result)
            
            # Prediction edge
            pred_result = analyze_prediction_edge(market, engine, config)
            if pred_result:
                results["prediction_opportunities"].append(pred_result)
                
        except Exception as e:
            results["markets_with_error"] += 1
            logger.debug(f"Error on market {market.get('id')}: {e}")
    
    # Clear cache after scan
    engine.clear_cache()
    
    # Log results
    logger.info(f"=== SCAN COMPLETE ===")
    logger.info(f"Markets checked: {results['markets_checked']}")
    logger.info(f"Spread opportunities: {len(results['spread_opportunities'])}")
    logger.info(f"Prediction opportunities: {len(results['prediction_opportunities'])}")
    
    if results["spread_opportunities"]:
        logger.info(f"--- TOP SPREAD OPPORTUNITIES ---")
        for opp in sorted(results["spread_opportunities"], key=lambda x: x.get("profit_per_100", 0), reverse=True)[:3]:
            logger.info(f"  {opp['question'][:50]}... Spread: ${opp['spread']:.2f} Profit: ${opp['profit_per_100']:.2f}")
    
    if results["prediction_opportunities"]:
        logger.info(f"--- TOP PREDICTION OPPORTUNITIES ---")
        for opp in sorted(results["prediction_opportunities"], key=lambda x: x.get("confidence", 0), reverse=True)[:5]:
            logger.info(f"  {opp['question'][:50]}...")
            logger.info(f"    Action: {opp['action']} | Edge: {opp.get('edge', 0):.1%} | Confidence: {opp.get('confidence', 0):.2f}x")
    
    # Save to log file
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Don't save full log each time, just summary
    summary = {
        "timestamp": results["timestamp"],
        "markets_checked": results["markets_checked"],
        "spread_count": len(results["spread_opportunities"]),
        "prediction_count": len(results["prediction_opportunities"]),
        "spread_opportunities": results["spread_opportunities"][:5],  # Top 5
        "prediction_opportunities": results["prediction_opportunities"][:10]  # Top 10
    }
    
    with open(log_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Log saved to {log_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Climate Arbitrage Bot v2.1")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper", help="Trading mode")
    parser.add_argument("--loop", action="store_true", help="Run in loop")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds (default 5 min)")
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
    
    logger.info(f"Starting Climate Arbitrage Bot v2.1 (mode: {args.mode})")
    logger.info(f"Spread threshold: {config.get('spread_threshold', 0.95)}")
    logger.info(f"Prediction threshold: {config.get('prediction_threshold', 0.08)}")
    
    def scan_once():
        try:
            return run_scan(pm_client, config)
        except Exception as e:
            logger.error(f"Error in scan: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
