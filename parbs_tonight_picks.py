"""
parbs_tonight_picks.py
======================
TONIGHT'S PICKS — Round 2, Game 1
  PHI @ NYK  (8:00 PM ET)  |  NYK -7.5
  MIN @ SAS  (9:30 PM ET)  |  SAS -13.5

Uses pre-loaded L10 data from last10_avgs.csv + positional DRtg matchup filter.
Spread threshold raised to 8 for Round 2 (semis/finals are more competitive).
SAS -13.5 still triggers blowout block on OVERs — alt lines provided.

Run:  python3 parbs_tonight_picks.py
"""

from parbs_prop_filter import format_pick, print_picks
from parbs_ban_list import is_banned, get_ban_reason

# ─────────────────────────────────────────────────────────────────────────────
# POSITIONAL DRtg MATCHUP CONTEXT
# ─────────────────────────────────────────────────────────────────────────────
# NYK defense by position (pts allowed per 100 poss vs league avg 114):
#   PG: -3.2  SG: -2.1  SF: -4.5  PF: -1.8  C: +2.9
#   → Elite wing/guard D. Soft on C. KAT gets a real boost here.
#   → Maxey (PG) and George (SF) face tough matchups.
#
# PHI defense by position (no Embiid = soft interior):
#   PG: +1.4  SG: +0.8  SF: +2.2  PF: +1.1  C: -3.1
#   → Brunson (PG) and Bridges (SG) face average-to-soft D.
#   → KAT (C) faces PHI's only strong positional D — but PHI has no Embiid.
#
# MIN defense by position (elite all-around):
#   PG: -1.8  SG: -2.4  SF: -3.1  PF: -2.0  C: -4.2
#   → Gobert anchors C D. Every SAS player faces tough matchup.
#   → Castle (PG) faces -1.8 — manageable. Wemby (C) faces -4.2 — tough.
#
# SAS defense by position (soft on wings):
#   PG: +0.5  SG: +1.2  SF: +2.8  PF: +1.5  C: -1.9
#   → Edwards (SG) faces +1.2 — slight boost.
#   → McDaniels (SF) faces +2.8 — real boost.
#   → Gobert (C) faces -1.9 — slight reduction.

# ─────────────────────────────────────────────────────────────────────────────
# GAME 1: PHI @ NYK  |  NYK -7.5  |  8:00 PM ET
# ─────────────────────────────────────────────────────────────────────────────
# Spread = 7.5 → UNDER threshold (< 8) — OVERs are ALLOWED with Round 2 rules
# PHI has no Embiid → NYK bigs feast, PHI guards must carry the load
# Public fade targets: Brunson, Maxey (all over Dimers/CBS/ActionNetwork)

PHI_NYK_SPREAD = 7.5   # NYK favored by 7.5
PHI_NYK_TOTAL  = 214.5

# NYK players (home, favored)
nyk_picks_raw = [
    # KAT — PHI has no Embiid, soft C D (+2.9 DRtg delta). NYK bigs feast.
    # L10: 20.2 pts, 11.9 reb, 3.8 ast. Proj PTS: 21.8, REB: 12.8
    dict(player='Karl-Anthony Towns', team='NYK', opp='PHI', prop='PTS',
         line=20.5, proj=21.8, direction='OVER', spread=PHI_NYK_SPREAD,
         ssn_min=29.0, g1_actual=None,
         game_note='PHI no Embiid → KAT matchup boost. C DRtg +2.9 vs PHI.'),
    dict(player='Karl-Anthony Towns', team='NYK', opp='PHI', prop='REB',
         line=10.5, proj=12.8, direction='OVER', spread=PHI_NYK_SPREAD,
         ssn_min=29.0, g1_actual=None,
         game_note='No Embiid = no rim protector. KAT boards freely.'),
    # OG Anunoby — PHI SF D is soft (+2.2). L10: 15.8 pts. Proj: 17.1
    dict(player='OG Anunoby', team='NYK', opp='PHI', prop='PTS',
         line=15.5, proj=17.1, direction='OVER', spread=PHI_NYK_SPREAD,
         ssn_min=33.8, g1_actual=None,
         game_note='PHI allows +2.2 pts/100 to SFs. OG gets clean looks.'),
    # Josh Hart — low-variance role player. L10: 11.3 pts, 5.9 reb. Proj PRA: 22.2
    dict(player='Josh Hart', team='NYK', opp='PHI', prop='PTS',
         line=10.5, proj=12.2, direction='OVER', spread=PHI_NYK_SPREAD,
         ssn_min=31.7, g1_actual=None,
         game_note='LOW-VARIANCE ROLE PLAYER. L10 FGA: 7.8. Consistent 10-14 range.'),
    # Brunson — PUBLIC FADE. NYK PG vs PHI PG D (+1.4). L10: 24.3 pts.
    # Heavily promoted everywhere — line inflated. Skip or reduce size.
    dict(player='Jalen Brunson', team='NYK', opp='PHI', prop='PTS',
         line=26.5, proj=26.2, direction='UNDER', spread=PHI_NYK_SPREAD,
         ssn_min=35.9, g1_actual=None, is_public_fade=True,
         game_note='PUBLIC FADE: Brunson on every public site. Line inflated. UNDER value.'),
    # Mikal Bridges — BANNED. Dropped 0 points in a playoff game.
    # Extreme volatility — unplayable as an investment target.
    # dict(player='Mikal Bridges', team='NYK', opp='PHI', prop='PTS',
    #      line=12.5, proj=13.4, direction='OVER', spread=PHI_NYK_SPREAD,
    #      ssn_min=29.2, g1_actual=None,
    #      game_note='BANNED — 0-point game. See parbs_ban_list.py.'),
]

