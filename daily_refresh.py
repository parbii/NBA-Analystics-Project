"""
daily_refresh.py
================
Free, zero-key daily data pipeline.

Fetch order (per player):
  1. ESPN hidden API  — fastest, live/same-day box scores
  2. nba_api          — full season game logs after games complete
  3. StatMuse scraper — fallback if nba_api gets rate-limited

After fetching:
  → Stitches all player CSVs into Bulls_Master_2026.csv
  → Runs Bulls dashboard analysis  (bulls_advanced_signals.csv)
  → Runs Parbs role-player engine  (parbs_picks_global_report.csv)
  → Runs chart + thumbnail generation

Usage:
  python daily_refresh.py              # full run
  python daily_refresh.py --fetch-only # skip analysis/charts
  python daily_refresh.py --analyze-only # skip fetching
"""

import os, sys, time, random, logging, importlib, runpy
import requests
import pandas as pd
from datetime import date, datetime
from io import StringIO

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    handlers=[
        logging.FileHandler(f"logs/refresh_{date.today()}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("daily_refresh")

# ── Roster ────────────────────────────────────────────────────────────────────
# Add / remove players here. nba_api_id comes from stats.nba.com player IDs.
ROSTER = [
    {"name": "Josh Giddey",       "nba_api_id": "1630581"},
    {"name": "Coby White",        "nba_api_id": "1629632"},
    {"name": "Nikola Vucevic",    "nba_api_id": "202696"},
    {"name": "Zach LaVine",       "nba_api_id": "203897"},
    {"name": "Patrick Williams",  "nba_api_id": "1630172"},
    {"name": "Ayo Dosunmu",       "nba_api_id": "1630544"},
    {"name": "Tre Jones",         "nba_api_id": "1630200"},
    {"name": "Jaden Ivey",        "nba_api_id": "1630596"},
    {"name": "Collin Sexton",     "nba_api_id": "1629012"},
    {"name": "Matas Buzelis",     "nba_api_id": "1642258"},
]

SEASON = "2025-26"

# ── Helpers ───────────────────────────────────────────────────────────────────
def csv_path(player_name: str) -> str:
    return f"{player_name.lower().replace(' ', '_')}_stats_2026.csv"

def cooldown(lo=4, hi=9):
    wait = random.uniform(lo, hi)
    log.info(f"  ⏳ cooling off {round(wait, 1)}s...")
    time.sleep(wait)

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — ESPN hidden API (no key, live same-day data)
# ─────────────────────────────────────────────────────────────────────────────
ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def espn_get_today_game_ids() -> list:
    """Returns ESPN game IDs for today's NBA slate."""
    today = date.today().strftime("%Y%m%d")
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        f"?dates={today}"
    )
    try:
        r = requests.get(url, headers=ESPN_HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get("events", [])
        ids = [e["id"] for e in events]
        log.info(f"ESPN: {len(ids)} game(s) found today.")
        return ids
    except Exception as e:
        log.warning(f"ESPN scoreboard failed: {e}")
        return []

def espn_player_stats_from_game(game_id: str) -> pd.DataFrame:
    """Pulls box score for one game, returns a flat player-stats DataFrame."""
    url = (
        "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
        f"?event={game_id}"
    )
    try:
        r = requests.get(url, headers=ESPN_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        rows = []
        for team in data.get("boxscore", {}).get("players", []):
            team_abbr = team["team"]["abbreviation"]
            for stat_group in team.get("statistics", []):
                keys = stat_group.get("keys", [])
                for athlete in stat_group.get("athletes", []):
                    vals = athlete.get("stats", [])
                    row = dict(zip(keys, vals))
                    row["PLAYER"] = athlete["athlete"]["displayName"]
                    row["TEAM_ABBR"] = team_abbr
                    row["GAME_ID"] = game_id
                    row["GAME_DATE"] = date.today().isoformat()
                    rows.append(row)
        return pd.DataFrame(rows)
    except Exception as e:
        log.warning(f"ESPN box score failed for game {game_id}: {e}")
        return pd.DataFrame()

def fetch_via_espn(player_name: str) -> bool:
    """
    Pulls today's box score stats for a player from ESPN.
    Appends to their existing CSV so history is preserved.
    """
    game_ids = espn_get_today_game_ids()
    if not game_ids:
        return False

    for gid in game_ids:
        df = espn_player_stats_from_game(gid)
        if df.empty:
            continue
        # Normalise name matching (case-insensitive)
        match = df[df["PLAYER"].str.lower() == player_name.lower()]
        if match.empty:
            continue

        # Standardise columns
        match = match.copy()
        match.columns = [c.upper() for c in match.columns]

        out = csv_path(player_name)
        if os.path.exists(out):
            existing = pd.read_csv(out)
            existing.columns = [c.upper() for c in existing.columns]
            combined = pd.concat([existing, match], ignore_index=True)
            # Deduplicate by game id if column exists
            if "GAME_ID" in combined.columns:
                combined = combined.drop_duplicates(subset=["GAME_ID"])
            combined.to_csv(out, index=False)
        else:
            match.to_csv(out, index=False)

        log.info(f"  ✅ ESPN: {player_name} — today's box score saved.")
        return True

    log.info(f"  ℹ️  ESPN: {player_name} not in today's games.")
    return False

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — nba_api (full season game logs, no key)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_via_nba_api(player_name: str, nba_api_id: str) -> bool:
    """Pulls full season game log from stats.nba.com."""
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        log.warning("nba_api not installed. Run: pip install nba_api")
        return False

    NBA_HEADERS = {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Referer": "https://stats.nba.com/",
    }

    try:
        log.info(f"  🏀 nba_api: fetching {player_name}...")
        gl = playergamelog.PlayerGameLog(
            player_id=nba_api_id,
            season=SEASON,
            headers=NBA_HEADERS,
            timeout=90,
        )
        df = gl.get_data_frames()[0]
        if df.empty:
            log.warning(f"  ⚠️  nba_api returned empty for {player_name}")
            return False

        df["PLAYER_NAME"] = player_name
        df.columns = [c.upper() for c in df.columns]
        df.to_csv(csv_path(player_name), index=False)
        log.info(f"  ✅ nba_api: {player_name} — {len(df)} games saved.")
        return True
    except Exception as e:
        log.warning(f"  ❌ nba_api failed for {player_name}: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3 — StatMuse scraper (fallback, no key)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_via_statmuse(player_name: str) -> bool:
    """Falls back to StatMuse HTML scraping."""
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), "data_ingestion"))
        from sm_scraper import SMScraper
        scraper = SMScraper()
        return scraper.sync_player(player_name)
    except Exception as e:
        log.warning(f"  ❌ StatMuse failed for {player_name}: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# FETCH ORCHESTRATOR — tries all 3 sources in order
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player(player: dict) -> bool:
    name = player["name"]
    nba_id = player["nba_api_id"]
    log.info(f"\n{'─'*55}")
    log.info(f"🔄 Syncing: {name}")

    # 1. Try ESPN first (live/today)
    if fetch_via_espn(name):
        cooldown(2, 5)
        return True

    # 2. Try nba_api for full game log
    if fetch_via_nba_api(name, nba_id):
        cooldown(6, 11)
        return True

    # 3. Fall back to StatMuse
    log.info(f"  🔁 Falling back to StatMuse for {name}...")
    if fetch_via_statmuse(name):
        cooldown(3, 7)
        return True

    log.error(f"  💀 All sources failed for {name}. Skipping.")
    return False

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────────────────────────────────────
def run_fetch():
    log.info("\n" + "="*55)
    log.info("  STEP 1 — FETCHING PLAYER DATA")
    log.info("="*55)
    results = {"ok": [], "failed": []}
    for player in ROSTER:
        ok = fetch_player(player)
        (results["ok"] if ok else results["failed"]).append(player["name"])

    log.info(f"\n✅ Fetched:  {results['ok']}")
    if results["failed"]:
        log.warning(f"❌ Failed:   {results['failed']}")
    return results

def run_stitch():
    log.info("\n" + "="*55)
    log.info("  STEP 2 — STITCHING MASTER CSV")
    log.info("="*55)
    import glob
    all_files = glob.glob("*_stats_2026.csv")
    if not all_files:
        log.error("No player CSVs found. Run fetch first.")
        return

    frames = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            player_name = f.split("_stats")[0].replace("_", " ").title()
            df["PLAYER_NAME"] = player_name
            df.columns = [c.upper() for c in df.columns]
            frames.append(df)
        except Exception as e:
            log.warning(f"Could not read {f}: {e}")

    master = pd.concat(frames, axis=0, ignore_index=True)
    master.to_csv("Bulls_Master_2026.csv", index=False)
    log.info(f"✅ Bulls_Master_2026.csv — {len(master)} rows across {len(frames)} players.")

def run_analysis():
    log.info("\n" + "="*55)
    log.info("  STEP 3 — RUNNING ANALYSIS")
    log.info("="*55)
    scripts = [
        ("bulls_dashboard.py",      "Bulls advanced signals"),
        ("parbs_master_analysis.py","Parbs role-player engine"),
        ("parbs_global_analysis.py","Parbs matchup/defense signals"),
    ]
    for script, label in scripts:
        if not os.path.exists(script):
            log.warning(f"  ⚠️  {script} not found, skipping.")
            continue
        try:
            log.info(f"  ▶ Running {label}...")
            runpy.run_path(script, run_name="__main__")
            log.info(f"  ✅ {label} complete.")
        except Exception as e:
            log.error(f"  ❌ {label} failed: {e}")

def run_tf_model():
    log.info("\n" + "="*55)
    log.info("  STEP 4 — TF PROP MODEL (Regression + Filters)")
    log.info("="*55)
    if not os.path.exists("Bulls_Master_2026.csv"):
        log.warning("  ⚠️  Bulls_Master_2026.csv not found, skipping TF model.")
        return
    try:
        import tf_prop_model
        # Re-train weekly (Monday), predict every day
        import datetime
        if datetime.date.today().weekday() == 0:  # Monday
            log.info("  🧠 Monday — re-training model on fresh data...")
            tf_prop_model.train()
        tf_prop_model.predict()
        log.info("  ✅ TF predictions saved → tf_prop_predictions.csv")
    except ImportError:
        log.warning("  ⚠️  TensorFlow not installed. Run: pip install tensorflow scikit-learn")
    except Exception as e:
        log.error(f"  ❌ TF model failed: {e}")

def run_visuals():
    log.info("\n" + "="*55)
    log.info("  STEP 5 — GENERATING CHARTS & THUMBNAILS")
    log.info("="*55)
    for script, label in [
        ("parbs_chart_gen.py",  "Global chart"),
        ("parbs_thumb_gen.py",  "Elite pick thumbnail"),
    ]:
        if not os.path.exists(script):
            log.warning(f"  ⚠️  {script} not found, skipping.")
            continue
        try:
            log.info(f"  ▶ {label}...")
            runpy.run_path(script, run_name="__main__")
            log.info(f"  ✅ {label} done.")
        except Exception as e:
            log.error(f"  ❌ {label} failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fetch_only   = "--fetch-only"   in sys.argv
    analyze_only = "--analyze-only" in sys.argv

    start = datetime.now()
    log.info(f"\n{'='*55}")
    log.info(f"  🏀 PARB'S DAILY REFRESH — {date.today()}")
    log.info(f"{'='*55}")

    if not analyze_only:
        run_fetch()
        run_stitch()

    if not fetch_only:
        run_analysis()
        run_tf_model()
        run_visuals()

    elapsed = round((datetime.now() - start).total_seconds(), 1)
    log.info(f"\n🏁 Done in {elapsed}s. Check logs/refresh_{date.today()}.log for full output.")
