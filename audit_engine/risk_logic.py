import numpy as np

class RiskAuditor:
    def calculate_ts_volatility(self, ts_history):
        """Calculates Standard Deviation of the TS Delta."""
        if len(ts_history) < 5: return 0
        
        # 1. Season Average TS%
        season_avg = np.mean(ts_history)
        
        # 2. Calculate Deltas (Game TS% - Season Avg)
        deltas = [ts - season_avg for ts in ts_history[-10:]]
        
        # 3. Standard Deviation of the Deltas
        volatility = np.std(deltas)
        return round(volatility, 4)

    def check_fatigue(self, mins):
        return "FATIGUED" if sum(mins[-3:]) > 110 else "FRESH"