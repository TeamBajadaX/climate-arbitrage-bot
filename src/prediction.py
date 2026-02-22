"""
Prediction Edge - Comparar NOAA forecasts vs Polymarket prices
"""
import logging
from datetime import datetime

from weather import NOAAClient, get_coords_for_city, get_historical_precip_probability

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Compara forecasts de NOAA vs precios de Polymarket
    para encontrar edges en la predicción
    """
    
    def __init__(self, threshold: float = 0.08, use_cache: bool = True):
        """
        Args:
            threshold: Diferencia mínima para considerar edge (default 8%)
            use_cache: Usar cache para evitar múltiples llamadas a NOAA
        """
        self.threshold = threshold
        self.noaa = NOAAClient()
        self.cache = {}  # Cache forecasts
        self.use_cache = use_cache
    
    def parse_market_question(self, question: str) -> dict:
        """
        Parse market question para extraer:
        - City
        - Variable (temperature, rain, snow)
        - Threshold value
        - Operator
        
        Example: "Will London exceed 25°C on Feb 25, 2026?"
        """
        question_lower = question.lower()
        
        result = {
            "city": None,
            "city_raw": None,
            "variable": None,
            "threshold": None,
            "operator": None,
            "date": None,
            "unit": "celsius"
        }
        
        # Cities - buscar la más larga primero para evitar partial matches
        cities = [
            "new york", "buenos aires", "san francisco", "los angeles", "sao paulo", 
            "cape town", "hong kong", "kuala lumpur", "new delhi", "tel aviv",
            "london", "paris", "tokyo", "sydney", "miami", "chicago", 
            "seoul", "berlin", "madrid", "rome", "dubai", "singapore"
        ]
        
        for city in cities:
            if city in question_lower:
                result["city"] = city.title()
                result["city_raw"] = city
                break
        
        # Variables
        if any(x in question_lower for x in ["°c", "celsius", "temperature"]):
            result["variable"] = "temperature"
        elif "rain" in question_lower:
            result["variable"] = "rain"
        elif "snow" in question_lower:
            result["variable"] = "snow"
        elif "storm" in question_lower:
            result["variable"] = "storm"
        elif "hurricane" in question_lower:
            result["variable"] = "hurricane"
        elif "flood" in question_lower:
            result["variable"] = "flood"
        
        # Operators
        if any(x in question_lower for x in ["exceed", "above", "higher than", "more than", "over"]):
            result["operator"] = ">"
        elif any(x in question_lower for x in ["fall below", "below", "lower than", "under", "less than"]):
            result["operator"] = "<"
        elif any(x in question_lower for x in ["hit", "reach", "be at"]):
            result["operator"] = "="
        
        # Units
        if "°f" in question_lower or "fahrenheit" in question_lower:
            result["unit"] = "fahrenheit"
        
        # Extract threshold value
        import re
        # Match numbers like 25, 25.5, etc.
        numbers = re.findall(r'\d+\.?\d*', question_lower)
        if numbers:
            result["threshold"] = float(numbers[0])
        
        # Extract date if present
        # Format: "Feb 25, 2026" or "February 25, 2026"
        date_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s*\d{4}', question_lower)
        if date_match:
            result["date"] = date_match.group(0)
        
        return result
    
    def get_noaa_prediction(self, parsed: dict) -> dict:
        """
        Obtener predicción de NOAA basada en la pregunta parseada
        
        Args:
            parsed: Dict del parse_market_question
        
        Returns:
            Dict con probability y details
        """
        city = parsed.get("city_raw")
        variable = parsed.get("variable", "temperature")
        threshold = parsed.get("threshold")
        operator = parsed.get("operator", ">")
        date = parsed.get("date")
        unit = parsed.get("unit", "celsius")
        
        if not city:
            return {"probability": None, "error": "City not found in question"}
        
        # Get coordinates
        coords = get_coords_for_city(city)
        if not coords:
            return {"probability": None, "error": f"No coordinates for city: {city}"}
        
        lat, lon = coords
        
        # Generate cache key
        cache_key = f"{city}_{variable}_{threshold}_{operator}_{date}"
        
        # Check cache
        if self.use_cache and cache_key in self.cache:
            logger.debug(f"Using cached prediction for {cache_key}")
            return self.cache[cache_key]
        
        result = {"source": "NOAA", "city": city}
        
        if variable == "temperature" and threshold:
            # Temperature prediction
            # Convert threshold to Celsius if needed
            if unit == "fahrenheit":
                threshold_c = (threshold - 32) * 5/9
            else:
                threshold_c = threshold
            
            # Get probability from NOAA
            prob_result = self.noaa.get_temperature_probability(
                lat, lon, threshold_c, operator, date
            )
            
            result.update(prob_result)
            
        elif variable in ["rain", "snow", "storm", "hurricane", "flood"]:
            # Use historical probability for precip/meteorological events
            month = datetime.now().month
            if date:
                # Try to extract month from date
                date_lower = date.lower()
                months = {
                    "january": 1, "february": 2, "march": 3, "april": 4,
                    "may": 5, "june": 6, "july": 7, "august": 8,
                    "september": 9, "october": 10, "november": 11, "december": 12
                }
                for m_name, m_num in months.items():
                    if m_name in date_lower:
                        month = m_num
                        break
            
            # Historical probability
            if variable == "rain":
                probability = get_historical_precip_probability(city, month)
            elif variable == "snow":
                # Snow probability is low unless cold
                probability = get_historical_precip_probability(city, month) * 0.3 if month in [12, 1, 2, 3] else 0.1
            else:
                probability = get_historical_precip_probability(city, month) * 0.2
            
            result["probability"] = probability
            result["method"] = "historical"
            result["month"] = month
            result["note"] = f"Historical probability for {variable}"
        else:
            return {"probability": None, "error": f"Unknown variable: {variable}"}
        
        # Cache result
        if self.use_cache:
            self.cache[cache_key] = result
        
        return result
    
    def calculate_edge(self, noaa_prob: float, market_price: float) -> dict:
        """
        Calcular edge entre predicción NOAA y precio de mercado
        
        Args:
            noaa_prob: Probabilidad de NOAA (0-1)
            market_price: Precio de mercado (0-1)
        
        Returns:
            Dict con edge, direction, y confidence
        """
        if noaa_prob is None:
            return {
                "has_edge": False,
                "edge": None,
                "direction": None,
                "confidence": 0,
                "error": "No NOAA probability"
            }
        
        diff = noaa_prob - market_price
        
        if abs(diff) < self.threshold:
            return {
                "has_edge": False,
                "edge": diff,
                "direction": None,
                "confidence": abs(diff) / self.threshold if self.threshold > 0 else 0
            }
        
        direction = "YES" if diff > 0 else "NO"
        
        return {
            "has_edge": True,
            "edge": diff,
            "direction": direction,
            "confidence": abs(diff) / self.threshold,
            "recommendation": f"Buy {direction} if market price + margin"
        }
    
    def analyze_market(self, market: dict, noaa_data: dict = None) -> dict:
        """
        Analizar un market completo
        
        Args:
            market: Datos del market de Polymarket
            noaa_data: Datos opcionales de NOAA (si no se provee, usa el método)
        
        Returns:
            Análisis completo con recomendación
        """
        question = market.get("question", "")
        parsed = self.parse_market_question(question)
        
        # Si no hay datos de NOAA, obtenerlos
        if noaa_data is None:
            noaa_data = self.get_noaa_prediction(parsed)
        
        # Get market prices
        # Try different fields depending on market structure
        yes_price = market.get("yes_price") or market.get("outcomePrices", [0.5, 0.5])[0] if isinstance(market.get("outcomePrices"), list) else 0.5
        no_price = market.get("no_price") or market.get("outcomePrices", [0.5, 0.5])[1] if isinstance(market.get("outcomePrices"), list) else 0.5
        
        # Handle different price formats
        if isinstance(yes_price, str):
            try:
                yes_price = float(yes_price)
                no_price = float(no_price)
            except:
                yes_price, no_price = 0.5, 0.5
        
        result = {
            "market_id": market.get("id"),
            "question": question,
            "parsed": parsed,
            "market_price_yes": yes_price,
            "market_price_no": no_price,
            "noaa_data": noaa_data,
            "edge_analysis": None,
            "trade_recommendation": None
        }
        
        # Calcular edge
        if noaa_data and "probability" in noaa_data:
            result["edge_analysis"] = self.calculate_edge(
                noaa_data["probability"],
                yes_price
            )
            
            if result["edge_analysis"]["has_edge"]:
                result["trade_recommendation"] = {
                    "action": result["edge_analysis"]["direction"],
                    "reason": f"NOAA probability {noaa_data['probability']:.1%} vs market {yes_price:.1%}",
                    "edge": result["edge_analysis"]["edge"],
                    "confidence": result["edge_analysis"]["confidence"]
                }
        
        return result
    
    def rank_markets(self, markets: list) -> list:
        """
        Rank markets por potencial de edge
        
        Args:
            markets: Lista de markets
        
        Returns:
            Markets ordenados por confidence de edge
        """
        analyzed = []
        
        for market in markets:
            try:
                analysis = self.analyze_market(market)
                if analysis.get("edge_analysis", {}).get("has_edge"):
                    analyzed.append(analysis)
            except Exception as e:
                logger.debug(f"Error analyzing market: {e}")
                continue
        
        # Ordenar por confidence
        analyzed.sort(
            key=lambda x: x.get("edge_analysis", {}).get("confidence", 0),
            reverse=True
        )
        
        return analyzed
    
    def clear_cache(self):
        """Clear the prediction cache"""
        self.cache = {}
        logger.info("Prediction cache cleared")