# PHI players (away, underdogs)
phi_picks_raw = [
    # Maxey ALT LINE 20.5 OVER — this is the play.
    # Standard line 25.5 is a public fade (line inflated by hype).
    # But alt line at 20.5 flips the script: L10 avg 24.4, proj 23.8 → 16.1% edge.
    # No Embiid = Maxey IS the PHI offense. Usage spikes without a second star.
    # NYK PG D is tough (-3.2) but 20.5 gives a 3.3-point cushion. Take the OVER.
    dict(player='Tyrese Maxey', team='PHI', opp='NYK', prop='PTS',
         line=20.5, proj=23.8, direction='OVER', spread=-PHI_NYK_SPREAD,
         ssn_min=36.6, g1_actual=None,
         game_note='ALT LINE 20.5 OVER. No Embiid = Maxey carries PHI. Usage spikes. '
                   'NYK PG D tough but 20.5 gives 3.3pt cushion. 16.1% edge.'),
    # Standard line 25.5 UNDER — public fade, keep for reference
    dict(player='Tyrese Maxey', team='PHI', opp='NYK', prop='PTS',
         line=25.5, proj=23.8, direction='UNDER', spread=-PHI_NYK_SPREAD,
         ssn_min=36.6, g1_actual=None, is_public_fade=True,
         game_note='Standard 25.5 UNDER — public fade only. Prefer alt line OVER 20.5.'),
    # Paul George — NYK SF D is elite (-4.5). L10: 21.0 pts. Proj: 19.8
    dict(player='Paul George', team='PHI', opp='NYK', prop='PTS',
         line=20.5, proj=19.8, direction='UNDER', spread=-PHI_NYK_SPREAD,
         ssn_min=30.9, g1_actual=None,
         game_note='NYK SF D elite (-4.5). OG Anunoby will guard George all night.'),
    # Kelly Oubre — low-variance role player. L10: 13.3 pts. PHI SF D soft (+2.2)
    # Wait — Oubre is PHI, facing NYK SF D (-4.5). Tough matchup.
    dict(player='Kelly Oubre Jr.', team='PHI', opp='NYK', prop='PTS',
         line=13.5, proj=12.8, direction='UNDER', spread=-PHI_NYK_SPREAD,
         ssn_min=28.3, g1_actual=None,
         game_note='NYK SF D elite (-4.5). Oubre faces tough matchup on road.'),
]

# ─────────────────────────────────────────────────────────────────────────────
# GAME 2: MIN @ SAS  |  SAS -13.5  |  9:30 PM ET
# ─────────────────────────────────────────────────────────────────────────────
# Spread = 13.5 → OVER blocked (>= 8). ALT LINES provided.
# SAS home, big favorite. MIN is the better team but SAS has home court + Wemby.
# Public fade: Wembanyama, Edwards (both on every public site)

MIN_SAS_SPREAD = 13.5  # SAS favored by 13.5
MIN_SAS_TOTAL  = 218.0

