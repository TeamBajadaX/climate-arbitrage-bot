#!/usr/bin/env python3
"""
Weekly Report Generator
Genera un reporte semanal de performance del bot
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict


def load_all_logs(log_dir: Path) -> list:
    """Cargar todos los logs de la semana"""
    logs = []
    
    # Load position files
    for f in log_dir.glob("positions_*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
                data["_file"] = f.name
                logs.append(data)
        except:
            pass
    
    # Load scan files
    for f in log_dir.glob("scan_*.json"):
        try:
            with open(f) as fp:
                for line in fp:
                    if line.strip():
                        data = json.loads(line)
                        data["_file"] = f.name
                        logs.append(data)
        except:
            pass
    
    return logs


def calculate_metrics(positions: list) -> dict:
    """Calcular métricas de performance"""
    if not positions:
        return {
            "total": 0,
            "profit": 0,
            "win_rate": 0,
            "by_rule": {}
        }
    
    closed = [p for p in positions if p.get("status") == "closed"]
    wins = [p for p in closed if p.get("profit", 0) > 0]
    losses = [p for p in closed if p.get("profit", 0) <= 0]
    
    total_profit = sum(p.get("profit", 0) for p in closed)
    win_rate = len(wins) / len(closed) if closed else 0
    
    # Performance por regla
    by_rule = defaultdict(lambda: {"count": 0, "profit": 0, "wins": 0})
    for p in closed:
        reason = p.get("close_reason", "unknown")
        rule = reason.split()[0] if reason else "unknown"
        by_rule[rule]["count"] += 1
        by_rule[rule]["profit"] += p.get("profit", 0)
        if p.get("profit", 0) > 0:
            by_rule[rule]["wins"] += 1
    
    return {
        "total": len(positions),
        "closed": len(closed),
        "open": len(positions) - len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_profit": total_profit,
        "avg_profit": total_profit / len(closed) if closed else 0,
        "by_rule": dict(by_rule)
    }


def generate_weekly_report(log_dir: Path, week_start: datetime = None) -> dict:
    """Generar reporte semanal"""
    if week_start is None:
        week_start = datetime.now() - timedelta(days=7)
    
    logs = load_all_logs(log_dir)
    
    # Extraer todas las posiciones
    all_positions = []
    for log in logs:
        if "positions" in log:
            all_positions.extend(log.get("positions", []))
    
    metrics = calculate_metrics(all_positions)
    
    # Analizar oportunidades por ciudad
    city_stats = defaultdict(lambda: {"count": 0, "profit": 0})
    for pos in all_positions:
        question = pos.get("question", "")
        # Extraer ciudad (simple)
        cities = ["london", "paris", "new york", "tokyo", "munich", "salzburg", 
                  "ljubljana", "budapest", "strasbourg", "miami", "chicago", "seoul"]
        for city in cities:
            if city.lower() in question.lower():
                city_stats[city]["count"] += 1
                city_stats[city]["profit"] += pos.get("profit", 0)
                break
    
    # Analizar por estrategia
    strategy_stats = defaultdict(lambda: {"count": 0, "profit": 0})
    for pos in all_positions:
        # Determinar estrategia basada en la pregunta o datos
        strategy = "prediction"  # default
        if "spread" in str(pos.get("strategy", "")).lower():
            strategy = "spread"
        strategy_stats[strategy]["count"] += 1
        strategy_stats[strategy]["profit"] += pos.get("profit", 0)
    
    report = {
        "period": {
            "start": week_start.isoformat(),
            "end": datetime.now().isoformat()
        },
        "summary": {
            "total_trades": metrics["total"],
            "closed_trades": metrics["closed"],
            "open_trades": metrics["open"],
            "wins": metrics["wins"],
            "losses": metrics["losses"],
            "win_rate": f"{metrics['win_rate']:.1%}",
            "total_profit": f"${metrics['total_profit']:.2f}",
            "avg_profit_per_trade": f"${metrics['avg_profit']:.2f}",
            "roi": f"{(metrics['total_profit'] / 300 * 100):.1f}%"  # Assuming $300 bankroll
        },
        "performance_by_rule": {},
        "performance_by_city": dict(city_stats),
        "performance_by_strategy": dict(strategy_stats),
        "recommendations": []
    }
    
    # Agregar performance por regla
    for rule, stats in metrics.get("by_rule", {}).items():
        wr = stats["wins"] / stats["count"] if stats["count"] > 0 else 0
        report["performance_by_rule"][rule] = {
            "trades": stats["count"],
            "profit": f"${stats['profit']:.2f}",
            "win_rate": f"{wr:.1%}"
        }
    
    # Generar recomendaciones
    # Mejor regla
    if metrics.get("by_rule"):
        best_rule = max(metrics["by_rule"].items(), key=lambda x: x[1]["profit"])
        report["recommendations"].append(f"Mejor regla: {best_rule[0]} (${best_rule[1]['profit']:.2f})")
    
    # Mejor ciudad
    if city_stats:
        best_city = max(city_stats.items(), key=lambda x: x[1]["profit"])
        report["recommendations"].append(f"Mejor ciudad: {best_city[0]} ({best_city[1]['count']} trades)")
    
    # Recomendación general
    if metrics["win_rate"] > 0.55:
        report["recommendations"].append("✓ Win rate > 55%: Considerar activar live trading")
    elif metrics["win_rate"] < 0.45:
        report["recommendations"].append("✗ Win rate < 45%: Revisar estrategia")
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Weekly Report Generator")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    parser.add_argument("--output", default=None, help="Output file")
    args = parser.parse_args()
    
    log_dir = Path(__file__).parent / "logs"
    
    week_start = datetime.now() - timedelta(days=args.days)
    report = generate_weekly_report(log_dir, week_start)
    
    output = json.dumps(report, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)
    
    # Also print summary
    print("\n" + "="*50)
    print("WEEKLY SUMMARY")
    print("="*50)
    s = report["summary"]
    print(f"Trades: {s['total_trades']} (closed: {s['closed_trades']})")
    print(f"Win Rate: {s['win_rate']}")
    print(f"Profit: {s['total_profit']}")
    print(f"ROI: {s['roi']}")
    print("\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  - {rec}")


if __name__ == "__main__":
    main()
