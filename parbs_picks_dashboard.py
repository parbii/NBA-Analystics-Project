import pandas as pd
import os

# Clear terminal for a professional "Production" look
os.system('clear')

# 1. Load the Scraped Data
df = pd.read_csv('Bulls_Master_2026.csv')

# 2. Filter for players with real rotation minutes (at least 15 MPG)
# Basketball-Reference uses 'MP' for Minutes Played
rotation_players = df[df['MP'] > 15].copy()

# 3. Investment Logic: Efficiency vs Volume
# We'll look at Points relative to Minutes to find the "Alpha"
rotation_players['PTS_per_MIN'] = rotation_players['PTS'] / rotation_players['MP']

# 4. Generate the "Parb's Picks" Table
dashboard = rotation_players[['Player', 'PTS', 'MP', 'FG%', '3P%', 'FT%']].sort_values('PTS', ascending=False)

print("="*80)
print("   🏀 PARB'S PICKS: BULLS INVESTMENT DASHBOARD (MARCH 2026) 🏀")
print("="*80)
print(dashboard.to_string(index=False))
print("="*80)
print("INVESTMENT SIGNAL: Look for players with high FG% but low PTS (Value Gaps).")

# 5. Save for your Portfolio
dashboard.to_csv('parbs_final_bulls_report.csv', index=False)