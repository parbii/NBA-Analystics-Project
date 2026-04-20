"""
parbs_investment_engine.py
==========================
Nightly investment scoring engine. Combines:
  - Season averages (floor/baseline)
  - Last 10 game averages (recent form)
  - Regression-to-mean delta (hot/cold signal)
  - Opponent defensive rating (matchup difficulty)
  - Role boost (star out = more usage)
  - Minutes trend (usage going up or down)
  - Play-In / Playoff context (elevated effort multiplier)

Outputs a ranked investment score (0-100) per player with a
confidence tier: ELITE / STRONG / SOLID / LEAN / FADE

Run:
  python3 parbs_investment_engine.py
"""

import os, sys, time, random, unicodedata
import requests
import pandas as pd
import numpy as np
from datetime import date

os.system('clear')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
NBA_HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://stats.nba.com/',
}

# ── Defensive ratings (updated each run from parbs_master_analysis) ──────────
DEF_RATINGS = {
    'OKC':104.9,'SAS':108.5,'BOS':109.8,'ORL':108.7,'GSW':111.1,
    'LAL':114.4,'CHI':115.1,'UTA':119.1,'UTAH':119.1,'WAS':117.8,
    'SAC':117.6,'CHO':112.9,'NOP':115.3,'DET':121.2,'MIL':118.2,
    'ATL':119.5,'MIN':110.3,'DAL':113.7,'PHX':116.2,'DEN':112.8,
    'MEM':115.9,'NYK':111.6,'IND':117.4,'CLE':109.1,'MIA':113.3,
    'PHI':114.6,'POR':119.3,'HOU':116.7,'LAC':113.2,'TOR':118.8,'BKN':120.1,
}
LEAGUE_AVG_DRTG = 114.0

