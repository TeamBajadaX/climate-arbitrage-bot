"""
Weather data providers - NOAA, Wunderground, etc.
"""
import httpx
import os


class WeatherClient:
    """Base class for weather data"""
    
    def get_forecast(self, location: str, date: str) -> dict:
        raise NotImplementedError


class NOAAClient(WeatherClient):
    """NOAA National Weather Service API (free)"""
    
    def __init__(self):
        self.base_url = "https://api.weather.gov"
        self.client = httpx.Client(timeout=30.0)
    
    def get_forecast(self, lat: float, lon: float, date: str = None) -> dict:
        """
        Get forecast from NOAA
        Requires lat/lon, not city name
        """
        # First get the grid point
        points_url = f"{self.base_url}/points/{lat},{lon}"
        points_resp = self.client.get(points_url)
        
        if points_resp.status_code != 200:
            return {"error": f"Failed to get grid point: {points_resp.status_code}"}
        
        points_data = points_resp.json()
        forecast_url = points_data["properties"]["forecast"]
        
        # Then get the forecast
        forecast_resp = self.client.get(forecast_url)
        forecast_data = forecast_resp.json()
        
        return {
            "source": "NOAA",
            "location": f"{lat},{lon}",
            "forecast": forecast_data.get("periods", [])[:7],  # 7 days
            "raw": forecast_data
        }
    
    def get_hourly(self, lat: float, lon: float) -> dict:
        """Get hourly forecast"""
        points_url = f"{self.base_url}/points/{lat},{lon}"
        points_resp = self.client.get(points_url)
        points_data = points_resp.json()
        
        hourly_url = points_data["properties"]["forecastHourly"]
        hourly_resp = self.client.get(hourly_url)
        
        return hourly_resp.json()


class WundergroundClient(WeatherClient):
    """Weather Underground (source of Polymarket resolution)"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.weather.com/v3"
    
    def get_forecast(self, location: str, date: str = None) -> dict:
        """
        Get forecast - location can be city name or airport code
        Note: This is a placeholder, actual API needs key
        """
        if not self.api_key:
            return {"error": "API key required"}
        
        endpoint = f"{self.base_url}/weather/forecast"
        params = {
            "location": location,
            "apiKey": self.api_key,
            "language": "en-US",
            "units": "m"  # metric
        }
        
        resp = self.client.get(endpoint, params=params)
        return resp.json()


# City to coordinates mapping (common cities)
CITY_COORDS = {
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "new york": (40.7128, -74.0060),
    "tokyo": (35.6762, 139.6503),
    "seoul": (37.5665, 126.9780),
    "berlin": (52.5200, 13.4050),
    "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964),
    "sydney": (-33.8688, 151.2093),
    "dubai": (25.2048, 55.2708),
    "miami": (25.7617, -80.1918),
    "chicago": (41.8781, -87.6298),
    "buenos aires": (-34.6037, -58.3816),
}


def get_coords_for_city(city: str) -> tuple:
    """Get lat/lon for a city name"""
    city_lower = city.lower()
    return CITY_COORDS.get(city_lower)
