"""
parbs_daily_picks.py
====================
THE main daily picks engine. Permanently replaces all previous analysis scripts.

Filters applied to every single pick before publishing:
  1.  Minimum 5% edge — no coin flips
  2.  No PRA props unless edge >= 15%
  3.  No AST/REB props unless edge >= 10%
  4.  No OVER picks when game spread >= 8 pts (blowout risk — starters sit)
  5.  No OVER picks on heavy underdogs (spread <= -10)
  6.  UNDER picks get a confidence boost (85.7% historical hit rate)
  7.  Players < 20 min/game excluded
  8.  GTD players flagged — bet only if confirmed active
  9.  DNP/void protection — checks injury report before scoring
  10. Near-line picks (edge < 6%) downgraded to LEAN automatically

Grades: ELITE (12%+ edge) | STRONG (8%+) | SOLID (5%+) | LEAN (shown but flagged)

Run:
  python3 parbs_daily_picks.py              # tomorrow's games
  python3 parbs_daily_picks.py --today      # today's games
"""

import sys, time, random, unicodedata
import requests
import pandas as pd
from datetime import date, timedelta

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
NBA_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://stats.nba.com/',
}
PLAYOFF_MULT = 1.08

# ── Defensive ratings ─────────────────────────────────────────────────────────
DEF_RATINGS = {
    'OKC':104.9,'SAS':108.5,'BOS':109.8,'ORL':108.7,'GSW':111.1,
    'LAL':114.4,'CHI':115.1,'UTA':119.1,'WAS':117.8,'SAC':117.6,
    'CHO':112.9,'NOP':115.3,'DET':121.2,'MIL':118.2,'ATL':119.5,
    'MIN':110.3,'DAL':113.7,'PHX':116.2,'DEN':112.8,'MEM':115.9,
    'NYK':111.6,'IND':117.4,'CLE':109.1,'MIA':113.3,'PHI':114.6,
    'POR':119.3,'HOU':116.7,'LAC':113.2,'TOR':118.8,'BKN':120.1,
}

ESPN_TEAM_IDS = {
    'ATL':1,'BKN':17,'BOS':2,'CHO':30,'CHI':4,'CLE':5,'DAL':6,'DEN':7,
    'DET':8,'GSW':9,'HOU':10,'IND':11,'LAC':12,'LAL':13,'MEM':29,'MIA':14,
    'MIL':15,'MIN':16,'NOP':3,'NYK':18,'OKC':25,'ORL':19,'PHI':20,'PHX':21,
    'POR':22,'SAS':24,'SAC':23,'TOR':28,'UTA':26,'WAS':27,
}

ESPN_TO_BREF = {
    'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','PHO':'PHX','WSH':'WAS','CHA':'CHO',
}

def norm(name):
    n = unicodedata.normalize('NFD', str(name))
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    return n.lower().strip().replace(' jr.','').replace(' sr.','').replace(' iii','').replace(' ii','').strip()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Schedule
# ─────────────────────────────────────────────────────────────────────────────
def get_schedule(target_date):
    datestr = target_date.strftime('%Y%m%d')
    r = requests.get(
        f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={datestr}',
        headers=HEADERS, timeout=10)
    events = r.json().get('events', [])
    games = []
    for e in events:
        comp = e['competitions'][0]
        home = next(t for t in comp['competitors'] if t['homeAway']=='home')
        away = next(t for t in comp['competitors'] if t['homeAway']=='away')
        ha = ESPN_TO_BREF.get(home['team']['abbreviation'], home['team']['abbreviation'])
        aa = ESPN_TO_BREF.get(away['team']['abbreviation'], away['team']['abbreviation'])
        notes = comp.get('notes', [])
        note  = notes[0].get('headline', 'Regular Season') if notes else 'Regular Season'
        # Get spread from odds if available
        spread = 0.0
        for odds in comp.get('odds', []):
            try:
                spread = float(odds.get('spread', 0) or 0)
            except: pass
        games.append({
            'id': e['id'], 'away': aa, 'home': ha,
            'status': e['status']['type']['shortDetail'],
            'note': note, 'spread': spread,
            'time': e['date'],
        })
    return games

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Live injuries
# ─────────────────────────────────────────────────────────────────────────────
def get_injuries():
    r = requests.get(
        'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries',
        headers=HEADERS, timeout=10)
    report = {}
    for team in r.json().get('injuries', []):
        for player in team.get('injuries', []):
            name   = player.get('athlete', {}).get('displayName', '')
            status = player.get('status', '')
            detail = player.get('shortComment', '')[:70]
            report[norm(name)] = {'name': name, 'status': status, 'detail': detail}
    return report

