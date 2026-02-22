"""
Trade Manager - Gestión de posiciones y reglas de cierre
"""
import logging
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CloseRule(Enum):
    """Reglas de cierre disponibles"""
    HOLD = "hold"                    # Mantener hasta resolución
    SELL_ON_EDGE_LOSS = "edge_loss"  # Vender si el edge desaparece
    STOP_LOSS = "stop_loss"          # Vender si pierde X%
    TIME_BASED = "time_based"        # Cerrar X horas antes
    PROFIT_TAKE = "profit_take"      # Vender si profit > X%
    TRAILING_STOP = "trailing_stop"  # Stop dinámico


class TradeManager:
    """
    Gestiona posiciones y aplica reglas de cierre
    
    Soporta múltiples estrategias de cierre para testing:
    1. HOLD - Mantener hasta resolución
    2. SELL_ON_EDGE_LOSS - Vender si el edge desaparece
    3. STOP_LOSS - Vender si pierde X%
    4. TIME_BASED - Cerrar X horas antes de resolución
    5. PROFIT_TAKE - Vender si profit > X%
    6. TRAILING_STOP - Stop dinámico desde máximo
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.positions = {}  # market_id -> position
        
        # Configuración de reglas
        self.stop_loss_pct = self.config.get("stop_loss_pct", 0.10)  # 10%
        self.profit_take_pct = self.config.get("profit_take_pct", 0.30)  # 30%
        self.trailing_stop_pct = self.config.get("trailing_stop_pct", 0.15)  # 15%
        self.hours_before_close = self.config.get("hours_before_close", 1)  # 1 hora
        self.edge_loss_threshold = self.config.get("edge_loss_threshold", 0.02)  # 2%
        
        # Rules to test (all enabled for experiment)
        self.enabled_rules = [
            CloseRule.HOLD,
            CloseRule.SELL_ON_EDGE_LOSS,
            CloseRule.STOP_LOSS,
            CloseRule.TIME_BASED,
            CloseRule.PROFIT_TAKE,
            CloseRule.TRAILING_STOP,
        ]
    
    def open_position(self, market_id: str, side: str, amount: float, 
                     price: float, question: str, noaa_prob: float = None):
        """Abrir una nueva posición"""
        position = {
            "market_id": market_id,
            "side": side,  # "YES" or "NO"
            "amount": amount,
            "price_entry": price,
            "question": question,
            "noaa_prob": noaa_prob,
            "opened_at": datetime.now(),
            "status": "open",
            "price_highest": price,
            "price_lowest": price,
            "close_reasons": {},  # Track which rules would trigger
            "trades": []  # Record of any closes/reopens
        }
        
        self.positions[market_id] = position
        logger.info(f"Opened position: {side} {amount} @ {price:.2f} - {question[:50]}...")
        
        return position
    
    def update_position(self, market_id: str, current_price: float, 
                      noaa_prob: float = None, resolution_time: datetime = None):
        """
        Actualizar posición y evaluar reglas de cierre
        
        Returns:
            List of triggered rules (for analysis)
        """
        if market_id not in self.positions:
            return []
        
        pos = self.positions[market_id]
        if pos["status"] != "open":
            return []
        
        # Update price tracking
        pos["price_highest"] = max(pos["price_highest"], current_price)
        pos["price_lowest"] = min(pos["price_lowest"], current_price)
        
        # Calculate current profit/loss
        if pos["side"] == "YES":
            profit_pct = (current_price - pos["price_entry"]) / pos["price_entry"]
        else:  # NO
            profit_pct = (pos["price_entry"] - current_price) / pos["price_entry"]
        
        pos["current_price"] = current_price
        pos["profit_pct"] = profit_pct
        pos["last_updated"] = datetime.now()
        
        triggered = []
        
        # Evaluate each rule
        for rule in self.enabled_rules:
            should_close = False
            reason = ""
            
            if rule == CloseRule.HOLD:
                # Never close early
                reason = "HOLD - mantener hasta resolución"
                
            elif rule == CloseRule.STOP_LOSS:
                if profit_pct < -self.stop_loss_pct:
                    should_close = True
                    reason = f"STOP_LOSS: Profit {profit_pct:.1%} < -{self.stop_loss_pct:.1%}"
                    
            elif rule == CloseRule.PROFIT_TAKE:
                if profit_pct > self.profit_take_pct:
                    should_close = True
                    reason = f"PROFIT_TAKE: Profit {profit_pct:.1%} > {self.profit_take_pct:.1%}"
                    
            elif rule == CloseRule.TRAILING_STOP:
                if pos["price_highest"] > pos["price_entry"]:
                    trigger_price = pos["price_highest"] * (1 - self.trailing_stop_pct)
                    if current_price < trigger_price:
                        should_close = True
                        reason = f"TRAILING_STOP: Price {current_price:.2f} < trigger {trigger_price:.2f}"
                        
            elif rule == CloseRule.TIME_BASED:
                if resolution_time:
                    hours_until = (resolution_time - datetime.now()).total_seconds() / 3600
                    if hours_until < self.hours_before_close:
                        should_close = True
                        reason = f"TIME_BASED: {hours_until:.1f}h hasta resolución"
                        
            elif rule == CloseRule.SELL_ON_EDGE_LOSS:
                if noaa_prob is not None:
                    current_edge = noaa_prob - current_price
                    initial_edge = noaa_prob - pos["price_entry"]
                    if current_edge < initial_edge - self.edge_loss_threshold:
                        should_close = True
                        reason = f"EDGE_LOSS: Edge cayó de {initial_edge:.1%} a {current_edge:.1%}"
            
            # Record rule status
            pos["close_reasons"][rule.value] = {
                "triggered": should_close,
                "reason": reason,
                "profit_pct": profit_pct
            }
            
            if should_close:
                triggered.append(rule)
        
        return triggered
    
    def close_position(self, market_id: str, reason: str, price: float = None):
        """Cerrar posición"""
        if market_id not in self.positions:
            return None
        
        pos = self.positions[market_id]
        
        close_price = price or pos.get("current_price", pos["price_entry"])
        
        if pos["side"] == "YES":
            profit = (close_price - pos["price_entry"]) * pos["amount"]
        else:
            profit = (pos["price_entry"] - close_price) * pos["amount"]
        
        pos["status"] = "closed"
        pos["close_reason"] = reason
        pos["close_price"] = close_price
        pos["closed_at"] = datetime.now()
        pos["profit"] = profit
        
        logger.info(f"Closed position: {reason} @ {close_price:.2f}, Profit: ${profit:.2f}")
        
        return pos
    
    def get_position_summary(self) -> dict:
        """Get summary of all positions"""
        open_positions = [p for p in self.positions.values() if p["status"] == "open"]
        closed_positions = [p for p in self.positions.values() if p["status"] == "closed"]
        
        total_profit = sum(p.get("profit", 0) for p in closed_positions)
        
        # Analyze which rules worked best
        rule_performance = {}
        for rule in CloseRule:
            closed_with_rule = [p for p in closed_positions if p.get("close_reason", "").startswith(rule.value)]
            if closed_with_rule:
                rule_profit = sum(p.get("profit", 0) for p in closed_with_rule)
                rule_performance[rule.value] = {
                    "count": len(closed_with_rule),
                    "total_profit": rule_profit,
                    "avg_profit": rule_profit / len(closed_with_rule) if closed_with_rule else 0
                }
        
        return {
            "total_positions": len(self.positions),
            "open": len(open_positions),
            "closed": len(closed_positions),
            "total_profit": total_profit,
            "rule_performance": rule_performance,
            "positions": list(self.positions.values())
        }
    
    def simulate_no_trade(self, market_id: str, resolution_price: float) -> dict:
        """
        Simular qué hubiera pasado si no hubiéramos tradeado
        
        Para comparar estrategia vs no-hacer-nada
        """
        if market_id not in self.positions:
            return None
        
        pos = self.positions[market_id]
        
        # What we made
        our_profit = pos.get("profit", 0)
        
        # What would have happened if we did nothing
        if pos["side"] == "YES":
            no_trade_profit = (resolution_price - pos["price_entry"]) * pos["amount"]
        else:
            no_trade_profit = (pos["price_entry"] - resolution_price) * pos["amount"]
        
        return {
            "market_id": market_id,
            "our_profit": our_profit,
            "no_trade_profit": no_trade_profit,
            "difference": our_profit - no_trade_profit,
            "resolution_price": resolution_price
        }


class KellyExit:
    """
    Modelo matemático para decidir cuándo salir basado en Kelly Criterion
    
    La idea: si la edge disminuye, la posición óptima puede ser reducir size
    """
    
    def __init__(self, initial_kelly: float = 0.25):
        self.initial_kelly = initial_kelly
    
    def calculate_exit_kelly(self, current_win_rate: float, odds: float, 
                           current_size_pct: float) -> dict:
        """
        Calcular tamaño óptimo de salida
        
        Args:
            current_win_rate: Win rate actual observado
            odds: Odds del trade
            current_size_pct: Tamaño actual como % del bankroll
        
        Returns:
            Dict con recomendación y razones
        """
        # Full Kelly para el trade actual
        from kelly import kelly_fraction
        optimal_kelly = kelly_fraction(current_win_rate, odds)
        
        # Comparar con tamaño actual
        if optimal_kelly <= 0:
            # Negative expectation - salir completamente
            return {
                "action": "EXIT",
                "size_pct": 0,
                "reason": f"Negative expectation (win_rate={current_win_rate:.1%}, odds={odds})",
                "confidence": "high"
            }
        
        # Si el Kelly actual es mucho menor que el inicial, reducir posición
        kelly_ratio = optimal_kelly / self.initial_kelly
        
        if kelly_ratio < 0.5:
            # Reducir significativamente
            new_size = current_size_pct * kelly_ratio
            return {
                "action": "REDUCE",
                "size_pct": new_size,
                "reason": f"Kelly ratio {kelly_ratio:.2f} < 0.5",
                "confidence": "medium"
            }
        elif kelly_ratio < 0.8:
            return {
                "action": "HOLD",
                "size_pct": current_size_pct,
                "reason": f"Kelly ratio {kelly_ratio:.2f} acceptable",
                "confidence": "low"
            }
        else:
            return {
                "action": "HOLD",
                "size_pct": current_size_pct,
                "reason": f"Kelly ratio {kelly_ratio:.2f} good",
                "confidence": "medium"
            }
    
    def expected_value_exit(self, current_price: float, resolution_price_expected: float,
                          probability: float) -> dict:
        """
        Modelo de Expected Value para decidir venta
        
        EV = P(win) * payout - P(lose) * cost
        
        Si EV actual < EV inicial, considerar vender
        """
        # Expected value si mantenemos
        if resolution_price_expected > 0.5:
            # YES side
            payout = current_price / resolution_price_expected if resolution_price_expected > 0 else 0
        else:
            payout = current_price / (1 - resolution_price_expected) if resolution_price_expected < 1 else 0
        
        win_prob = probability
        lose_prob = 1 - probability
        
        ev_hold = win_prob * payout - lose_prob * 1
        
        return {
            "ev_hold": ev_hold,
            "recommendation": "SELL" if ev_hold < 0 else "HOLD",
            "reason": f"EV={ev_hold:.2f}"
        }
