import pandas as pd
import os
import time
from balldontlie import BalldontlieAPI

class BDLScraper:
    def __init__(self, api_key):
        # Initialize with your free key from app.balldontlie.io
        self.api = BalldontlieAPI(api_key=api_key)
        self.root_path = os.getcwd()

    def sync_player(self, bdl_id, player_name):
        print(f"🏀 BDL SYNC: {player_name} (ID: {bdl_id})...")
        try:
            # Pull game stats for the current 2025-26 season
            stats = self.api.nba.stats.list(player_ids=[bdl_id], seasons=[2025])
            
            # Convert raw data to a list of dicts for Pandas
            data_list = [s.__dict__ for s in stats.data]
            df = pd.DataFrame(data_list)

            # Manual TS% Calculation: The "Alpha" Metric
            # PTS / (2 * (FGA + 0.44 * FTA))
            df['TS_Percentage'] = df['pts'] / (2 * (df['fga'] + (0.44 * df['fta'])))
            df = df.fillna(0) # Handle 0/0 attempts

            # Save the CSV so your Auditor can read it
            filename = f"{player_name.lower().replace(' ', '_')}_stats_2026.csv"
            df.to_csv(os.path.join(self.root_path, filename), index=False)
            
            print(f"✅ DATA SECURED: {player_name} stats live.")
            return True
        except Exception as e:
            print(f"❌ BDL Error for {player_name}: {e}")
            return False