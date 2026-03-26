import pandas as pd
import glob
import os

# 1. Identify all player CSV files in your current folder
# It looks for files ending in '_stats_2026.csv'
all_files = glob.glob("*_stats_2026.csv")

li = []

print(f"Stitching {len(all_files)} players together...")

for filename in all_files:
    # Load the individual player file
    df = pd.read_csv(filename, index_col=None, header=0)
    
    # Extract the name from the filename (e.g., 'tre_jones' from 'tre_jones_stats_2026.csv')
    player_name = filename.split('_stats')[0].replace('_', ' ').title()
    
    # Add a new column so we know who the stats belong to
    df['PLAYER_NAME'] = player_name
    
    # Standardize column names to uppercase
    df.columns = [c.upper() for c in df.columns]
    
    li.append(df)

# 2. Concatenate (stack) them all into one Master DataFrame
bulls_master = pd.concat(li, axis=0, ignore_index=True)

# 3. Save the master file
bulls_master.to_csv('Bulls_Master_2026.csv', index=False)

print("\n--- Success! ---")
print(f"Created 'Bulls_Master_2026.csv' with {len(bulls_master)} total rows.")
print("You can now safely delete the individual player CSVs if you want.")