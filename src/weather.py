"""
Weather data providers - NOAA, Wunderground, etc.
"""
import httpx
import re
from datetime import datetime, timedelta


class WeatherClient:
    """Base class for weather data"""
    
    def get_forecast(self, location: str, date: str = None) -> dict:
        raise NotImplementedError


class NOAAClient(WeatherClient):
    """NOAA National Weather Service API (free, no key required)"""
    
    def __init__(self):
        self.base_url = "https://api.weather.gov"
        self.client = httpx.Client(timeout=30.0, headers={
            "User-Agent": "ClimateArbitrageBot/1.0"
        })
    
    def get_grid_point(self, lat: float, lon: float) -> dict:
        """Get the grid point metadata for a location"""
        points_url = f"{self.base_url}/points/{lat},{lon}"
        resp = self.client.get(points_url)
        
        if resp.status_code != 200:
            return {"error": f"Failed to get grid point: {resp.status_code}"}
        
        return resp.json()
    
    def get_forecast(self, lat: float, lon: float, days: int = 14) -> dict:
        """
        Get forecast from NOAA
        
        Args:
            lat: Latitude
            lon: Longitude
            days: Number of days to forecast
        
        Returns:
            Dict with forecast data
        """
        # Get grid point
        grid = self.get_grid_point(lat, lon)
        if "error" in grid:
            return grid
        
        # Get forecast URL
        forecast_url = grid["properties"]["forecast"]
        
        # Get forecast
        resp = self.client.get(forecast_url)
        if resp.status_code != 200:
            return {"error": f"Failed to get forecast: {resp.status_code}"}
        
        data = resp.json()
        periods = data.get("periods", [])[:days * 2]  # 2 periods per day
        
        return {
            "source": "NOAA",
            "location": f"{lat},{lon}",
            "grid": grid["properties"],
            "periods": periods,
            "raw": data
        }
    
    def get_hourly(self, lat: float, lon: float, hours: int = 48) -> dict:
        """Get hourly forecast"""
        grid = self.get_grid_point(lat, lon)
        if "error" in grid:
            return grid
        
        hourly_url = grid["properties"]["forecastHourly"]
        resp = self.client.get(hourly_url)
        
        if resp.status_code != 200:
            return {"error": f"Failed to get hourly: {resp.status_code}"}
        
        data = resp.json()
        periods = data.get("periods", [])[:hours]
        
        return {
            "source": "NOAA",
            "location": f"{lat},{lon}",
            "periods": periods,
            "raw": data
        }
    
    def get_temperature_probability(self, lat: float, lon: float, threshold: float, 
                                   operator: str, date: str = None) -> dict:
        """
        Calculate probability of temperature exceeding/falling below a threshold
        
        Args:
            lat: Latitude
            lon: Longitude
            threshold: Temperature threshold (Celsius)
            operator: '>' or '<'
            date: Optional specific date (YYYY-MM-DD)
        
        Returns:
            Dict con probability y details
        """
        # Get forecast
        forecast = self.get_forecast(lat, lon, days=14)
        
        if "error" in forecast:
            return {"probability": None, "error": forecast["error"]}
        
        periods = forecast.get("periods", [])
        
        # Find matching periods
        temps = []
        for period in periods:
            # Parse temperature (NOAA usa Fahrenheit en US, Celsius en otros)
            temp_str = period.get("temperature", "")
            unit = period.get("temperatureUnit", "F")
            
            # Convert to Celsius if needed
            if unit == "F":
                temp_c = (int(temp_str) - 32) * 5/9
            else:
                temp_c = int(temp_str)
            
            # Get date
            start_time = period.get("startTime", "")
            period_date = start_time[:10] if start_time else None
            
            # Filter by date if specified
            if date and period_date != date:
                continue
            
            temps.append({
                "date": period_date,
                "temp": temp_c,
                "temp_f": int(temp_str),
                "description": period.get("shortForecast", "")
            })
        
        if not temps:
            return {"probability": None, "error": "No forecast data found"}
        
        # Calculate probability
        if operator == ">":
            exceeds = sum(1 for t in temps if t["temp"] > threshold)
        elif operator == "<":
            exceeds = sum(1 for t in temps if t["temp"] < threshold)
        else:
            return {"probability": None, "error": f"Invalid operator: {operator}"}
        
        probability = exceeds / len(temps) if temps else 0
        
        return {
            "probability": probability,
            "threshold": threshold,
            "operator": operator,
            "matching_periods": exceeds,
            "total_periods": len(temps),
            "sample_temps": temps[:5],  # First 5 for reference
            "unit": "celsius"
        }


