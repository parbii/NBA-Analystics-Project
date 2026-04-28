"""
hit_rate_audit.py
=================
Scores every prop pick made in this chat against actual results.
"""
import json

with open('game_results.json') as f:
    results = json.load(f)

def get_stat(game, player, stat):
    """Return actual stat value for a player in a game."""
    game_data = results.get(game, {})
    # Try exact match first
    if player in game_data:
        return game_data[player].get(stat)
    # Fuzzy: last name match
    last = player.split()[-1].lower()
    for name, stats in game_data.items():
        if name.split()[-1].lower() == last:
            return stats.get(stat)
    return None

def check(game, player, prop, line, direction, proj, conf_tier):
    actual = get_stat(game, player, prop)
    if actual is None:
        return None, None, None
    hit = (actual > line) if direction == 'OVER' else (actual < line)
    return hit, actual, round(actual - line, 1)

# ── All picks from this chat ──────────────────────────────────────────────────
# Format: (game_key, player, prop, line, direction, our_proj, conf_tier)
PICKS = [
    # ── Apr 17 Play-In: CHO @ ORL ────────────────────────────────────────────
    ('Apr 17 CHO@ORL Play-In', 'Paolo Banchero',  'pts', 22.5, 'OVER',  23.3, 'HIGH'),
    ('Apr 17 CHO@ORL Play-In', 'Paolo Banchero',  'pra', 23.5, 'OVER',  33.5, 'ELITE'),
    ('Apr 17 CHO@ORL Play-In', 'Franz Wagner',    'pra', 24.5, 'UNDER', 21.0, 'SOLID'),

    # ── Apr 17 Play-In: GSW @ PHX ────────────────────────────────────────────
    ('Apr 17 POR@PHX Play-In', 'Stephen Curry',   'pts', 27.5, 'UNDER', 23.4, 'STRONG'),
    ('Apr 17 POR@PHX Play-In', 'Stephen Curry',   'pts', 4.5,  'OVER',  4.2,  'SOLID'),   # 3PM — using pts as proxy
    ('Apr 17 POR@PHX Play-In', 'Jalen Green',     'pts', 18.5, 'OVER',  19.0, 'STRONG'),
    ('Apr 17 POR@PHX Play-In', 'Devin Booker',    'pra', 34.5, 'OVER',  38.0, 'ELITE'),
    ('Apr 17 POR@PHX Play-In', 'Dillon Brooks',   'pts', 17.5, 'UNDER', 16.6, 'SOLID'),

    # ── Apr 18 G1: TOR @ CLE ─────────────────────────────────────────────────
    ('Apr 18 TOR@CLE G1', 'Donovan Mitchell', 'pts', 27.5, 'OVER',  28.9, 'SOLID'),
    ('Apr 18 TOR@CLE G1', 'Brandon Ingram',   'pts', 20.5, 'OVER',  21.8, 'SOLID'),
    ('Apr 18 TOR@CLE G1', 'Evan Mobley',      'pra', 28.5, 'OVER',  33.2, 'ELITE'),
    ('Apr 18 TOR@CLE G1', 'James Harden',     'ast',  7.5, 'OVER',   8.3, 'STRONG'),

    # ── Apr 18 G1: MIN @ DEN ─────────────────────────────────────────────────
    ('Apr 18 MIN@DEN G1', 'Nikola Jokic',      'pra', 51.5, 'OVER',  55.7, 'STRONG'),
    ('Apr 18 MIN@DEN G1', 'Cameron Johnson',   'pts', 12.5, 'OVER',  14.3, 'ELITE'),
    ('Apr 18 MIN@DEN G1', 'Jaden McDaniels',   'pts', 14.5, 'OVER',  16.4, 'ELITE'),

    # ── Apr 18 G1: ATL @ NYK ─────────────────────────────────────────────────
    ('Apr 18 ATL@NYK G1', 'Jalen Brunson',     'pts', 27.5, 'OVER',  27.0, 'LEAN'),
    ('Apr 18 ATL@NYK G1', 'Mikal Bridges',     'pts', 12.5, 'OVER',  14.3, 'ELITE'),
    ('Apr 18 ATL@NYK G1', 'OG Anunoby',        'pts', 16.5, 'OVER',  17.5, 'SOLID'),

    # ── Apr 18 G1: HOU @ LAL ─────────────────────────────────────────────────
    ('Apr 18 HOU@LAL G1', 'Kevin Durant',      'pts', 24.5, 'OVER',  28.3, 'ELITE'),
    ('Apr 18 HOU@LAL G1', 'LeBron James',      'pts', 25.5, 'UNDER', 21.9, 'ELITE'),
    ('Apr 18 HOU@LAL G1', 'Alperen Sengun',    'pra', 28.5, 'OVER',  37.8, 'ELITE'),
    ('Apr 18 HOU@LAL G1', 'Amen Thompson',     'pra', 22.5, 'OVER',  35.2, 'ELITE'),

    # ── Apr 20 G2: TOR @ CLE ─────────────────────────────────────────────────
    ('Apr 20 TOR@CLE G2', 'Jakob Poeltl',      'pts',  8.5, 'OVER',  12.6, 'ELITE'),
    ('Apr 20 TOR@CLE G2', 'Max Strus',         'pts', 17.5, 'UNDER', 12.1, 'ELITE'),
    ('Apr 20 TOR@CLE G2', 'Jarrett Allen',     'pts', 13.5, 'OVER',  17.4, 'ELITE'),
    ('Apr 20 TOR@CLE G2', 'Scottie Barnes',    'pra', 28.5, 'OVER',  34.0, 'ELITE'),
    ('Apr 20 TOR@CLE G2', 'James Harden',      'pts', 19.5, 'OVER',  21.8, 'STRONG'),
    ('Apr 20 TOR@CLE G2', 'Evan Mobley',       'pts', 17.5, 'OVER',  19.2, 'STRONG'),
    ('Apr 20 TOR@CLE G2', 'Donovan Mitchell',  'pts', 27.5, 'OVER',  28.9, 'SOLID'),

    # ── Apr 20 G2: ATL @ NYK ─────────────────────────────────────────────────
    ('Apr 20 ATL@NYK G2', 'Josh Hart',         'reb', 10.5, 'UNDER',  7.5, 'ELITE'),
    ('Apr 20 ATL@NYK G2', 'Nickeil Alexander-Walker', 'pts', 19.5, 'OVER', 24.8, 'ELITE'),
    ('Apr 20 ATL@NYK G2', 'Jalen Johnson',     'pra', 33.5, 'OVER',  38.5, 'ELITE'),
    ('Apr 20 ATL@NYK G2', 'Jalen Brunson',     'ast',  7.5, 'OVER',   8.5, 'ELITE'),
    ('Apr 20 ATL@NYK G2', 'Dyson Daniels',     'ast',  5.5, 'OVER',   6.1, 'STRONG'),
    ('Apr 20 ATL@NYK G2', 'Dyson Daniels',     'reb',  7.5, 'OVER',   8.3, 'STRONG'),
    ('Apr 20 ATL@NYK G2', 'CJ McCollum',       'pts', 22.5, 'UNDER', 20.4, 'STRONG'),
    ('Apr 20 ATL@NYK G2', 'Jalen Johnson',     'pts', 21.5, 'OVER',  22.9, 'SOLID'),
    ('Apr 20 ATL@NYK G2', 'Karl-Anthony Towns','reb', 12.5, 'OVER',  13.3, 'SOLID'),
    ('Apr 20 ATL@NYK G2', 'OG Anunoby',        'pts', 16.5, 'OVER',  17.5, 'SOLID'),
]

