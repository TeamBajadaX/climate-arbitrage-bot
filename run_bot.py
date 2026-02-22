#!/usr/bin/env python3
"""
Bot runner - runs the climate arbitrage bot every 15 minutes
"""
import time
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def run_bot():
    """Run one iteration of the bot"""
    import datetime
    print(f"\n{'='*50}")
    print(f"=== Running bot at {datetime.datetime.now()} ===")
    print(f"{'='*50}")
    
    result = subprocess.run(
        [sys.executable, 'main.py'],
        capture_output=True,
        text=True,
        env={**os.environ, 'PYTHONPATH': 'src'}
    )
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print("Bot completed successfully")
    
    return result.returncode

def main():
    """Main loop"""
    print("Climate Arbitrage Bot started")
    print("Running every 15 minutes...")
    
    while True:
        try:
            run_bot()
        except Exception as e:
            print(f"Error: {e}")
        
        print("Sleeping 15 minutes...")
        time.sleep(900)  # 15 minutes

if __name__ == "__main__":
    main()
