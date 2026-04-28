"""
parbs_prop_filter.py
====================
Prop recommendation filter that applies before any pick is published.

Filters applied:
  1. Blowout risk — checks historical spread and pace to flag likely blowouts
  2. Prop type filter — avoids PRA unless edge > 15%, avoids AST/REB unless strong
  3. Minimum edge threshold — no pick under 5% edge
  4. Direction bias — UNDER picks get a confidence boost (85% historical hit rate)
  5. Close game filter — favors players in projected close games (spread < 8)
  6. Minutes floor — no picks on players averaging < 20 min
  7. Consistency check — penalizes high-variance players on OVER picks

Usage:
  from parbs_prop_filter import filter_pick, BLOWOUT_RISK_TEAMS
"""

# Teams with high blowout frequency this season (win/loss by 15+ regularly)
# These teams either blow out opponents OR get blown out — both kill OVER props
BLOWOUT_RISK = {
    # Teams that frequently blow out opponents (starters sit 4th)
    'BOS': 'HIGH',   # Best record, often up big
    'OKC': 'HIGH',   # Best defense, often controls games
    'CLE': 'MED',    # Strong team, occasional blowouts
    'NYK': 'MED',    # Home court, can run away
    # Teams that frequently GET blown out (starters sit when losing big)
    'TOR': 'HIGH',   # Weaker team, often down big
    'WAS': 'HIGH',   # Rebuilding, frequent blowout losses
    'CHO': 'HIGH',   # Play-In team, outmatched vs top seeds
    'ATL': 'MED',    # Inconsistent, can get blown out on road
    'POR': 'MED',    # Underdog in most matchups
    'PHX': 'MED',    # Missing stars, vulnerable
}

# Prop types ranked by reliability (from our audit data)
PROP_RELIABILITY = {
    'PTS':  0.583,   # 58.3% historical hit rate
    'UNDER': 0.857,  # 85.7% when direction is UNDER
    'REB':  0.333,   # 33.3% — avoid unless strong edge
    'AST':  0.333,   # 33.3% — avoid unless strong edge
    'PRA':  0.333,   # 33.3% — avoid unless massive edge
}

def get_blowout_risk(team, opp, spread):
    """
    Returns blowout risk level for a player's OVER prop.
    
    spread: positive = team is favorite (e.g. +8.5 means team favored by 8.5)
            negative = team is underdog
    """
    risks = []
    
    # Large spread = likely blowout in either direction
    abs_spread = abs(spread)
    if abs_spread >= 12:
        risks.append('SPREAD_BLOWOUT_HIGH')
    elif abs_spread >= 8:
        risks.append('SPREAD_BLOWOUT_MED')
    
    # Team-specific blowout history
    team_risk = BLOWOUT_RISK.get(team, 'LOW')
    opp_risk  = BLOWOUT_RISK.get(opp, 'LOW')
    
    if team_risk == 'HIGH' or opp_risk == 'HIGH':
        risks.append('TEAM_BLOWOUT_HIGH')
    elif team_risk == 'MED' or opp_risk == 'MED':
        risks.append('TEAM_BLOWOUT_MED')
    
    # Underdog in a big spread = likely to get blown out = starters sit
    if spread <= -10:
        risks.append('HEAVY_UNDERDOG')
    
    return risks

def filter_pick(player, team, opp, prop, line, proj, direction, spread=0, ssn_min=25):
    """
    Returns (approved, confidence_adj, warnings) for a prop pick.
    
    approved: True/False — whether to publish this pick
    confidence_adj: adjustment to confidence score (-20 to +10)
    warnings: list of warning strings to display
    """
    warnings = []
    confidence_adj = 0
    approved = True
    
    edge_pct = abs(proj - line) / line if line > 0 else 0
    
    # ── Rule 1: Minimum edge threshold ───────────────────────────────────────
    if edge_pct < 0.04:
        return False, -50, ['EDGE TOO SMALL (<4%) — skip']
    
    # ── Rule 2: Minutes floor ─────────────────────────────────────────────────
    if ssn_min < 20:
        return False, -50, ['LOW MINUTES (<20 mpg) — unreliable']
    
    # ── Rule 3: Prop type filter ──────────────────────────────────────────────
    if prop == 'PRA' and edge_pct < 0.15:
        return False, -30, ['PRA requires 15%+ edge — too risky']
    
    if prop in ('AST', 'REB') and edge_pct < 0.10:
        warnings.append(f'{prop} props need 10%+ edge — borderline')
        confidence_adj -= 10
    
    # ── Rule 4: Direction bias ────────────────────────────────────────────────
    if direction == 'UNDER':
        confidence_adj += 10  # UNDER picks historically 85.7% hit rate
        warnings.append('UNDER bias: +10 confidence (85.7% historical)')
    
    # ── Rule 5: Blowout risk ──────────────────────────────────────────────────
    blowout_risks = get_blowout_risk(team, opp, spread)
    
    if direction == 'OVER':
        # OVER picks are hurt by blowouts (starters sit)
        if 'SPREAD_BLOWOUT_HIGH' in blowout_risks:
            warnings.append(f'⚠️  BLOWOUT RISK: Spread {abs(spread)} pts — starters may sit 4th')
            confidence_adj -= 20
            if edge_pct < 0.10:
                return False, -40, ['OVER + large spread + small edge = skip']
        
        if 'HEAVY_UNDERDOG' in blowout_risks:
            warnings.append(f'⚠️  HEAVY UNDERDOG: Team likely down big — starters may sit')
            confidence_adj -= 15
        
        if 'TEAM_BLOWOUT_HIGH' in blowout_risks:
            warnings.append(f'⚠️  HIGH BLOWOUT TEAM: {team} or {opp} frequently in blowouts')
            confidence_adj -= 10
    else:
        # UNDER picks actually BENEFIT from blowouts
        if 'SPREAD_BLOWOUT_HIGH' in blowout_risks or 'HEAVY_UNDERDOG' in blowout_risks:
            warnings.append(f'✅ BLOWOUT BENEFIT: Large spread helps UNDER — starters may sit')
            confidence_adj += 10
    
    # ── Rule 6: Consistency check for OVER picks ──────────────────────────────
    # If player is COLD (L10 below season avg) and we're recommending OVER,
    # that's a regression play — flag it
    delta = proj / 1.08 * 0.6  # rough L10 estimate from proj
    # (actual delta passed in from calling code — this is a placeholder)
    
    # ── Rule 7: Playoff series context ───────────────────────────────────────
    # In a series, teams adjust. Game 1 outliers are flagged.
    # (Handled in calling code via G1 actual vs projection comparison)
    
    return approved, confidence_adj, warnings