TIER_ORDER = ['ELITE', 'STRONG', 'SOLID', 'LEAN', 'HIGH']

print()
print('='*110)
print('  PARBS PICKS — FULL HIT RATE AUDIT')
print('  Every prop pick made in this chat vs actual results')
print('='*110)

rows = []
no_data = []

for game, player, prop, line, direction, proj, tier in PICKS:
    hit, actual, diff = check(game, player, prop, line, direction, proj, tier)
    if hit is None:
        no_data.append((game, player, prop, line, direction, proj, tier))
        continue
    result = 'HIT  ✅' if hit else 'MISS ❌'
    diff_str = ('+' if diff > 0 else '') + str(diff)
    rows.append({
        'game': game, 'player': player, 'prop': prop.upper(),
        'line': line, 'direction': direction, 'proj': proj,
        'actual': actual, 'diff': diff, 'hit': hit,
        'result': result, 'tier': tier,
    })

# Print full table
print()
print('  ' + 'PLAYER'.ljust(26) + 'PROP'.ljust(6) + 'LINE'.ljust(7) + 'PROJ'.ljust(7) +
      'ACTUAL'.ljust(9) + 'PLAY'.ljust(8) + 'RESULT'.ljust(10) + 'TIER'.ljust(8) + 'GAME')
print('  ' + '-'*105)

