"""
Arbitrage detection logic
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ArbitrageDetector:
    """Detect arbitrage opportunities in Polymarket binary markets"""
    
    def __init__(self, spread_threshold: float = 0.95):
        self.spread_threshold = spread_threshold
    
    def check_market(self, market: dict, current_temp: float = None) -> dict:
        """
        Check if a market has arbitrage opportunity
        
        Args:
            market: Market data from Polymarket
            current_temp: Current temperature from weather API (for comparison)
        
        Returns:
            dict with analysis results
        """
        result = {
            "market_id": market.get("id"),
            "question": market.get("question"),
            "arb_opportunity": False,
            "spread": None,
            "potential_profit": None,
            "edge": None,
            "recommendation": None
        }
        
        # Get YES and NO prices
        # Note: This depends on market structure in Polymarket
        # Need to fetch order book for actual prices
        
        # For now, return placeholder
        return result
    
    def calculate_edge(self, forecast_temp: float, market_price: float) -> float:
        """
        Calculate the edge between forecast and market price
        
        Args:
            forecast_temp: Temperature from NOAA
            market_price: Probability from Polymarket (0-1)
        
        Returns:
            Edge as percentage
        """
        # This is simplified - real implementation needs:
        # 1. Convert temp to probability (e.g., will temp exceed X?)
        # 2. Compare model probability vs market probability
        
        if market_price == 0:
            return 0
        
        edge = forecast_temp - market_price
        return edge
    
    def rank_opportunities(self, opportunities: list) -> list:
        """
        Rank opportunities by profit potential
        
        Args:
            opportunities: List of opportunity dicts
        
        Returns:
            Sorted list (best first)
        """
        sorted_opps = sorted(
            opportunities,
            key=lambda x: x.get("potential_profit", 0),
            reverse=True
        )
        return sorted_opps


def estimate_profit(yes_price: float, no_price: float, amount: float) -> float:
    """
    Estimate profit from arbitrage trade
    
    When YES + NO < $1, you can guarantee profit
    """
    spread = yes_price + no_price
    cost = amount * spread
    payout = amount  # When either side wins, you get $1 per share
    
    profit = payout - cost
    profit_pct = (profit / cost) * 100 if cost > 0 else 0
    
    return {
        "cost": cost,
        "payout": payout,
        "profit": profit,
        "profit_pct": profit_pct,
        "spread": spread,
        "is_arbitrage": spread < 1.0
    }
