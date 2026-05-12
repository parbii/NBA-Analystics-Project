"""
mlb/mlb_engine.py
=================
MLB picks engine. Adapted from NBA statistical approach for baseball:
  - Pulls PrizePicks MLB lines (league_id=2)
  - Pulls game logs from pybaseball / Baseball-Reference
  - Applies t-tests, confidence intervals, regression
  - Pitcher matchup context (replaces positional DRtg)
  - Platoon splits (LHP vs RHP)
  - Ballpark factors
  - Mixed parlay builder ranked by EV

Run:
    python3 mlb/mlb_engine.py              # today's games
    python3 mlb/mlb_engine.py --tomorrow   # tomorrow's games

Dependencies:
    pip install pybaseball
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests, time
import numpy as np
from scipy import stats
from datetime import date, timedelta

PP_H = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
        'Referer': 'https://app.prizepicks.com/'}
ESPN_H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

MLB_LEAGUE_ID = 2  # PrizePicks league ID for MLB

# ─────────────────────────────────────────────────────────────────────────────
# MINIMUM LINE THRESHOLDS — adapted for baseball
# Baseball has much higher variance than basketball
# A 0-hit game is NORMAL (happens 25-30% of the time for good hitters)
# ─────────────────────────────────────────────────────────────────────────────
MIN_LINES_MLB = {
    'Hits':           0.5,   # standard — 0.5 is the lowest meaningful line
    'Total Bases':    0.5,
    'RBIs':           0.5,
    'Runs':           0.5,
    'Home Runs':      0.5,
    'Strikeouts':     3.5,   # pitcher K props — minimum 3.5
    'Hits Allowed':   3.5,
    'Earned Runs':    1.5,
    'Walks':          1.5,
}

# ─────────────────────────────────────────────────────────────────────────────
# BALLPARK FACTORS — how much each park inflates/deflates stats
# 1.0 = neutral. >1.0 = hitter-friendly. <1.0 = pitcher-friendly.
# ─────────────────────────────────────────────────────────────────────────────
BALLPARK_FACTORS = {
    'COL': 1.18,  # Coors Field — massive hitter boost
    'CIN': 1.08,  # Great American Ballpark
    'TEX': 1.06,  # Globe Life Field
    'BOS': 1.05,  # Fenway Park
    'PHI': 1.04,  # Citizens Bank Park
    'CHC': 1.03,  # Wrigley Field
    'MIL': 1.02,  # American Family Field
    'ATL': 1.01,  # Truist Park
    # Neutral parks
    'NYY': 1.00, 'NYM': 1.00, 'LAD': 0.99, 'HOU': 0.99,
    'SD':  0.98, 'STL': 0.98, 'MIN': 0.99, 'DET': 0.99,
    'CLE': 0.98, 'KC':  0.99, 'BAL': 1.01, 'TOR': 1.00,
    'TB':  0.97, 'CHW': 0.99, 'ARI': 1.01, 'WSH': 1.00,
    # Pitcher-friendly parks
    'SF':  0.95,  # Oracle Park
    'OAK': 0.96,  # Oakland Coliseum
    'MIA': 0.96,  # LoanDepot Park
    'SEA': 0.96,  # T-Mobile Park
    'PIT': 0.97,  # PNC Park
    'LAA': 0.98,  # Angel Stadium
}


def get_prizepicks_lines(target_date):
    """Pull all MLB PrizePicks lines for a given date."""
    datestr = target_date.strftime('%Y-%m-%d')
    pp = requests.get(
        f'https://api.prizepicks.com/projections?league_id={MLB_LEAGUE_ID}&per_page=500&single_stat=true',
        headers=PP_H, timeout=15).json()

    pp_pm = {}
    for item in pp.get('included', []):
        if item.get('type') == 'new_player':
            a = item.get('attributes', {})
            pp_pm[item['id']] = {'name': a.get('display_name', ''), 'team': a.get('team', '')}

    lines = {}
    for proj in pp.get('data', []):
        a = proj.get('attributes', {})
        if a.get('status') != 'pre_game': continue
        if datestr not in a.get('start_time', ''): continue
        pid = proj.get('relationships', {}).get('new_player', {}).get('data', {}).get('id', '')
        pi  = pp_pm.get(pid, {})
        name = pi.get('name', '')
        team = pi.get('team', '')
        stat = a.get('stat_display_name', '')
        line = a.get('line_score')
        ot   = a.get('odds_type', '')
        if line is None: continue
        key = (name, team, stat)
        if key not in lines:
            lines[key] = {'goblin': [], 'standard': [], 'demon': []}
        if ot in ('goblin', 'standard', 'demon'):
            lines[key][ot].append(line)

    for key in lines:
        lines[key]['goblin']   = sorted(lines[key]['goblin'])
        lines[key]['standard'] = sorted(lines[key]['standard'])
        lines[key]['demon']    = sorted(lines[key]['demon'], reverse=True)

    return lines


def get_mlb_schedule(target_date):
    """Pull MLB schedule from ESPN."""
    datestr = target_date.strftime('%Y%m%d')
    try:
        r = requests.get(
            f'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={datestr}',
            headers=ESPN_H, timeout=10)
        events = r.json().get('events', [])
        games = []
        for e in events:
            comp = e['competitions'][0]
            home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
            away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
            games.append({
                'away': away['team']['abbreviation'],
                'home': home['team']['abbreviation'],
                'status': e['status']['type']['shortDetail'],
            })
        return games
    except:
        return []


def run(target_date):
    print()
    print('=' * 80)
    print(f'  MLB ENGINE — {target_date.strftime("%A %B %d, %Y")}')
    print('=' * 80)

    # Schedule
    games = get_mlb_schedule(target_date)
    print(f'\n  {len(games)} MLB games found')
    for g in games[:10]:  # show first 10
        print(f"    {g['away']} @ {g['home']}  |  {g['status']}")
    if len(games) > 10:
        print(f"    ... and {len(games)-10} more")

    # PrizePicks lines
    lines = get_prizepicks_lines(target_date)
    print(f'\n  {len(lines)} PrizePicks MLB prop lines loaded')

    if not lines:
        print('\n  No MLB lines available for this date.')
        return

    # Group by stat type
    stat_counts = {}
    for (name, team, stat) in lines.keys():
        stat_counts[stat] = stat_counts.get(stat, 0) + 1

    print('\n  Lines by stat type:')
    for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
        print(f"    {stat:<20} {count} lines")

    # TODO: Pull game logs from pybaseball
    # TODO: Pitcher matchup analysis
    # TODO: Platoon splits
    # TODO: Ballpark factor adjustment
    # TODO: Run statistical analysis
    # TODO: Build parlays

    print('\n  MLB game log integration coming soon.')
    print('  Install: pip install pybaseball')
    print('  PrizePicks lines are live — need game log source for hit rate analysis.')


if __name__ == '__main__':
    use_tomorrow = '--tomorrow' in sys.argv
    target = date.today() + timedelta(days=1) if use_tomorrow else date.today()
    run(target)
