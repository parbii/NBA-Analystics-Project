import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog

# 1. The 2026 Bulls 'Rebuild' Core
bulls_roster = {
    'Josh_Giddey': '1630581',
    'Anfernee_Simons': '1629013',
    'Collin_Sexton': '1629012',
    'Jaden_Ivey': '1630596',
    'Matas_Buzelis': '1642258',
    'Tre_Jones': '1630200'
}

print("--- Starting 2026 Bulls Data Pipeline ---")

for name, p_id in bulls_roster.items():
    try:
        print(f"Fetching: {name}...")
        # Pull 2025-26 Season Data
        log = playergamelog.PlayerGameLog(player_id=p_id, season='2025-26')
        df = log.get_data_frames()[0]
        
        # Standardize columns to uppercase immediately to avoid KeyErrors later
        df.columns = [c.upper() for c in df.columns]
        
        # Save each to their own CSV
        df.to_csv(f"{name.lower()}_stats_2026.csv", index=False)
        
        # Wait 2 seconds so the NBA server doesn't get mad
        time.sleep(2)
        
    except Exception as e:
        print(f"Failed to fetch {name}: {e}")

print("\n--- Pipeline Complete! Check your folder for 6 new CSV files. ---")