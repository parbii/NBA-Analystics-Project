import pandas as pd
import numpy as np

# 1. Load the Master Data
# Make sure your stitched file is named correctly in your directory
df = pd.read_csv('Bulls_Master_2026.csv')

# 2. Data Cleaning
df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')
df = df.dropna(subset=['GAME_DATE'])

def calculate_ts_pct(pts, fga, fta):
    """Calculates True Shooting Percentage: The gold standard for scoring efficiency."""
    denominator = 2 * (fga + 0.44 * fta)
    return (pts / denominator) if denominator > 0 else 0

def analyze_player_full(player_name):
    # Filter for player and sort by most recent games
    p_data = df[df['PLAYER_NAME'] == player_name].sort_values('GAME_DATE', ascending=False)
    
    if p_data.empty or len(p_data) < 3: return None

    # Define recent sample (Last 5 games)
    recent = p_data.head(5)
    
    # --- BASIC PRA METRICS (Points, Rebounds, Assists) ---
    metrics = ['PTS', 'REB', 'AST']
    stats = {'Player': player_name}
    
    for m in metrics:
        season_avg = p_data[m].mean()
        recent_avg = recent[m].mean()
        stats[f'Ssn_{m}'] = round(season_avg, 1)
        stats[f'Rec_{m}'] = round(recent_avg, 1)
        stats[f'{m}_Heat'] = round(recent_avg - season_avg, 1)

    # --- ADVANCED EFFICIENCY ---
    # Season TS% vs Recent TS%
    s_ts = calculate_ts_pct(p_data['PTS'].sum(), p_data['FGA'].sum(), p_data['FTA'].sum())
    r_ts = calculate_ts_pct(recent['PTS'].sum(), recent['FGA'].sum(), recent['FTA'].sum())
    
    stats['TS_Delta'] = round((r_ts - s_ts) * 100, 1) # Efficiency change in %
    stats['+/-_Recent'] = round(recent['PLUS_MINUS'].mean(), 1) # Impact on winning
    
    # --- INVESTMENT SIGNALS ---
    # A 'HOT' signal requires points UP and efficiency UP
    is_hot = stats['PTS_Heat'] > 2 and stats['TS_Delta'] > 0
    is_cold = stats['PTS_Heat'] < -2 or stats['TS_Delta'] < -5
    
    stats['Status'] = '🔥 HOT' if is_hot else ('❄️ COLD' if is_cold else '➡️ STEADY')
    
    return stats

# 3. Execution
players = df['PLAYER_NAME'].unique()
results = []

for p in players:
    analysis = analyze_player_full(p)
    if analysis:
        results.append(analysis)

# 4. Final Output Formatting
dashboard = pd.DataFrame(results).sort_values('PTS_Heat', ascending=False)

# Reorder columns so the most important betting metrics are front and center
cols_order = [
    'Player', 'Status', 'Rec_PTS', 'PTS_Heat', 'Rec_REB', 'REB_Heat', 
    'Rec_AST', 'AST_Heat', 'TS_Delta', '+/-_Recent'
]
dashboard = dashboard[cols_order]

print("\n" + "="*115)
print("   CHICAGO BULLS ADVANCED INVESTMENT DASHBOARD: PRA + EFFICIENCY (MARCH 2026)")
print("="*115)
print(dashboard.to_string(index=False))
print("="*115)
print("TS_Delta: Efficiency Change (%) | +/-_Recent: Average Impact over last 5 games")

# Save a copy so you can show it to your Dean's Council or include in your portfolio
dashboard.to_csv('bulls_advanced_signals.csv', index=False)