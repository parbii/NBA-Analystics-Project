"""
parbs_team_stats.py
===================
Permanent team advanced stats module. Pulls live from nba_api every run
and caches to disk so repeated calls within the same day don't re-fetch.

Stats pulled for ALL 30 teams:
  BASE (per game):
    PTS     — points scored per game
    OREB    — offensive rebounds per game
    DREB    — defensive rebounds per game
    AST     — assists per game
    TOV     — turnovers per game
    STL     — steals per game
    BLK     — blocks per game

  ADVANCED:
    OFF_RATING  — points scored per 100 possessions
    DEF_RATING  — points allowed per 100 possessions (lower = better D)
    NET_RATING  — OFF_RATING - DEF_RATING (overall team quality)
    PACE        — possessions per 48 min
    OREB_PCT    — % of available offensive rebounds grabbed
    DREB_PCT    — % of available defensive rebounds grabbed
    TM_TOV_PCT  — turnover % per possession
    AST_PCT     — % of field goals that were assisted
    AST_TO      — assist-to-turnover ratio
    EFG_PCT     — effective field goal %
    TS_PCT      — true shooting %

  FOUR FACTORS:
    OPP_OREB_PCT — % of offensive rebounds opponent grabs vs this team
                   (how well this team PREVENTS opponent 2nd chances)
    OPP_TOV_PCT  — turnovers forced per possession
    OPP_EFG_PCT  — opponent effective FG% allowed

  OPPONENT (what they ALLOW per game):
    OPP_PTS  — points allowed per game
    OPP_OREB — opponent offensive rebounds allowed per game
    OPP_AST  — opponent assists allowed per game
    OPP_TOV  — opponent turnovers forced per game

Usage:
    from parbs_team_stats import get_team_stats, get_matchup_summary, print_team_profile

    stats = get_team_stats()          # pulls all 30 teams, caches for the day
    nyk = stats['NYK']
    print(nyk['OFF_RATING'])          # 118.7
    print(nyk['OPP_OREB_PCT'])        # 28.5%

    summary = get_matchup_summary('PHI', 'NYK', stats)
    print_team_profile('NYK', stats)
"""

import os, json, time
from datetime import date
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats

# ─────────────────────────────────────────────────────────────────────────────
# TEAM ABBREVIATION MAP — nba_api uses full names, we use abbreviations
# ─────────────────────────────────────────────────────────────────────────────
TEAM_NAME_TO_ABBR = {
    'Atlanta Hawks':           'ATL',
    'Boston Celtics':          'BOS',
    'Brooklyn Nets':           'BKN',
    'Charlotte Hornets':       'CHO',
    'Chicago Bulls':           'CHI',
    'Cleveland Cavaliers':     'CLE',
    'Dallas Mavericks':        'DAL',
    'Denver Nuggets':          'DEN',
    'Detroit Pistons':         'DET',
    'Golden State Warriors':   'GSW',
    'Houston Rockets':         'HOU',
    'Indiana Pacers':          'IND',
    'Los Angeles Clippers':    'LAC',
    'LA Clippers':             'LAC',
    'Los Angeles Lakers':      'LAL',
    'Memphis Grizzlies':       'MEM',
    'Miami Heat':              'MIA',
    'Milwaukee Bucks':         'MIL',
    'Minnesota Timberwolves':  'MIN',
    'New Orleans Pelicans':    'NOP',
    'New York Knicks':         'NYK',
    'Oklahoma City Thunder':   'OKC',
    'Orlando Magic':           'ORL',
    'Philadelphia 76ers':      'PHI',
    'Phoenix Suns':            'PHX',
    'Portland Trail Blazers':  'POR',
    'Sacramento Kings':        'SAC',
    'San Antonio Spurs':       'SAS',
    'Toronto Raptors':         'TOR',
    'Utah Jazz':               'UTA',
    'Washington Wizards':      'WAS',
}

CACHE_FILE = '.parbs_team_stats_cache.json'
SEASON     = '2025-26'