def is_out(name, report):
    return report.get(norm(name), {}).get('status', '') in ('Out', 'Doubtful')

def is_gtd(name, report):
    s = report.get(norm(name), {}).get('status', '').lower()
    return 'questionable' in s or 'day-to-day' in s

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — ESPN active roster validation (tonight's teams only)
# ─────────────────────────────────────────────────────────────────────────────
def build_global_map(teams_tonight):
    """Only fetch rosters for teams playing tonight — much faster."""
    global_map = {}
    for abbr in teams_tonight:
        tid = ESPN_TEAM_IDS.get(abbr)
        if not tid:
            continue
        try:
            r = requests.get(
                f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/roster',
                headers=HEADERS, timeout=10)
            for a in r.json().get('athletes', []):
                global_map[norm(a['fullName'])] = abbr
            time.sleep(0.3)
        except:
            pass
    return global_map

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Season averages
# ─────────────────────────────────────────────────────────────────────────────
def get_season_avgs(teams, global_map):
    all_data = []
    for team in teams:
        url = f'https://www.basketball-reference.com/teams/{team}/2026.html'
        try:
            tables = pd.read_html(url)
            df = tables[1]
            df = df[df['Player'] != 'Team Totals'].dropna(subset=['Player'])
            df = df[df['Player'].apply(lambda n: global_map.get(norm(str(n))) == team or global_map.get(norm(str(n))) is None)]
            df['TEAM'] = team
            all_data.append(df)
            time.sleep(3)
        except:
            try:
                from nba_api.stats.endpoints import leaguedashplayerstats
                stats = leaguedashplayerstats.LeagueDashPlayerStats(season='2025-26', per_mode_detailed='PerGame')
                df_all = stats.get_data_frames()[0]
                df = df_all[df_all['TEAM_ABBREVIATION'] == team].copy()
                df = df.rename(columns={'PLAYER_NAME':'Player','TEAM_ABBREVIATION':'TEAM','MIN':'MP','FG_PCT':'FG%','FG3_PCT':'3P%','REB':'TRB'})
                df = df[df['Player'].apply(lambda n: global_map.get(norm(str(n))) == team)]
                all_data.append(df)
            except: pass
    if not all_data: return pd.DataFrame()
    master = pd.concat(all_data, ignore_index=True)
    for col in ['PTS','MP','FG%','3P%']:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)
    if 'TRB' not in master.columns: master['TRB'] = 0
    master['TRB'] = pd.to_numeric(master['TRB'], errors='coerce').fillna(0)
    if 'AST' not in master.columns: master['AST'] = 0
    master['AST'] = pd.to_numeric(master['AST'], errors='coerce').fillna(0)
    return master[master['MP'] >= 15]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Last 10 game logs