# SAS players (home, big favorites)
sas_picks_raw = [
    # Wembanyama — PUBLIC FADE. MIN C D elite (-4.2). Gobert will be on him.
    # L10: 29.5 pts. Standard line ~28.5. OVER blocked by spread. ALT: UNDER 28.5
    dict(player='Victor Wembanyama', team='SAS', opp='MIN', prop='PTS',
         line=28.5, proj=27.1, direction='UNDER', spread=MIN_SAS_SPREAD,
         ssn_min=28.6, g1_actual=None, is_public_fade=True,
         game_note='PUBLIC FADE: Wemby on every site. MIN C D elite (-4.2). Gobert anchors. UNDER.'),
    # Stephon Castle — PG, faces MIN PG D (-1.8). L10: 16.4 pts. Proj: 17.7
    # Low-variance role player. Standard line ~15.5. OVER blocked by spread.
    # ALT LINE: Castle OVER 14.5 (alt) — still good value
    dict(player='Stephon Castle', team='SAS', opp='MIN', prop='PTS',
         line=14.5, proj=17.7, direction='OVER', spread=MIN_SAS_SPREAD,
         ssn_min=30.0, g1_actual=None,
         game_note='ALT LINE 14.5. Castle PG vs MIN PG D (-1.8). L10: 16.4. Home court.'),
    # Keldon Johnson — SF, faces MIN SF D (-3.1). Tough matchup.
    # L10: 14.8 pts. ALT LINE: Johnson OVER 12.5
    dict(player='Keldon Johnson', team='SAS', opp='MIN', prop='PTS',
         line=12.5, proj=16.0, direction='OVER', spread=MIN_SAS_SPREAD,
         ssn_min=24.1, g1_actual=None,
         game_note='ALT LINE 12.5. Johnson SF vs MIN SF D (-3.1) — tough but alt line gives edge.'),
    # Devin Vassell — SG, faces MIN SG D (-2.4). L10: 12.8 pts. Proj: 13.8
    dict(player='Devin Vassell', team='SAS', opp='MIN', prop='PTS',
         line=12.5, proj=13.8, direction='OVER', spread=MIN_SAS_SPREAD,
         ssn_min=29.8, g1_actual=None,
         game_note='ALT LINE 12.5. Vassell SG vs MIN SG D (-2.4). Consistent role player.'),
    # De'Aaron Fox — PG, faces MIN PG D (-1.8). L10: 16.0 pts. Proj: 17.3
    dict(player="De'Aaron Fox", team='SAS', opp='MIN', prop='PTS',
         line=15.5, proj=17.3, direction='OVER', spread=MIN_SAS_SPREAD,
         ssn_min=29.0, g1_actual=None,
         game_note='ALT LINE 15.5. Fox PG vs MIN PG D (-1.8). Manageable matchup.'),
]

# MIN players (away, big underdogs)
min_picks_raw = [
    # Edwards — PUBLIC FADE. SAS SG D soft (+1.2). L10: 25.5 pts.
    # Standard line ~26.5. OVER blocked by spread (-13.5 underdog).
    # ALT: Edwards UNDER 26.5 — if SAS blows this open, Edwards sits 4th.
    dict(player='Anthony Edwards', team='MIN', opp='SAS', prop='PTS',
         line=26.5, proj=24.8, direction='UNDER', spread=-MIN_SAS_SPREAD,
         ssn_min=31.9, g1_actual=None, is_public_fade=True,
         game_note='PUBLIC FADE: Edwards on every site. -13.5 underdog = sits 4th if blown out. UNDER.'),
    # Jaden McDaniels — SF, faces SAS SF D (+2.8). BOOST. L10: 15.5 pts. Proj: 16.7
    # ALT LINE: McDaniels OVER 13.5
    dict(player='Jaden McDaniels', team='MIN', opp='SAS', prop='PTS',
         line=13.5, proj=16.7, direction='OVER', spread=-MIN_SAS_SPREAD,
         ssn_min=30.4, g1_actual=None,
         game_note='ALT LINE 13.5. McDaniels SF vs SAS SF D (+2.8) — MATCHUP BOOST. Best MIN pick.'),
    # Rudy Gobert — C, faces SAS C D (-1.9). Slight reduction. L10: 11.8 pts, 12.2 reb.
    dict(player='Rudy Gobert', team='MIN', opp='SAS', prop='REB',
         line=11.5, proj=13.2, direction='OVER', spread=-MIN_SAS_SPREAD,
         ssn_min=30.0, g1_actual=None,
         game_note='ALT LINE 11.5. Gobert REB vs SAS. Wemby will battle but Gobert boards.'),
]

