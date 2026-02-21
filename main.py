#!/usr/bin/env python3
"""
Climate Arbitrage Bot - Main Entry Point
"""
import argparse
import logging
import yaml
import time
from pathlib import Path

from polymarket import PolymarketClient, get_weather_markets, calculate_spread, is_arbitrage_opportunity
from weather import NOAAClient, get_coords_for_city
from arbitrage import ArbitrageDetector, estimate_profit


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def scan_markets(pm_client: PolymarketClient, cities: list = None) -> list:
    """
    Scan Polymarket for weather-related markets
    
    Args:
        pm_client: Polymarket API client
        cities: Optional list of cities to filter
    
    Returns:
        List of weather markets
    """
    logger.info("Fetching markets from Polymarket...")
    markets = pm_client.get_markets(limit=500)
    
    weather_markets = get_weather_markets(markets)
    logger.info(f"Found {len(weather_markets)} weather markets")
    
    if cities:
        # Filter by cities
        filtered = []
        cities_lower = [c.lower() for c in cities]
        for market in weather_markets:
            q = market.get("question", "").lower()
            if any(c in q for c in cities_lower):
                filtered.append(market)
        weather_markets = filtered
        logger.info(f"Filtered to {len(weather_markets)} markets for cities: {cities}")
    
    return weather_markets


def analyze_market(market: dict, pm_client: PolymarketClient) -> dict:
    """Analyze a single market for arbitrage opportunities"""
    # This is a simplified version - real implementation needs
    # to fetch order book for each contract
    
    analysis = {
        "market_id": market.get("id"),
        "question": market.get("question"),
        "volume": market.get("volume"),
        "liquidity": market.get("liquidity"),
        "end_date": market.get("endDate"),
        "opportunities": []
    }
    
    return analysis


def main():
    parser = argparse.ArgumentParser(description="Climate Arbitrage Bot")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--cities", nargs="+", help="Cities to monitor")
    parser.add_argument("--loop", action="store_true", help="Run in loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in seconds")
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.info("Copy config.example.yaml to config.yaml")
        return
    
    config = load_config(config_path)
    
    # Initialize clients
    pm_client = PolymarketClient(
        api_key=config.get("polymarket", {}).get("api_key")
    )
    
    weather_client = NOAAClient()
    detector = ArbitrageDetector(
        spread_threshold=config.get("spread_threshold", 0.95)
    )
    
    cities = args.cities or []
    
    logger.info("Starting Climate Arbitrage Bot...")
    logger.info(f"Monitoring cities: {cities or 'All'}")
    
    def scan_once():
        markets = scan_markets(pm_client, cities)
        
        if not markets:
            logger.warning("No weather markets found")
            return
        
        for market in markets:
            analysis = analyze_market(market, pm_client)
            logger.info(f"Market: {analysis['question']}")
            logger.info(f"  Volume: ${analysis.get('volume', 'N/A')}")
    
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
