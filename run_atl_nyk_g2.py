import pandas as pd

MULT = 1.08

df = pd.read_csv('atl_nyk_g2_l10.csv')

G1 = {
    'Jalen Brunson':            {'pts':28,'reb':5,'ast':7,'min':36},
    'Karl-Anthony Towns':       {'pts':25,'reb':8,'ast':4,'min':33},
    'OG Anunoby':               {'pts':18,'reb':8,'ast':0,'min':38},
    'Mikal Bridges':            {'pts':11,'reb':2,'ast':1,'min':32},
    'Josh Hart':                {'pts':11,'reb':14,'ast':5,'min':37},
    'Jalen Johnson':            {'pts':23,'reb':7,'ast':3,'min':39},
    'CJ McCollum':              {'pts':26,'reb':3,'ast':1,'min':34},
    'Nickeil Alexander-Walker': {'pts':17,'reb':1,'ast':4,'min':39},
    'Dyson Daniels':            {'pts':4,'reb':9,'ast':11,'min':36},
    'Onyeka Okongwu':           {'pts':19,'reb':8,'ast':2,'min':37},
    'Jonathan Kuminga':         {'pts':8,'reb':4,'ast':1,'min':27},
}

# Lines sourced from DraftKings/FanDuel/SportsBettingDime/Covers
PLAYS = [
    # NYK
    ('Jalen Brunson',           'PTS', 26.5),
    ('Jalen Brunson',           'AST',  7.5),
    ('Karl-Anthony Towns',      'PTS', 21.5),
    ('Karl-Anthony Towns',      'REB', 12.5),
    ('OG Anunoby',              'PTS', 16.5),
    ('Mikal Bridges',           'PTS', 14.5),
    ('Josh Hart',               'REB', 10.5),
    # ATL
    ('Jalen Johnson',           'PTS', 21.5),
    ('Jalen Johnson',           'PRA', 33.5),
    ('CJ McCollum',             'PTS', 22.5),
    ('Nickeil Alexander-Walker','PTS', 19.5),
    ('Dyson Daniels',           'AST',  5.5),
    ('Dyson Daniels',           'REB',  7.5),
    ('Onyeka Okongwu',          'PTS', 13.5),
]

REASONS = {
    ('Jalen Brunson','PTS'):           '28 in G1. L10 avg 24.3 COLD. Line 26.5 — slight over but RTM risk.',
    ('Jalen Brunson','AST'):           '7 ast in G1. L10 avg 8.0. ATL cant stop his penetration.',
    ('Karl-Anthony Towns','PTS'):      '25 in G1. L10 avg 20.2. Line 21.5 is right at his mean.',
    ('Karl-Anthony Towns','REB'):      '8 reb in G1. L10 avg 11.9. Line 12.5 — G1 was below his mean.',
    ('OG Anunoby','PTS'):              '18 in G1. L10 avg 15.8 COLD. Line 16.5 — slight over.',
    ('Mikal Bridges','PTS'):           '11 in G1. L10 avg 12.4. Line 14.5 — model says UNDER.',
    ('Josh Hart','REB'):               '14 reb in G1 outlier. L10 avg 5.9. Line 10.5 — RTM DOWN hard.',
    ('Jalen Johnson','PTS'):           '23 in G1. L10 avg 20.3. Line 21.5 — on mean, slight over.',
    ('Jalen Johnson','PRA'):           '33 PRA in G1. L10 PRA 35.7. Line 33.5 — on mean.',
    ('CJ McCollum','PTS'):             '26 in G1 outlier. L10 avg 19.1. Line 22.5 — RTM DOWN.',
    ('Nickeil Alexander-Walker','PTS'):'17 in G1. L10 avg 24.3 HOT. Line 19.5 — OVER.',
    ('Dyson Daniels','AST'):           '11 ast in G1. L10 avg 5.5. Line 5.5 — OVER, consistent facilitator.',
    ('Dyson Daniels','REB'):           '9 reb in G1. L10 avg 8.2. Line 7.5 — OVER.',
    ('Onyeka Okongwu','PTS'):          '19 in G1 outlier. L10 avg 12.4. Line 13.5 — RTM DOWN.',
}

def get_row(name):
    r = df[df['Player'] == name]
    return r.iloc[0] if not r.empty else None

def project(name, prop):
    r = get_row(name)
    if r is None: return None, None
    sp=float(r['SSN_PTS']); sr=float(r['SSN_REB']); sa=float(r['SSN_AST'])
    lp=float(r['L10_PTS']); lr=float(r['L10_REB']); la=float(r['L10_AST'])
    lpra=float(r['L10_PRA'])
    pp=round((lp*0.6+sp*0.4)*MULT,1)
    pr=round((lr*0.6+sr*0.4)*MULT,1)
    pa=round((la*0.6+sa*0.4)*MULT,1)
    ppra=round(pp+pr+pa,1)
    delta=round(lp-sp,1)
    if prop=='PTS': return pp, delta
    if prop=='REB': return pr, delta
    if prop=='AST': return pa, delta
    if prop=='PRA': return ppra, delta
    return None, None

