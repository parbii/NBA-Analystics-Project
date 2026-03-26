import pandas as pd  # <--- This is the missing piece!

# 1. Load your saved data
team_df = pd.read_csv('bulls_2026_analysis.csv')
player_df = pd.read_csv('giddey_stats_2026.csv')

# 2. STANDARDIZE THE KEYS
# This ensures both dataframes use uppercase 'GAME_ID'
team_df.columns = [c.upper() for c in team_df.columns]
player_df.columns = [c.upper() for c in player_df.columns]

# 3. Merge the two tables
merged_df = pd.merge(team_df, player_df, on='GAME_ID', suffixes=('_team', '_player'))

# 4. Calculate a simple 'Win' correlation
# We turn 'W'/'L' into 1/0 so the math works
merged_df['WIN'] = merged_df['WL_team'].apply(lambda x: 1 if x == 'W' else 0)
# Calculate correlation between Player Points and a Team Win
score_corr = merged_df['PTS_player'].corr(merged_df['WIN'])

print(f"--- Analysis Complete ---")
print(f"Correlation between Giddey's Points and Bulls Wins: {score_corr:.2f}")

# Show the 'Investment' Insight
if score_corr > 0.3:
    print("Insight: Giddey's scoring has a moderate positive impact on winning.")
else:
    print("Insight: Giddey's scoring volume doesn't strictly dictate wins—look at Assists next.")