"""
daily_refresh.py
================
Parb's fully automated daily NBA pipeline.
Runs every day — skips automatically if no games are scheduled.

Pipeline order (every run):
  1. Check ESPN for today's games — exits cleanly if none
  2. Fetch tonight's rosters (B-Ref → ESPN → nba_api)
     → ESPN active roster validation strips traded/waived players
  3. Pull live injury report from ESPN
  4. Fetch Bulls player game logs (ESPN box score → nba_api → StatMuse)
  5. Stitch Bulls game logs into Bulls_Master_2026.csv
  6. Run full analysis (injuries filtered, all roles scored)
  7. TF prop model predictions (retrain every Monday)
  8. Generate charts + thumbnails

Usage:
  python3 daily_refresh.py                # full run
  python3 daily_refresh.py --fetch-only   # data only, skip analysis
  python3 daily_refresh.py --analyze-only # analysis only, skip fetching
  python3 daily_refresh.py --force        # run even if no games today
"""

import os, sys, time, random, logging, runpy
import requests
import pandas as pd
from datetime import date, datetime

# ── Logging ───────────────────────────────────────────────────────────────────
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

SEASON = "2025-26"

# ── Bulls roster (update each season) ────────────────────────────────────────
BULLS_ROSTER = [
    {"name": "Josh Giddey",      "nba_api_id": "1630581"},
    {"name": "Coby White",       "nba_api_id": "1629632"},
    {"name": "Nikola Vucevic",   "nba_api_id": "202696"},
    {"name": "Patrick Williams", "nba_api_id": "1630172"},
    {"name": "Ayo Dosunmu",      "nba_api_id": "1630544"},
    {"name": "Tre Jones",        "nba_api_id": "1630200"},
    {"name": "Jaden Ivey",       "nba_api_id": "1630596"},
    {"name": "Collin Sexton",    "nba_api_id": "1629012"},
    {"name": "Matas Buzelis",    "nba_api_id": "1642258"},
]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 0 — Game day check
# ─────────────────────────────────────────────────────────────────────────────
def get_todays_games() -> list:
    """Returns list of game event dicts from ESPN. Empty = no games today."""
    today = date.today().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as e:
        log.warning(f"ESPN schedule check failed: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Tonight's rosters (delegates to parbs_league_master.py)
#           Includes: B-Ref stats → ESPN active validation → nba_api fallback
#           Injury report pulled inside parbs_master_analysis.py
# ─────────────────────────────────────────────────────────────────────────────
def run_league_master():
    log.info("\n" + "="*55)
    log.info("  STEP 1 — FETCHING TONIGHT'S ROSTERS (ALL SOURCES)")
    log.info("  Validates every player against ESPN active roster")
    log.info("="*55)
    try:
        runpy.run_path("parbs_league_master.py", run_name="__main__")
        log.info("  ✅ Parbs_League_Master_2026.csv — verified active players only.")
    except Exception as e:
        log.error(f"  ❌ League master failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Bulls game log fetching
# ─────────────────────────────────────────────────────────────────────────────
def csv_path(name: str) -> str:
    return f"{name.lower().replace(' ', '_')}_stats_2026.csv"

def cooldown(lo=5, hi=10):
    wait = random.uniform(lo, hi)
    log.info(f"  ⏳ {round(wait,1)}s cooldown...")
    time.sleep(wait)

def fetch_via_espn(player_name: str, game_ids: list) -> bool:
    for gid in game_ids:
        url = (f"https://site.web.api.espn.com/apis/site/v2/sports/basketball"
               f"/nba/summary?event={gid}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            rows = []
            for team in r.json().get("boxscore", {}).get("players", []):
                abbr = team["team"]["abbreviation"]
                for grp in team.get("statistics", []):
                    keys = grp.get("keys", [])
                    for athlete in grp.get("athletes", []):
                        row = dict(zip(keys, athlete.get("stats", [])))
                        row.update({"PLAYER": athlete["athlete"]["displayName"],
                                    "TEAM_ABBR": abbr, "GAME_ID": gid,
                                    "GAME_DATE": date.today().isoformat()})
                        rows.append(row)
            if not rows:
                continue
            df = pd.DataFrame(rows)
            match = df[df["PLAYER"].str.lower() == player_name.lower()]
            if match.empty:
                continue
            match = match.copy()
            match.columns = [c.upper() for c in match.columns]
            out = csv_path(player_name)
            if os.path.exists(out):
                existing = pd.read_csv(out)
                existing.columns = [c.upper() for c in existing.columns]
                combined = pd.concat([existing, match], ignore_index=True)
                if "GAME_ID" in combined.columns:
                    combined = combined.drop_duplicates(subset=["GAME_ID"])
                combined.to_csv(out, index=False)
            else:
                match.to_csv(out, index=False)
            log.info(f"  ✅ ESPN: {player_name} box score saved.")
            return True
        except Exception as e:
            log.warning(f"  ESPN box score error for game {gid}: {e}")
    return False

def fetch_via_nba_api(player_name: str, nba_api_id: str) -> bool:
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        log.warning("nba_api not installed.")
        return False
    nba_headers = {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Referer": "https://stats.nba.com/",
    }
    try:
        log.info(f"  🏀 nba_api: {player_name}...")
        gl = playergamelog.PlayerGameLog(
            player_id=nba_api_id, season=SEASON,
            headers=nba_headers, timeout=90)
        df = gl.get_data_frames()[0]
        if df.empty:
            return False
        df["PLAYER_NAME"] = player_name
        df.columns = [c.upper() for c in df.columns]
        df.to_csv(csv_path(player_name), index=False)
        log.info(f"  ✅ nba_api: {player_name} — {len(df)} games.")
        return True
    except Exception as e:
        log.warning(f"  ❌ nba_api: {player_name}: {e}")
        return False

def fetch_via_statmuse(player_name: str) -> bool:
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), "data_ingestion"))
        from sm_scraper import SMScraper
        return SMScraper().sync_player(player_name)
    except Exception as e:
        log.warning(f"  ❌ StatMuse: {player_name}: {e}")
        return False

