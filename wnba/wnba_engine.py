"""
wnba/wnba_engine.py
===================
WNBA picks engine. Same statistical approach as NBA:
  - Pulls PrizePicks WNBA lines (league_id=3)
  - Pulls game logs from Basketball-Reference
  - Applies t-tests, confidence intervals, regression
  - Minimum line thresholds (PTS≥5, REB≥2, AST≥2)
  - Mixed parlay builder ranked by EV

Run:
    python3 wnba/wnba_engine.py              # today's games
    python3 wnba/wnba_engine.py --tomorrow   # tomorrow's games
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

WNBA_LEAGUE_ID = 3  # PrizePicks league ID for WNBA

# Minimum line thresholds (same as NBA)
MIN_LINES = {'Points': 5.0, 'Rebounds': 2.0, 'Assists': 2.0, 'Pts+Rebs+Asts': 10.0}

def passes_min(stat, line, hit_p, ltype):
    if ltype == 'demon': return True
    threshold = MIN_LINES.get(stat, 0)
    if line < threshold:
        if stat == 'Points': return False  # HARD floor
        if hit_p < 0.95: return False
    return True


def get_prizepicks_lines(target_date):
    """Pull all WNBA PrizePicks lines for a given date."""
    datestr = target_date.strftime('%Y-%m-%d')
    pp = requests.get(
        f'https://api.prizepicks.com/projections?league_id={WNBA_LEAGUE_ID}&per_page=500&single_stat=true',
        headers=PP_H, timeout=15).json()

    pp_pm = {}
    for item in pp.get('included', []):
        if item.get('type') == 'new_player':
            a = item.get('attributes', {})
            pp_pm[item['id']] = {'name': a.get('display_name', ''), 'team': a.get('team', '')}

    CORE = {'Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts'}
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
        if stat not in CORE or line is None: continue
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


def get_wnba_schedule(target_date):
    """Pull WNBA schedule from ESPN."""
    datestr = target_date.strftime('%Y%m%d')
    try:
        r = requests.get(
            f'https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={datestr}',
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
    print(f'  WNBA ENGINE — {target_date.strftime("%A %B %d, %Y")}')
    print('=' * 80)

    # Schedule
    games = get_wnba_schedule(target_date)
    print(f'\n  {len(games)} WNBA games found')
    for g in games:
        print(f"    {g['away']} @ {g['home']}  |  {g['status']}")

    # PrizePicks lines
    lines = get_prizepicks_lines(target_date)
    print(f'\n  {len(lines)} PrizePicks WNBA prop lines loaded')

    if not lines:
        print('\n  No WNBA lines available for this date.')
        print('  WNBA season typically runs May-September.')
        return

    # TODO: Pull game logs from Basketball-Reference WNBA
    # TODO: Run statistical analysis (same as NBA engine)
    # TODO: Build parlays

    print('\n  WNBA game log integration coming soon.')
    print('  PrizePicks lines are live — need game log source for hit rate analysis.')
    print('  Options: Basketball-Reference WNBA, ESPN WNBA stats')


if __name__ == '__main__':
    use_tomorrow = '--tomorrow' in sys.argv
    target = date.today() + timedelta(days=1) if use_tomorrow else date.today()
    run(target)
