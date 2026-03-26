import pandas as pd
import os
import time
from io import StringIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

class BRefScraper:
    def __init__(self):
        self.root_path = os.getcwd()
        options = Options()
        options.add_argument("--headless") # Runs in background
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        # This is the secret sauce: it makes Selenium look like a normal Mac user
        stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)

    def get_player_slug(self, name):
        first, last = name.lower().split(' ')
        return f"{last[:5]}{first[:2]}01", last[0]

    def sync_player(self, player_name):
        print(f"🔄 FINAL AUDIT ATTEMPT: {player_name}...")
        slug, initial = self.get_player_slug(player_name)
        url = f"https://www.basketball-reference.com/players/{initial}/{slug}/gamelog/2026"
        
        try:
            self.driver.get(url)
            time.sleep(3) # Let the table load
            
            # Find the game log table by its ID
            html = self.driver.page_source
            df_list = pd.read_html(StringIO(html), attrs={'id': 'pgl_basic'})
            df = df_list[0]
            
            # Cleaning & TS% Delta Math
            df = df[df['G'] != 'G'].copy()
            for col in ['PTS', 'FGA', 'FTA', 'MP']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df['TS_Percentage'] = df['PTS'] / (2 * (df['FGA'] + (0.44 * df['FTA'])))
            df['TS_Percentage'] = df['TS_Percentage'].fillna(0)
            
            filename = f"{player_name.lower().replace(' ', '_')}_stats_2026.csv"
            df.to_csv(filename, index=False)
            print(f"✅ BOOM. {player_name} data is in the system.")
            return True
        except Exception as e:
            print(f"❌ Still blocked: {e}")
            return False
        finally:
            self.driver.quit()