ESPN_TEAM_IDS = {
    'ATL':1,'BKN':17,'BOS':2,'CHO':30,'CHI':4,'CLE':5,'DAL':6,'DEN':7,
    'DET':8,'GSW':9,'HOU':10,'IND':11,'LAC':12,'LAL':13,'MEM':29,'MIA':14,
    'MIL':15,'MIN':16,'NOP':3,'NYK':18,'OKC':25,'ORL':19,'PHI':20,'PHX':21,
    'POR':22,'SAS':24,'SAC':23,'TOR':28,'UTA':26,'UTAH':26,'WAS':27,
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def norm(name):
    n = unicodedata.normalize('NFD', str(name))
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn')
    return n.lower().strip().replace(' jr.','').replace(' sr.','').replace(' iii','').replace(' ii','').strip()

def cooldown():
    time.sleep(random.uniform(3, 6))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Tonight's schedule
# ─────────────────────────────────────────────────────────────────────────────
def get_todays_games():
    today = date.today().strftime('%Y%m%d')
    url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get('events', [])
        games, opp_map, game_notes = [], {}, {}
        for e in events:
            comp = e['competitions'][0]
            home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
            away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
            ha = home['team']['abbreviation'].upper()
            aa = away['team']['abbreviation'].upper()
            # Normalise ESPN abbrs to our keys
            ESPN_TO_KEY = {'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','PHO':'PHX','WSH':'WAS','CHA':'CHO','UTA':'UTAH'}
            ha = ESPN_TO_KEY.get(ha, ha)
            aa = ESPN_TO_KEY.get(aa, aa)
            status = e['status']['type']['shortDetail']
            notes  = comp.get('notes', [])
            note   = notes[0].get('headline','') if notes else 'Regular Season'
            opp_map[ha] = aa
            opp_map[aa] = ha
            game_notes[ha] = note
            game_notes[aa] = note
            games.append((aa, ha, status, note))
        return games, opp_map, game_notes
    except Exception as e:
        print(f'  ESPN schedule failed: {e}')
        return [], {}, {}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Live injury report
# ─────────────────────────────────────────────────────────────────────────────
def get_injuries():
    try:
        r = requests.get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries',
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        report = {}
        for team in r.json().get('injuries', []):
            for player in team.get('injuries', []):
                name   = player.get('athlete', {}).get('displayName', '')
                status = player.get('status', '')
                detail = player.get('shortComment', '')[:70]
                report[norm(name)] = {'name': name, 'status': status, 'detail': detail}
        return report
    except Exception as e:
        print(f'  Injury report failed: {e}')
        return {}

def is_out(name, report):
    return report.get(norm(name), {}).get('status', '') in ('Out', 'Doubtful')

def is_gtd(name, report):
    s = report.get(norm(name), {}).get('status', '').lower()
    return 'questionable' in s or 'day-to-day' in s

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — ESPN active roster validation (global map)
# ─────────────────────────────────────────────────────────────────────────────
def build_global_map():
    print('  Building ESPN global roster map...')
    global_map = {}
    seen = set()
    for abbr, tid in ESPN_TEAM_IDS.items():
        if tid in seen:
            continue
        seen.add(tid)
        try:
            r = requests.get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/roster',
                             headers=HEADERS, timeout=10)
            r.raise_for_status()
            for a in r.json().get('athletes', []):
                global_map[norm(a['fullName'])] = abbr
            time.sleep(0.25)
        except:
            pass
    print(f'  {len(global_map)} players mapped across 30 teams.')
    return global_map

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Season averages from B-Ref / nba_api
# ─────────────────────────────────────────────────────────────────────────────
def get_season_avgs(teams, global_map):
    from io import StringIO
    all_data = []
    for team in teams:
        url = f'https://www.basketball-reference.com/teams/{team}/2026.html'
        try:
            tables = pd.read_html(url)
            df = tables[1]
            df = df[df['Player'] != 'Team Totals'].dropna(subset=['Player'])
            # Validate team via ESPN global map
            df = df[df['Player'].apply(lambda n: global_map.get(norm(str(n))) == team or global_map.get(norm(str(n))) is None)]
            df['TEAM'] = team
            df['SOURCE'] = 'B-Ref'
            all_data.append(df)
            time.sleep(3)
        except Exception as e:
            # Fallback to nba_api
            try:
                from nba_api.stats.endpoints import leaguedashplayerstats
                stats = leaguedashplayerstats.LeagueDashPlayerStats(season='2025-26', per_mode_detailed='PerGame')
                df_all = stats.get_data_frames()[0]
                df = df_all[df_all['TEAM_ABBREVIATION'] == team].copy()
                df = df.rename(columns={'PLAYER_NAME':'Player','TEAM_ABBREVIATION':'TEAM','MIN':'MP','FG_PCT':'FG%','FG3_PCT':'3P%','REB':'TRB'})
                df = df[df['Player'].apply(lambda n: global_map.get(norm(str(n))) == team)]
                df['SOURCE'] = 'nba_api'
                all_data.append(df)
            except Exception as e2:
                print(f'  Both sources failed for {team}: {e2}')

    if not all_data:
        return pd.DataFrame()
    master = pd.concat(all_data, ignore_index=True)
    for col in ['PTS','MP','FG%','3P%']:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)
    return master[master['MP'] >= 8]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Last 10 game averages via nba_api
