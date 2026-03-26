import pandas as pd
import os

os.system('clear')

# 2026 DEFENSIVE RATINGS (Lower is better defense)
def_rankings = {
    'OKC': 107.2, 'SAS': 109.5, 'BOS': 111.4, 'GSW': 114.2, 
    'LAL': 117.1, 'CHI': 117.8, 'ATL': 119.5, 'MIL': 118.2
}

print("📊 ANALYZING MATCHUPS VS DEFENSE...")

try:
    df = pd.read_csv('Parbs_League_Master_2026.csv')
    
    # THE FIX: Force all columns to uppercase and strip spaces
    df.columns = [c.upper().strip() for c in df.columns]
    
    # Find the team column (might be 'TM' or 'TEAM_ABBR')
    team_col = 'TEAM_ABBR' if 'TEAM_ABBR' in df.columns else 'TM'
    
    # Convert stats to numbers
    df['PTS'] = pd.to_numeric(df['PTS'], errors='coerce')
    df['MP'] = pd.to_numeric(df['MP'], errors='coerce')
    df = df.dropna(subset=['PTS', 'MP'])

    # Starter Logic: 28+ Minutes
    starters = df[df['MP'] > 28].copy()

    def get_signal(row):
        drtg = def_rankings.get(row[team_col], 115.0)
        if row['PTS'] > 22 and drtg > 118: return "🔥 GREEN LIGHT"
        if drtg < 111: return "❄️ LOCKDOWN"
        return "➡️ STEADY"

    starters['SIGNAL'] = starters.apply(get_signal, axis=1)

    print("="*90)
    print(starters[['PLAYER', team_col, 'PTS', 'MP', 'SIGNAL']].sort_values('PTS', ascending=False).head(20).to_string(index=False))
    print("="*90)

except Exception as e:
    print(f"❌ Analysis Failed: {e}")