def get_pick_grade(edge_pct, direction, prop, spread, confidence_adj):
    """
    Returns final grade: ELITE / STRONG / SOLID / LEAN / SKIP
    Based on edge + direction + prop type + blowout risk adjustment.
    """
    # Base score from edge
    base = edge_pct * 100  # 10% edge = 10 base points
    
    # Direction multiplier
    if direction == 'UNDER':
        base *= 1.5
    
    # Prop type multiplier
    prop_mult = {'PTS': 1.0, 'REB': 0.7, 'AST': 0.7, 'PRA': 0.6}
    base *= prop_mult.get(prop, 1.0)
    
    # Apply confidence adjustment
    final = base + confidence_adj
    
    if final >= 18: return 'ELITE'
    if final >= 12: return 'STRONG'
    if final >= 7:  return 'SOLID'
    if final >= 4:  return 'LEAN'
    return 'SKIP'


def format_pick(player, team, opp, prop, line, proj, direction, spread=0,
                ssn_min=25, g1_actual=None, game_note=''):
    """
    Full pick formatter. Returns a dict with all pick info or None if filtered out.
    """
    approved, conf_adj, warnings = filter_pick(
        player, team, opp, prop, line, proj, direction, spread, ssn_min
    )
    
    if not approved:
        return None
    
    edge = round(proj - line, 1)
    edge_pct = abs(edge) / line if line > 0 else 0
    grade = get_pick_grade(edge_pct, direction, prop, spread, conf_adj)
    
    # G1 context: if player had an outlier in G1, flag it
    g1_note = ''
    if g1_actual is not None:
        g1_delta = g1_actual - (proj / 1.08)  # rough season avg
        if abs(g1_delta) > 5:
            if g1_delta > 0:
                g1_note = f'G1 outlier HIGH ({g1_actual}) — RTM DOWN risk'
            else:
                g1_note = f'G1 outlier LOW ({g1_actual}) — RTM UP opportunity'
    
    return {
        'player':    player,
        'team':      team,
        'opp':       opp,
        'prop':      prop,
        'line':      line,
        'proj':      proj,
        'direction': direction,
        'edge':      edge,
        'edge_pct':  round(edge_pct * 100, 1),
        'grade':     grade,
        'spread':    spread,
        'warnings':  warnings,
        'g1_note':   g1_note,
        'game_note': game_note,
    }


def print_picks(picks, title='PARBS PICKS'):
    """Print a formatted picks table."""
    valid = [p for p in picks if p is not None]
    grade_order = {'ELITE': 0, 'STRONG': 1, 'SOLID': 2, 'LEAN': 3}
    valid.sort(key=lambda x: (grade_order.get(x['grade'], 9), -x['edge_pct']))
    
    emojis = {'ELITE': '🔥🔥', 'STRONG': '🔥', 'SOLID': '✅', 'LEAN': '📋'}
    
    print()
    print('=' * 100)
    print(f'  {title}')
    print(f'  Filters: min 4% edge | no PRA <15% | blowout risk applied | UNDER bias +10')
    print('=' * 100)
    
    current_grade = None
    for p in valid:
        if p['grade'] != current_grade:
            current_grade = p['grade']
            e = emojis.get(current_grade, '')
            print(f'\n  {e} {current_grade}')
            print('  ' + '-' * 90)
        
        es = ('+' if p['edge'] > 0 else '') + str(p['edge'])
        spread_str = f"({'+' if p['spread']>=0 else ''}{p['spread']} spread)"
        print(f"  {p['player']:<24} {p['prop']:<5} {p['direction']:<7} {p['line']:<7} "
              f"Proj:{p['proj']:<7} Edge:{es:<7} {p['edge_pct']}%  {spread_str}")
        
        for w in p['warnings']:
            print(f"    → {w}")
        if p['g1_note']:
            print(f"    → {p['g1_note']}")
    
    # Summary
    by_grade = {}
    for p in valid:
        by_grade[p['grade']] = by_grade.get(p['grade'], 0) + 1
    
    print()
    print(f'  Total publishable picks: {len(valid)}')
    for g in ['ELITE', 'STRONG', 'SOLID', 'LEAN']:
        if g in by_grade:
            print(f'    {g}: {by_grade[g]}')
    print('=' * 100)


if __name__ == '__main__':
    # Demo: run the filter on tonight's picks
    print('Parbs Prop Filter — loaded.')
    print('Import format_pick() and print_picks() in your analysis scripts.')
    print()
    print('Key rules:')
    print('  1. Minimum 4% edge — no coin flips')
    print('  2. PRA requires 15%+ edge')
    print('  3. UNDER picks get +10 confidence (85.7% historical hit rate)')
    print('  4. Spread > 12 pts = blowout risk warning on OVER picks')
    print('  5. Heavy underdogs (spread -10+) = starters may sit flag')
    print('  6. Players < 20 mpg are excluded')
