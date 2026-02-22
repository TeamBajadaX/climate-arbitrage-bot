"""
Weather data providers - NOAA, Open-Meteo (free), historical data
"""
import httpx
import re
from datetime import datetime, timedelta


class WeatherClient:
    """Base class for weather data"""
    
    def get_forecast(self, location: str, date: str = None) -> dict:
        raise NotImplementedError


# Historical average temperatures for major cities (Celsius) - February/March
TEMP_HISTORICAL = {
    "london": {"feb": (5, 10), "mar": (6, 12)},
    "paris": {"feb": (3, 10), "mar": (5, 13)},
    "munich": {"feb": (-2, 5), "mar": (2, 10)},
    "salzburg": {"feb": (-2, 6), "mar": (2, 11)},
    "vienna": {"feb": (0, 6), "mar": (4, 12)},
    "budapest": {"feb": (0, 7), "mar": (4, 13)},
    "prague": {"feb": (-1, 5), "mar": (3, 11)},
    "berlin": {"feb": (0, 6), "mar": (3, 11)},
    "madrid": {"feb": (5, 14), "mar": (7, 16)},
    "rome": {"feb": (6, 14), "mar": (8, 16)},
    "lisbon": {"feb": (10, 16), "mar": (11, 18)},
    "amsterdam": {"feb": (2, 8), "mar": (4, 11)},
    "new york": {"feb": (0, 8), "mar": (4, 12)},
    "miami": {"feb": (18, 26), "mar": (20, 27)},
    "chicago": {"feb": (-4, 4), "mar": (1, 10)},
    "seattle": {"feb": (5, 10), "mar": (7, 12)},
    "los angeles": {"feb": (12, 21), "mar": (13, 22)},
    "san francisco": {"feb": (10, 15), "mar": (11, 17)},
    "toronto": {"feb": (-5, 2), "mar": (-1, 7)},
    "buenos aires": {"feb": (18, 28), "mar": (16, 25)},
    "sydney": {"feb": (19, 26), "mar": (17, 24)},
    "tokyo": {"feb": (5, 12), "mar": (8, 15)},
    "seoul": {"feb": (-2, 7), "mar": (4, 13)},
    "ljubljana": {"feb": (1, 9), "mar": (5, 14)},
    "krakow": {"feb": (-2, 5), "mar": (2, 10)},
    "strasbourg": {"feb": (1, 8), "mar": (4, 12)},
}


class HistoricalWeatherClient(WeatherClient):
    """
    Weather client using historical averages
    Works for all cities globally
    """
    
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
    
    def get_forecast(self, location: str, date: str = None) -> dict:
        """Get historical weather data"""
        city = location.lower()
        
        if city not in TEMP_HISTORICAL:
            return {"error": f"City not found: {city}"}
        
        # Get current month
        month = datetime.now().month
        month_key = "feb" if month in [2, 3] else "mar"
        
        min_temp, max_temp = TEMP_HISTORICAL[city][month_key]
        avg_temp = (min_temp + max_temp) / 2
        
        return {
            "source": "historical",
            "city": city,
            "month": month_key,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "avg_temp": avg_temp,
            "note": "Using historical averages"
        }
    
    def get_temperature_probability(self, city: str, threshold_f: float, 
                                  operator: str, date: str = None) -> dict:
        """
        Calculate probability of temperature using historical data
        
        Args:
            city: City name
            threshold_f: Temperature threshold in Fahrenheit
            operator: '>' or '<'
            date: Optional date
        
        Returns:
            Dict con probability
        """
        city = city.lower()
        
        if city not in TEMP_HISTORICAL:
            return {"probability": None, "error": f"City not found: {city}"}
        
        # Convert F to C
        threshold_c = (threshold_f - 32) * 5/9
        
        # Get month
        month = datetime.now().month
        month_key = "feb" if month in [2, 3] else "mar"
        
        min_temp, max_temp = TEMP_HISTORICAL[city][month_key]
        
        # Simple probability based on historical range
        if operator == ">":
            if threshold_c < min_temp:
                probability = 1.0
            elif threshold_c > max_temp:
                probability = 0.0
            else:
                probability = (max_temp - threshold_c) / (max_temp - min_temp)
        else:  # <
            if threshold_c > max_temp:
                probability = 1.0
            elif threshold_c < min_temp:
                probability = 0.0
            else:
                probability = (threshold_c - min_temp) / (max_temp - min_temp)        
        return {
            "probability": probability,
            "threshold_c": threshold_c,
            "threshold_f": threshold_f,
            "operator": operator,
            "city": city,
            "historical_range": f"{min_temp}°C - {max_temp}°C",
            "method": "historical_average"
        }


