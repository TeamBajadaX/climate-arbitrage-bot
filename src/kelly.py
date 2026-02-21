"""
Kelly Criterion Calculator
"""
import math


def kelly_fraction(win_rate: float, odds: float) -> float:
    """
    Calculate Kelly Criterion percentage
    
    Args:
        win_rate: Probability of winning (0-1)
        odds: Payout multiplier (e.g., 2.0 = win 2x)
    
    Returns:
        Kelly percentage (0-1)
    """
    if odds <= 1:
        return 0
    
    q = 1 - win_rate
    b = odds - 1
    
    kelly = (b * win_rate - q) / b
    
    # Don't bet if negative expectation
    if kelly <= 0:
        return 0
    
    return kelly


def capped_kelly(win_rate: float, odds: float, cap: float = 0.25) -> float:
    """
    Kelly criterion capped to a fraction of the full Kelly
    
    Args:
        win_rate: Probability of winning (0-1)
        odds: Payout multiplier
        cap: Fraction of full Kelly to use (default 25%)
    
    Returns:
        Capped Kelly percentage
    """
    full_kelly = kelly_fraction(win_rate, odds)
    return min(full_kelly * cap, 1.0)


def position_size(bankroll: float, kelly_pct: float, min_bet: float = 10, max_bet: float = 100) -> float:
    """
    Calculate position size based on Kelly
    
    Args:
        bankroll: Total capital
        kelly_pct: Kelly percentage from capped_kelly()
        min_bet: Minimum bet allowed
        max_bet: Maximum bet allowed
    
    Returns:
        Position size in USD
    """
    size = bankroll * kelly_pct
    return max(min_bet, min(size, max_bet))


def expected_value(win_rate: float, odds: float, bet_size: float) -> float:
    """
    Calculate expected value of a bet
    
    Args:
        win_rate: Probability of winning
        odds: Payout multiplier
        bet_size: Amount bet
    
    Returns:
        Expected value
    """
    win_amount = bet_size * (odds - 1)
    lose_amount = -bet_size
    
    expected = win_rate * win_amount + (1 - win_rate) * lose_amount
    return expected


# Example usage
if __name__ == "__main__":
    # Example: 60% win rate, 2x odds
    wr = 0.60
    odds = 2.0
    
    k = kelly_fraction(wr, odds)
    ck = capped_kelly(wr, odds, 0.25)
    pos = position_size(1000, ck)
    ev = expected_value(wr, odds, pos)
    
    print(f"Win rate: {wr*100}%")
    print(f"Odds: {odds}x")
    print(f"Full Kelly: {k*100:.2f}%")
    print(f"Capped Kelly (25%): {ck*100:.2f}%")
    print(f"Position size ($1000 bankroll): ${pos:.2f}")
    print(f"Expected value: ${ev:.2f}")
