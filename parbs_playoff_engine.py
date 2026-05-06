"""
parbs_playoff_engine.py
=======================
PLAYOFF-SPECIFIC picks engine. Handles series context that the regular
season engine cannot:

  - Tracks game-by-game results within a series
  - Applies blowout hangover flags (e.g. PHI lost G1 by 40)
  - Uses PLAYOFF game logs only (not regular season)
  - Adjusts for series momentum, desperation, and rest patterns
  - Pulls live PrizePicks goblin/standard/demon lines
  - Applies positional DRtg matchup multipliers
  - Checks live injury report and active rosters

Run:
    python3 parbs_playoff_engine.py              # today's playoff games
    python3 parbs_playoff_engine.py --tomorrow   # tomorrow's games

Series results are entered manually at the top of the script each day.
"""

import sys, time, unicodedata, requests
import numpy as np
from scipy import stats
from datetime import date, timedelta
from nba_api.stats.static import players as nba_players_static
from nba_api.stats.endpoints import playergamelog

from parbs_blowout_risk import (
    BlowoutRiskEngine, get_full_risk_summary,
    get_pos_label, POSITIONAL_DRTG, PLAYER_POSITIONS
)
from parbs_ban_list import is_banned

# ─────────────────────────────────────────────────────────────────────────────
# SERIES RESULTS — Update this daily with actual scores
# Format: engine.record_game('AWAY', 'HOME', away_score, home_score)
# ─────────────────────────────────────────────────────────────────────────────
SERIES_ENGINES = {}

def build_series_engines():
    """
    Build BlowoutRiskEngine for each active series.
    UPDATE THESE SCORES EACH DAY.
    """
    engines = {}

    # PHI @ NYK — East Semifinals
    phi_nyk = BlowoutRiskEngine()
    phi_nyk.record_game('PHI', 'NYK', score_a=88, score_b=128)  # G1: NYK won by 40
    engines['PHI'] = phi_nyk
    engines['NYK'] = phi_nyk

    # MIN @ SAS — West Semifinals
    min_sas = BlowoutRiskEngine()
    min_sas.record_game('MIN', 'SAS', score_a=98, score_b=114)  # G1: SAS won by 16
    engines['MIN'] = min_sas
    engines['SAS'] = min_sas

    # CLE @ DET — East Semifinals (add results as series progresses)
    cle_det = BlowoutRiskEngine()
    # cle_det.record_game('CLE', 'DET', score_a=X, score_b=Y)  # G1
    engines['CLE'] = cle_det
    engines['DET'] = cle_det

    # LAL @ OKC — West Semifinals
    lal_okc = BlowoutRiskEngine()
    # lal_okc.record_game('LAL', 'OKC', score_a=X, score_b=Y)  # G1
    engines['LAL'] = lal_okc
    engines['OKC'] = lal_okc

    return engines

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
ESPN_H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
PP_H   = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
          'Referer': 'https://app.prizepicks.com/'}

PUBLIC_FADE = {
    'Jalen Brunson', 'Tyrese Maxey', 'Victor Wembanyama',
    'Anthony Edwards', 'Shai Gilgeous-Alexander', 'LeBron James',
    'Cade Cunningham', 'Donovan Mitchell',
}

CORE_STATS = {'Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts'}

def norm(s):
    n = unicodedata.normalize('NFD', str(s))
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    return n.lower().strip().replace("'","").replace("'","").replace(".","")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Schedule
# ─────────────────────────────────────────────────────────────────────────────
def get_schedule(target_date):
    datestr = target_date.strftime('%Y%m%d')
    r = requests.get(
        f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={datestr}',
        headers=ESPN_H, timeout=10)
    games = []
    for e in r.json().get('events', []):
        comp = e['competitions'][0]
        home = next(t for t in comp['competitors'] if t['homeAway']=='home')
        away = next(t for t in comp['competitors'] if t['homeAway']=='away')
        ha = home['team']['abbreviation']
        aa = away['team']['abbreviation']
        notes = comp.get('notes', [])
        note  = notes[0].get('headline', '') if notes else ''
        spread = 0.0
        for odds in comp.get('odds', []):
            try: spread = float(odds.get('spread', 0) or 0)
            except: pass
        games.append({
            'away': aa, 'home': ha, 'spread': spread,
            'note': note, 'status': e['status']['type']['shortDetail'],
        })
    return games

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Live injuries
# ─────────────────────────────────────────────────────────────────────────────
def get_injuries():
    r = requests.get(
        'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries',
        headers=ESPN_H, timeout=10)
    report = {}
    for team in r.json().get('injuries', []):
        for p in team.get('injuries', []):
            nm = p.get('athlete', {}).get('displayName', '')
            st = p.get('status', '')
            dt = p.get('shortComment', '')[:70]
            report[norm(nm)] = {'name': nm, 'status': st, 'detail': dt}
    return report

