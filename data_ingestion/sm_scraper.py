import pandas as pd
import requests
import os
import time
from io import StringIO

class SMScraper:
    def __init__(self):
        self.root_path = os.getcwd()
        # Header makes the request look like it's coming from your MacBook
        self.headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

    def sync_player(self, player_name):
        print(f"📊 STATMUSE SYNC: {player_name}...")
        # We format the URL to ask StatMuse for the game log
        query = player_name.replace(" ", "-").lower()
        url = f"https://www.statmuse.com/nba/ask/{query}-game-log-this-season"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            # Use StringIO to read the HTML table directly
            tables = pd.read_html(StringIO(response.text))
            df = tables[0] # The game log is always the first table

            # MAPPING: Match your Audit Engine headers
            df = df.rename(columns={'MP': 'Minutes', 'TS%': 'TS_Percentage', 'DATE': 'Game_Date'})
            
            # MATH CLEANING: StatMuse uses '58.2%', we need '0.582'
            if 'TS_Percentage' in df.columns:
                df['TS_Percentage'] = df['TS_Percentage'].astype(str).str.replace('%', '').astype(float) / 100

            # SAVE: Update the CSV in your root folder
            filename = f"{player_name.lower().replace(' ', '_')}_stats_2026.csv"
            df.to_csv(os.path.join(self.root_path, filename), index=False)
            
            print(f"✅ SUCCESS: {player_name} data secured via StatMuse.")
            return True
        except Exception as e:
            print(f"❌ StatMuse Error: {e}")
            return False

if __name__ == "__main__":
    scraper = SMScraper()
    scraper.sync_player("Anthony Edwards")