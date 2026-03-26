import pandas as pd
import numpy as np

def run_6pm_volume_audit(player_name, game_logs_df):
    """
    Calculates PRA Volatility and Usage-to-Efficiency ratio.
    """
    # 1. Calculate Game-by-Game PRA
    game_logs_df['PRA'] = game_logs_df['PTS'] + game_logs_df['REB'] + game_logs_df['AST']
    
    # 2. PRA Volatility (Standard Deviation of the last 10)
    pra_history = game_logs_df['PRA'].tail(10).tolist()
    volatility_pra = round(np.std(pra_history), 2)
    
    # 3. Usage Rate Audit
    # If using season totals for USG%, we pull the average
    avg_usage = game_logs_df['USG_PCT'].mean() if 'USG_PCT' in game_logs_df.columns else 0
    
    # ALPHA STATUS
    # High USG + Low PRA Volatility = The "Blue Chip" Investment
    if avg_usage > 28 and volatility_pra < 6.0:
        status = "💎 BLUE CHIP"
    elif avg_usage > 30 and volatility_pra > 9.0:
        status = "⚠️ VOLATILE STAR"
    else:
        status = "⚖️ STABLE VOLUME"
        
    return {
        'Player': player_name,
        'Avg_PRA': round(np.mean(pra_history), 1),
        'Volatility_PRA': volatility_pra,
        'Usage_Rate': f"{round(avg_usage, 1)}%",
        'Status': status
    }