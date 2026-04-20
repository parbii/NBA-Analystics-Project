import pandas as pd
import time
import random
from nba_api.stats.endpoints import playergamelog

# Anti-blocking headers — looks like a real Chrome browser
HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://stats.nba.com/',
}

# Full 2026 Bulls core roster
bulls_roster = {
    'Josh_Giddey': '1630581',
    'Anfernee_Simons': '1629013',
    'Collin_Sexton': '1629012',
    'Jaden_Ivey': '1630596',
    'Matas_Buzelis': '1642258',
    'Tre_Jones': '1630200',
    'Nikola_Vucevic': '202696',
    'Patrick_Williams': '1630172',
    'Coby_White': '1629632',
    'Ayo_Dosunmu': '1630544',
    'Julian_Phillips': '1641763',
}

print("🏀 Starting 2026 Bulls Data Pipeline...")

for name, p_id in bulls_roster.items():
    try:
        print(f"📦 Fetching: {name}...")
        log = playergamelog.PlayerGameLog(
            player_id=p_id, season='2025-26',
            headers=HEADERS, timeout=120
        )
        df = log.get_data_frames()[0]

        if not df.empty:
            df['PLAYER_NAME'] = name.replace('_', ' ')
            df.columns = [c.upper() for c in df.columns]
            df.to_csv(f"{name.lower()}_stats_2026.csv", index=False)
            print(f"✅ Secured {name}")
        
        # Randomized cooldown to stay under the radar
        wait = random.uniform(5, 10)
        print(f"😴 Cooling off for {round(wait, 1)}s...")
        time.sleep(wait)

    except Exception as e:
        print(f"❌ Failed {name}: {e}")

print("\n--- Pipeline Complete! Run bulls_master_stitcher.py to unify the roster. ---")