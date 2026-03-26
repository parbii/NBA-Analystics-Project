import pandas as pd
import time
import os

os.system('clear')

# 1. The Teams Playing Tomorrow (March 10)
# Abbreviations: CHI, GSW, MIN, LAL, BOS, SAS, DAL, ATL, PHX, MIL, DET, BKN, PHI, MEM
teams_to_scrape = ['CHI', 'GSW', 'MIN', 'LAL', 'BOS', 'SAS', 'DAL', 'ATL', 'PHX', 'MIL']

print("🚀 PARB'S GLOBAL ENGINE: FETCHING ALL MATCHUPS FOR MARCH 10...")

all_data = []

for team in teams_to_scrape:
    url = f"https://www.basketball-reference.com/teams/{team}/2026.html"
    try:
        print(f"📦 Scraping {team} roster...")
        # Table [1] is usually the 'Per Game' stats
        df = pd.read_html(url)[1]
        
        # CLEANING: Remove 'Team Totals' and empty rows
        df = df[df['Player'] != 'Team Totals']
        df = df.dropna(subset=['Player'])
        
        # Tag the team so we know who is who
        df['TEAM_ABBR'] = team
        all_data.append(df)
        
        # 3-second sleep to be respectful and avoid blocks
        time.sleep(3) 
        
    except Exception as e:
        print(f"⚠️ Could not get {team}: {e}")

# Combine everything into one master file
if all_data:
    master_df = pd.concat(all_data, ignore_index=True)
    master_df.to_csv('Parbs_League_Master_2026.csv', index=False)
    print(f"\n✅ SUCCESS: Secured {len(master_df)} players across {len(teams_to_scrape)} teams.")
    print("Run 'parbs_global_analysis.py' next to see the Hot/Cold signals!")