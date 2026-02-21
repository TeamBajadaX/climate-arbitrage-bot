"""
Prediction Edge - Comparar NOAA forecasts vs Polymarket prices
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PredictionEngine:
    """
    Compara forecasts de NOAA vs precios de Polymarket
    para encontrar edges en la predicción
    """
    
    def __init__(self, threshold: float = 0.08):
        """
        Args:
            threshold: Diferencia mínima para considerar edge (default 8%)
        """
        self.threshold = threshold
    
    def parse_market_question(self, question: str) -> dict:
        """
        Parse market question to extract:
        - City
        - Variable (temperature, rain, snow)
        - Threshold value
        - Date
        
        Example: "Will London exceed 25°C on Feb 25, 2026?"
        """
        question = question.lower()
        
        result = {
            "city": None,
            "variable": None,
            "threshold": None,
            "operator": None,
            "date": None
        }
        
        # Cities
        cities = [
            "london", "new york", "paris", "tokyo", "sydney",
            "miami", "chicago", "seoul", "berlin", "madrid", "rome",
            "buenos aires", "dubai", "singapore", "hong kong"
        ]
        
        for city in cities:
            if city in question:
                result["city"] = city.title()
                break
        
        # Variables
        if "temperature" in question or "°c" in question or "°f" in question or "celsius" in question:
            result["variable"] = "temperature"
        elif "rain" in question:
            result["variable"] = "rain"
        elif "snow" in question:
            result["variable"] = "snow"
        elif "storm" in question:
            result["variable"] = "storm"
        
        # Operators
        if "exceed" in question or "above" in question or "higher than" in question:
            result["operator"] = ">"
        elif "fall below" in question or "below" in question:
            result["operator"] = "<"
        
        # Extract threshold value
        import re
        numbers = re.findall(r'\d+', question)
        if numbers:
            result["threshold"] = float(numbers[0])
        
        return result
    
    def get_noaa_prediction(self, city: str, variable: str, date: str = None) -> dict:
        """
        Obtener predicción de NOAA para una ciudad
        
        TODO: Implementar con NOAA API real
        
        Returns:
            Dict con 'probability' y 'value'
        """
        # Placeholder - implementar con NOAA API
        return {
            "probability": None,
            "value": None,
            "source": "NOAA",
            "note": "Implementar con API"
        }
    
    def calculate_edge(self, noaa_prob: float, market_price: float) -> dict:
        """
        Calcular edge entre predicción NOAA y precio de mercado
        
        Args:
            noaa_prob: Probabilidad de NOAA (0-1)
            market_price: Precio de mercado (0-1)
        
        Returns:
            Dict con edge, direction, y confidence
        """
        diff = noaa_prob - market_price
        
        if abs(diff) < self.threshold:
            return {
                "has_edge": False,
                "edge": diff,
                "direction": None,
                "confidence": abs(diff) / self.threshold
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
        
        # Si no hay datos de NOAA, intentar obtenerlos
        if noaa_data is None:
            if parsed["city"]:
                noaa_data = self.get_noaa_prediction(
                    parsed["city"],
                    parsed.get("variable", "temperature")
                )
        
        result = {
            "market_id": market.get("id"),
            "question": question,
            "parsed": parsed,
            "market_price_yes": market.get("yes_price", 0.5),
            "market_price_no": market.get("no_price", 0.5),
            "noaa_data": noaa_data,
            "edge_analysis": None,
            "trade_recommendation": None
        }
        
        # Calcular edge
        if noaa_data and noaa_data.get("probability"):
            result["edge_analysis"] = self.calculate_edge(
                noaa_data["probability"],
                result["market_price_yes"]
            )
            
            if result["edge_analysis"]["has_edge"]:
                result["trade_recommendation"] = {
                    "action": result["edge_analysis"]["direction"],
                    "reason": f"NOAA probability {noaa_data['probability']:.1%} vs market {result['market_price_yes']:.1%}",
                    "edge": result["edge_analysis"]["edge"]
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
            analysis = self.analyze_market(market)
            if analysis.get("edge_analysis", {}).get("has_edge"):
                analyzed.append(analysis)
        
        # Ordenar por confidence
        analyzed.sort(
            key=lambda x: x.get("edge_analysis", {}).get("confidence", 0),
            reverse=True
        )
        
        return analyzed