def _fetch_all_stats() -> dict:
    """
    Pull all four stat tables from nba_api and merge into one dict per team.
    Returns: {abbr: {stat: value, ...}, ...}
    """
    print('  [team_stats] Pulling live team stats from nba_api...')

    def pull(measure, per_mode='PerGame'):
        df = leaguedashteamstats.LeagueDashTeamStats(
            season=SEASON,
            measure_type_detailed_defense=measure,
            per_mode_detailed=per_mode,
            timeout=30
        ).get_data_frames()[0]
        time.sleep(1.5)
        return df

    base_df = pull('Base',         'PerGame')
    adv_df  = pull('Advanced',     'PerGame')
    ff_df   = pull('Four Factors', 'PerGame')
    opp_df  = pull('Opponent',     'PerGame')

    teams = {}

    for _, row in base_df.iterrows():
        name = row['TEAM_NAME']
        abbr = TEAM_NAME_TO_ABBR.get(name)
        if not abbr:
            continue
        teams[abbr] = {
            # Identity
            'name':     name,
            'abbr':     abbr,
            'gp':       int(row.get('GP', 0)),
            'w':        int(row.get('W', 0)),
            'l':        int(row.get('L', 0)),
            # Base per game
            'PTS':      round(float(row.get('PTS',  0)), 1),
            'OREB':     round(float(row.get('OREB', 0)), 1),
            'DREB':     round(float(row.get('DREB', 0)), 1),
            'REB':      round(float(row.get('REB',  0)), 1),
            'AST':      round(float(row.get('AST',  0)), 1),
            'TOV':      round(float(row.get('TOV',  0)), 1),
            'STL':      round(float(row.get('STL',  0)), 1),
            'BLK':      round(float(row.get('BLK',  0)), 1),
        }

    for _, row in adv_df.iterrows():
        name = row['TEAM_NAME']
        abbr = TEAM_NAME_TO_ABBR.get(name)
        if not abbr or abbr not in teams:
            continue
        teams[abbr].update({
            'OFF_RATING': round(float(row.get('OFF_RATING', 0)), 1),
            'DEF_RATING': round(float(row.get('DEF_RATING', 0)), 1),
            'NET_RATING': round(float(row.get('NET_RATING', 0)), 1),
            'PACE':       round(float(row.get('PACE',       0)), 1),
            'OREB_PCT':   round(float(row.get('OREB_PCT',   0)) * 100, 1),
            'DREB_PCT':   round(float(row.get('DREB_PCT',   0)) * 100, 1),
            'TM_TOV_PCT': round(float(row.get('TM_TOV_PCT', 0)) * 100, 1),
            'AST_PCT':    round(float(row.get('AST_PCT',    0)) * 100, 1),
            'AST_TO':     round(float(row.get('AST_TO',     0)), 2),
            'EFG_PCT':    round(float(row.get('EFG_PCT',    0)) * 100, 1),
            'TS_PCT':     round(float(row.get('TS_PCT',     0)) * 100, 1),
        })

    for _, row in ff_df.iterrows():
        name = row['TEAM_NAME']
        abbr = TEAM_NAME_TO_ABBR.get(name)
        if not abbr or abbr not in teams:
            continue
        teams[abbr].update({
            'OPP_OREB_PCT': round(float(row.get('OPP_OREB_PCT', 0)) * 100, 1),
            'OPP_TOV_PCT':  round(float(row.get('OPP_TOV_PCT',  0)) * 100, 1),
            'OPP_EFG_PCT':  round(float(row.get('OPP_EFG_PCT',  0)) * 100, 1),
        })

    for _, row in opp_df.iterrows():
        name = row['TEAM_NAME']
        abbr = TEAM_NAME_TO_ABBR.get(name)
        if not abbr or abbr not in teams:
            continue
        teams[abbr].update({
            'OPP_PTS':  round(float(row.get('OPP_PTS',  0)), 1),
            'OPP_OREB': round(float(row.get('OPP_OREB', 0)), 1),
            'OPP_AST':  round(float(row.get('OPP_AST',  0)), 1),
            'OPP_TOV':  round(float(row.get('OPP_TOV',  0)), 1),
        })

    print(f'  [team_stats] {len(teams)} teams loaded.')
    return teams


def get_team_stats(force_refresh: bool = False) -> dict:
    """
    Returns full team stats dict. Caches to disk for the day.
    Set force_refresh=True to bypass cache.
    """
    today = date.today().isoformat()

    # Check cache
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            if cached.get('date') == today:
                print(f'  [team_stats] Using cached stats ({today})')
                return cached['data']
        except Exception:
            pass

    # Fetch fresh
    data = _fetch_all_stats()

    # Save cache
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({'date': today, 'data': data}, f)
    except Exception:
        pass

    return data


# ─────────────────────────────────────────────────────────────────────────────
# MATCHUP SUMMARY — what each team's stats mean for tonight's picks
# ─────────────────────────────────────────────────────────────────────────────