def is_out(name, report):
    return report.get(norm(name), {}).get('status', '') in ('Out', 'Doubtful')

def inj_tag(name, report):
    s = report.get(norm(name), {}).get('status', '')
    if s in ('Out', 'Doubtful'): return '❌ OUT'
    if 'Question' in s or 'Day' in s: return '⚠️ GTD'
    return '✅'

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — PrizePicks lines
# ─────────────────────────────────────────────────────────────────────────────
def get_prizepicks_lines(target_date, tonight_teams):
    datestr = target_date.strftime('%Y-%m-%d')
    pp = requests.get(
        'https://api.prizepicks.com/projections?league_id=7&per_page=500&single_stat=true',
        headers=PP_H, timeout=15).json()

    pp_pm = {}
    for item in pp.get('included', []):
        if item.get('type') == 'new_player':
            a = item.get('attributes', {})
            pp_pm[item['id']] = {'name': a.get('display_name',''), 'team': a.get('team','')}

    lines = {}
    for proj in pp.get('data', []):
        a = proj.get('attributes', {})
        if a.get('status') != 'pre_game': continue
        if datestr not in a.get('start_time', ''): continue
        pid  = proj.get('relationships',{}).get('new_player',{}).get('data',{}).get('id','')
        pi   = pp_pm.get(pid, {})
        team = pi.get('team', '')
        if team not in tonight_teams: continue
        name = pi.get('name', '')
        stat = a.get('stat_display_name', '')
        line = a.get('line_score')
        ot   = a.get('odds_type', '')
        if stat not in CORE_STATS or line is None: continue
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

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Playoff game logs (PLAYOFF DATA ONLY)
# ─────────────────────────────────────────────────────────────────────────────
def get_playoff_log(name, all_nba):
    matches = [p for p in all_nba
               if p['full_name'].lower() == name.lower() and p['is_active']]
    if not matches:
        parts = name.lower().split()
        matches = [p for p in all_nba
                   if parts[0] in p['full_name'].lower()
                   and parts[-1] in p['full_name'].lower()
                   and p['is_active']]
    if not matches: return None
    try:
        gl = playergamelog.PlayerGameLog(
            player_id=matches[0]['id'], season='2025-26',
            season_type_all_star='Playoffs', timeout=30)
        df = gl.get_data_frames()[0]
        return df if not df.empty else None
    except: return None

def get_series(df, stat):
    if df is None or df.empty: return []
    if stat == 'Pts+Rebs+Asts':
        return list(reversed((df['PTS'] + df['REB'] + df['AST']).tolist()))
    col_map = {'Points':'PTS','Rebounds':'REB','Assists':'AST'}
    col = col_map.get(stat)
    return list(reversed(df[col].tolist())) if col and col in df.columns else []

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Statistical analysis
# ─────────────────────────────────────────────────────────────────────────────
def stat_block(data, line):
    arr = np.array(data, dtype=float)
    n   = len(arr)
    mu  = arr.mean()
    sd  = arr.std(ddof=1)
    se  = sd / np.sqrt(n)
    tc  = stats.t.ppf(0.975, df=n-1)
    ci_lo = round(mu - tc*se, 1)
    ci_hi = round(mu + tc*se, 1)
    hits  = sum(1 for x in data if x > line)
    hit_p = hits / n
    t_val = (mu - line) / se if se > 0 else 0
    p_val = stats.t.sf(t_val, df=n-1)
    x = np.arange(1, n+1, dtype=float)
    slope, intercept, _, _, _ = stats.linregress(x, arr)
    proj_next = round(intercept + slope*(n+1), 1)
    trend = '📈' if slope > 0.5 else ('📉' if slope < -0.5 else '➡️')
    return {
        'n': n, 'mu': round(mu,1), 'sd': round(sd,2),
        'ci_lo': ci_lo, 'ci_hi': ci_hi,
        'hits': hits, 'hit_p': hit_p,
        't_val': round(t_val,3), 'p_val': round(p_val,4),
        'slope': round(slope,3), 'proj': proj_next, 'trend': trend,
    }

