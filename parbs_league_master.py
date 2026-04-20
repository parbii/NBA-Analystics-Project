"""
parbs_league_master.py
======================
Step 1: Auto-fetches tonight's NBA schedule from ESPN (no key needed).
Step 2: Scrapes every active team's per-game roster from Basketball-Reference.
        → If B-Ref returns 404, automatically falls back to ESPN roster API.
Step 3: Validates every player against ESPN's CURRENT active roster.
        → Removes traded/waived players who still appear on B-Ref season pages.
Step 4: Saves to Parbs_League_Master_2026.csv for downstream analysis.

Stat source note:
  - Basketball-Reference: full season per-game averages (primary stats)
  - ESPN active roster:   current team membership validation (always checked)
  - nba_api:              per-game fallback for teams with B-Ref 404s

Run:
  python3 parbs_league_master.py
"""

import pandas as pd
import requests
import time
import os
from datetime import date
from io import StringIO

os.system('clear')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

# ── Abbreviation maps ─────────────────────────────────────────────────────────
ESPN_TO_BREF = {
    'GS': 'GSW', 'NY': 'NYK', 'NO': 'NOP', 'SA': 'SAS',
    'PHO': 'PHX', 'UTA': 'UTA', 'WSH': 'WAS', 'CHA': 'CHO',
}

# ESPN numeric team IDs (used for active roster validation)
ESPN_TEAM_IDS = {
    'ATL':1,  'BKN':17, 'BOS':2,  'CHO':30, 'CHI':4,
    'CLE':5,  'DAL':6,  'DEN':7,  'DET':8,  'GSW':9,
    'HOU':10, 'IND':11, 'LAC':12, 'LAL':13, 'MEM':29,
    'MIA':14, 'MIL':15, 'MIN':16, 'NOP':3,  'NYK':18,
    'OKC':25, 'ORL':19, 'PHI':20, 'PHX':21, 'POR':22,
    'SAS':24, 'SAC':23, 'TOR':28, 'UTA':26, 'UTAH':26,
    'WAS':27,
}

# ESPN uses full slug for roster endpoint (fallback only)
BREF_TO_ESPN_SLUG = {
    'ATL': 'atlanta-hawks',     'BOS': 'boston-celtics',
    'BKN': 'brooklyn-nets',     'CHO': 'charlotte-hornets',
    'CHI': 'chicago-bulls',     'CLE': 'cleveland-cavaliers',
    'DAL': 'dallas-mavericks',  'DEN': 'denver-nuggets',
    'DET': 'detroit-pistons',   'GSW': 'golden-state-warriors',
    'HOU': 'houston-rockets',   'IND': 'indiana-pacers',
    'LAC': 'la-clippers',       'LAL': 'los-angeles-lakers',
    'MEM': 'memphis-grizzlies', 'MIA': 'miami-heat',
    'MIL': 'milwaukee-bucks',   'MIN': 'minnesota-timberwolves',
    'NOP': 'new-orleans-pelicans', 'NYK': 'new-york-knicks',
    'OKC': 'oklahoma-city-thunder', 'ORL': 'orlando-magic',
    'PHI': 'philadelphia-76ers', 'PHX': 'phoenix-suns',
    'POR': 'portland-trail-blazers', 'SAC': 'sacramento-kings',
    'SAS': 'san-antonio-spurs', 'TOR': 'toronto-raptors',
    'UTA': 'utah-jazz',         'UTAH': 'utah-jazz',
    'WAS': 'washington-wizards',
}

def espn_to_bref(abbr: str) -> str:
    return ESPN_TO_BREF.get(abbr.upper(), abbr.upper())

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Pull tonight's teams from ESPN
# ─────────────────────────────────────────────────────────────────────────────
def get_tonights_teams() -> list:
    today = date.today().strftime('%Y%m%d')
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        f"?dates={today}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get('events', [])

        teams, matchups, opp_map = [], [], {}
        for event in events:
            comp = event['competitions'][0]
            home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
            away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
            home_abbr = espn_to_bref(home['team']['abbreviation'])
            away_abbr = espn_to_bref(away['team']['abbreviation'])
            game_time = event['status']['type']['shortDetail']
            matchups.append(f"{away_abbr} @ {home_abbr}  ({game_time})")
            teams.extend([home_abbr, away_abbr])
            opp_map[home_abbr] = away_abbr
            opp_map[away_abbr] = home_abbr

        print(f"\n📅 {date.today().strftime('%A, %B %d %Y')} — {len(events)} games tonight:\n")
        for m in matchups:
            print(f"   🏀 {m}")
        print()
        return teams, opp_map

    except Exception as e:
        print(f"⚠️  ESPN schedule fetch failed: {e}")
        print("⚠️  Falling back to manual team list.")
        return ['CHI', 'GSW', 'MIN', 'LAL', 'BOS', 'SAS', 'DAL', 'ATL', 'PHX', 'MIL'], {}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2a — Primary: Basketball-Reference per-game stats
