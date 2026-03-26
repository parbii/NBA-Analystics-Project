import pandas as pd
import os

os.system('clear')

# 1. LIVE 2026 DEFENSIVE RATINGS
def_rankings = {
    'OKC': 104.9, 'SAS': 108.5, 'BOS': 109.8, 'GSW': 111.1, 
    'LAL': 114.4, 'CHI': 115.1, 'UTA': 119.1, 'WAS': 117.8,
    'SAC': 117.6, 'CHO': 112.9, 'NOP': 115.3, 'DET': 121.2
}

matchups = {'MIN': 'LAC', 'LAC': 'MIN', 'NYK': 'UTA', 'UTA': 'NYK', 'CHI': 'GSW'}

print("🚀 PARB'S ROLE-PLAYER ENGINE: ANALYZING VALUE GAPS...")

try:
    df = pd.read_csv('Parbs_League_Master_2026.csv')
    df.columns = [c.upper().strip() for c in df.columns]
    
    # Ensure all numeric columns are handled
    for col in ['PTS', 'MP', 'FG%', '3P%']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['PLAYER', 'PTS', 'MP'])

    def get_role_player_signal(row):
        opponent = matchups.get(row['TEAM_ABBR'], 'AVG')
        opp_drtg = def_rankings.get(opponent, 114.0)
        
        # LOGIC 1: The "Microwave" (High Efficiency Role Player)
        # 10-18 PPG but shooting over 50% FG and 40% 3P
        if 10 <= row['PTS'] <= 18 and row['FG%'] > 0.50 and row['3P%'] > 0.40:
            return "🔥 HOT (Efficiency)"
            
        # LOGIC 2: The "Opportunity" (Increased Minutes vs Weak D)
        # Role players playing 26+ minutes against defenses rated > 117
        if row['MP'] > 26 and opp_drtg > 117:
            return "🚀 VALUE (Matchup)"
            
        # LOGIC 3: High Volume Starters (Original Logic)
        if row['PTS'] > 22:
            return "🔥 HOT (High Usage)"
            
        return "➡️ STEADY"

    df['SIGNAL'] = df.apply(get_role_player_signal, axis=1)
    
    # Save the expanded report
    df.to_csv('parbs_picks_global_report.csv', index=False)
    print("✅ Expanded Report Generated: Role player predictions included.")

except Exception as e:
    print(f"❌ Analysis Failed: {e}")