# ─────────────────────────────────────────────────────────────────────────────
def get_last10(player_name):
    from nba_api.stats.static import players as nba_players
    from nba_api.stats.endpoints import playergamelog

    all_p = nba_players.get_players()
    n = norm(player_name)
    matches = [p for p in all_p if norm(p['full_name']) == n and p['is_active']]
    if not matches:
        # fuzzy: first + last
        parts = n.split()
        if len(parts) >= 2:
            matches = [p for p in all_p if parts[-1] in norm(p['full_name']) and parts[0] in norm(p['full_name']) and p['is_active']]
    if not matches:
        return None

    pid = matches[0]['id']
    try:
        gl = playergamelog.PlayerGameLog(player_id=pid, season='2025-26', headers=NBA_HEADERS, timeout=60)
        df = gl.get_data_frames()[0]
        if df.empty:
            return None
        last10 = df.head(10)
        return {
            'L10_PTS':  round(last10['PTS'].mean(), 1),
            'L10_REB':  round(last10['REB'].mean(), 1),
            'L10_AST':  round(last10['AST'].mean(), 1),
            'L10_FG%':  round(last10['FGM'].sum() / last10['FGA'].sum(), 3) if last10['FGA'].sum() > 0 else 0,
            'L10_3P%':  round(last10['FG3M'].sum() / last10['FG3A'].sum(), 3) if last10['FG3A'].sum() > 0 else 0,
            'L10_MIN':  round(last10['MIN'].mean(), 1),
            'L10_PRA':  round((last10['PTS'] + last10['REB'] + last10['AST']).mean(), 1),
            'GAMES':    len(df),
        }
    except:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Investment scoring model
# ─────────────────────────────────────────────────────────────────────────────
def score_player(row, l10, opp_drtg, stars_out, injury_report, game_note):
    """
    Returns a 0-100 investment score. Higher = more reliable investment.

    Components:
      Base volume score     (0-25): season PPG relative to league
      Matchup score         (0-20): opponent DRtg (weak D = more points)
      Form score            (0-20): L10 vs season delta
      Regression score      (0-15): cold players regressing up = value
      Role boost score      (0-10): star out = more usage
      Consistency score     (0-10): low variance = reliable floor
    """
    score = 0
    notes = []

    ssn_pts = float(row.get('PTS', 0) or 0)
    ssn_mp  = float(row.get('MP', 0) or 0)
    ssn_fg  = float(row.get('FG%', 0) or 0)
    ssn_3p  = float(row.get('3P%', 0) or 0)

    if ssn_mp < 8:
        return 0, []

    # ── 1. Base volume (0-25) ─────────────────────────────────────────────────
    # 30 PPG = 25pts, 20 PPG = ~17pts, 10 PPG = ~8pts
    base = min(25, (ssn_pts / 30) * 25)
    score += base

    # ── 2. Matchup vs opponent DRtg (0-20) ───────────────────────────────────
    # DRtg 120 = 20pts, DRtg 105 = 0pts (tough D)
    matchup = max(0, min(20, ((opp_drtg - 105) / 15) * 20))
    score += matchup
    if opp_drtg > 117:
        notes.append('WEAK D (' + str(opp_drtg) + ')')
    elif opp_drtg < 110:
        notes.append('TOUGH D (' + str(opp_drtg) + ')')

    # ── 3. Recent form — L10 vs season (0-20) ────────────────────────────────
    if l10:
        pts_delta = l10['L10_PTS'] - ssn_pts
        fg_delta  = l10['L10_FG%'] - ssn_fg
        # Positive delta = hot = slight regression risk but still good
        # Use weighted combo
        form_raw = (pts_delta * 0.6) + (fg_delta * 100 * 0.4)
        form = max(-10, min(20, 10 + form_raw))
        score += form
        if pts_delta > 3:
            notes.append('HOT L10 (+' + str(round(pts_delta,1)) + ' pts)')
        elif pts_delta < -3:
            notes.append('COLD L10 (' + str(round(pts_delta,1)) + ' pts)')
    else:
        score += 10  # neutral if no L10 data

    # ── 4. Regression-to-mean value (0-15) ───────────────────────────────────
    # Cold players in elimination games are high-value — they WILL try harder
    if l10:
        pts_delta = l10['L10_PTS'] - ssn_pts
        is_playoff = any(x in str(game_note) for x in ['Play-In','Playoff','Round','Finals'])
        if pts_delta < -3 and is_playoff:
            # Cold star in elimination = regression UP likely
            rtm = min(15, abs(pts_delta) * 1.5)
            score += rtm
            notes.append('RTM UP (playoff)')
        elif pts_delta < -3:
            rtm = min(10, abs(pts_delta) * 0.8)
            score += rtm
            notes.append('RTM UP')
        elif pts_delta > 5:
            # Very hot — slight regression risk
            score -= 3
            notes.append('RTM DOWN risk')

    # ── 5. Role boost (0-10) ─────────────────────────────────────────────────
    if stars_out:
        boost = min(10, len(stars_out) * 4)
        score += boost
        notes.append('BOOST (' + ', '.join(stars_out) + ' out)')

    # ── 6. Consistency / minutes floor (0-10) ────────────────────────────────
    # High minutes + high FG% = reliable
    if ssn_mp >= 28 and ssn_fg >= 0.48:
        score += 10
        notes.append('EFFICIENT STARTER')
    elif ssn_mp >= 24 and ssn_fg >= 0.44:
        score += 6
    elif ssn_mp >= 18:
        score += 3

    # ── 7. Playoff multiplier ─────────────────────────────────────────────────
    is_playoff = any(x in str(game_note) for x in ['Play-In','Playoff','Round','Finals'])
    if is_playoff and ssn_pts >= 15:
        score *= 1.08
        notes.append('PLAYOFF')

    score = round(min(100, max(0, score)), 1)
    return score, notes

