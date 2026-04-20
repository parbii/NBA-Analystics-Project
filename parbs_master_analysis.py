"""
parbs_master_analysis.py
========================
Every run automatically:
  1. Pulls live ESPN injury report — filters OUT / Doubtful players
  2. Loads tonight's full 651-player roster (all sources)
  3. Scores EVERY rotation player (not just stars) with role-player signals
  4. Flags injured stars and surfaces their replacements with boosted signals
  5. Outputs full tiered report: HOT / VALUE / ROLE BOOST / STEADY / INJURED
"""

import pandas as pd
import requests
import os

os.system('clear')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

DEF_RATINGS = {
    'OKC':104.9,'SAS':108.5,'BOS':109.8,'ORL':108.7,'GSW':111.1,
    'LAL':114.4,'CHI':115.1,'UTA':119.1,'UTAH':119.1,'WAS':117.8,
    'SAC':117.6,'CHO':112.9,'NOP':115.3,'DET':121.2,'MIL':118.2,
    'ATL':119.5,'MIN':110.3,'DAL':113.7,'PHX':116.2,'DEN':112.8,
    'MEM':115.9,'NYK':111.6,'IND':117.4,'CLE':109.1,'MIA':113.3,
    'PHI':114.6,'POR':119.3,'HOU':116.7,'LAC':113.2,'TOR':118.8,'BKN':120.1,
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Live injury report from ESPN
# ─────────────────────────────────────────────────────────────────────────────
def get_injury_report() -> dict:
    """Returns {player_name_lower: status_string}"""
    print("🏥 Pulling live injury report from ESPN...")
    url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        report = {}
        for team in data.get('injuries', []):
            team_abbr = team.get('team', {}).get('abbreviation', '')
            for player in team.get('injuries', []):
                name   = player.get('athlete', {}).get('displayName', '')
                status = player.get('status', 'Unknown')
                detail = player.get('shortComment', '')
                import unicodedata
                key = unicodedata.normalize('NFD', name)
                key = ''.join(c for c in key if unicodedata.category(c) != 'Mn')
                key = key.lower().strip()
                report[key] = {
                    'name':   name,
                    'team':   team_abbr,
                    'status': status,
                    'detail': detail[:60],
                }
        out_count = sum(1 for v in report.values() if v['status'] in ('Out','Doubtful'))
        dtd_count = sum(1 for v in report.values() if 'questionable' in v['status'].lower() or 'day' in v['status'].lower())
        print(f"  ✅ {len(report)} players on report — {out_count} Out/Doubtful, {dtd_count} Questionable/DTD\n")
        return report
    except Exception as e:
        print(f"  ⚠️  Injury report failed: {e} — proceeding without it\n")
        return {}

def _normalize(name: str) -> str:
    """Lowercase, strip accents/punctuation for comparison."""
    import unicodedata
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return name.lower().strip()

def _lookup(name: str, report: dict):
    """Return report entry for a player or None. Exact match only."""
    key = _normalize(name)
    # Direct hit
    if key in report:
        return report[key]
    # Try without suffixes (Jr., Sr., III, II)
    base = key.replace(' jr.','').replace(' sr.','').replace(' iii','').replace(' ii','').strip()
    if base in report:
        return report[base]
    # Try report keys stripped of suffixes
    for k, v in report.items():
        k_base = k.replace(' jr.','').replace(' sr.','').replace(' iii','').replace(' ii','').strip()
        if k_base == base:
            return v
    return None

def is_out(name: str, report: dict) -> bool:
    entry = _lookup(name, report)
    return entry is not None and entry.get('status', '') in ('Out', 'Doubtful')

def is_questionable(name: str, report: dict) -> bool:
    entry = _lookup(name, report)
    if entry is None:
        return False
    status = entry.get('status', '').lower()
    return 'questionable' in status or 'day-to-day' in status

def get_injury_detail(name: str, report: dict) -> str:
    entry = _lookup(name, report)
    return entry.get('detail', 'Out') if entry else 'Out'

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Load roster data
# ─────────────────────────────────────────────────────────────────────────────
def load_roster() -> pd.DataFrame:
    print("📂 Loading roster data...")
    df = pd.read_csv('Parbs_League_Master_2026.csv')
    df.columns = [c.upper().strip() for c in df.columns]
    for col in ['PTS', 'MP', 'FG%', '3P%', 'FT%']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['PLAYER', 'PTS', 'MP'])
    df = df[df['PLAYER'] != 'Team Totals']
    df = df[df['PTS'] < 200]  # strip any raw totals rows
    print(f"  ✅ {len(df)} players loaded across {df['TEAM_ABBR'].nunique()} teams\n")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Signal engine (every player, not just stars)
