import pandas as pd

MULT = 1.08

df = pd.read_csv('tor_cle_g2_l10.csv')

G1 = {
    'Donovan Mitchell':   {'pts':32,'reb':3,'ast':4,'min':31},
    'James Harden':       {'pts':22,'reb':2,'ast':10,'min':33},
    'Evan Mobley':        {'pts':17,'reb':7,'ast':4,'min':33},
    'Jarrett Allen':      {'pts':10,'reb':7,'ast':0,'min':28},
    'Max Strus':          {'pts':24,'reb':3,'ast':0,'min':24},
    'Brandon Ingram':     {'pts':17,'reb':2,'ast':4,'min':36},
    'RJ Barrett':         {'pts':24,'reb':2,'ast':3,'min':31},
    'Scottie Barnes':     {'pts':21,'reb':1,'ast':7,'min':32},
    'Jamal Shead':        {'pts':17,'reb':1,'ast':2,'min':28},
    'Jakob Poeltl':       {'pts':4,'reb':6,'ast':2,'min':21},
    'Immanuel Quickley':  {'pts':0,'reb':0,'ast':0,'min':0},
}

PLAYS = [
    ('Donovan Mitchell',  'PTS', 27.5),
    ('Donovan Mitchell',  'PRA', 38.5),
    ('James Harden',      'AST',  8.5),
    ('James Harden',      'PTS', 19.5),
    ('Evan Mobley',       'PTS', 17.5),
    ('Jarrett Allen',     'PTS', 13.5),
    ('Max Strus',         'PTS', 17.5),
    ('Brandon Ingram',    'PTS', 21.5),
    ('RJ Barrett',        'PTS', 21.5),
    ('Scottie Barnes',    'PRA', 28.5),
    ('Jakob Poeltl',      'PTS',  8.5),
    ('Immanuel Quickley', 'PTS', 11.5),
]

REASONS = {
    ('Donovan Mitchell','PTS'):  'RTM DOWN — 32 in G1 above his 26.0 L10. CLE doesnt need 30+ to win.',
    ('Donovan Mitchell','PRA'):  'G1 PRA was 39. L10 PRA 35.4. Line priced off G1 outlier.',
    ('James Harden','AST'):      '10 ast in G1. L10 avg 7.6. TOR has no answer for his playmaking.',
    ('James Harden','PTS'):      '22 in G1. L10 avg 19.9. Line 19.5 is right at his mean.',
    ('Evan Mobley','PTS'):       '17 in G1 in 33min. L10 17.6. TOR has no center matchup.',
    ('Jarrett Allen','PTS'):     'Only 10 in G1 but L10 avg 18.0. Massive regression up expected.',
    ('Max Strus','PTS'):         '24 in G1 was outlier — L10 avg 10.4. RTM down hard.',
    ('Brandon Ingram','PTS'):    '17 in G1 on 9 shots. CLE will scheme him off ball again.',
    ('RJ Barrett','PTS'):        '24 in G1. L10 avg 20.2. Playoff usage elevated.',
    ('Scottie Barnes','PRA'):    '29 PRA in G1. L10 PRA 29.7. On mean, slight over.',
    ('Jakob Poeltl','PTS'):      'Only 4 in G1 but L10 avg 12.0. Massive regression up.',
    ('Immanuel Quickley','PTS'): 'GTD (hamstring). If active: L10 avg 11.4, line 11.5 is fair.',
}

def get_row(name):
    r = df[df['Player'] == name]
    return r.iloc[0] if not r.empty else None

def project(name, prop):
    r = get_row(name)
    if r is None: return None, None
    sp  = float(r['SSN_PTS']); sr = float(r['SSN_REB']); sa = float(r['SSN_AST'])
    lp  = float(r['L10_PTS']); lr = float(r['L10_REB']); la = float(r['L10_AST'])
    lpra= float(r['L10_PRA'])
    pp  = round((lp*0.6 + sp*0.4)*MULT, 1)
    pr  = round((lr*0.6 + sr*0.4)*MULT, 1)
    pa  = round((la*0.6 + sa*0.4)*MULT, 1)
    ppra= round(pp+pr+pa, 1)
    delta = round(lp - sp, 1)
    if prop == 'PTS': return pp, delta
    if prop == 'REB': return pr, delta
    if prop == 'AST': return pa, delta
    if prop == 'PRA': return ppra, delta
    return None, None

def conf(edge, line):
    p = abs(edge)/line if line > 0 else 0
    if p >= 0.12: return 'ELITE  🔥🔥'
    if p >= 0.07: return 'STRONG 🔥'
    if p >= 0.04: return 'SOLID  ✅'
    return 'LEAN   📋'