for r in rows:
    diff_str = ('+' if r['diff'] > 0 else '') + str(r['diff'])
    print('  ' + r['player'].ljust(26) + r['prop'].ljust(6) +
          str(r['line']).ljust(7) + str(r['proj']).ljust(7) +
          str(r['actual']).ljust(9) + r['direction'].ljust(8) +
          r['result'].ljust(10) + r['tier'].ljust(8) +
          r['game'])

# ── Summary stats ─────────────────────────────────────────────────────────────
total = len(rows)
hits  = sum(1 for r in rows if r['hit'])
misses = total - hits

print()
print('='*110)
print(f'  OVERALL: {hits}/{total} — {round(hits/total*100,1)}% hit rate')
print('='*110)

# By tier
print()
print('  BY CONFIDENCE TIER:')
print('  ' + '-'*50)
for tier in TIER_ORDER:
    tier_rows = [r for r in rows if r['tier'] == tier]
    if not tier_rows: continue
    t_hits = sum(1 for r in tier_rows if r['hit'])
    pct = round(t_hits/len(tier_rows)*100, 1)
    bar = '█' * int(pct/5) + '░' * (20 - int(pct/5))
    print(f'  {tier:<8} {t_hits}/{len(tier_rows)}  {pct:>5}%  {bar}')

# By prop type
print()
print('  BY PROP TYPE:')
print('  ' + '-'*50)
for prop in ['PTS','REB','AST','PRA']:
    prop_rows = [r for r in rows if r['prop'] == prop]
    if not prop_rows: continue
    p_hits = sum(1 for r in prop_rows if r['hit'])
    pct = round(p_hits/len(prop_rows)*100, 1)
    print(f'  {prop:<6} {p_hits}/{len(prop_rows)}  {pct:>5}%')

# By direction
print()
print('  BY DIRECTION:')
print('  ' + '-'*50)
for direction in ['OVER','UNDER']:
    d_rows = [r for r in rows if r['direction'] == direction]
    if not d_rows: continue
    d_hits = sum(1 for r in d_rows if r['hit'])
    pct = round(d_hits/len(d_rows)*100, 1)
    print(f'  {direction:<8} {d_hits}/{len(d_rows)}  {pct:>5}%')

# Misses breakdown
misses_list = [r for r in rows if not r['hit']]
if misses_list:
    print()
    print('  MISSES:')
    print('  ' + '-'*80)
    for r in misses_list:
        diff_str = ('+' if r['diff'] > 0 else '') + str(r['diff'])
        player = r['player']; prop = r['prop']; direction = r['direction']
        line = r['line']; actual = r['actual']; tier = r['tier']; game = r['game']
        print(f'  ❌ {player:<26} {prop:<5} {direction} {line}  '
              f'Actual: {actual}  ({diff_str})  [{tier}]  {game}')

if no_data:
    print()
    print(f'  NOTE: {len(no_data)} picks had no box score data (game not yet played or player DNP):')
    for game, player, prop, line, direction, proj, tier in no_data:
        print(f'    {player} {prop.upper()} {direction} {line} — {game}')

print()
print('='*110)