def grade_pick(hit_p, edge, p_val, ci_lo, line):
    if hit_p == 1.0 and line < ci_lo and p_val < 0.05:
        return 'ELITE'
    elif hit_p >= 0.80 and edge >= 15 and p_val < 0.05:
        return 'STRONG'
    elif hit_p >= 0.80 and edge >= 8:
        return 'SOLID'
    elif hit_p >= 0.67:
        return 'LEAN'
    return None

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def run(target_date):
    print()
    print('='*100)
    print(f'  PARBS PLAYOFF ENGINE — {target_date.strftime("%A %B %d, %Y")}')
    print('  Playoff data only | Blowout risk | Usage risk | Positional DRtg')
    print('='*100)

    # Schedule
    print('\n  Fetching schedule...')
    games = get_schedule(target_date)
    if not games:
        print('  No games found.')
        return

    playoff_games = [g for g in games if 'Semifinal' in g['note']
                     or 'Final' in g['note'] or 'Round' in g['note']
                     or 'Play-In' in g['note']]
    if not playoff_games:
        playoff_games = games  # fallback

    for g in playoff_games:
        print(f"    {g['away']} @ {g['home']}  |  {g['status']}  |  "
              f"Spread: {g['spread']}  |  {g['note']}")

    tonight_teams = set()
    opp_map    = {}
    spread_map = {}
    for g in playoff_games:
        tonight_teams.add(g['away'])
        tonight_teams.add(g['home'])
        opp_map[g['away']] = g['home']
        opp_map[g['home']] = g['away']
        spread_map[g['home']] = g['spread']
        spread_map[g['away']] = -g['spread']

    # Injuries
    print('\n  Pulling live injury report...')
    injury_report = get_injuries()
    out_players = [v['name'] for v in injury_report.values()
                   if v['status'] in ('Out','Doubtful')]
    print(f"  OUT/Doubtful: {', '.join(out_players[:8]) if out_players else 'None'}")

    # PrizePicks
    print('\n  Pulling PrizePicks lines...')
    pp_lines = get_prizepicks_lines(target_date, tonight_teams)
    print(f"  {len(pp_lines)} prop lines loaded")

    # Series engines
    series_engines = build_series_engines()

    # Playoff logs
    print('\n  Pulling playoff game logs...')
    all_nba = nba_players_static.get_players()

    # Get all players with PrizePicks lines tonight
    pp_players = set()
    for (name, team, stat) in pp_lines.keys():
        if team in tonight_teams:
            pp_players.add((name, team))

    logs = {}
    for name, team in pp_players:
        if is_out(name, injury_report): continue
        if is_banned(name): continue
        df = get_playoff_log(name, all_nba)
        logs[(name, team)] = df
        n = len(df) if df is not None else 0
        sys.stdout.write(f'\r    {name:<28} {n} games  ')
        sys.stdout.flush()
        time.sleep(1.0)
    print(f'\n  {len(logs)} players loaded')

    # Score
    print('\n  Scoring picks...')
    results = []

    for (name, team), df in logs.items():
        if is_out(name, injury_report): continue
        if is_banned(name): continue

        opp    = opp_map.get(team, '?')
        spread = spread_map.get(team, 0.0)
        engine = series_engines.get(team, BlowoutRiskEngine())

        for stat in ['Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts']:
            s_data = get_series(df, stat)
            if len(s_data) < 3: continue

            key   = (name, team, stat)
            ldata = pp_lines.get(key, {'goblin':[],'standard':[],'demon':[]})

            for ltype, llist in [('goblin', ldata['goblin']),
                                  ('standard', ldata['standard']),
                                  ('demon', ldata['demon'])]:
                for line in llist:
                    sb = stat_block(s_data, line)
                    if sb['hit_p'] < 0.65: continue

                    # Get L10 FGA for usage risk (approximate from log)
                    l10_fga = 10.0  # default
                    if df is not None and 'FGA' in df.columns:
                        l10_fga = round(df.head(10)['FGA'].mean(), 1)

                    # Full risk assessment
                    risk = get_full_risk_summary(
                        player_name=name, team=team, opp_team=opp,
                        stat=stat, direction='OVER', line=line,
                        proj=sb['mu'], spread=spread,
                        ssn_min=30.0,  # use playoff avg min if available
                        l10_fga=l10_fga,
                        series_engine=engine,
                    )

                    if not risk['approved']: continue

                    edge = risk['edge_pct']
                    grade = grade_pick(sb['hit_p'], edge, sb['p_val'],
                                       sb['ci_lo'], line)
                    if grade is None: continue

                    miss = [f"G{i+1}({int(x)})" for i,x in enumerate(s_data)
                            if x <= line]
                    log_str = ' '.join([f"G{i+1}:{int(x)}"
                                        for i,x in enumerate(s_data)])

                    results.append({
                        'player': name, 'team': team, 'opp': opp,
                        'stat': stat, 'ltype': ltype, 'line': line,
                        'grade': grade, 'hit_p': sb['hit_p'],
                        'hits': sb['hits'], 'n': sb['n'],
                        'edge': edge, 'p_val': sb['p_val'],
                        'mu': sb['mu'], 'adj': risk['adj_proj'],
                        'ci_lo': sb['ci_lo'], 'ci_hi': sb['ci_hi'],
                        'trend': sb['trend'], 'proj': sb['proj'],
                        'risk_level': risk['overall_risk'],
                        'blow_risk': risk['blowout_risk'],
                        'usage_risk': risk['usage_risk'],
                        'pos_label': risk['pos_label'],
                        'flags': risk['flags'],
                        'miss': miss, 'log': log_str,
                        'fade': name in PUBLIC_FADE,
                        'spread': spread,
                    })

    # Print
    GO = {'ELITE':0,'STRONG':1,'SOLID':2,'LEAN':3}
    LO = {'goblin':0,'standard':1,'demon':2}
    results.sort(key=lambda x:(GO.get(x['grade'],9), LO.get(x['ltype'],9),
                                -x['hit_p'], -x['edge']))

    EMOJI  = {'ELITE':'🔥🔥','STRONG':'🔥','SOLID':'✅','LEAN':'📋'}
    RISK_E = {'NONE':'','LOW':'🟡','MEDIUM':'🟠','HIGH':'🔴','CRITICAL':'🚨'}

    print()
    print('='*100)
    print(f'  PLAYOFF PICKS — {target_date.strftime("%A %B %d, %Y")}')
    print('  Showing: goblin lines | 65%+ playoff hit rate | all risk flags')
    print('='*100)

    cur_game = None; cur_grade = None
    game_map = {}
    for g in playoff_games:
        game_map[g['away']] = f"{g['away']}@{g['home']}"
        game_map[g['home']] = f"{g['away']}@{g['home']}"

    for r in results:
        if r['ltype'] != 'goblin': continue
        game_key = game_map.get(r['team'], r['team'])
        if game_key != cur_game:
            cur_game = game_key
            cur_grade = None
            g = next((x for x in playoff_games
                       if x['away']==r['team'] or x['home']==r['team']), None)
            sp = f"Spread: {g['spread']}" if g else ''
            print(f"\n{'━'*100}")
            print(f"  {game_key}  |  {sp}  |  {g['note'] if g else ''}")
            print(f"{'━'*100}")

        if r['grade'] != cur_grade:
            cur_grade = r['grade']
            e = EMOJI.get(cur_grade,'')
            print(f"\n  {e} {cur_grade}")
            print(f"  {'Player':<22} {'Tm':<4} {'Stat':<8} {'Line':>7} "
                  f"{'PO Avg':>7} {'Adj':>6} {'CI':>14} "
                  f"{'Hit%':>6} {'Edge%':>7} {'p':>7}  Risk")
            print(f"  {'─'*95}")

        fade = ' 🚫' if r['fade'] else ''
        miss = f" ⚠️{','.join(r['miss'])}" if r['miss'] else ''
        ci   = f"[{r['ci_lo']},{r['ci_hi']}]"
        risk_icon = RISK_E.get(r['risk_level'],'')

        print(f"  {r['player']:<22} {r['team']:<4} {r['stat']:<8} {r['line']:>7.1f} "
              f"{r['mu']:>7.1f} {r['adj']:>6.1f} {ci:>14} "
              f"{r['hit_p']*100:>5.0f}% {r['edge']:>6.1f}% {r['p_val']:>7.4f}  "
              f"{risk_icon} {r['risk_level']}{fade}{miss}")
        print(f"    Log: {r['log']}  |  {r['pos_label']}  |  {r['trend']} G{r['n']+1}:{r['proj']}")
        for flag in r['flags'][:3]:
            print(f"    → {flag}")

    # Parlay builder
    seen = set(); deduped = []
    for r in results:
        if r['ltype'] == 'goblin':
            k = (r['player'], r['stat'])
            if k not in seen:
                seen.add(k); deduped.append(r)

    clean = [p for p in deduped
             if not p['fade']
             and p['grade'] in ('ELITE','STRONG')
             and p['risk_level'] not in ('CRITICAL',)]

    def build6(pool):
        seen_p = set(); legs = []
        for p in pool:
            if p['player'] in seen_p: continue
            legs.append(p); seen_p.add(p['player'])
            if len(legs) == 6: break
        return legs if len(set(game_map.get(p['team'],p['team']) for p in legs)) >= 2 else None

    def score(p): return p['hit_p'] * p['edge'] * (1/(p['p_val']+0.001))
    by_score = sorted(clean, key=score, reverse=True)
    p6 = build6(by_score)

    print()
    print('='*100)
    print('  OPTIMAL 6-LEG PARLAY — Real playoff data, no fades, risk-filtered')
    print('='*100)

    if p6:
        prob = 1.0
        for p in p6: prob *= p['hit_p']
        ev = prob*25 - (1-prob)*1
        p5 = sum((1-p6[i]['hit_p']) * float(np.prod([p6[j]['hit_p']
                  for j in range(len(p6)) if j!=i]))
                  for i in range(len(p6)))
        print()
        for i,p in enumerate(p6,1):
            miss = f"  ⚠️ {','.join(p['miss'])}" if p['miss'] else ''
            risk_icon = RISK_E.get(p['risk_level'],'')
            print(f"  Leg {i}: {p['player']:<24} {p['stat']:<8} OVER {p['line']:<6} "
                  f"{EMOJI.get(p['grade'],'')} {p['grade']} | "
                  f"{p['hit_p']*100:.0f}% | +{p['edge']:.1f}% | "
                  f"{risk_icon} {p['risk_level']}{miss}")
        probs_str = ' x '.join([f"{p['hit_p']*100:.0f}%" for p in p6])
        print(f"\n  P(all 6 hit) = {probs_str} = {prob*100:.1f}%")
        print(f"  EV at 25x    = {prob:.3f}x$25 - {1-prob:.3f}x$1 = ${ev:.2f} per $1")
        if p5 > 0:
            print(f"  P(5/6 hit)   = {p5*100:.1f}%  -> ~2x on Flex")
    else:
        print('  Not enough clean picks for a 6-leg parlay.')

    print()
    print('='*100)
    print('  Run: python3 parbs_playoff_engine.py --tomorrow  for next game')
    print('='*100)


if __name__ == '__main__':
    use_tomorrow = '--tomorrow' in sys.argv
    target = date.today() + timedelta(days=1) if use_tomorrow else date.today()
    run(target)
