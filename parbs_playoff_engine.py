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
from parbs_team_stats import get_team_stats, get_matchup_summary, print_matchup

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

ESPN_ABBR_MAP = {
    'NY':'NYK','SA':'SAS','GS':'GSW','NO':'NOP','PHO':'PHX',
    'WSH':'WAS','CHA':'CHO','UTH':'UTA',
}

def fix_abbr(a):
    return ESPN_ABBR_MAP.get(a, a)

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

    # Team advanced stats — pulled live, cached daily
    print('\n  Pulling team advanced stats...')
    team_stats = get_team_stats()

    # Print matchup context for tonight's games
    print()
    print('='*100)
    print('  TEAM ADVANCED STATS — MATCHUP CONTEXT')
    print('  Source: nba_api stats.nba.com | 2025-26 season | cached daily')
    print('='*100)
    for g in playoff_games:
        away_n = fix_abbr(g['away'])
        home_n = fix_abbr(g['home'])
        if away_n in team_stats and home_n in team_stats:
            print_matchup(away_n, home_n, team_stats)
        else:
            # Try raw abbreviations
            print_matchup(g['away'], g['home'], team_stats)

    # Injuries
    print('\n  Pulling live injury report...')
    injury_report = get_injuries()
    out_players = [v['name'] for v in injury_report.values()
                   if v['status'] in ('Out','Doubtful')]
    print(f"  OUT/Doubtful: {', '.join(out_players[:8]) if out_players else 'None'}")

    # PrizePicks
    print('\n  Pulling PrizePicks lines...')
    tonight_teams_norm = {fix_abbr(t) for t in tonight_teams} | tonight_teams
    pp_lines = get_prizepicks_lines(target_date, tonight_teams_norm)
    print(f"  {len(pp_lines)} prop lines loaded")

    # Series engines
    series_engines = build_series_engines()

    # Playoff logs
    print('\n  Pulling playoff game logs...')
    all_nba = nba_players_static.get_players()

    # Normalize tonight_teams and maps
    tonight_teams_norm = {fix_abbr(t) for t in tonight_teams} | tonight_teams
    opp_map_norm    = {fix_abbr(k): fix_abbr(v) for k,v in opp_map.items()}
    spread_map_norm = {fix_abbr(k): v for k,v in spread_map.items()}
    series_engines_norm = {}
    for k,v in series_engines.items():
        series_engines_norm[fix_abbr(k)] = v
        series_engines_norm[k] = v

    opp_map    = opp_map_norm
    spread_map = spread_map_norm
    series_engines = series_engines_norm

    # Get all players with PrizePicks lines tonight
    pp_players = set()
    for (name, team, stat) in pp_lines.keys():
        norm_team = fix_abbr(team)
        if norm_team in tonight_teams_norm or team in tonight_teams_norm:
            pp_players.add((name, fix_abbr(team)))

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
        if is_banned(name): continue  # full ban check

        opp    = opp_map.get(team, '?')
        spread = spread_map.get(team, 0.0)
        engine = series_engines.get(team, BlowoutRiskEngine())

        for stat in ['Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts']:
            if is_banned(name, stat): continue
            s_data = get_series(df, stat)
            if len(s_data) < 3: continue

            # Try both normalized and original team abbreviation
            key = (name, team, stat)
            ldata = pp_lines.get(key)
            if ldata is None:
                # Try original ESPN abbreviation
                for orig, norm_t in ESPN_ABBR_MAP.items():
                    if norm_t == team:
                        ldata = pp_lines.get((name, orig, stat))
                        if ldata: break
            if ldata is None:
                ldata = {'goblin':[],'standard':[],'demon':[]}

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

                    # Full risk assessment — uses live team stats
                    t_stats = team_stats.get(team, {})
                    ssn_min_live = 30.0
                    if df is not None and 'MIN' in df.columns:
                        ssn_min_live = round(float(df['MIN'].mean()), 1)

                    risk = get_full_risk_summary(
                        player_name=name, team=team, opp_team=opp,
                        stat=stat, direction='OVER', line=line,
                        proj=sb['mu'], spread=spread,
                        ssn_min=ssn_min_live,
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

    # ── Separate goblin and demon pools ──────────────────────────────────────
    GO = {'ELITE':0,'STRONG':1,'SOLID':2,'LEAN':3}

    def score(p):
        return p['hit_p'] * abs(p['edge']) * (1/(p['p_val']+0.001))

    def dedup_pool(pool):
        seen_p = set(); out = []
        for r in sorted(pool, key=score, reverse=True):
            k = (r['player'], r['stat'])
            if k not in seen_p:
                seen_p.add(k); out.append(r)
        return out

    # Goblin pool — safest, highest hit rate
    goblin_pool = dedup_pool([
        r for r in results
        if r['ltype'] == 'goblin'
        and not r['fade']
        and r['grade'] in ('ELITE','STRONG','SOLID')
        and r['risk_level'] not in ('CRITICAL',)
    ])

    # Demon pool — elevated lines, >50% hit rate only
    demon_pool = dedup_pool([
        r for r in results
        if r['ltype'] == 'demon'
        and not r['fade']
        and r['hit_p'] >= 0.50
        and r['grade'] in ('ELITE','STRONG','SOLID','LEAN')
        and r['risk_level'] not in ('CRITICAL',)
    ])

    # ── Parlay math helpers ───────────────────────────────────────────────────
    # PrizePicks actual payouts — goblin lines pay MUCH less than demons
    # These are approximate multipliers based on user-confirmed data:
    #   All-goblin parlays pay roughly:
    #     2-leg: ~1.5x  |  3-leg: ~1.8x  |  4-leg: ~2x  |  5-leg: ~3x  |  6-leg: ~5x
    #   All-demon parlays pay roughly:
    #     2-leg: ~3x  |  3-leg: ~6x  |  4-leg: ~10x  |  5-leg: ~20x  |  6-leg: ~35x
    #   Mixed parlays scale between goblin and demon based on composition
    #   Standard lines are in between
    PAYOUTS_GOBLIN = {2: 1.5, 3: 1.8, 4: 2.0, 5: 3.0, 6: 5.0}
    PAYOUTS_DEMON  = {2: 3.0, 3: 6.0, 4: 10.0, 5: 20.0, 6: 35.0}
    PAYOUTS_STD    = {2: 2.0, 3: 3.5, 4: 5.0, 5: 10.0, 6: 18.0}

    def get_payout(legs, size):
        """Calculate payout based on mix of goblin/demon/standard legs."""
        g = sum(1 for r in legs if r['ltype'] == 'goblin')
        d = sum(1 for r in legs if r['ltype'] == 'demon')
        s = sum(1 for r in legs if r['ltype'] == 'standard')
        total = g + d + s
        if total == 0: return 1.0
        # Weighted average between goblin and demon payouts
        gob_pay = PAYOUTS_GOBLIN.get(size, 2.0)
        dem_pay = PAYOUTS_DEMON.get(size, 10.0)
        std_pay = PAYOUTS_STD.get(size, 5.0)
        # Weight by proportion of each type
        payout = (g * gob_pay + d * dem_pay + s * std_pay) / total
        return round(payout, 1)

    PAYOUTS = {2:3.0, 3:6.0, 4:10.0, 5:20.0, 6:35.0}  # legacy fallback

    def parlay_prob(legs):
        p = 1.0
        for r in legs: p *= r['hit_p']
        return p

    def parlay_ev(legs, payout):
        p = parlay_prob(legs)
        return p, round(p*payout - (1-p)*1, 2)

    def p_flex_5of6(legs):
        if len(legs) < 6: return 0.0
        return sum(
            (1-legs[i]['hit_p']) * float(np.prod([legs[j]['hit_p']
             for j in range(len(legs)) if j!=i]))
            for i in range(len(legs))
        )

    def build_parlay(pool, n, require_games=2):
        seen_p = set(); legs = []
        for p in pool:
            if p['player'] in seen_p: continue
            legs.append(p); seen_p.add(p['player'])
            if len(legs) == n: break
        if len(set(game_map.get(p['team'],p['team']) for p in legs)) < require_games:
            return []
        return legs

    def print_parlay(legs, title, payout, label_type=''):
        if not legs: return
        prob, ev = parlay_ev(legs, payout)
        p5 = p_flex_5of6(legs) if len(legs)==6 else 0
        probs_str = ' x '.join([f"{p['hit_p']*100:.0f}%" for p in legs])
        lbadge = {'goblin':'🟢','demon':'🔴','mixed':'🟡'}
        badge = lbadge.get(label_type,'')
        print(f"\n  {badge} {title}  (~{payout:.0f}x payout)")
        print(f"  {'─'*90}")
        for i,r in enumerate(legs,1):
            lt = '🟢 GOB' if r['ltype']=='goblin' else '🔴 DEM'
            miss_str = '  ⚠️ '+','.join(r['miss']) if r['miss'] else ''
            print(f"  Leg {i}: {lt}  {r['player']:<22} {r['stat']:<8} OVER {r['line']:<6} "
                  f"{EMOJI.get(r['grade'],'')} {r['grade']:<8} | "
                  f"{r['hit_p']*100:.0f}% | +{r['edge']:.1f}%{miss_str}")
        print(f"  P(all hit) = {probs_str} = {prob*100:.1f}%")
        print(f"  EV at {payout:.0f}x  = {prob:.3f}x${payout:.0f} - {1-prob:.3f}x$1 = ${ev:.2f} per $1")
        if p5 > 0:
            print(f"  P(5/6 flex) = {p5*100:.1f}%  → ~2x partial")
        return prob, ev

    # ── Print goblin summary ──────────────────────────────────────────────────
    print()
    print('='*100)
    print('  BEST GOBLIN PICKS — Safest plays, highest hit rate')
    print('  🟢 = goblin line (lower threshold, reduced payout, highest confidence)')
    print('='*100)
    print(f"\n  {'#':<3} {'Player':<22} {'Tm':<4} {'Stat':<8} {'Goblin':>7} "
          f"{'PO Avg':>7} {'Hit%':>6} {'Edge%':>7} {'p':>7}  Grade")
    print(f"  {'─'*85}")
    for i,r in enumerate(goblin_pool[:12],1):
        miss_str = ' ⚠️'+','.join(r['miss']) if r['miss'] else ''
        print(f"  {i:<3} {r['player']:<22} {r['team']:<4} {r['stat']:<8} {r['line']:>7.1f} "
              f"{r['mu']:>7.1f} {r['hit_p']*100:>5.0f}% {r['edge']:>6.1f}% "
              f"{r['p_val']:>7.4f}  {EMOJI.get(r['grade'],'')} {r['grade']}{miss_str}")

    # ── Print demon summary ───────────────────────────────────────────────────
    print()
    print('='*100)
    print('  BEST DEMON PICKS — Elevated lines, >50% hit rate, higher payout')
    print('  🔴 = demon line (higher threshold, bigger payout, more risk)')
    print('='*100)
    if demon_pool:
        print(f"\n  {'#':<3} {'Player':<22} {'Tm':<4} {'Stat':<8} {'Demon':>7} "
              f"{'PO Avg':>7} {'Hit%':>6} {'Edge%':>7} {'p':>7}  Grade")
        print(f"  {'─'*85}")
        for i,r in enumerate(demon_pool[:12],1):
            miss_str = ' ⚠️'+','.join(r['miss']) if r['miss'] else ''
            print(f"  {i:<3} {r['player']:<22} {r['team']:<4} {r['stat']:<8} {r['line']:>7.1f} "
                  f"{r['mu']:>7.1f} {r['hit_p']*100:>5.0f}% {r['edge']:>6.1f}% "
                  f"{r['p_val']:>7.4f}  {EMOJI.get(r['grade'],'')} {r['grade']}{miss_str}")
    else:
        print('  No demon picks above 50% hit rate tonight.')

    # ── Mixed parlay builder ──────────────────────────────────────────────────
    print()
    print('='*100)
    print('  MIXED PARLAY BUILDER — Ranked by EV (best return on investment)')
    print('  Strategy: anchor with safe goblins, boost payout with 1-2 demons')
    print('  All parlays: no public fades | 2+ games | no duplicate players')
    print('='*100)

    # Build mixed pool: top goblins + top demons
    top_goblins = goblin_pool[:8]
    top_demons  = demon_pool[:6]

    # Generate all parlay sizes and configurations
    all_parlays = []

    for size in [2, 3, 4, 5, 6]:
        payout = PAYOUTS[size]

        # Pure goblin
        legs_g = build_parlay(top_goblins, size)
        if legs_g:
            prob, ev = parlay_ev(legs_g, payout)
            all_parlays.append({
                'legs':legs_g,'size':size,'payout':payout,
                'prob':prob,'ev':ev,'type':'goblin',
                'label':f'SAFE {size}-LEG (all goblin)',
            })

        # Mixed: goblins + 1 demon
        if top_demons and size >= 3:
            mixed1 = build_parlay(top_goblins, size-1) + [top_demons[0]]
            # Remove duplicate players
            seen_mix = set()
            mixed1_clean = []
            for r in mixed1:
                if r['player'] not in seen_mix:
                    seen_mix.add(r['player']); mixed1_clean.append(r)
            if len(mixed1_clean) == size:
                prob, ev = parlay_ev(mixed1_clean, payout)
                all_parlays.append({
                    'legs':mixed1_clean,'size':size,'payout':payout,
                    'prob':prob,'ev':ev,'type':'mixed',
                    'label':f'MIXED {size}-LEG (1 demon)',
                })

        # Mixed: goblins + 2 demons
        if len(top_demons) >= 2 and size >= 4:
            mixed2 = build_parlay(top_goblins, size-2) + top_demons[:2]
            seen_mix = set()
            mixed2_clean = []
            for r in mixed2:
                if r['player'] not in seen_mix:
                    seen_mix.add(r['player']); mixed2_clean.append(r)
            if len(mixed2_clean) == size:
                prob, ev = parlay_ev(mixed2_clean, payout)
                all_parlays.append({
                    'legs':mixed2_clean,'size':size,'payout':payout,
                    'prob':prob,'ev':ev,'type':'mixed',
                    'label':f'MIXED {size}-LEG (2 demons)',
                })

        # Pure demon
        if len(top_demons) >= size:
            legs_d = build_parlay(top_demons, size)
            if legs_d:
                prob, ev = parlay_ev(legs_d, payout)
                all_parlays.append({
                    'legs':legs_d,'size':size,'payout':payout,
                    'prob':prob,'ev':ev,'type':'demon',
                    'label':f'HIGH-RISK {size}-LEG (all demon)',
                })

    # Sort by EV descending — best return on investment first
    all_parlays.sort(key=lambda x: -x['ev'])

    # Print top parlays by EV
    print()
    print(f"  {'Rank':<5} {'Parlay':<35} {'P(win)':>8} {'EV/dollar':>10}  Type")
    print(f"  {'─'*70}")
    for i,p in enumerate(all_parlays[:15],1):
        badge = '🟢' if p['type']=='goblin' else ('🔴' if p['type']=='demon' else '🟡')
        print(f"  {i:<5} {p['label']:<35} {p['prob']*100:>7.1f}% {p['ev']:>9.2f}  {badge}")

    # Print top 5 in detail
    print()
    print('  TOP 5 PARLAYS IN DETAIL (best EV):')
    for p in all_parlays[:5]:
        print_parlay(p['legs'], p['label'], p['payout'], p['type'])

    print()
    print('='*100)
    print('  HOW TO READ THIS:')
    print('  🟢 SAFE    = all goblin lines. Highest hit rate, lowest payout.')
    print('  🟡 MIXED   = mostly goblins + 1-2 demons. Best risk/reward balance.')
    print('  🔴 HIGH-RISK = all demon lines. Highest payout, more variance.')
    print('  EV/dollar  = expected profit per $1 bet long-term. Higher = better.')
    print('  Best play  = highest EV that you are comfortable with the risk level.')
    print('='*100)
    print()
    print('  Run: python3 parbs_playoff_engine.py --tomorrow  for next game')
    print('='*100)


if __name__ == '__main__':
    use_tomorrow = '--tomorrow' in sys.argv
    target = date.today() + timedelta(days=1) if use_tomorrow else date.today()
    run(target)