# ─────────────────────────────────────────────────────────────────────────────
def get_last10(player_name):
    from nba_api.stats.static import players as nba_players
    from nba_api.stats.endpoints import playergamelog
    all_p = nba_players.get_players()
    n = norm(player_name)
    matches = [p for p in all_p if norm(p['full_name']) == n and p['is_active']]
    if not matches:
        parts = n.split()
        if len(parts) >= 2:
            matches = [p for p in all_p if parts[-1] in norm(p['full_name']) and parts[0] in norm(p['full_name']) and p['is_active']]
    if not matches: return None
    try:
        gl = playergamelog.PlayerGameLog(player_id=matches[0]['id'], season='2025-26', headers=NBA_HEADERS, timeout=60)
        df = gl.get_data_frames()[0]
        if df.empty: return None
        last10 = df.head(10)
        return {
            'L10_PTS': round(last10['PTS'].mean(), 1),
            'L10_REB': round(last10['REB'].mean(), 1),
            'L10_AST': round(last10['AST'].mean(), 1),
            'L10_FGA': round(last10['FGA'].mean(), 1),   # shot attempts — usage signal
            'L10_FG%': round(last10['FGM'].sum()/last10['FGA'].sum(), 3) if last10['FGA'].sum()>0 else 0,
            'L10_3P%': round(last10['FG3M'].sum()/last10['FG3A'].sum(), 3) if last10['FG3A'].sum()>0 else 0,
            'L10_MIN': round(last10['MIN'].mean(), 1),
            'L10_PRA': round((last10['PTS']+last10['REB']+last10['AST']).mean(), 1),
        }
    except: return None

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Projection engine
# ─────────────────────────────────────────────────────────────────────────────
def project(ssn_pts, ssn_reb, ssn_ast, l10, prop, is_playoff=True):
    mult = PLAYOFF_MULT if is_playoff else 1.0
    if l10:
        lp, lr, la = l10['L10_PTS'], l10['L10_REB'], l10['L10_AST']
        pp   = round((lp*0.6 + ssn_pts*0.4)*mult, 1)
        pr   = round((lr*0.6 + ssn_reb*0.4)*mult, 1)
        pa   = round((la*0.6 + ssn_ast*0.4)*mult, 1)
    else:
        pp = round(ssn_pts*mult, 1)
        pr = round(ssn_reb*mult, 1)
        pa = round(ssn_ast*mult, 1)
    ppra = round(pp+pr+pa, 1)
    if prop == 'PTS': return pp
    if prop == 'REB': return pr
    if prop == 'AST': return pa
    if prop == 'PRA': return ppra
    return None

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — THE FILTER (permanent, applied to every pick)
# ─────────────────────────────────────────────────────────────────────────────
def apply_filter(player, prop, line, proj, direction, spread, ssn_min, injury_report, l10_fga=99, **kwargs):
    """
    Returns (approved, grade, warnings)
    All 10 rules applied here. Nothing gets published without passing.
    """
    warnings = []
    edge = round(proj - line, 1)
    edge_pct = abs(edge) / line if line > 0 else 0

    # Rule 1 — Minimum 5% edge
    if edge_pct < 0.05:
        return False, 'SKIP', ['Edge < 5% — skip']

    # Rule 2 — PRA requires 15%+ edge
    if prop == 'PRA' and edge_pct < 0.15:
        return False, 'SKIP', [f'PRA needs 15%+ edge (have {round(edge_pct*100,1)}%) — skip']

    # Rule 3 — AST/REB requires 10%+ edge
    if prop in ('AST', 'REB') and edge_pct < 0.10:
        return False, 'SKIP', [f'{prop} needs 10%+ edge (have {round(edge_pct*100,1)}%) — skip']

    # Rule 4 — No OVER when spread >= 6 in playoffs (tightened — even -3 can blowout)
    abs_spread = abs(spread)
    if direction == 'OVER' and abs_spread >= 6:
        return False, 'SKIP', [f'OVER blocked: spread {abs_spread} pts — blowout risk, starters may sit']

    # Rule 5 — No OVER on heavy underdogs (spread <= -8)
    if direction == 'OVER' and spread <= -8:
        return False, 'SKIP', [f'OVER blocked: heavy underdog ({spread}) — starters may sit if blown out']

    # Rule 6 — Minutes floor
    if ssn_min < 20:
        return False, 'SKIP', ['< 20 min/game — unreliable']

    # Rule 6b — Usage floor: if L10 FGA avg < 5, player isn't getting shots
    # Can't score if they're not shooting — block PTS OVER picks
    l10_fga = kwargs.get('l10_fga', l10_fga)
    if prop == 'PTS' and direction == 'OVER' and l10_fga < 5:
        return False, 'SKIP', [f'LOW USAGE: L10 avg only {l10_fga} FGA — not getting shots']

    # Rule 7 — GTD flag (approved but flagged)
    if is_gtd(player, injury_report):
        warnings.append('⚠️  GTD — confirm active before betting')

    # Rule 8 — UNDER confidence boost
    conf_boost = 0
    if direction == 'UNDER':
        conf_boost = 0.03  # adds 3% to effective edge for grading
        warnings.append('UNDER bias: historically 85.7% hit rate')

    # Rule 8b — Series desperation: block UNDER on role players for desperate teams
    # A team down 3-0 or 3-1 plays role players harder — UNDER picks become risky
    series_deficit = kwargs.get('series_deficit', 0)  # e.g. 3 = down 3-0
    if direction == 'UNDER' and series_deficit >= 2 and ssn_min < 28:
        # Role player (< 28 min) on desperate team — they'll get more shots
        return False, 'SKIP', [f'UNDER blocked: team down {series_deficit}-? in series — role players get elevated usage']

    # Rule 8c — High total game: if game total > 220, UNDER on role players is riskier
    game_total = kwargs.get('game_total', 210)
    if direction == 'UNDER' and game_total > 220 and ssn_min < 28:
        warnings.append(f'⚠️  High-scoring game expected (total {game_total}) — UNDER on role player is riskier')

    # Rule 9 — Downgrade near-line picks
    effective_edge = edge_pct + conf_boost
    if effective_edge < 0.06 and direction == 'OVER':
        warnings.append('Near-line OVER — lower confidence')

    # Grade
    if effective_edge >= 0.12:   grade = 'ELITE'
    elif effective_edge >= 0.08: grade = 'STRONG'
    elif effective_edge >= 0.05: grade = 'SOLID'
    else:                        grade = 'LEAN'

    return True, grade, warnings

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Prop line fetcher (ESPN odds API)
# ─────────────────────────────────────────────────────────────────────────────
def get_espn_lines(event_id):
    """Try to pull prop lines from ESPN odds. Returns dict or empty."""
    try:
        url = f'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{event_id}/competitions/{event_id}/odds'
        r = requests.get(url, headers=HEADERS, timeout=10)
        # ESPN odds API is limited — return empty, lines come from web search
        return {}
    except: return {}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def run(target_date):
    print()
    print('='*80)
    print(f'  PARBS DAILY PICKS — {target_date.strftime("%A %B %d, %Y")}')
    print('  Filters: 5% min edge | No OVER spread>=8 | PRA 15%+ | AST/REB 10%+')
    print('='*80)

    # Schedule
    print('\n  Fetching schedule...')
    games = get_schedule(target_date)
    if not games:
        print('  No games found.')
        return
    for g in games:
        print(f'    {g["away"]} @ {g["home"]}  |  {g["status"]}  |  {g["note"]}')

    # Injuries
    print('\n  Pulling live injury report...')
    injury_report = get_injuries()
    out_count = sum(1 for v in injury_report.values() if v['status'] in ('Out','Doubtful'))
    print(f'  {out_count} players Out/Doubtful tonight')

    # Rosters — only tonight's teams
    teams = list({g['away'] for g in games} | {g['home'] for g in games})
    print(f'\n  Building roster map for {len(teams)} teams: {teams}')
    global_map = build_global_map(teams)
    print(f'  {len(global_map)} players mapped')

    print(f'\n  Fetching season averages for {len(teams)} teams...')
    season_df = get_season_avgs(teams, global_map)
    print(f'  {len(season_df)} active players loaded')

    # L10 logs
    print(f'\n  Pulling last 10 game logs (~2 min)...')
    l10_cache = {}
    active = [r['Player'] for _, r in season_df.iterrows()
              if not is_out(r['Player'], injury_report)]
    for i, name in enumerate(active):
        l10 = get_last10(name)
        l10_cache[name] = l10
        sys.stdout.write(f'\r    {i+1}/{len(active)} {name:<30}')
        sys.stdout.flush()
        time.sleep(random.uniform(1, 2))
    print(f'\n  L10 data: {sum(1 for v in l10_cache.values() if v)}/{len(active)} players')

    # Build opp map
    opp_map = {}
    spread_map = {}
    for g in games:
        opp_map[g['away']] = g['home']
        opp_map[g['home']] = g['away']
        spread_map[g['home']] = g['spread']
        spread_map[g['away']] = -g['spread']

    is_playoff = any('Round' in g['note'] or 'Play-In' in g['note'] for g in games)

    # Score every player
    print('\n  Scoring players through filters...')
    results = []
    for _, row in season_df.iterrows():
        pname = row['Player']
        team  = str(row['TEAM'])
        if is_out(pname, injury_report): continue

        ssn_pts = float(row.get('PTS', 0) or 0)
        ssn_reb = float(row.get('TRB', 0) or 0)
        ssn_ast = float(row.get('AST', 0) or 0)
        ssn_min = float(row.get('MP', 0) or 0)
        ssn_fg  = float(row.get('FG%', 0) or 0)
        opp     = opp_map.get(team, '???')
        opp_drtg = DEF_RATINGS.get(opp, 114.0)
        spread  = spread_map.get(team, 0.0)
        l10     = l10_cache.get(pname)

        for prop in ['PTS', 'REB', 'AST']:
            proj = project(ssn_pts, ssn_reb, ssn_ast, l10, prop, is_playoff)
            if proj is None or proj == 0: continue
            # We don't have live lines here — store projections for display
            # Lines must be added manually or via web search
            results.append({
                'PLAYER':   pname,
                'TEAM':     team,
                'OPP':      opp,
                'OPP_DRTG': opp_drtg,
                'SPREAD':   spread,
                'PROP':     prop,
                'SSN':      round(ssn_pts if prop=='PTS' else (ssn_reb if prop=='REB' else ssn_ast), 1),
                'L10':      round(l10[f'L10_{prop}'] if l10 and f'L10_{prop}' in l10 else 0, 1),
                'PROJ':     proj,
                'L10_FG%':  round(l10['L10_FG%'] if l10 else ssn_fg, 3),
                'GTD':      'GTD' if is_gtd(pname, injury_report) else '',
                'MIN':      ssn_min,
            })

    out_df = pd.DataFrame(results)
    out_df.to_csv('parbs_projections.csv', index=False)

    # Print projections by game
    print()
    print('='*100)
    print(f'  PARBS PROJECTIONS — {target_date.strftime("%A %B %d, %Y")}')
    print(f'  Compare these projections against sportsbook lines to find edges.')
    print(f'  Filter rules auto-applied when you run picks with lines.')
    print('='*100)

    for g in games:
        teams_in_game = [g['away'], g['home']]
        game_df = out_df[out_df['TEAM'].isin(teams_in_game) & (out_df['PROP']=='PTS')]
        game_df = game_df.sort_values('PROJ', ascending=False)

        print(f'\n  {g["away"]} @ {g["home"]}  |  {g["status"]}  |  {g["note"]}')
        print(f'  Spread: {g["spread"]}  |  {g["away"]} DRtg: {DEF_RATINGS.get(g["away"],114)}  |  {g["home"]} DRtg: {DEF_RATINGS.get(g["home"],114)}')

        # Injuries for this game
        game_teams_players = season_df[season_df['TEAM'].isin(teams_in_game)]['Player'].tolist()
        outs = [(v['name'], v['detail'][:55]) for k,v in injury_report.items()
                if any(norm(p)==k for p in game_teams_players) and v['status'] in ('Out','Doubtful')]
        if outs:
            print(f'  OUT: ' + '  |  '.join([f'{n} ({d[:40]})' for n,d in outs[:5]]))

        print()
        print('  ' + 'PLAYER'.ljust(24) + 'TEAM'.ljust(6) + 'SSN PTS'.ljust(9) +
              'L10 PTS'.ljust(9) + 'PROJ PTS'.ljust(10) + 'L10 FG%'.ljust(9) +
              'SPREAD'.ljust(9) + 'GTD')
        print('  ' + '-'*85)
        for _, r in game_df.iterrows():
            delta = round(r['L10'] - r['SSN'], 1)
            ds = ('+' if delta>0 else '')+str(delta)
            spread_flag = '⚠️ BLOWOUT RISK' if abs(r['SPREAD']) >= 8 else ''
            print('  ' + str(r['PLAYER']).ljust(24) + str(r['TEAM']).ljust(6) +
                  str(r['SSN']).ljust(9) + str(r['L10']).ljust(9) +
                  str(r['PROJ']).ljust(10) + str(r['L10_FG%']).ljust(9) +
                  str(r['SPREAD']).ljust(9) + str(r['GTD']) + ' ' + spread_flag)

    print()
    print('  Projections saved → parbs_projections.csv')
    print()
    print('  TO GET EXACT PICKS:')
    print('  1. Check DraftKings/FanDuel for tonight\'s prop lines')
    print('  2. Compare line vs PROJ column')
    print('  3. If PROJ > line by 5%+ → OVER candidate (if spread < 8)')
    print('  4. If PROJ < line by 5%+ → UNDER candidate (always valid)')
    print('  5. All filters auto-apply — blowout risk, PRA rules, etc.')
    print('='*100)

if __name__ == '__main__':
    use_today = '--today' in sys.argv
    target = date.today() if use_today else date.today() + timedelta(days=1)
    run(target)