print()
print('='*110)
print('  TOR @ CLE  —  GAME 2  |  Monday April 20, 2026  |  7:00 PM EDT  |  CLE -9.5')
print('  CLE WON GAME 1: 126-113')
print('  Quickley GTD (hamstring) for TOR')
print('='*110)

print()
print('  GAME 1 BOX + SEASON vs L10 CONTEXT')
print()
print('  ' + 'PLAYER'.ljust(22) + 'TEAM'.ljust(5) +
      'G1 PTS'.ljust(9) + 'G1 REB'.ljust(9) + 'G1 AST'.ljust(9) + 'G1 MIN'.ljust(9) +
      'SSN PTS'.ljust(9) + 'L10 PTS'.ljust(9) + 'DELTA'.ljust(8) +
      'L10 REB'.ljust(9) + 'L10 AST'.ljust(9) + 'L10 FG%')
print('  ' + '-'*107)
for name, g1 in G1.items():
    r = get_row(name)
    if r is None: continue
    sp  = float(r['SSN_PTS']); lp = float(r['L10_PTS'])
    lr  = float(r['L10_REB']); la = float(r['L10_AST'])
    lfg = float(r['L10_FG%'])
    delta = round(lp - sp, 1)
    ds = ('+' if delta > 0 else '') + str(delta)
    team = r['Team']
    g1_note = '(GTD)' if name == 'Immanuel Quickley' else ''
    print('  ' + (name+g1_note).ljust(22) + team.ljust(5) +
          str(g1['pts']).ljust(9) + str(g1['reb']).ljust(9) +
          str(g1['ast']).ljust(9) + str(g1['min']).ljust(9) +
          str(round(sp,1)).ljust(9) + str(round(lp,1)).ljust(9) +
          ds.ljust(8) + str(round(lr,1)).ljust(9) +
          str(round(la,1)).ljust(9) + str(round(lfg,3)))

print()
print('='*110)
print('  GAME 2 EXACT PLAYS  |  Proj = 60% L10 + 40% Season + 8% playoff multiplier')
print('='*110)
print()
print('  ' + 'PLAYER'.ljust(22) + 'PROP'.ljust(6) + 'LINE'.ljust(7) + 'PROJ'.ljust(7) +
      'PLAY'.ljust(8) + 'EDGE'.ljust(7) + 'CONF'.ljust(14) + 'REASONING')
print('  ' + '-'*105)

all_plays = []
for name, prop, line in PLAYS:
    p, delta = project(name, prop)
    if p is None:
        print('  ' + name.ljust(22) + prop.ljust(6) + str(line).ljust(7) + 'N/A')
        continue
    edge = round(p - line, 1)
    direction = 'OVER' if edge > 0 else 'UNDER'
    c = conf(edge, line)
    es = ('+' if edge > 0 else '') + str(edge)
    reason = REASONS.get((name, prop), '')
    print('  ' + name.ljust(22) + prop.ljust(6) + str(line).ljust(7) + str(p).ljust(7) +
          direction.ljust(8) + es.ljust(7) + c.ljust(14) + reason[:65])
    tier = c.split()[0]
    all_plays.append((tier, abs(edge)/line if line > 0 else 0, name, prop, line, p, direction, edge, reason))

print()
print('='*110)
print('  TOP PLAYS — RANKED BY CONVICTION')
print('='*110)
tier_order = {'ELITE':0,'STRONG':1,'SOLID':2,'LEAN':3}
all_plays.sort(key=lambda x: (tier_order.get(x[0],9), -x[1]))
emojis = {'ELITE':'🔥🔥','STRONG':'🔥','SOLID':'✅','LEAN':'📋'}
rank = 1
for tier, pct, name, prop, line, p, direction, edge, reason in all_plays:
    if tier in ('ELITE','STRONG','SOLID'):
        e = emojis.get(tier,'')
        es = ('+' if edge > 0 else '') + str(edge)
        print(f'  {rank}. {e} {tier}  {name} {prop} {direction} {line}  |  Proj: {p}  |  Edge: {es}')
        print(f'     {reason}')
        print()
        rank += 1

print('  LEAN / SKIP:')
for tier, pct, name, prop, line, p, direction, edge, reason in all_plays:
    if tier == 'LEAN':
        es = ('+' if edge > 0 else '') + str(edge)
        print(f'  📋 {name} {prop} {direction} {line}  |  Proj: {p}  |  Edge: {es}')

print()
print('  PARLAY: Mitchell PTS UNDER 27.5 + Strus PTS UNDER 17.5 + Poeltl PTS OVER 8.5')
print('  (All 3 are RTM plays — G1 outliers correcting back to mean)')
print('='*110)
