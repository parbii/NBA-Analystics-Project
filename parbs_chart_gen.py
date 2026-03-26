import pandas as pd
import matplotlib.pyplot as plt
import os

os.system('clear')

# 1. LOAD AND FIX DATA
try:
    # We use the report you generated earlier
    df = pd.read_csv('parbs_picks_global_report.csv')
    
    # THE MIS FIX: Force all columns to UPPERCASE and remove extra spaces
    df.columns = [c.upper().strip() for c in df.columns]
    
    # Convert stats to numeric so the sort works
    df['PTS'] = pd.to_numeric(df['PTS'], errors='coerce')
    
    # Identify the Team column (could be TM or TEAM_ABBR)
    tm_col = 'TEAM_ABBR' if 'TEAM_ABBR' in df.columns else 'TM'
    
    # 2. SELECTION: Get a mix of top Stars and Role Player Value
    # This ensures your chart is full of high-value info
    stars = df.sort_values('PTS', ascending=False).head(10)
    role_players = df[df['SIGNAL'].str.contains('VALUE|EFFICIENCY', na=False)].head(5)
    
    chart_df = pd.concat([stars, role_players]).drop_duplicates().head(15)
    
    # 3. DATA BINDING: Mapping the actual values to a list for the table
    # This prevents the "Blank Cell" bug
    display_data = []
    for _, row in chart_df.iterrows():
        display_data.append([
            str(row['PLAYER']),
            str(row[tm_col]),
            f"{row['PTS']:.1f}",
            str(row['SIGNAL'])
        ])

    print(f"✅ Data Binding Success: {len(display_data)} rows loaded.")

except Exception as e:
    print(f"❌ Data Error: {e}")
    exit()

# 4. VISUAL ENGINE
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(12, 18))
ax.axis('off')

table = ax.table(
    cellText=display_data,
    colLabels=['PLAYER', 'TEAM', 'PPG', 'STATUS'],
    cellLoc='center', loc='center',
    colColours=['#1e272e']*4
)

table.auto_set_font_size(False)
table.set_fontsize(14)
table.scale(1.1, 4.2) # Tall for mobile screens

# 5. DYNAMIC COLORING
for i in range(len(display_data)):
    signal = display_data[i][3]
    cell = table[(i+1, 3)] # The Status Column
    
    if "HOT" in signal or "GREEN" in signal:
        cell.get_text().set_color('#2ecc71') # Green
    elif "VALUE" in signal or "EFFICIENCY" in signal:
        cell.get_text().set_color('#f1c40f') # Gold
    elif "COLD" in signal or "LOCK" in signal:
        cell.get_text().set_color('#3498db') # Blue
    else:
        cell.get_text().set_color('#bdc3c7') # Gray

plt.title("PARB'S PICKS: GLOBAL INVESTMENT AUDIT\nMARCH 11, 2026", 
          fontsize=22, fontweight='bold', pad=40, color='white')

# 6. SAVE THE IMAGE
plt.savefig('parbs_global_chart_FINAL.png', bbox_inches='tight', dpi=300, facecolor='#050505')
print("🔥 FULL DATA SECURED: Check 'parbs_global_chart_FINAL.png' now!")