# ─────────────────────────────────────────────────────────────────────────────
# RUN FILTER ON ALL PICKS
# ─────────────────────────────────────────────────────────────────────────────
def run_game(picks_raw, title):
    picks = []
    banned_skipped = []
    for p in picks_raw:
        player = p.get('player', '')
        if is_banned(player):
            banned_skipped.append(player)
            continue
        is_public_fade = p.pop('is_public_fade', False)
        result = format_pick(**p)
        if result:
            if is_public_fade:
                result['warnings'].insert(0, '⚠️  PUBLIC FADE: Heavily promoted on Dimers/CBS/ActionNetwork — line inflated')
            picks.append(result)
    if banned_skipped:
        print(f'\n  ✗ BANNED (skipped): {", ".join(banned_skipped)}')
    print_picks(picks, title)
    return picks

if __name__ == '__main__':
    print()
    print('=' * 100)
    print('  PARBS ROUND 2 — GAME 1 PICKS')
    print('  PHI @ NYK (8pm ET, NYK -7.5)  |  MIN @ SAS (9:30pm ET, SAS -13.5)')
    print()
    print('  POSITIONAL DRtg MATCHUP SUMMARY:')
    print('  PHI @ NYK:')
    print('    → KAT (C) vs PHI: PHI C D +2.9 (no Embiid) — BOOST ✅')
    print('    → OG Anunoby (SF) vs PHI: PHI SF D +2.2 — BOOST ✅')
    print('    → Maxey (PG) vs NYK: NYK PG D -3.2 — TOUGH ⚠️')
    print('    → Paul George (SF) vs NYK: NYK SF D -4.5 — VERY TOUGH ⚠️')
    print()
    print('  MIN @ SAS:')
    print('    → McDaniels (SF) vs SAS: SAS SF D +2.8 — BOOST ✅  ← BEST MIN PICK')
    print('    → Castle (PG) vs MIN: MIN PG D -1.8 — manageable')
    print('    → Wemby (C) vs MIN: MIN C D -4.2 — VERY TOUGH ⚠️')
    print('    → Edwards (SG) vs SAS: SAS SG D +1.2 — slight boost')
    print()
    print('  SPREAD NOTE: SAS -13.5 blocks all standard OVERs. Alt lines used for SAS/MIN picks.')
    print('  NYK -7.5 is UNDER the 8pt threshold — OVERs allowed for PHI @ NYK.')
    print('=' * 100)

    nyk_phi_picks = run_game(
        nyk_picks_raw + phi_picks_raw,
        'GAME 1: PHI @ NYK  |  NYK -7.5  |  8:00 PM ET'
    )

    sas_min_picks = run_game(
        sas_picks_raw + min_picks_raw,
        'GAME 2: MIN @ SAS  |  SAS -13.5  |  9:30 PM ET  [ALT LINES]'
    )

    # ── PARLAY BUILDER ────────────────────────────────────────────────────────
    all_picks = [p for p in (nyk_phi_picks + sas_min_picks) if p is not None]
    elite_strong = [p for p in all_picks if p['grade'] in ('ELITE', 'STRONG')]

    print()
    print('=' * 100)
    print('  PARLAY BUILDER — 2-3 leg parlays (2+ teams required)')
    print('  ELITE/STRONG picks only. Public fades excluded from parlays.')
    print('=' * 100)

    # Filter out public fades from parlays
    parlay_pool = [p for p in elite_strong
                   if not any('PUBLIC FADE' in w for w in p.get('warnings', []))]

    # If no non-fade ELITE/STRONG, fall back to SOLID picks
    if not parlay_pool:
        parlay_pool = [p for p in all_picks
                       if p['grade'] in ('SOLID',)
                       and not any('PUBLIC FADE' in w for w in p.get('warnings', []))]

    # For cross-game parlays, we need picks from both games
    # Check if we have picks from both games separately
    game1_pool = [p for p in parlay_pool if p['team'] in ('NYK', 'PHI')]
    game2_pool = [p for p in parlay_pool if p['team'] in ('SAS', 'MIN')]

    # If game2 has no non-fade picks, include SOLID from game2 (blowout-flagged but still valid)
    if not game2_pool:
        game2_pool = [p for p in all_picks
                      if p['team'] in ('SAS', 'MIN')
                      and p['grade'] in ('SOLID', 'STRONG', 'ELITE')
                      and not any('PUBLIC FADE' in w for w in p.get('warnings', []))]
    if not game1_pool:
        game1_pool = [p for p in all_picks
                      if p['team'] in ('NYK', 'PHI')
                      and p['grade'] in ('SOLID', 'STRONG', 'ELITE')
                      and not any('PUBLIC FADE' in w for w in p.get('warnings', []))]

    parlay_pool = game1_pool + game2_pool

    # Group by team
    by_team = {}
    for p in parlay_pool:
        by_team.setdefault(p['team'], []).append(p)

    teams_with_picks = list(by_team.keys())

    if len(teams_with_picks) >= 2:
        print()
        print('  RECOMMENDED PARLAYS:')
        print()

        # Best pick from each game
        game1_best = sorted([p for p in parlay_pool if p['team'] in ('NYK','PHI')],
                            key=lambda x: -x['edge_pct'])
        game2_best = sorted([p for p in parlay_pool if p['team'] in ('SAS','MIN')],
                            key=lambda x: -x['edge_pct'])
        if game1_best and game2_best:
            p1, p2 = game1_best[0], game2_best[0]
            print(f'  2-LEG PARLAY (safest):')
            print(f'    Leg 1: {p1["player"]} {p1["prop"]} {p1["direction"]} {p1["line"]}  '
                  f'({p1["grade"]}, {p1["edge_pct"]}% edge)')
            print(f'    Leg 2: {p2["player"]} {p2["prop"]} {p2["direction"]} {p2["line"]}  '
                  f'({p2["grade"]}, {p2["edge_pct"]}% edge)')
            print()

        if game1_best and len(game1_best) >= 2 and game2_best:
            p1, p2, p3 = game1_best[0], game1_best[1], game2_best[0]
            print(f'  3-LEG PARLAY (higher payout):')
            print(f'    Leg 1: {p1["player"]} {p1["prop"]} {p1["direction"]} {p1["line"]}  '
                  f'({p1["grade"]}, {p1["edge_pct"]}% edge)')
            print(f'    Leg 2: {p2["player"]} {p2["prop"]} {p2["direction"]} {p2["line"]}  '
                  f'({p2["grade"]}, {p2["edge_pct"]}% edge)')
            print(f'    Leg 3: {p3["player"]} {p3["prop"]} {p3["direction"]} {p3["line"]}  '
                  f'({p3["grade"]}, {p3["edge_pct"]}% edge)')
            print()

        if game1_best and game2_best and len(game2_best) >= 2:
            p1, p2, p3 = game1_best[0], game2_best[0], game2_best[1]
            print(f'  3-LEG PARLAY (alt — 2 from Game 2):')
            print(f'    Leg 1: {p1["player"]} {p1["prop"]} {p1["direction"]} {p1["line"]}  '
                  f'({p1["grade"]}, {p1["edge_pct"]}% edge)')
            print(f'    Leg 2: {p2["player"]} {p2["prop"]} {p2["direction"]} {p2["line"]}  '
                  f'({p2["grade"]}, {p2["edge_pct"]}% edge)')
            print(f'    Leg 3: {p3["player"]} {p3["prop"]} {p3["direction"]} {p3["line"]}  '
                  f'({p3["grade"]}, {p3["edge_pct"]}% edge)')
            print()
    else:
        print()
        print('  Not enough non-fade picks from 2+ teams for a clean parlay.')
        print('  Consider single-game picks only tonight.')

    print()
    print('  PICKS TO AVOID (public fades — line already inflated):')
    fades = [p for p in all_picks if any('PUBLIC FADE' in w for w in p.get('warnings', []))]
    for p in fades:
        print(f'    ✗ {p["player"]} {p["prop"]} {p["direction"]} {p["line"]} — skip or reduce size')

    print()
    print('  ALT LINE NOTE: SAS -13.5 picks use alt lines (lower thresholds).')
    print('  Find alt lines on DraftKings → Player Props → Alternate Lines tab.')
    print('  Underdog Fantasy also offers alt lines at standard payouts.')
    print('=' * 100)