def conf(edge, line):
    p = abs(edge)/line if line > 0 else 0
    if p >= 0.12: return 'ELITE  🔥🔥'
    if p >= 0.07: return 'STRONG 🔥'
    if p >= 0.04: return 'SOLID  ✅'
    return 'LEAN   📋'

print()
print('='*112)
print('  ATL @ NYK  —  GAME 2  |  Monday April 20, 2026  |  8:00 PM EDT  |  NYK -5.5')
print('  NYK WON GAME 1: 113-102  |  Brunson 28, KAT 25, OG 18 | ATL: McCollum 26, Johnson 23, Okongwu 19')
print('='*112)

print()
print('  GAME 1 BOX + SEASON vs L10 CONTEXT')
print()
print('  ' + 'PLAYER'.ljust(26) + 'TEAM'.ljust(5) +
      'G1 PTS'.ljust(8) + 'G1 REB'.ljust(8) + 'G1 AST'.ljust(8) + 'G1 MIN'.ljust(8) +
      'SSN PTS'.ljust(9) + 'L10 PTS'.ljust(9) + 'DELTA'.ljust(8) +
      'L10 REB'.ljust(9) + 'L10 AST'.ljust(9) + 'L10 FG%')
print('  ' + '-'*110)
for name, g1 in G1.items():
    r = get_row(name)
    if r is None: continue
    sp=float(r['SSN_PTS']); lp=float(r['L10_PTS'])
    lr=float(r['L10_REB']); la=float(r['L10_AST']); lfg=float(r['L10_FG%'])
    delta=round(lp-sp,1)
    ds=('+' if delta>0 else '')+str(delta)
    print('  ' + name.ljust(26) + r['Team'].ljust(5) +
          str(g1['pts']).ljust(8) + str(g1['reb']).ljust(8) +
          str(g1['ast']).ljust(8) + str(g1['min']).ljust(8) +
          str(round(sp,1)).ljust(9) + str(round(lp,1)).ljust(9) +
          ds.ljust(8) + str(round(lr,1)).ljust(9) +
          str(round(la,1)).ljust(9) + str(round(lfg,3)))

print()
print('='*112)
print('  GAME 2 EXACT PLAYS  |  Proj = 60% L10 + 40% Season + 8% playoff multiplier')
print('='*112)
print()
print('  ' + 'PLAYER'.ljust(26) + 'PROP'.ljust(6) + 'LINE'.ljust(7) + 'PROJ'.ljust(7) +
      'PLAY'.ljust(8) + 'EDGE'.ljust(7) + 'CONF'.ljust(14) + 'REASONING')
print('  ' + '-'*108)

all_plays = []
for name, prop, line in PLAYS:
    p, delta = project(name, prop)
    if p is None:
        print('  ' + name.ljust(26) + prop.ljust(6) + str(line).ljust(7) + 'N/A')
        continue
    edge = round(p - line, 1)
    direction = 'OVER' if edge > 0 else 'UNDER'
    c = conf(edge, line)
    es = ('+' if edge>0 else '')+str(edge)
    reason = REASONS.get((name, prop), '')
    print('  ' + name.ljust(26) + prop.ljust(6) + str(line).ljust(7) + str(p).ljust(7) +
          direction.ljust(8) + es.ljust(7) + c.ljust(14) + reason[:68])
    tier = c.split()[0]
    all_plays.append((tier, abs(edge)/line if line>0 else 0, name, prop, line, p, direction, edge, reason))

print()
print('='*112)
print('  TOP PLAYS — RANKED BY CONVICTION')
print('='*112)
tier_order = {'ELITE':0,'STRONG':1,'SOLID':2,'LEAN':3}
all_plays.sort(key=lambda x: (tier_order.get(x[0],9), -x[1]))
emojis = {'ELITE':'🔥🔥','STRONG':'🔥','SOLID':'✅','LEAN':'📋'}
rank = 1
for tier, pct, name, prop, line, p, direction, edge, reason in all_plays:
    if tier in ('ELITE','STRONG','SOLID'):
        e = emojis.get(tier,'')
        es = ('+' if edge>0 else '')+str(edge)
        print(f'  {rank}. {e} {tier}  {name} {prop} {direction} {line}  |  Proj: {p}  |  Edge: {es}')
        print(f'     {reason}')
        print()
        rank += 1

print('  LEAN / SKIP:')
for tier, pct, name, prop, line, p, direction, edge, reason in all_plays:
    if tier == 'LEAN':
        es = ('+' if edge>0 else '')+str(edge)
        print(f'  📋 {name} {prop} {direction} {line}  |  Proj: {p}  |  Edge: {es}  |  {reason[:60]}')

print()
print('  PARLAY: Josh Hart REB UNDER 10.5 + CJ McCollum PTS UNDER 22.5 + Okongwu PTS UNDER 13.5')
print('  (All 3 are RTM plays — G1 outliers correcting back to mean)')
print('='*112)
