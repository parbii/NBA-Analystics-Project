import pandas as pd

# The URL for the 2025-26 Bulls 
url = "https://www.basketball-reference.com/teams/CHI/2026.html"

print("🚀 Parb's Analytics: Bypassing NBA API... Scraping Basketball-Reference...")

try:
    # Adding flavor='bs4' tells pandas to use the most reliable scraping engine
    all_tables = pd.read_html(url, flavor='bs4')
    
    # Table [0] is usually the Roster, Table [1] is often the Per Game stats
    # We want the Per Game stats for your "Heat" analysis
    bulls_stats = all_tables[1]
    
    # Clean up: Basketball-Reference often has 'Rk' as the first column
    bulls_stats = bulls_stats.dropna(subset=['Player'])
    
    # Save it so your dashboard can use it
    bulls_stats.to_csv('Bulls_Master_2026.csv', index=False)
    
    print("\n✅ SUCCESS: Full Bulls Roster Secured.")
    print(bulls_stats[['Player', 'PTS', 'MP', 'FG%']].head(10))

except Exception as e:
    print(f"❌ Scraping Failed: {e}")