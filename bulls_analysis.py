import pandas as pd
import time
from nba_api.stats.endpoints import leaguegamefinder

# 1. Chicago Bulls Unique ID
BULLS_ID = '1610612741'

print("Connecting to NBA servers... (This might take a second)")

# 2. Use a 'Header' to look more like a real web browser (helps avoid blocks)
headers = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://stats.nba.com/',
    'Connection': 'keep-alive'
}

try:
    # Adding a small delay before we start
    time.sleep(1)
    
    # 3. Pull all games with the headers included
    gamefinder = leaguegamefinder.LeagueGameFinder(team_id_nullable=BULLS_ID, headers=headers, timeout=60)
    all_games = gamefinder.get_data_frames()[0]

    # 4. Filter for 2025-26 Season
    bulls_season = all_games[all_games.SEASON_ID == '22025'].copy()

    # 5. Sort and Calculate Rolling Average
    bulls_season['GAME_DATE'] = pd.to_datetime(bulls_season['GAME_DATE'])
    bulls_season = bulls_season.sort_values('GAME_DATE')
    bulls_season['Rolling_PTS'] = bulls_season['PTS'].rolling(window=5).mean()

    # 6. Display results
    print("\n--- Chicago Bulls: Current Form Analysis ---")
    cols = ['GAME_DATE', 'MATCHUP', 'WL', 'PTS', 'Rolling_PTS']
    print(bulls_season[cols].tail(10))

    # 7. Save to CSV
    bulls_season.to_csv('bulls_2026_analysis.csv', index=False)
    print("\nSuccess! File saved as: bulls_2026_analysis.csv")

except Exception as e:
    print(f"\nConnection failed again: {e}")
    print("Tip: If you're on a VPN, try turning it off. Sometimes NBA.com blocks VPN IP addresses.")