# ─────────────────────────────────────────────────────────────────────────────
def get_signal(row, opp_drtg: float, star_out: bool) -> str:
    pts  = row['PTS']
    mp   = row['MP']
    fg   = row.get('FG%', 0) or 0
    tp   = row.get('3P%', 0) or 0

    # Star replacement boost — role player gets more minutes when star is out
    if star_out and 8 <= pts <= 20 and mp >= 15:
        return '⬆️  ROLE BOOST (Star Out)'

    # Elite usage
    if pts > 22:
        return '🔥 HOT (High Usage)'

    # Efficiency microwave: high FG% + 3P% in 10-20 PPG range
    if 10 <= pts <= 20 and fg > 0.50 and tp > 0.38:
        return '🔥 HOT (Efficiency)'

    # Value matchup: role player with 26+ min vs weak defense
    if mp >= 26 and opp_drtg > 117:
        return '🚀 VALUE (Matchup)'

    # Solid role player vs weak D
    if 12 <= pts <= 22 and opp_drtg > 116:
        return '✅ PLAY (Weak D)'

    # Reliable floor: 15+ min, decent scoring
    if mp >= 20 and pts >= 10:
        return '➡️  STEADY'

    # Deep rotation — still worth knowing
    if mp >= 12 and pts >= 5:
        return '📋 DEEP ROT'

    return '🔕 DNP RISK'

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Build per-team injury context
# ─────────────────────────────────────────────────────────────────────────────
def build_team_injury_context(df: pd.DataFrame, report: dict) -> dict:
    """
    Returns {team_abbr: {'stars_out': [...], 'star_pts_lost': float}}
    A 'star' = player averaging 18+ PPG on that team.
    """
    context = {}
    for team, group in df.groupby('TEAM_ABBR'):
        stars_out = []
        pts_lost  = 0.0
        for _, row in group.iterrows():
            if row['PTS'] >= 18 and is_out(row['PLAYER'], report):
                stars_out.append(row['PLAYER'])
                pts_lost += row['PTS']
        context[team] = {'stars_out': stars_out, 'pts_lost': round(pts_lost, 1)}
    return context

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
print("🚀 PARB'S FULL ANALYSIS ENGINE — CHECKING ALL SOURCES...\n")
print("=" * 70)

injury_report  = get_injury_report()
df             = load_roster()
team_context   = build_team_injury_context(df, injury_report)

results = []

