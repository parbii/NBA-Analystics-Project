import pandas as pd
import time
from nba_api.stats.endpoints import playergamelog

# The ones that timed out
missing_starters = {
    'Josh_Giddey': '1630581',
    'Anfernee_Simons': '1629013',
    'Matas_Buzelis': '1642258'
}

# Standard professional headers
headers = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://stats.nba.com/',
}

print("--- Retrying Missing Bulls Starters ---")

for name, p_id in missing_starters.items():
    try:
        print(f"Fetching: {name} (with 60s timeout)...")
        # Adding headers and a longer timeout
        log = playergamelog.PlayerGameLog(player_id=p_id, season='2025-26', headers=headers, timeout=60)
        df = log.get_data_frames()[0]
        
        df.columns = [c.upper() for c in df.columns]
        df.to_csv(f"{name.lower()}_stats_2026.csv", index=False)
        
        print(f"✅ Saved {name}!")
        time.sleep(5) # Give the server a 5-second break between these big requests
        
    except Exception as e:
        print(f"❌ Still couldn't get {name}: {e}")

print("\nCheck your folder—hopefully the full starting five is now present!")