# City coordinates mapping
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
    "lisbon": (38.7223, -9.1393),
    "amsterdam": (52.3676, 4.9041),
    "vienna": (48.2082, 16.3738),
    "prague": (50.0755, 14.4378),
    "warsaw": (52.2297, 21.0122),
    "budapest": (47.4979, 19.0402),
    "athens": (37.9838, 23.7275),
    "salzburg": (47.8095, 13.0550),
    "ljubljana": (46.0569, 14.5058),
    "krakow": (50.0647, 19.9450),
    "strasbourg": (48.5734, 7.7521),
    "seattle": (47.6062, -122.3321),
    "dallas": (32.7767, -96.7970),
    "atlanta": (33.7490, -84.3880),
    "ankara": (39.9334, 32.8597),
    "wellington": (-41.2865, 174.7762),
}


def get_coords_for_city(city: str) -> tuple:
    """Get lat/lon for a city name"""
    city_lower = city.lower()
    return CITY_COORDS.get(city_lower)


def get_historical_temp(city: str, month: int = None) -> tuple:
    """Get historical temperature range for a city"""
    if month is None:
        month = datetime.now().month
    
    month_key = "feb" if month in [2, 3] else "mar"
    city = city.lower()
    
    if city in TEMP_HISTORICAL:
        return TEMP_HISTORICAL[city].get(month_key, (5, 15))
    
    return (5, 15)  # Default


