import pandas as pd
import time
import requests
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster, playergamelog

# 1. NEW SESSION HEADERS (Fresh Identity)
def get_headers():
    return {
        'Host': 'stats.nba.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'x-nba-stats-origin': 'stats',
        'x-nba-stats-token': 'true',
        'Referer': 'https://stats.nba.com/',
    }

def fetch_team_data(team_abbr):
    nba_team = [t for t in teams.get_teams() if t['abbreviation'] == team_abbr][0]
    print(f"🚀 Targeted Fetch for: {nba_team['full_name']}")
    
    try:
        # Get Roster
        roster = commonteamroster.CommonTeamRoster(team_id=nba_team['id'], season='2025-26', headers=get_headers()).get_data_frames()[0]
        for _, player in roster.head(5).iterrows(): # Just the core 5 starters
            p_name = player['PLAYER']
            print(f"   ∟ Pulling: {p_name}")
            
            log = playergamelog.PlayerGameLog(player_id=player['PLAYER_ID'], season='2025-26', headers=get_headers())
            df = log.get_data_frames()[0]
            
            if not df.empty:
                df['PLAYER_NAME'] = p_name
                df['TEAM'] = team_abbr
                df.to_csv(f"league_data/{team_abbr}_{p_name.replace(' ', '_')}.csv", index=False)
            
            time.sleep(10) # Heavy 10-second delay between players
            
    except Exception as e:
        print(f"❌ Still Blocked: {e}")

# --- CHANGE THIS TO THE TEAM YOU WANT TO TARGET ---
fetch_team_data('LAL') # Try Lakers, Warriors (GSW), or Suns (PHX)