def tier_label(score):
    if score >= 78: return 'ELITE'
    if score >= 65: return 'STRONG'
    if score >= 52: return 'SOLID'
    if score >= 40: return 'LEAN'
    return 'FADE'

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('='*70)
    print('  PARBS INVESTMENT ENGINE — ' + date.today().strftime('%A %B %d, %Y'))
    print('='*70)

    # Step 1 — Schedule
    print('\n  Fetching tonight\'s schedule...')
    games, opp_map, game_notes = get_todays_games()
    if not games:
        print('  No games today. Exiting.')
        sys.exit(0)

    teams_tonight = list(opp_map.keys())
    print(f'  {len(games)} game(s) — {len(teams_tonight)} teams')
    for away, home, status, note in games:
        print(f'    {away} @ {home}  |  {status}  |  {note}')

    # Step 2 — Injuries
    print('\n  Pulling live injury report...')
    injury_report = get_injuries()
    print(f'  {len(injury_report)} players on report')

    # Step 3 — ESPN roster validation
    print('\n  Validating rosters against ESPN...')
    global_map = build_global_map()

    # Step 4 — Season averages
    print('\n  Fetching season averages...')
    season_df = get_season_avgs(teams_tonight, global_map)
    print(f'  {len(season_df)} active players loaded')

    # Step 5 — Last 10 game logs
    print('\n  Pulling last 10 game logs (this takes ~2 min)...')
    l10_cache = {}
    active_players = [r['Player'] for _, r in season_df.iterrows()
                      if not is_out(r['Player'], injury_report) and r['MP'] >= 12]
    for i, pname in enumerate(active_players):
        l10 = get_last10(pname)
        l10_cache[pname] = l10
        if l10:
            sys.stdout.write(f'\r    {i+1}/{len(active_players)} — {pname:<30}')
            sys.stdout.flush()
        cooldown()
    print(f'\n  L10 data: {sum(1 for v in l10_cache.values() if v)} / {len(active_players)} players')

    # Step 6 — Score every player
    print('\n  Scoring players...')
    results = []
    for _, row in season_df.iterrows():
        pname  = row['Player']
        team   = str(row['TEAM'])
        opp    = opp_map.get(team, '???')
        opp_drtg = DEF_RATINGS.get(opp, LEAGUE_AVG_DRTG)
        note   = game_notes.get(team, 'Regular Season')

        if is_out(pname, injury_report):
            continue

        # Stars out on this team
        stars_out = [r['Player'] for _, r in season_df[season_df['TEAM'] == team].iterrows()
                     if r['PTS'] >= 18 and is_out(r['Player'], injury_report)]

        l10 = l10_cache.get(pname)
        inv_score, inv_notes = score_player(row, l10, opp_drtg, stars_out, injury_report, note)

        if inv_score < 20:
            continue  # skip deep bench with no signal

        results.append({
            'PLAYER':      pname,
            'TEAM':        team,
            'OPP':         opp,
            'OPP_DRTG':    opp_drtg,
            'SSN_PTS':     round(float(row.get('PTS', 0) or 0), 1),
            'SSN_FG%':     round(float(row.get('FG%', 0) or 0), 3),
            'SSN_3P%':     round(float(row.get('3P%', 0) or 0), 3),
            'SSN_MIN':     round(float(row.get('MP', 0) or 0), 1),
            'L10_PTS':     l10['L10_PTS'] if l10 else '-',
            'L10_FG%':     l10['L10_FG%'] if l10 else '-',
            'L10_3P%':     l10['L10_3P%'] if l10 else '-',
            'L10_MIN':     l10['L10_MIN'] if l10 else '-',
            'L10_PRA':     l10['L10_PRA'] if l10 else '-',
            'PTS_DELTA':   round(l10['L10_PTS'] - float(row.get('PTS',0) or 0), 1) if l10 else '-',
            'GTD':         'GTD' if is_gtd(pname, injury_report) else '',
            'SCORE':       inv_score,
            'TIER':        tier_label(inv_score),
            'NOTES':       ' | '.join(inv_notes),
            'GAME':        note,
        })

    out_df = pd.DataFrame(results).sort_values('SCORE', ascending=False)
    out_df.to_csv('parbs_investment_picks.csv', index=False)

    # ── Print report ──────────────────────────────────────────────────────────
    print()
    print('='*115)
    print(f'  PARBS TOP INVESTMENT PICKS  |  {date.today().strftime("%A %B %d, %Y")}')
    print(f'  {len(out_df)} players scored  |  Ranked by investment score (0-100)')
    print('='*115)

    tiers = ['ELITE','STRONG','SOLID','LEAN']
    for t in tiers:
        tier_df = out_df[out_df['TIER'] == t]
        if tier_df.empty:
            continue
        print(f'\n  ── {t} ({len(tier_df)} players) ──')
        print('  ' + 'PLAYER'.ljust(24) + 'TEAM'.ljust(5) + 'OPP'.ljust(5) +
              'DRTG'.ljust(7) + 'SSN'.ljust(7) + 'L10'.ljust(7) + 'DELTA'.ljust(8) +
              'L10PRA'.ljust(8) + 'FG%S'.ljust(7) + 'FG%L'.ljust(7) +
              'GTD'.ljust(5) + 'SCORE'.ljust(7) + 'CONTEXT')
        print('  ' + '-'*110)
        for _, r in tier_df.iterrows():
            delta = ('+' if str(r['PTS_DELTA']) != '-' and float(str(r['PTS_DELTA'])) > 0 else '') + str(r['PTS_DELTA']) if r['PTS_DELTA'] != '-' else '-'
            print('  ' +
                  str(r['PLAYER']).ljust(24) +
                  str(r['TEAM']).ljust(5) +
                  str(r['OPP']).ljust(5) +
                  str(r['OPP_DRTG']).ljust(7) +
                  str(r['SSN_PTS']).ljust(7) +
                  str(r['L10_PTS']).ljust(7) +
                  str(delta).ljust(8) +
                  str(r['L10_PRA']).ljust(8) +
                  str(r['SSN_FG%']).ljust(7) +
                  str(r['L10_FG%']).ljust(7) +
                  str(r['GTD']).ljust(5) +
                  str(r['SCORE']).ljust(7) +
                  str(r['NOTES'])[:55])

    print()
    print('  SCORE: 78+ = ELITE | 65+ = STRONG | 52+ = SOLID | 40+ = LEAN')
    print('  DELTA = L10 minus season avg. Negative = COLD (regression UP likely).')
    print('  Saved → parbs_investment_picks.csv')
    print('='*115)
