"""
Polymarket API client
"""
import httpx


class PolymarketClient:
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.client = httpx.Client()
    
    def get_markets(self, cursor: str = None, limit: int = 100):
        """Get all markets - handles both old and new API formats"""
        endpoint = f"{self.BASE_URL}/markets"
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        resp = self.client.get(endpoint, headers=headers, params=params)
        data = resp.json()
        
        # Handle both old format (markets) and new format (data)
        if "data" in data:
            return {
                "markets": data["data"],
                "nextCursor": data.get("next_cursor")
            }
        return data
    
    def get_order_book(self, condition_id: str):
        """Get order book for a market"""
        endpoint = f"{self.BASE_URL}/orderbook"
        params = {"conditionId": condition_id}
        resp = self.client.get(endpoint, params=params)
        return resp.json()
    
    def get_contracts(self, condition_id: str):
        """Get YES/NO contracts for a condition"""
        endpoint = f"{self.BASE_URL}/contracts"
        params = {"conditionId": condition_id}
        resp = self.client.get(endpoint, params=params)
        return resp.json()
    
    def place_order(self, contract_id: str, side: str, amount: float, price: float):
        """Place an order"""
        endpoint = f"{self.BASE_URL}/orders"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "contractId": contract_id,
            "side": side,  # "Buy" or "Sell"
            "amount": amount,
            "price": price
        }
        resp = self.client.post(endpoint, json=data, headers=headers)
        return resp.json()
    
    def get_positions(self, address: str):
        """Get positions for an address"""
        endpoint = f"{self.BASE_URL}/positions"
        params = {"address": address}
        resp = self.client.get(endpoint, params=params)
        return resp.json()


def get_weather_markets(markets: list) -> list:
    """Filter markets related to weather"""
    weather_keywords = ["weather", "temperature", "rain", "snow", "storm", "hurricane"]
    
    weather_markets = []
    for market in markets:
        question = market.get("question", "").lower()
        description = market.get("description", "").lower()
        
        if any(kw in question or kw in description for kw in weather_keywords):
            weather_markets.append(market)
    
    return weather_markets


def get_temperature_events(client, limit: int = 100) -> list:
    """
    Get temperature-related events from Polymarket API
    Uses tag_id 103040 for Daily Temperature
    """
    # First get all temperature events
    events = []
    cursor = None
    
    while len(events) < limit:
        params = {
            "tag_id": "103040",  # Daily Temperature tag
            "active": "true",
            "closed": "false",
            "limit": min(100, limit - len(events))
        }
        if cursor:
            params["cursor"] = cursor
            
        resp = client.get("https://gamma-api.polymarket.com/events", params=params)
        if resp.status_code != 200:
            break
            
        page = resp.json()
        if not page:
            break
            
        events.extend(page)
        cursor = page[-1].get("slug") if page else None
        if not cursor:
            break
    
    return events


def get_markets_from_events(events: list) -> list:
    """Extract all markets from events"""
    markets = []
    for event in events:
        event_markets = event.get("markets", [])
        for m in event_markets:
            m["event_title"] = event.get("title", "")
            m["event_slug"] = event.get("slug", "")
            markets.append(m)
    return markets


def calculate_spread(yes_price: float, no_price: float) -> float:
    """Calculate the total spread cost"""
    return yes_price + no_price


def is_arbitrage_opportunity(yes_price: float, no_price: float, threshold: float = 0.95) -> bool:
    """Check if spread is below threshold (arbitrage opportunity)"""
    spread = calculate_spread(yes_price, no_price)
    return spread < threshold