def get_matchup_summary(team: str, opp: str, stats: dict) -> dict:
    """
    Returns a matchup analysis dict for a player on `team` facing `opp`.
    Covers all the stats that affect prop picks.
    """
    t = stats.get(team, {})
    o = stats.get(opp,  {})

    if not t or not o:
        return {}

    notes = []

    # ── Scoring environment ───────────────────────────────────────────────────
    opp_def = o.get('DEF_RATING', 114)
    if opp_def <= 108:
        notes.append(f'⚠️  {opp} elite D (DEF RTG {opp_def}) — tough scoring environment')
    elif opp_def >= 116:
        notes.append(f'✅ {opp} soft D (DEF RTG {opp_def}) — easy scoring environment')

    opp_pts_allowed = o.get('OPP_PTS', 114)
    notes.append(f'{opp} allows {opp_pts_allowed} PPG (DEF RTG {opp_def})')

    # ── Rebounding ────────────────────────────────────────────────────────────
    opp_dreb = o.get('DREB_PCT', 73)
    opp_oreb_allowed = o.get('OPP_OREB_PCT', 28)
    team_oreb = t.get('OREB_PCT', 28)

    if opp_dreb >= 76:
        notes.append(f'⚠️  {opp} DREB% {opp_dreb}% — elite at ending possessions, limits 2nd chances')
    elif opp_dreb <= 69:
        notes.append(f'✅ {opp} DREB% {opp_dreb}% — misses stay alive, {team} bigs can crash')

    if opp_oreb_allowed >= 31:
        notes.append(f'✅ {opp} allows {opp_oreb_allowed}% OREB — gives up 2nd chances freely')
    elif opp_oreb_allowed <= 25:
        notes.append(f'⚠️  {opp} allows only {opp_oreb_allowed}% OREB — locks down the glass')

    # ── Assists / ball movement ───────────────────────────────────────────────
    team_ast_pct = t.get('AST_PCT', 60)
    team_ast_to  = t.get('AST_TO', 1.8)
    if team_ast_pct >= 64:
        notes.append(f'✅ {team} AST% {team_ast_pct}% — elite ball movement, assists flow naturally')
    elif team_ast_pct <= 57:
        notes.append(f'→ {team} AST% {team_ast_pct}% — isolation-heavy, fewer assisted buckets')

    opp_ast_allowed = o.get('OPP_AST', 25)
    notes.append(f'{opp} allows {opp_ast_allowed} AST/G to opponents')

    # ── Turnovers ─────────────────────────────────────────────────────────────
    team_tov = t.get('TM_TOV_PCT', 14)
    opp_tov_forced = o.get('OPP_TOV_PCT', 14)
    if opp_tov_forced >= 16:
        notes.append(f'⚠️  {opp} forces {opp_tov_forced}% TOV rate — high pressure defense')
    if team_tov >= 16:
        notes.append(f'⚠️  {team} TOV% {team_tov}% — sloppy with ball, limits possessions')

    # ── Pace ──────────────────────────────────────────────────────────────────
    team_pace = t.get('PACE', 100)
    opp_pace  = o.get('PACE', 100)
    avg_pace  = round((team_pace + opp_pace) / 2, 1)
    if avg_pace >= 102:
        notes.append(f'✅ Fast pace expected ({avg_pace} avg) — more possessions, more counting stats')
    elif avg_pace <= 97:
        notes.append(f'→ Slow pace expected ({avg_pace} avg) — fewer possessions, lower totals')

    return {
        'team':             team,
        'opp':              opp,
        'opp_def_rtg':      opp_def,
        'opp_pts_allowed':  opp_pts_allowed,
        'opp_dreb_pct':     opp_dreb,
        'opp_oreb_allowed': opp_oreb_allowed,
        'team_oreb_pct':    team_oreb,
        'team_ast_pct':     team_ast_pct,
        'team_ast_to':      team_ast_to,
        'opp_tov_forced':   opp_tov_forced,
        'team_tov_pct':     team_tov,
        'avg_pace':         avg_pace,
        'notes':            notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def print_team_profile(abbr: str, stats: dict):
    """Print a full team stat profile."""
    t = stats.get(abbr)
    if not t:
        print(f'  No data for {abbr}')
        return

    print(f"""
  {'─'*70}
  {t['name']} ({abbr})  |  {t['w']}-{t['l']}
  {'─'*70}
  OFFENSE:
    Points/G:    {t.get('PTS',0)}    OFF RTG:  {t.get('OFF_RATING',0)}
    AST/G:       {t.get('AST',0)}    AST%:     {t.get('AST_PCT',0)}%
    AST/TO:      {t.get('AST_TO',0)}    TOV/G:    {t.get('TOV',0)}
    OREB/G:      {t.get('OREB',0)}    OREB%:    {t.get('OREB_PCT',0)}%
    eFG%:        {t.get('EFG_PCT',0)}%   TS%:      {t.get('TS_PCT',0)}%
    PACE:        {t.get('PACE',0)}

  DEFENSE:
    Pts Allowed: {t.get('OPP_PTS',0)}   DEF RTG:  {t.get('DEF_RATING',0)}
    NET RTG:     {t.get('NET_RATING',0)}
    DREB/G:      {t.get('DREB',0)}    DREB%:    {t.get('DREB_PCT',0)}%
    OPP OREB%:   {t.get('OPP_OREB_PCT',0)}%  (lower = better at preventing 2nd chances)
    TOV Forced:  {t.get('OPP_TOV_PCT',0)}%  OPP AST:  {t.get('OPP_AST',0)}/G
    OPP eFG%:    {t.get('OPP_EFG_PCT',0)}%""")


def print_matchup(team: str, opp: str, stats: dict):
    """Print a full matchup analysis."""
    m = get_matchup_summary(team, opp, stats)
    if not m:
        print(f'  No matchup data for {team} vs {opp}')
        return

    t = stats.get(team, {})
    o = stats.get(opp,  {})

    print(f"""
  {'━'*70}
  MATCHUP: {team} vs {opp}
  {'━'*70}
  {team} OFF RTG {t.get('OFF_RATING',0)}  vs  {opp} DEF RTG {o.get('DEF_RATING',0)}
  NET RTG: {team} {t.get('NET_RATING',0):+.1f}  |  {opp} {o.get('NET_RATING',0):+.1f}
  Avg pace: {m['avg_pace']}  |  {team} OREB% {m['team_oreb_pct']}%  |  {opp} DREB% {m['opp_dreb_pct']}%
  {opp} allows {m['opp_oreb_allowed']}% OREB  |  {team} AST% {m['team_ast_pct']}%
  {'─'*70}""")
    for note in m['notes']:
        print(f'  → {note}')


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — run standalone to see all 30 teams
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    stats = get_team_stats(force_refresh='--refresh' in sys.argv)

    if len(sys.argv) >= 3 and sys.argv[1] == '--matchup':
        # python3 parbs_team_stats.py --matchup PHI NYK
        team, opp = sys.argv[2], sys.argv[3]
        print_team_profile(team, stats)
        print_team_profile(opp, stats)
        print_matchup(team, opp, stats)
    else:
        # Print all 30 teams sorted by NET_RATING
        print()
        print('='*90)
        print(f'  ALL 30 TEAMS — 2025-26 Season Advanced Stats')
        print(f'  Sorted by NET_RATING (best to worst)')
        print('='*90)
        print(f"\n  {'Team':<6} {'W-L':<7} {'PTS':>5} {'OPP':>5} {'OFF':>6} "
              f"{'DEF':>6} {'NET':>6} {'PACE':>6} {'OREB%':>7} {'DREB%':>7} "
              f"{'AST%':>7} {'TOV%':>6} {'OPP OREB%':>10}")
        print(f"  {'─'*88}")

        sorted_teams = sorted(stats.values(),
                              key=lambda x: x.get('NET_RATING', 0), reverse=True)
        for t in sorted_teams:
            wl = f"{t['w']}-{t['l']}"
            print(f"  {t['abbr']:<6} {wl:<7} {t.get('PTS',0):>5} "
                  f"{t.get('OPP_PTS',0):>5} {t.get('OFF_RATING',0):>6} "
                  f"{t.get('DEF_RATING',0):>6} {t.get('NET_RATING',0):>+6.1f} "
                  f"{t.get('PACE',0):>6} {t.get('OREB_PCT',0):>6}% "
                  f"{t.get('DREB_PCT',0):>6}% {t.get('AST_PCT',0):>6}% "
                  f"{t.get('TM_TOV_PCT',0):>5}% {t.get('OPP_OREB_PCT',0):>9}%")

        print()
        print(f'  Cached to {CACHE_FILE} — refreshes daily automatically.')
        print(f'  Force refresh: python3 parbs_team_stats.py --refresh')
        print(f'  Matchup view:  python3 parbs_team_stats.py --matchup PHI NYK')