class OpenMeteoClient:
    """
    Open-Meteo API - Free weather forecasting API (no key required)
    Provides 7-day forecast for any location globally
    """
    
    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.client = httpx.Client(timeout=30.0)
    
    def get_forecast(self, lat: float, lon: float, days: int = 7) -> dict:
        """
        Get forecast from Open-Meteo
        
        Returns:
            Dict with daily forecasts including max/min temperature
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
            "forecast_days": days
        }
        
        resp = self.client.get(self.base_url, params=params)
        
        if resp.status_code != 200:
            return {"error": f"API error: {resp.status_code}"}
        
        data = resp.json()
        daily = data.get("daily", {})
        
        forecasts = []
        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        
        for i, date in enumerate(dates):
            forecasts.append({
                "date": date,
                "max_temp": max_temps[i] if i < len(max_temps) else None,
                "min_temp": min_temps[i] if i < len(min_temps) else None,
            })
        
        return {
            "source": "Open-Meteo",
            "lat": lat,
            "lon": lon,
            "forecasts": forecasts,
            "timezone": data.get("timezone")
        }
    
    def get_temperature_probability(self, lat: float, lon: float, threshold_f: float,
                                  operator: str, target_date: str = None) -> dict:
        """
        Calculate probability of temperature exceeding threshold
        
        Uses forecast + historical variance for probability estimation
        """
        forecast = self.get_forecast(lat, lon, days=7)
        
        if "error" in forecast:
            return {"probability": None, "error": forecast["error"]}
        
        # Convert F to C
        threshold_c = (threshold_f - 32) * 5/9
        
        forecasts = forecast.get("forecasts", [])
        
        if not forecasts:
            return {"probability": None, "error": "No forecast data"}
        
        # Find target date or use first available
        target_forecast = None
        if target_date:
            for f in forecasts:
                if target_date in f.get("date", ""):
                    target_forecast = f
                    break
        
        if not target_forecast:
            # Use the first forecast (tomorrow)
            target_forecast = forecasts[0]
        
        max_temp = target_forecast.get("max_temp")
        min_temp = target_forecast.get("min_temp")
        
        if max_temp is None or min_temp is None:
            return {"probability": None, "error": "No temperature data"}
        
        # Calculate probability based on forecast range and historical variance
        # Using a simple model: if threshold is below min, 100%; above max, 0%
        # Otherwise, interpolate with some variance
        import random
        variance = 3  # degrees Celsius of variance (historical weather variability)
        
        if operator == ">":
            if threshold_c < min_temp - variance:
                probability = 1.0
            elif threshold_c > max_temp + variance:
                probability = 0.0
            else:
                # Linear interpolation through the range + variance
                range_total = (max_temp + variance) - (min_temp - variance)
                position = (threshold_c - (min_temp - variance)) / range_total
                probability = max(0, min(1, 1 - position))
        else:  # operator == "<"
            if threshold_c > max_temp + variance:
                probability = 1.0
            elif threshold_c < min_temp - variance:
                probability = 0.0
            else:
                range_total = (max_temp + variance) - (min_temp - variance)
                position = (threshold_c - (min_temp - variance)) / range_total
                probability = max(0, min(1, position))
        
        return {
            "probability": probability,
            "threshold_c": threshold_c,
            "threshold_f": threshold_f,
            "operator": operator,
            "forecast_max_c": max_temp,
            "forecast_min_c": min_temp,
            "method": "openmeteo_forecast",
            "source": "Open-Meteo"
        }


# Historical precipitation probability by city/month
PRECIP_HISTORICAL = {
    "london": {"feb": 0.45, "mar": 0.40},
    "paris": {"feb": 0.40, "mar": 0.35},
    "new york": {"feb": 0.30, "mar": 0.35},
    "madrid": {"feb": 0.30, "mar": 0.30},
    "rome": {"feb": 0.35, "mar": 0.30},
    "berlin": {"feb": 0.35, "mar": 0.30},
    "amsterdam": {"feb": 0.45, "mar": 0.40},
    "vienna": {"feb": 0.35, "mar": 0.30},
    "budapest": {"feb": 0.30, "mar": 0.25},
    "munich": {"feb": 0.40, "mar": 0.35},
    "salzburg": {"feb": 0.40, "mar": 0.35},
    "ljubljana": {"feb": 0.35, "mar": 0.35},
    "krakow": {"feb": 0.35, "mar": 0.30},
    "strasbourg": {"feb": 0.40, "mar": 0.35},
    "prague": {"feb": 0.35, "mar": 0.30},
    "lisbon": {"feb": 0.30, "mar": 0.30},
    "athens": {"feb": 0.30, "mar": 0.25},
    "warsaw": {"feb": 0.35, "mar": 0.30},
    "seattle": {"feb": 0.50, "mar": 0.45},
    "miami": {"feb": 0.25, "mar": 0.25},
    "chicago": {"feb": 0.30, "mar": 0.35},
    "toronto": {"feb": 0.35, "mar": 0.35},
    "buenos aires": {"feb": 0.35, "mar": 0.35},
    "sydney": {"feb": 0.30, "mar": 0.35},
    "tokyo": {"feb": 0.30, "mar": 0.35},
    "seoul": {"feb": 0.25, "mar": 0.30},
}


def get_historical_precip_probability(city: str, month: int = None) -> float:
    """Get historical precipitation probability for a city"""
    if month is None:
        month = datetime.now().month
    
    month_names = ["jan", "feb", "mar", "apr", "may", "jun", 
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    month_key = month_names[month - 1]
    
    city_lower = city.lower()
    
    if city_lower in PRECIP_HISTORICAL:
        return PRECIP_HISTORICAL[city_lower].get(month_key, 0.35)
    
    # Default probability
    return 0.35