def run_fetch(game_ids: list):
    log.info("\n" + "="*55)
    log.info("  STEP 2 — FETCHING BULLS GAME LOGS")
    log.info("="*55)
    ok, failed = [], []
    for player in BULLS_ROSTER:
        name, pid = player["name"], player["nba_api_id"]
        log.info(f"\n  🔄 {name}")
        if fetch_via_espn(name, game_ids):
            ok.append(name); cooldown(2, 5); continue
        if fetch_via_nba_api(name, pid):
            ok.append(name); cooldown(6, 11); continue
        log.info(f"  🔁 StatMuse fallback...")
        if fetch_via_statmuse(name):
            ok.append(name); cooldown(3, 7); continue
        log.error(f"  💀 All sources failed: {name}")
        failed.append(name)
    log.info(f"\n  ✅ Fetched: {ok}")
    if failed:
        log.warning(f"  ❌ Failed:  {failed}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Stitch Bulls master CSV
# ─────────────────────────────────────────────────────────────────────────────
def run_stitch():
    log.info("\n" + "="*55)
    log.info("  STEP 3 — STITCHING BULLS MASTER CSV")
    log.info("="*55)
    import glob
    files = glob.glob("*_stats_2026.csv")
    if not files:
        log.error("  No player CSVs found.")
        return
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["PLAYER_NAME"] = f.split("_stats")[0].replace("_", " ").title()
            df.columns = [c.upper() for c in df.columns]
            frames.append(df)
        except Exception as e:
            log.warning(f"  Could not read {f}: {e}")
    master = pd.concat(frames, ignore_index=True)
    master.to_csv("Bulls_Master_2026.csv", index=False)
    log.info(f"  ✅ Bulls_Master_2026.csv — {len(master)} rows, {len(frames)} players.")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Full analysis (injuries + all roles)
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis():
    log.info("\n" + "="*55)
    log.info("  STEP 4 — RUNNING ANALYSIS (injuries + all roles)")
    log.info("="*55)
    for script, label in [
        ("bulls_dashboard.py",       "Bulls advanced signals"),
        ("parbs_master_analysis.py", "Parbs full report (injuries + roles)"),
        ("parbs_global_analysis.py", "Parbs matchup/defense signals"),
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
# STEP 5 — TF prop model
# ─────────────────────────────────────────────────────────────────────────────
def run_tf_model():
    log.info("\n" + "="*55)
    log.info("  STEP 5 — TF PROP MODEL")
    log.info("="*55)
    if not os.path.exists("Bulls_Master_2026.csv"):
        log.warning("  ⚠️  Bulls_Master_2026.csv missing, skipping.")
        return
    try:
        import tf_prop_model
        if date.today().weekday() == 0:  # Monday = retrain
            log.info("  🧠 Monday — retraining on fresh data...")
            tf_prop_model.train()
        tf_prop_model.predict()
        log.info("  ✅ Predictions → tf_prop_predictions.csv")
    except ImportError:
        log.warning("  ⚠️  TensorFlow not installed: pip install tensorflow scikit-learn")
    except Exception as e:
        log.error(f"  ❌ TF model failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Charts + thumbnails
# ─────────────────────────────────────────────────────────────────────────────
def run_visuals():
    log.info("\n" + "="*55)
    log.info("  STEP 6 — CHARTS & THUMBNAILS")
    log.info("="*55)
    for script, label in [
        ("parbs_chart_gen.py", "Global chart"),
        ("parbs_thumb_gen.py", "Elite pick thumbnail"),
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
    force        = "--force"        in sys.argv

    start = datetime.now()
    log.info(f"\n{'='*55}")
    log.info(f"  🏀 PARB'S DAILY REFRESH — {date.today().strftime('%A, %B %d %Y')}")
    log.info(f"{'='*55}")

    # ── Game day guard ────────────────────────────────────────────────────────
    games = get_todays_games()
    if not games and not force:
        log.info("  📅 No NBA games scheduled today. Pipeline skipped.")
        log.info("  Run with --force to override.")
        sys.exit(0)

    log.info(f"  📅 {len(games)} game(s) tonight — running full pipeline.\n")
    game_ids = [g["id"] for g in games]

    if not analyze_only:
        run_league_master()   # rosters + ESPN active validation + injury awareness
        run_fetch(game_ids)   # Bulls game logs
        run_stitch()          # Bulls_Master_2026.csv

    if not fetch_only:
        run_analysis()        # injuries filtered, all roles scored
        run_tf_model()        # regression predictions
        run_visuals()         # charts + thumbnails
        # Investment engine — always last, uses all prior outputs
        log.info("\n" + "="*55)
        log.info("  STEP 7 — DAILY PICKS ENGINE (filtered)")
        log.info("="*55)
        try:
            import parbs_daily_picks
            parbs_daily_picks.run(date.today())
            log.info("  ✅ Picks → parbs_projections.csv")
        except Exception as e:
            log.error(f"  ❌ Daily picks failed: {e}")

    elapsed = round((datetime.now() - start).total_seconds(), 1)
    log.info(f"\n{'='*55}")
    log.info(f"  🏁 Done in {elapsed}s — {date.today()}")
    log.info(f"  📋 Log → logs/refresh_{date.today()}.log")
    log.info(f"{'='*55}")
