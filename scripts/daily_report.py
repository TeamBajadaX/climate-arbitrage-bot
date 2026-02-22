#!/usr/bin/env python3
"""
Daily Report Generator
Genera un reporte diario de performance del bot
"""
import json
from pathlib import Path
from datetime import datetime


def generate_daily_report(log_dir: Path, date: str = None) -> dict:
    """Generar reporte diario"""
    import json
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # Load position file for this date
    pos_file = log_dir / f"positions_{date}.json"
    
    if not pos_file.exists():
        return {"error": f"No data for {date}"}
    
    with open(pos_file) as f:
        data = json.load(f)
    
    positions = data.get("positions", [])
    closed = [p for p in positions if p.get("status") == "closed"]
    open_pos = [p for p in positions if p.get("status") == "open"]
    
    total_profit = sum(p.get("profit", 0) for p in closed)
    wins = sum(1 for p in closed if p.get("profit", 0) > 0)
    win_rate = wins / len(closed) if closed else 0
    
    # Por regla
    by_rule = {}
    for p in closed:
        reason = p.get("close_reason", "unknown")
        rule = reason.split()[0] if reason else "unknown"
        if rule not in by_rule:
            by_rule[rule] = {"count": 0, "profit": 0}
        by_rule[rule]["count"] += 1
        by_rule[rule]["profit"] += p.get("profit", 0)
    
    report = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_positions": len(positions),
            "open": len(open_pos),
            "closed": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "win_rate": f"{win_rate:.1%}",
            "total_profit": f"${total_profit:.2f}"
        },
        "open_positions": [
            {
                "question": p.get("question", "")[:60],
                "side": p.get("side"),
                "amount": p.get("amount"),
                "entry_price": p.get("price_entry"),
                "current_price": p.get("current_price"),
                "profit_pct": f"{p.get('profit_pct', 0):.1%}" if p.get('profit_pct') else "N/A"
            }
            for p in open_pos[:10]  # Top 10
        ],
        "closed_positions": [
            {
                "question": p.get("question", "")[:60],
                "side": p.get("side"),
                "profit": f"${p.get('profit', 0):.2f}",
                "close_reason": p.get("close_reason", "")
            }
            for p in closed[-10:]  # Last 10
        ],
        "performance_by_rule": by_rule
    }
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Daily Report Generator")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument("--output", default=None, help="Output file")
    args = parser.parse_args()
    
    log_dir = Path(__file__).parent / "logs"
    report = generate_daily_report(log_dir, args.date)
    
    output = json.dumps(report, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)
    
    # Print summary
    if "error" not in report:
        print("\n" + "="*50)
        print(f"DAILY SUMMARY - {report['date']}")
        print("="*50)
        s = report["summary"]
        print(f"Total: {s['total_positions']} | Open: {s['open']} | Closed: {s['closed']}")
        print(f"Win Rate: {s['win_rate']}")
        print(f"Profit: {s['total_profit']}")


if __name__ == "__main__":
    main()
