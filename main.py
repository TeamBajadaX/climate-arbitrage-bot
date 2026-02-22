#!/usr/bin/env python3
"""
Climate Arbitrage Bot - Main Entry Point v3.0
Soporta:
1. Spread Arbitrage (YES + NO < $1)
2. Prediction Edge (NOAA vs Market) - CON NOAA API REAL
3. Trade Manager con 6 reglas de cierre + Kelly Exit
4. Paper Trading para testing
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
from trade_manager import TradeManager, CloseRule, KellyExit

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


def get_market_price(market: dict) -> tuple:
    """Extract YES and NO prices from market"""
    # Try different fields
    yes_price = market.get("yes_price")
    no_price = market.get("no_price")
    
    if yes_price is None:
        # Try outcomePrices
        outcome_prices = market.get("outcomePrices")
        if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
            try:
                yes_price = float(outcome_prices[0])
                no_price = float(outcome_prices[1])
            except:
                pass
    
    # Handle string prices
    if isinstance(yes_price, str):
        try:
            yes_price = float(yes_price)
            no_price = float(no_price)
        except:
            return None, None
    
    return yes_price, no_price


def analyze_spread_arbitrage(market: dict, threshold: float = 0.95) -> dict:
    """Check if market has spread arbitrage opportunity"""
    yes_price, no_price = get_market_price(market)
    
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
                "noaa_method": noaa.get("method"),
                "edge": rec.get("edge"),
                "action": rec.get("action"),
                "reason": rec.get("reason"),
                "confidence": rec.get("confidence", 0)
            }
    except Exception as e:
        logger.debug(f"Error analyzing prediction: {e}")
    
    return None


def should_open_position(opportunity: dict, config: dict, trade_manager: TradeManager) -> bool:
    """
    Determinar si debemos abrir una posición basado en:
    - Kelly criterion
    - Configuración
    - Posiciones existentes
    """
    # Check if we already have a position for this market
    market_id = opportunity.get("market_id")
    if market_id in trade_manager.positions:
        logger.debug(f"Ya tenemos posición en {market_id}")
        return False
    
    # Check min confidence
    min_confidence = config.get("min_confidence", 0.55)
    confidence = opportunity.get("confidence", 0)
    
    if confidence < min_confidence:
        logger.debug(f"Confidence {confidence:.2f} < {min_confidence}")
        return False
    
    # Check min edge
    min_edge = config.get("min_edge", 0.05)
    edge = abs(opportunity.get("edge", 0))
    if edge < min_edge:
        logger.debug(f"Edge {edge:.1%} < {min_edge}")
        return False
    
    return True


def calculate_position_size(config: dict, opportunity: dict, win_rate: float = 0.6) -> float:
    """Calcular tamaño de posición usando Kelly criterion"""
    bankroll = config.get("trading", {}).get("bankroll", 500)
    kelly_fraction = config.get("trading", {}).get("kelly_fraction", 0.25)
    min_bet = config.get("trading", {}).get("min_bet", 10)
    max_bet = config.get("trading", {}).get("max_bet", 100)
    max_position_pct = config.get("trading", {}).get("max_position_pct", 0.10)
    
    # Calculate Kelly
    odds = 1.0 / opportunity.get("market_price_yes", 0.5)  # Odds implícitas
    kelly_pct = capped_kelly(win_rate, odds, kelly_fraction)
    
    # Apply position limits
    max_by_pct = bankroll * max_position_pct
    
    size = bankroll * kelly_pct
    size = max(min_bet, min(size, max_bet, max_by_pct))
    
    return size


def run_scan(pm_client: PolymarketClient, config: dict, trade_manager: TradeManager):
    """Run one scan cycle"""
    results = {
        "timestamp": datetime.now().isoformat(),
        "spread_opportunities": [],
        "prediction_opportunities": [],
        "new_positions": [],
        "closed_positions": [],
        "markets_checked": 0,
    }
    
    markets = get_all_weather_markets(pm_client)
    results["markets_checked"] = len(markets)
    
    # Initialize prediction engine
    engine = PredictionEngine(
        threshold=config.get("prediction_threshold", 0.08),
        use_cache=True
    )
    
    spread_threshold = config.get("spread_threshold", 0.95)
    mode = config.get("mode", "paper")
    
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
                
                # Abrir posición si es paper mode y hay oportunidad
                if mode == "paper" and should_open_position(pred_result, config, trade_manager):
                    # Simular apertura
                    size = calculate_position_size(config, pred_result)
                    position = trade_manager.open_position(
                        market_id=pred_result["market_id"],
                        side=pred_result["action"],
                        amount=size,
                        price=pred_result["market_price_yes"],
                        question=pred_result["question"],
                        noaa_prob=pred_result.get("noaa_probability")
                    )
                    if position:
                        results["new_positions"].append({
                            "market_id": pred_result["market_id"],
                            "side": pred_result["action"],
                            "amount": size,
                            "question": pred_result["question"][:50]
                        })
            
            # Update existing positions
            yes_price, no_price = get_market_price(market)
            if yes_price:
                triggered = trade_manager.update_position(
                    market_id=market.get("id"),
                    current_price=yes_price,
                    noaa_prob=pred_result.get("noaa_probability") if pred_result else None
                )
                
                # Cerrar posiciones si hay reglas triggeredas
                for rule in triggered:
                    pos = trade_manager.close_position(
                        market_id=market.get("id"),
                        reason=f"{rule.value} triggered",
                        price=yes_price
                    )
                    if pos:
                        results["closed_positions"].append({
                            "market_id": market.get("id"),
                            "reason": rule.value,
                            "profit": pos.get("profit", 0)
                        })
                    
        except Exception as e:
            logger.debug(f"Error on market {market.get('id')}: {e}")
    
    # Clear cache after scan
    engine.clear_cache()
    
    # Log results
    logger.info(f"=== SCAN COMPLETE ===")
    logger.info(f"Markets checked: {results['markets_checked']}")
    logger.info(f"Spread opportunities: {len(results['spread_opportunities'])}")
    logger.info(f"Prediction opportunities: {len(results['prediction_opportunities'])}")
    logger.info(f"New positions: {len(results['new_positions'])}")
    logger.info(f"Closed positions: {len(results['closed_positions'])}")
    
    # Mostrar mejores oportunidades
    if results["spread_opportunities"]:
        logger.info(f"--- TOP SPREAD ---")
        for opp in sorted(results["spread_opportunities"], key=lambda x: x.get("profit_per_100", 0), reverse=True)[:3]:
            logger.info(f"  {opp['question'][:50]}... Spread: ${opp['spread']:.2f}")
    
    if results["prediction_opportunities"]:
        logger.info(f"--- TOP PREDICTION ---")
        for opp in sorted(results["prediction_opportunities"], key=lambda x: x.get("confidence", 0), reverse=True)[:5]:
            logger.info(f"  {opp['action']} {opp.get('city', '?')} | Edge: {opp.get('edge', 0):.1%}")
    
    # Save logs
    save_logs(results, trade_manager)
    
    return results


def save_logs(scan_results: dict, trade_manager: TradeManager):
    """Guardar logs de la sesión"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Summary scan
    scan_file = log_dir / f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    summary = {
        "timestamp": scan_results["timestamp"],
        "markets_checked": scan_results["markets_checked"],
        "spread_count": len(scan_results["spread_opportunities"]),
        "prediction_count": len(scan_results["prediction_opportunities"]),
        "new_positions": scan_results["new_positions"],
    }
    
    with open(scan_file, 'a') as f:
        f.write(json.dumps(summary) + "\n")
    
    # Full trade manager state
    state_file = log_dir / f"positions_{datetime.now().strftime('%Y%m%d')}.json"
    state = trade_manager.get_position_summary()
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Climate Arbitrage Bot v3.0")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper", help="Trading mode")
    parser.add_argument("--loop", action="store_true", help="Run in loop")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds")
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.info("Copy config.example.yaml to config.yaml")
        return
    
    config = load_config(config_path)
    config["mode"] = args.mode
    
    # Initialize clients and managers
    pm_client = PolymarketClient(
        api_key=config.get("polymarket", {}).get("api_key")
    )
    
    # Trade manager con todas las reglas
    trade_config = {
        "stop_loss_pct": config.get("stop_loss_pct", 0.10),
        "profit_take_pct": config.get("profit_take_pct", 0.30),
        "trailing_stop_pct": config.get("trailing_stop_pct", 0.15),
        "hours_before_close": config.get("hours_before_close", 1),
        "edge_loss_threshold": config.get("edge_loss_threshold", 0.02),
    }
    trade_manager = TradeManager(trade_config)
    
    # Kelly exit manager
    kelly_exit = KellyExit(initial_kelly=config.get("trading", {}).get("kelly_fraction", 0.25))
    
    logger.info(f"=== Climate Arbitrage Bot v3.0 ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Rules enabled:")
    for rule in CloseRule:
        logger.info(f"  - {rule.value}")
    logger.info(f"Spread threshold: {config.get('spread_threshold', 0.95)}")
    logger.info(f"Prediction threshold: {config.get('prediction_threshold', 0.08)}")
    logger.info(f"Stop loss: {config.get('stop_loss_pct', 0.10):.0%}")
    logger.info(f"Profit take: {config.get('profit_take_pct', 0.30):.0%}")
    logger.info(f"Trailing stop: {config.get('trailing_stop_pct', 0.15):.0%}")
    
    def scan_once():
        try:
            return run_scan(pm_client, config, trade_manager)
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
                # Print final summary
                summary = trade_manager.get_position_summary()
                logger.info(f"=== FINAL SUMMARY ===")
                logger.info(f"Total positions: {summary['total_positions']}")
                logger.info(f"Open: {summary['open']}, Closed: {summary['closed']}")
                logger.info(f"Total profit: ${summary['total_profit']:.2f}")
                logger.info(f"Rule performance: {summary['rule_performance']}")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(args.interval)
    else:
        scan_once()


if __name__ == "__main__":
    main()
