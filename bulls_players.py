from nba_api.stats.endpoints import playergamelog
import pandas as pd
import time

# 1. Josh Giddey's Unique ID
GIDDEY_ID = '1630581' 

print("Fetching player data for Josh Giddey...")

try:
    # 2. Pull the game log for the 2025-26 season
    # Season Type 'Regular Season' = 'Regular Season'
    glog = playergamelog.PlayerGameLog(player_id=GIDDEY_ID, season='2025-26')
    df = glog.get_data_frames()[0]

    # 3. Clean up and show key metrics for betting (Points, Rebounds, Assists)
    # These are the 'Player Props' markets
    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])
    cols = ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'MIN']
    
    print("\n--- Josh Giddey: Recent Performance ---")
    print(df[cols].head(10))

    # 4. Save to CSV
    df.to_csv('giddey_stats_2026.csv', index=False)
    print("\nSuccess! Player stats saved to giddey_stats_2026.csv")

except Exception as e:
    print(f"Error: {e}")