class WundergroundClient(WeatherClient):
    """Weather Underground (source of Polymarket resolution)"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.weather.com/v3"
        self.client = httpx.Client(timeout=30.0)
    
    def get_forecast(self, location: str, date: str = None) -> dict:
        """Get forecast from Wunderground"""
        if not self.api_key:
            return {"error": "API key required"}
        
        endpoint = f"{self.base_url}/weather/forecast"
        params = {
            "location": location,
            "apiKey": self.api_key,
            "language": "en-US",
            "units": "m"
        }
        
        resp = self.client.get(endpoint, params=params)
        
        if resp.status_code != 200:
            return {"error": f"API error: {resp.status_code}"}
        
        return resp.json()


# City to coordinates mapping (NOAA usa lat/lon)
CITY_COORDS = {
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "new york": (40.7128, -74.0060),
    "tokyo": (35.6762, 139.6503),
    "sydney": (-33.8688, 151.2093),
    "miami": (25.7617, -80.1918),
    "chicago": (41.8781, -87.6298),
    "seoul": (37.5665, 126.9780),
    "berlin": (52.5200, 13.4050),
    "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964),
    "buenos aires": (-34.6037, -58.3816),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "hong kong": (22.3193, 114.1694),
    "boston": (42.3601, -71.0589),
    "los angeles": (34.0522, -118.2437),
    "san francisco": (37.7749, -122.4194),
    "toronto": (43.6532, -79.3832),
    "mexico city": (19.4326, -99.1332),
    "sao paulo": (-23.5505, -46.6333),
    "lisbon": (38.7223, -9.1393),
    "amsterdam": (52.3676, 4.9041),
    "vienna": (48.2082, 16.3738),
    "prague": (50.0755, 14.4378),
    "warsaw": (52.2297, 21.0122),
    "budapest": (47.4979, 19.0402),
    "athens": (37.9838, 23.7275),
    "istanbul": (41.0082, 28.9784),
    "moscow": (55.7558, 37.6173),
    "cairo": (30.0444, 31.2357),
    "tel aviv": (32.0853, 34.7818),
    "bangkok": (13.7563, 100.5018),
    "jakarta": (-6.2088, 106.8456),
    "manila": (14.5995, 120.9842),
    "kuala lumpur": (3.1390, 101.6869),
    "shanghai": (31.2304, 121.4737),
    "beijing": (39.9042, 116.4074),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.7041, 77.1025),
    "karachi": (24.8607, 67.0011),
    "dhaka": (23.8103, 90.4125),
    "nairobi": (-1.2921, 36.8219),
    "johannesburg": (-26.2041, 28.0473),
    "cape town": (-33.9249, 18.4241),
    "lagos": (6.5244, 3.3792),
    "cairo": (30.0444, 31.2357),
    "addis ababa": (8.9806, 38.7578),
}


def get_coords_for_city(city: str) -> tuple:
    """Get lat/lon for a city name"""
    city_lower = city.lower()
    return CITY_COORDS.get(city_lower)


def get_city_name_variations(city: str) -> list:
    """Get variations of city name for matching"""
    variations = [city.lower()]
    
    # Common variations
    if "new york" in city.lower():
        variations.extend(["nyc", "ny", "new york city"])
    elif "buenos aires" in city.lower():
        variations.extend(["buenos aires", "ba"])
    elif "los angeles" in city.lower():
        variations.extend(["la", "los angeles"])
    elif "san francisco" in city.lower():
        variations.extend(["sf", "san francisco"])
    elif "sao paulo" in city.lower():
        variations.extend(["sp", "sao paulo"])
    
    return variations


# Probabilidad histórica de precipitación por ciudad/mes (para markets de lluvia)
PRECIP_HISTORICAL = {
    "london": {"jan": 0.5, "feb": 0.45, "mar": 0.4, "apr": 0.35, "may": 0.35, "jun": 0.35,
               "jul": 0.3, "aug": 0.35, "sep": 0.4, "oct": 0.5, "nov": 0.55, "dec": 0.55},
    "paris": {"jan": 0.45, "feb": 0.4, "mar": 0.35, "apr": 0.3, "may": 0.35, "jun": 0.3,
              "jul": 0.25, "aug": 0.25, "sep": 0.3, "oct": 0.4, "nov": 0.45, "dec": 0.5},
    "new york": {"jan": 0.3, "feb": 0.3, "mar": 0.35, "apr": 0.35, "may": 0.4, "jun": 0.4,
                 "jul": 0.35, "aug": 0.35, "sep": 0.35, "oct": 0.35, "nov": 0.35, "dec": 0.35},
}


def get_historical_precip_probability(city: str, month: int = None) -> float:
    """Get historical precipitation probability for a city"""
    if month is None:
        month = datetime.now().month
    
    city_lower = city.lower()
    month_names = ["jan", "feb", "mar", "apr", "may", "jun", 
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    month_key = month_names[month - 1]
    
    # Try exact match first
    if city_lower in PRECIP_HISTORICAL:
        return PRECIP_HISTORICAL[city_lower].get(month_key, 0.3)
    
    # Try partial match
    for city_key, data in PRECIP_HISTORICAL.items():
        if city_key in city_lower or city_lower in city_key:
            return data.get(month_key, 0.3)
    
    # Default
    return 0.3