# ─────────────────────────────────────────────────────────────────────────────
def scrape_bref(team: str):
    url = f"https://www.basketball-reference.com/teams/{team}/2026.html"
    try:
        tables = pd.read_html(url)
        df = tables[1]
        df = df[df['Player'] != 'Team Totals']
        df = df.dropna(subset=['Player'])
        df['TEAM_ABBR'] = team
        df['DATA_SOURCE'] = 'B-Ref'
        return df
    except Exception as e:
        print(f"   ⚠️  B-Ref 404 for {team}: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2b — Fallback: ESPN roster + season stats API
# ─────────────────────────────────────────────────────────────────────────────
def scrape_espn(team: str):
    slug = BREF_TO_ESPN_SLUG.get(team)
    if not slug:
        print(f"   ❌ No ESPN slug for {team}, skipping.")
        return None

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{slug}/roster"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        rows = []
        for athlete in data.get('athletes', []):
            stats = athlete.get('statistics', {})
            # ESPN returns a flat stats array with labels
            labels = stats.get('labels', [])
            values = stats.get('splits', {}).get('categories', [])
            stat_dict = {}
            for cat in values:
                for i, label in enumerate(cat.get('labels', [])):
                    if i < len(cat.get('values', [])):
                        stat_dict[label] = cat['values'][i]

            rows.append({
                'Player':    athlete.get('fullName', ''),
                'Pos':       athlete.get('position', {}).get('abbreviation', ''),
                'PTS':       stat_dict.get('PTS', 0),
                'REB':       stat_dict.get('REB', 0),
                'AST':       stat_dict.get('AST', 0),
                'MP':        stat_dict.get('MIN', 0),
                'FG%':       stat_dict.get('FG%', 0),
                '3P%':       stat_dict.get('3P%', 0),
                'FT%':       stat_dict.get('FT%', 0),
                'TEAM_ABBR': team,
                'DATA_SOURCE': 'ESPN',
            })

        df = pd.DataFrame(rows)
        df = df[df['Player'] != ''].dropna(subset=['Player'])
        if df.empty:
            return None
        return df

    except Exception as e:
        print(f"   ❌ ESPN fallback also failed for {team}: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2c — Third fallback: nba_api leaguedashplayerstats
# Pulls season per-game averages directly from stats.nba.com
# ─────────────────────────────────────────────────────────────────────────────

# Cache the full league stats pull so we only hit the API once per run
_nba_api_cache = None

def get_nba_api_cache():
    global _nba_api_cache
    if _nba_api_cache is not None:
        return _nba_api_cache
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        print("   🏀 Pulling full league stats from nba_api (one-time)...")
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season='2025-26',
            per_mode_detailed='PerGame',
        )
        df = stats.get_data_frames()[0]
        # Normalise column names to match B-Ref format
        df = df.rename(columns={
            'PLAYER_NAME': 'Player',
            'TEAM_ABBREVIATION': 'TEAM_ABBR',
            'MIN': 'MP',
            'FG_PCT': 'FG%',
            'FG3_PCT': '3P%',
            'FT_PCT': 'FT%',
        })
        df['DATA_SOURCE'] = 'nba_api'
        _nba_api_cache = df
        return df
    except Exception as e:
        print(f"   ❌ nba_api league stats failed: {e}")
        return None

def scrape_nba_api(team: str):
    df = get_nba_api_cache()
    if df is None:
        return None
    # nba_api uses 'UTA' not 'UTAH'
    lookup = 'UTA' if team == 'UTAH' else team
    team_df = df[df['TEAM_ABBR'] == lookup].copy()
    if team_df.empty:
        return None
    team_df['TEAM_ABBR'] = team  # keep original abbr consistent
    return team_df

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — ESPN active roster validation
# Fetches current team membership from ESPN to strip traded/waived players
# ─────────────────────────────────────────────────────────────────────────────

import unicodedata

def _norm(name: str) -> str:
    """Lowercase, strip accents, strip suffixes for fuzzy name matching."""
    n = unicodedata.normalize('NFD', str(name))
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    n = n.lower().strip()
    for suffix in [' jr.', ' sr.', ' iii', ' ii', ' iv']:
        n = n.replace(suffix, '')
    return n.strip()

_espn_roster_cache = {}

def get_espn_active_names(team: str) -> set:
    """Returns a set of normalised player names currently on this team per ESPN."""
    if team in _espn_roster_cache:
        return _espn_roster_cache[team]

    team_id = ESPN_TEAM_IDS.get(team)
    if not team_id:
        return set()

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        athletes = r.json().get('athletes', [])
        names = {_norm(a['fullName']) for a in athletes}
        _espn_roster_cache[team] = names
        return names
    except Exception as e:
        print(f"   ⚠️  ESPN active roster check failed for {team}: {e}")
        return set()

# Build a full league-wide name → correct team map from ESPN
_espn_global_map = {}   # norm_name → bref_abbr

ESPN_ID_TO_BREF = {v: k for k, v in ESPN_TEAM_IDS.items() if k not in ('UTAH',)}
# Prefer the canonical abbr (UTA not UTAH)
ESPN_ID_TO_BREF[26] = 'UTA'

def build_espn_global_map():
    """
    Fetches all 30 ESPN rosters once and builds a global
    {normalised_player_name: correct_team_abbr} lookup.
    Called once per run — cached after that.
    """
    global _espn_global_map
    if _espn_global_map:
        return _espn_global_map

    print("   🌐 Building global ESPN player→team map (all 30 rosters)...")
    seen_ids = set()
    for bref_abbr, espn_id in ESPN_TEAM_IDS.items():
        if espn_id in seen_ids:
            continue
        seen_ids.add(espn_id)
        canonical = ESPN_ID_TO_BREF.get(espn_id, bref_abbr)
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{espn_id}/roster"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            for a in r.json().get('athletes', []):
                _espn_global_map[_norm(a['fullName'])] = canonical
            # Also populate the per-team cache
            names = {_norm(a['fullName']) for a in r.json().get('athletes', [])}
            _espn_roster_cache[canonical] = names
            _espn_roster_cache[bref_abbr] = names
        except Exception:
            pass
        time.sleep(0.3)

    print(f"   ✅ Global map built: {len(_espn_global_map)} players across 30 teams.")
    return _espn_global_map

def validate_roster(df: pd.DataFrame, team: str) -> pd.DataFrame:
    """
    Two-pass validation:
    1. Remove players NOT on this team's ESPN roster (traded/waived).
    2. Correct team tag for any player whose ESPN team differs from B-Ref tag.
       e.g. Anthony Davis tagged DAL by B-Ref but ESPN says WAS → fix to WAS.
    """
    global_map = build_espn_global_map()
    active_names = get_espn_active_names(team)

    player_col = 'Player' if 'Player' in df.columns else 'PLAYER'
    team_col   = 'TEAM_ABBR'
    original_count = len(df)

    # Pass 1 — strip players not on this team per ESPN
    if active_names:
        def is_active(name):
            return _norm(str(name)) in active_names
        df_valid = df[df[player_col].apply(is_active)].copy()
        removed = original_count - len(df_valid)
        if removed > 0:
            removed_names = df[~df[player_col].apply(is_active)][player_col].tolist()
            print(f"   🔍 Validated vs ESPN: removed {removed} → {removed_names}")
    else:
        df_valid = df.copy()

    # Pass 2 — correct team tags using global map
    corrections = 0
    for idx, row in df_valid.iterrows():
        norm = _norm(str(row[player_col]))
        correct_team = global_map.get(norm)
        if correct_team and correct_team != row.get(team_col, ''):
            df_valid.at[idx, team_col] = correct_team
            corrections += 1
    if corrections > 0:
        print(f"   🔧 Corrected {corrections} team tag(s) to match ESPN current roster.")

    return df_valid
def get_roster(team: str):
    print(f"   📦 {team} — trying B-Ref...", end=' ', flush=True)
    df = scrape_bref(team)
    if df is not None:
        print(f"✅ ({len(df)} players)", end=' ', flush=True)
        df = validate_roster(df, team)
        if not df.empty:
            return df

    print(f"↩️  ESPN...", end=' ', flush=True)
    df = scrape_espn(team)
    if df is not None:
        # ESPN roster endpoint already returns current players — no extra validation needed
        print(f"✅ ESPN ({len(df)} players)")
        return df

    print(f"↩️  nba_api...", end=' ', flush=True)
    df = scrape_nba_api(team)
    if df is not None:
        print(f"✅ nba_api ({len(df)} players)", end=' ', flush=True)
        df = validate_roster(df, team)
        print()
        return df

    print("❌ all 3 sources failed.")
    return None

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
print("🚀 PARB'S GLOBAL ENGINE — AUTO-DETECTING TONIGHT'S MATCHUPS...")
print("="*60)

teams_tonight, opp_map = get_tonights_teams()
print(f"🔍 Fetching rosters for {len(teams_tonight)} teams...\n")

all_data = []
failed = []
for i, team in enumerate(teams_tonight):
    df = get_roster(team)
    if df is not None:
        all_data.append(df)
    else:
        failed.append(team)
    time.sleep(2 if i < 3 else 3)

if all_data:
    master_df = pd.concat(all_data, ignore_index=True)

    master_df['OPP'] = master_df['TEAM_ABBR'].map(opp_map).fillna('???')

    master_df.to_csv('Parbs_League_Master_2026.csv', index=False)
    sources = master_df['DATA_SOURCE'].value_counts().to_dict() if 'DATA_SOURCE' in master_df.columns else {}
    print(f"\n{'='*60}")
    print(f"✅ SUCCESS: {len(master_df)} players across {len(all_data)} teams.")
    if sources:
        print(f"📊 Sources: {sources}")
    if failed:
        print(f"❌ Could not retrieve: {failed}")
    print(f"📁 Saved → Parbs_League_Master_2026.csv")
    print(f"▶  Run parbs_master_analysis.py next for signals.")
    print(f"{'='*60}")
else:
    print("❌ No data collected. Check your connection and try again.")
