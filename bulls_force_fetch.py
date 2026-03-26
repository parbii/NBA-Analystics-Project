import pandas as pd
import time
import random
import requests
from nba_api.stats.endpoints import playergamelog

# 1. Identity Spoofing (Makes you look like a Chrome browser)
headers = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://stats.nba.com/',
}

# 2. The 2026 Bulls Core Roster (Missing Players)
# We are grabbing the bigs and the young wings
target_players = {
    'Matas_Buzelis': '1642258',
    'Nikola_Vucevic': '202696',
    'Patrick_Williams': '1630172',
    'Coby_White': '1629632',
    'Ayo_Dosunmu': '1630544',
    'Julian_Phillips': '1641763'
}

print("🏀 SECURING THE REMAINING BULLS...")

for name, p_id in target_players.items():
    try:
        print(f"📦 Fetching: {name}...")
        
        # Pulling game logs for the 2025-26 season
        log = playergamelog.PlayerGameLog(player_id=p_id, season='2025-26', headers=headers, timeout=120)
        df = log.get_data_frames()[0]
        
        if not df.empty:
            df['PLAYER_NAME'] = name.replace('_', ' ')
            df.to_csv(f"{name.lower()}_stats_2026.csv", index=False)
            print(f"✅ Secured {name}")
        
        # Randomized sleep to stay under the radar
        wait = random.uniform(7, 12)
        print(f"😴 Cooling off for {round(wait, 1)}s...")
        time.sleep(wait)

    except Exception as e:
        print(f"❌ Failed {name}: {e}. The NBA is still blocking your IP.")

print("\nOnce finished, run your 'Master Stitcher' to unify the roster!")