for _, row in df.iterrows():
    player = row['PLAYER']
    team   = str(row['TEAM_ABBR'])
    pts    = row['PTS']
    mp     = row['MP']

    # Skip DNP-risk bench warmers entirely (< 8 min)
    if mp < 8:
        continue

    # Injury status
    if is_out(player, injury_report):
        inj_detail = get_injury_detail(player, injury_report)
        results.append({
            'PLAYER':   player,
            'TEAM':     team,
            'OPP':      row.get('OPP', '???'),
            'OPP_DRTG': 0,
            'PPG':      round(pts, 1),
            'MPG':      round(mp, 1),
            'FG%':      round(row.get('FG%', 0) or 0, 3),
            '3P%':      round(row.get('3P%', 0) or 0, 3),
            'SIGNAL':   f'🚫 OUT — {inj_detail}',
            'INJ_FLAG': 'OUT',
            'STARS_OUT':'',
            'PTS_LOST': 0,
        })
        continue

    inj_flag = 'GTD' if is_questionable(player, injury_report) else ''

    # Opponent + defensive rating
    # Build matchup map from tonight's schedule
    opp      = row.get('OPP', '')
    opp_drtg = DEF_RATINGS.get(str(opp), 114.0)

    # Check if a star on this team is out (role boost opportunity)
    star_out = len(team_context.get(team, {}).get('stars_out', [])) > 0

    signal = get_signal(row, opp_drtg, star_out)

    results.append({
        'PLAYER':    player,
        'TEAM':      team,
        'OPP':       opp,
        'OPP_DRTG':  opp_drtg,
        'PPG':       round(pts, 1),
        'MPG':       round(mp, 1),
        'FG%':       round(row.get('FG%', 0) or 0, 3),
        '3P%':       round(row.get('3P%', 0) or 0, 3),
        'SIGNAL':    signal,
        'INJ_FLAG':  inj_flag,
        'STARS_OUT': ', '.join(team_context.get(team, {}).get('stars_out', [])),
        'PTS_LOST':  team_context.get(team, {}).get('pts_lost', 0),
    })

out_df = pd.DataFrame(results)
out_df.to_csv('parbs_picks_global_report.csv', index=False)

# ── Print report ──────────────────────────────────────────────────────────────
active = out_df[~out_df['SIGNAL'].str.startswith('🚫')]
injured = out_df[out_df['SIGNAL'].str.startswith('🚫')]

tiers = {
    '🔥 HOT':         active[active['SIGNAL'].str.contains('HOT',    na=False)],
    '⬆️  ROLE BOOST': active[active['SIGNAL'].str.contains('BOOST',  na=False)],
    '🚀 VALUE':        active[active['SIGNAL'].str.contains('VALUE',  na=False)],
    '✅ PLAY':         active[active['SIGNAL'].str.contains('PLAY',   na=False)],
    '➡️  STEADY':      active[active['SIGNAL'].str.contains('STEADY', na=False)],
    '📋 DEEP ROT':     active[active['SIGNAL'].str.contains('DEEP',   na=False)],
}

H = '─'
print("\n" + "=" * 100)
print(f"  🏀 PARBS FULL REPORT — ALL PLAYERS, ALL ROLES")
print(f"  {len(active)} active players  |  {len(injured)} ruled out tonight")
print("=" * 100)

for tier_label, tier_df in tiers.items():
    if tier_df.empty:
        continue
    tier_df = tier_df.sort_values('PPG', ascending=False)
    print(f"\n  {tier_label}  ({len(tier_df)} players)\n")
    print(f"  {'PLAYER':<26}{'TEAM':<6}{'PPG':<7}{'MPG':<7}{'FG%':<7}{'3P%':<7}{'GTD':<5}{'STARS OUT'}")
    print("  " + H * 85)
    for _, r in tier_df.iterrows():
        gtd  = '⚠️' if r['INJ_FLAG'] == 'GTD' else ''
        sout = r['STARS_OUT'] if r['STARS_OUT'] else ''
        print(f"  {str(r['PLAYER']):<26}{str(r['TEAM']):<6}{r['PPG']:<7.1f}{r['MPG']:<7.1f}{r['FG%']:<7.3f}{r['3P%']:<7.3f}{gtd:<5}{sout}")

# ── Injured stars summary ─────────────────────────────────────────────────────
print(f"\n  🚫 INJURED / OUT TONIGHT  ({len(injured)} players)\n")
print(f"  {'PLAYER':<28}{'TEAM':<6}{'PPG':<7}REASON")
print("  " + H * 75)
for _, r in injured.sort_values('PPG', ascending=False).iterrows():
    reason = str(r['SIGNAL']).replace('🚫 OUT — ', '')
    print(f"  {str(r['PLAYER']):<28}{str(r['TEAM']):<6}{r['PPG']:<7.1f}{reason}")

print()
print("  📊 Sources: B-Ref + ESPN fallback + nba_api | Injuries: ESPN live feed")
print("=" * 100)
