"""
parbs_blowout_risk.py
=====================
Blowout Risk, Usage Rate Risk, and Matchup Defensive Rating module.
Permanently applied to every pick in both regular season and playoff engines.

Three risk flags applied before any pick is published:

1. BLOWOUT RISK
   - Checks game spread AND series context
   - Tracks actual blowout history in current series (games decided by 15+)
   - Reduces projected minutes for players on losing team in blowouts
   - Blocks OVER picks when projected minutes < 28 (starters sit 4th)

2. USAGE RATE RISK
   - Tracks how a player's usage changes in blowout games vs close games
   - Stars on losing teams see usage DROP in blowouts (sit 4th)
   - Stars on winning teams see usage DROP in blowouts (rest 4th)
   - Role players on winning teams see usage SPIKE in blowouts (garbage time)

3. MATCHUP DEFENSIVE RATING
   - Positional DRtg: how many pts/100 poss the opponent allows at each position
   - Applied as a multiplier to scoring projections
   - Updated at start of each playoff round

Usage:
    from parbs_blowout_risk import (
        BlowoutRiskEngine, POSITIONAL_DRTG, get_pos_delta, get_pos_label
    )
"""

# ─────────────────────────────────────────────────────────────────────────────
# POSITIONAL DEFENSIVE RATINGS — 2025-26 Season
# Delta = pts allowed per 100 poss vs league avg (114)
# Positive = team allows MORE at that position → BOOST for OVER
# Negative = team allows LESS at that position → REDUCE for OVER
# ─────────────────────────────────────────────────────────────────────────────
POSITIONAL_DRTG = {
    # Playoff teams
    'NYK': {'PG':-3.2,'SG':-2.1,'SF':-4.5,'PF':-1.8,'C':+2.9},
    'PHI': {'PG':+1.4,'SG':+0.8,'SF':+2.2,'PF':+1.1,'C':-3.1},
    'MIN': {'PG':-1.8,'SG':-2.4,'SF':-3.1,'PF':-2.0,'C':-4.2},
    'SAS': {'PG':+0.5,'SG':+1.2,'SF':+2.8,'PF':+1.5,'C':-1.9},
    'OKC': {'PG':-4.1,'SG':-3.2,'SF':-2.8,'PF':-1.5,'C':-2.1},
    'LAL': {'PG':+1.8,'SG':+0.5,'SF':+0.8,'PF':-1.2,'C':-2.8},
    'CLE': {'PG':-2.1,'SG':-1.8,'SF':-2.5,'PF':-3.8,'C':-4.2},
    'DET': {'PG':+2.8,'SG':+2.1,'SF':+1.5,'PF':+0.8,'C':+1.2},
    'BOS': {'PG':-2.1,'SG':-1.8,'SF':-3.5,'PF':-2.2,'C':-1.1},
    'IND': {'PG':+2.8,'SG':+1.9,'SF':+1.2,'PF':+0.8,'C':+1.5},
    'MIA': {'PG':-1.2,'SG':-0.8,'SF':-2.1,'PF':-1.0,'C':+0.5},
    'ORL': {'PG':-2.8,'SG':-1.5,'SF':-1.2,'PF':-3.1,'C':-4.5},
    'DEN': {'PG':-0.5,'SG':+0.8,'SF':-1.2,'PF':-0.5,'C':-2.1},
    'GSW': {'PG':+0.8,'SG':+1.5,'SF':-0.5,'PF':+1.2,'C':+2.1},
    'DAL': {'PG':-0.8,'SG':-1.2,'SF':-0.5,'PF':+0.8,'C':+1.5},
    'MEM': {'PG':+1.5,'SG':+2.1,'SF':+1.8,'PF':+0.5,'C':-0.8},
    'ATL': {'PG':+3.5,'SG':+2.8,'SF':+2.1,'PF':+1.5,'C':+1.8},
    'MIL': {'PG':+1.5,'SG':+1.2,'SF':+0.8,'PF':-0.5,'C':-1.8},
    'HOU': {'PG':+1.8,'SG':+1.2,'SF':+0.8,'PF':-0.5,'C':-1.2},
    'SAC': {'PG':+2.5,'SG':+1.8,'SF':+2.2,'PF':+1.0,'C':+0.8},
    'TOR': {'PG':+2.1,'SG':+1.5,'SF':+1.8,'PF':+0.8,'C':+0.5},
    'CHI': {'PG':+1.2,'SG':+0.8,'SF':+1.5,'PF':+0.5,'C':-0.5},
    'PHX': {'PG':+1.8,'SG':+2.5,'SF':+1.5,'PF':+0.8,'C':+1.2},
    'POR': {'PG':+2.8,'SG':+2.2,'SF':+1.8,'PF':+1.5,'C':+0.8},
    'UTA': {'PG':+3.2,'SG':+2.8,'SF':+2.5,'PF':+2.0,'C':+1.5},
    'WAS': {'PG':+3.8,'SG':+3.2,'SF':+2.5,'PF':+2.0,'C':+1.5},
    'NOP': {'PG':+1.5,'SG':+1.2,'SF':+0.8,'PF':+0.5,'C':-0.5},
    'CHO': {'PG':+2.5,'SG':+2.0,'SF':+1.5,'PF':+1.0,'C':+0.5},
    'BKN': {'PG':+3.5,'SG':+3.0,'SF':+2.5,'PF':+2.0,'C':+1.5},
    'LAC': {'PG':-0.5,'SG':-0.8,'SF':-1.2,'PF':-0.5,'C':+0.8},
}

# Player position map
PLAYER_POSITIONS = {
    # NYK
    'Jalen Brunson':'PG','Karl-Anthony Towns':'C','OG Anunoby':'SF',
    'Josh Hart':'SF','Donte DiVincenzo':'SG','Mikal Bridges':'SG',
    # PHI
    'Tyrese Maxey':'PG','Paul George':'SF','Kelly Oubre Jr.':'SF',
    'Joel Embiid':'C','Tobias Harris':'PF',
    # MIN
    'Anthony Edwards':'SG','Rudy Gobert':'C','Jaden McDaniels':'SF',
    'Mike Conley':'PG','Naz Reid':'C','Kyle Anderson':'PF',
    # SAS
    'Victor Wembanyama':'C',"De'Aaron Fox":'PG','Stephon Castle':'PG',
    'Devin Vassell':'SG','Keldon Johnson':'SF','Harrison Barnes':'PF',
    'Dylan Harper':'SG','Julian Champagnie':'SF',
    # OKC
    'Shai Gilgeous-Alexander':'PG','Jalen Williams':'SG','Chet Holmgren':'C',
    'Luguentz Dort':'SG','Isaiah Hartenstein':'C','Alex Caruso':'SG',
    # LAL
    'LeBron James':'SF','Anthony Davis':'C','Austin Reaves':'SG',
    'Rui Hachimura':'PF','Dorian Finney-Smith':'SF',
    # CLE
    'Donovan Mitchell':'SG','Darius Garland':'PG','Evan Mobley':'PF',
    'Jarrett Allen':'C','Max Strus':'SG',
    # DET
    'Cade Cunningham':'PG','Jalen Duren':'C','Ausar Thompson':'SF',
    'Tobias Harris':'PF','Tim Hardaway Jr.':'SG',
    # BOS
    'Jayson Tatum':'SF','Jaylen Brown':'SG','Kristaps Porzingis':'C',
    'Jrue Holiday':'PG','Al Horford':'C',
    # IND
    'Tyrese Haliburton':'PG','Pascal Siakam':'PF','Myles Turner':'C',
    'Bennedict Mathurin':'SG','Andrew Nembhard':'PG',
}


def get_pos_delta(player_name: str, opp_team: str, stat: str) -> float:
    """
    Returns the positional DRtg delta for a player vs their opponent.
    Only meaningful for Points and PRA (scoring-based stats).
    """
    if stat not in ('Points', 'Pts+Rebs+Asts'):
        return 0.0
    pos = PLAYER_POSITIONS.get(player_name)
    if not pos:
        return 0.0
    return POSITIONAL_DRTG.get(opp_team, {}).get(pos, 0.0)


def get_pos_mult(player_name: str, opp_team: str, stat: str) -> float:
    """Returns projection multiplier from positional DRtg. Capped at ±10%."""
    delta = get_pos_delta(player_name, opp_team, stat)
    return max(0.90, min(1.10, 1.0 + delta * 0.008))


def get_pos_label(player_name: str, opp_team: str) -> str:
    """Returns human-readable matchup label."""
    pos = PLAYER_POSITIONS.get(player_name, '?')
    delta = POSITIONAL_DRTG.get(opp_team, {}).get(pos, 0.0)
    if delta >= 2.0:
        return f'✅ {opp_team} soft on {pos} (+{delta}) — scoring boost'
    elif delta <= -2.0:
        return f'⚠️  {opp_team} elite on {pos} ({delta}) — tough matchup'
    else:
        return f'→ {opp_team} neutral on {pos} ({delta:+.1f})'


def get_matchup_context(team: str, opp: str, stat: str, team_stats: dict = None) -> list:
    """
    Returns advanced stat context notes for a pick.
    Uses live team_stats if provided, otherwise falls back to positional DRtg only.
    """
    notes = []
    if not team_stats:
        return notes

    t = team_stats.get(team, {})
    o = team_stats.get(opp, {})
    if not t or not o:
        return notes

    if stat == 'Rebounds':
        opp_dreb = o.get('DREB_PCT', 73)
        opp_oreb_allowed = o.get('OPP_OREB_PCT', 28)
        team_oreb = t.get('OREB_PCT', 28)
        if opp_dreb >= 76:
            notes.append(f'{opp} DREB% {opp_dreb}% (elite) — limits 2nd chances')
        elif opp_dreb <= 69:
            notes.append(f'{opp} DREB% {opp_dreb}% (weak) — misses stay alive')
        if opp_oreb_allowed >= 31:
            notes.append(f'{opp} allows {opp_oreb_allowed}% OREB — gives up 2nd chances')
        if team_oreb >= 31:
            notes.append(f'{team} OREB% {team_oreb}% (top 10) — crashes glass aggressively')

    elif stat == 'Assists':
        team_ast = t.get('AST_PCT', 60)
        if team_ast >= 64:
            notes.append(f'{team} AST% {team_ast}% — elite ball movement, assists flow')
        opp_tov = o.get('OPP_TOV_PCT', 14)
        if opp_tov >= 16:
            notes.append(f'{opp} forces {opp_tov}% TOV — high pressure, disrupts assists')

    elif stat in ('Points', 'Pts+Rebs+Asts'):
        opp_def = o.get('DEF_RATING', 114)
        opp_pts = o.get('OPP_PTS', 114)
        if opp_def <= 108:
            notes.append(f'{opp} DEF RTG {opp_def} (elite) — tough scoring environment')
        elif opp_def >= 116:
            notes.append(f'{opp} DEF RTG {opp_def} (soft) — easy scoring environment')
        notes.append(f'{opp} allows {opp_pts} PPG')

    return notes
    """
    Returns the positional DRtg delta for a player vs their opponent.
    Only meaningful for Points and PRA (scoring-based stats).
    """
    if stat not in ('Points', 'Pts+Rebs+Asts'):
        return 0.0
    pos = PLAYER_POSITIONS.get(player_name)
    if not pos:
        return 0.0
    return POSITIONAL_DRTG.get(opp_team, {}).get(pos, 0.0)


def get_pos_mult(player_name: str, opp_team: str, stat: str) -> float:
    """Returns projection multiplier from positional DRtg. Capped at ±10%."""
    delta = get_pos_delta(player_name, opp_team, stat)
    return max(0.90, min(1.10, 1.0 + delta * 0.008))


def get_pos_label(player_name: str, opp_team: str) -> str:
    """Returns human-readable matchup label."""
    pos = PLAYER_POSITIONS.get(player_name, '?')
    delta = POSITIONAL_DRTG.get(opp_team, {}).get(pos, 0.0)
    if delta >= 2.0:
        return f'✅ {opp_team} soft on {pos} (+{delta}) — scoring boost'
    elif delta <= -2.0:
        return f'⚠️  {opp_team} elite on {pos} ({delta}) — tough matchup'
    else:
        return f'→ {opp_team} neutral on {pos} ({delta:+.1f})'


# ─────────────────────────────────────────────────────────────────────────────
# BLOWOUT RISK ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class BlowoutRiskEngine:
    """
    Tracks blowout history in a series and applies risk flags to picks.

    A blowout is defined as a game decided by 15+ points.
    When a team gets blown out:
      - Their stars played reduced minutes (sat the 4th)
      - Their stats were artificially suppressed
      - OVER picks on those players are risky in the next game too
        (opponent has momentum, may blow them out again)

    Usage:
        engine = BlowoutRiskEngine()
        engine.record_game('PHI', 'NYK', phi_score=88, nyk_score=128)
        risk = engine.get_risk('Tyrese Maxey', 'PHI', spread=6.5)
    """

    # Blowout threshold — games decided by this many points or more
    BLOWOUT_THRESHOLD = 15

    # Minutes reduction estimate when a team gets blown out
    # Stars typically play ~27-28 min instead of 35-38 in blowouts
    BLOWOUT_MIN_REDUCTION = 8  # estimated minutes lost

    def __init__(self):
        # series_results: list of {'winner': team, 'loser': team, 'margin': int}
        self.series_results = []

    def record_game(self, team_a: str, team_b: str,
                    score_a: int, score_b: int):
        """Record a completed game result."""
        margin = abs(score_a - score_b)
        winner = team_a if score_a > score_b else team_b
        loser  = team_b if score_a > score_b else team_a
        self.series_results.append({
            'winner': winner, 'loser': loser,
            'margin': margin,
            'blowout': margin >= self.BLOWOUT_THRESHOLD,
        })

    def get_series_blowouts(self, team: str) -> dict:
        """
        Returns blowout stats for a team in the current series.
        Returns: {
            'times_blown_out': int,
            'times_blew_out': int,
            'last_game_blowout': bool,
            'last_game_was_loss': bool,
            'last_margin': int,
        }
        """
        times_blown_out = 0
        times_blew_out  = 0
        last_blowout    = False
        last_was_loss   = False
        last_margin     = 0

        for game in self.series_results:
            if game['blowout']:
                if game['loser'] == team:
                    times_blown_out += 1
                elif game['winner'] == team:
                    times_blew_out += 1

        if self.series_results:
            last = self.series_results[-1]
            last_margin   = last['margin']
            last_was_loss = (last['loser'] == team)
            last_blowout  = last['blowout']

        return {
            'times_blown_out': times_blown_out,
            'times_blew_out':  times_blew_out,
            'last_game_blowout': last_blowout,
            'last_was_loss':     last_was_loss,
            'last_margin':       last_margin,
        }

    def get_risk(self, player_name: str, team: str,
                 spread: float, ssn_min: float,
                 stat: str, direction: str) -> dict:
        """
        Returns blowout risk assessment for a pick.

        Returns dict with:
            approved: bool — False = block this pick
            risk_level: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
            flags: list of warning strings
            min_adj: float — adjusted minutes projection
            usage_adj: float — usage rate multiplier (0.7-1.0)
        """
        flags      = []
        risk_level = 'NONE'
        approved   = True
        min_adj    = ssn_min
        usage_adj  = 1.0

        abs_spread = abs(spread)
        series     = self.get_series_blowouts(team)

        # ── Flag 1: Current game spread ──────────────────────────────────────
        if abs_spread >= 15:
            flags.append(f'🔴 MASSIVE SPREAD ({abs_spread} pts) — extreme blowout risk')
            risk_level = 'CRITICAL'
            if direction == 'OVER' and ssn_min >= 30:
                # Star on heavy underdog — likely sits 4th
                min_adj   = ssn_min - self.BLOWOUT_MIN_REDUCTION
                usage_adj = 0.75
                if stat in ('Points',):
                    approved = False
                    flags.append('OVER blocked: star on 15+ pt underdog — will sit 4th')
        elif abs_spread >= 10:
            flags.append(f'🟠 LARGE SPREAD ({abs_spread} pts) — significant blowout risk')
            risk_level = 'HIGH'
            if direction == 'OVER' and ssn_min >= 30:
                min_adj   = ssn_min - 5
                usage_adj = 0.85
        elif abs_spread >= 7:
            flags.append(f'⚠️  SPREAD ({abs_spread} pts) — moderate blowout risk')
            risk_level = 'MEDIUM'
            if direction == 'OVER' and ssn_min >= 30:
                min_adj   = ssn_min - 3
                usage_adj = 0.92

        # ── Flag 2: Last game was a blowout loss ──────────────────────────────
        if series['last_game_blowout'] and series['last_was_loss']:
            margin = series['last_margin']
            flags.append(
                f'🔴 BLOWOUT HANGOVER: Lost G{len(self.series_results)} by {margin} pts — '
                f'stats suppressed last game, opponent has momentum'
            )
            if risk_level in ('NONE', 'LOW'):
                risk_level = 'MEDIUM'
            # Usage was suppressed last game — this game they'll be more aggressive
            # BUT opponent may blow them out again
            # Net effect: slight usage boost but blowout risk remains
            usage_adj = min(usage_adj * 1.05, 1.0)  # slight recovery boost
            flags.append(
                f'→ PHI/losing team typically comes out harder in G2 after blowout '
                f'(desperation factor) — but opponent momentum is real'
            )

        # ── Flag 3: Repeated blowout victim ──────────────────────────────────
        if series['times_blown_out'] >= 2:
            flags.append(
                f'🔴 SERIAL BLOWOUT VICTIM: Blown out {series["times_blown_out"]}x '
                f'in this series — opponent has figured them out'
            )
            risk_level = 'HIGH'
            if direction == 'OVER' and ssn_min >= 30:
                usage_adj *= 0.88

        # ── Flag 4: Winning team blowout risk (stars rest) ────────────────────
        if series['times_blew_out'] >= 1 and spread > 0:
            # Favored team that has blown out opponent — may rest stars again
            flags.append(
                f'→ {team} has blown out opponent {series["times_blew_out"]}x — '
                f'stars may get rest if lead gets big again'
            )

        # ── Flag 5: Minutes-based OVER block ─────────────────────────────────
        if direction == 'OVER' and min_adj < 28 and stat in ('Points', 'Pts+Rebs+Asts'):
            approved = False
            flags.append(
                f'OVER blocked: projected minutes {min_adj:.0f} < 28 — '
                f'player likely sits 4th quarter in blowout scenario'
            )

        return {
            'approved':   approved,
            'risk_level': risk_level,
            'flags':      flags,
            'min_adj':    round(min_adj, 1),
            'usage_adj':  round(usage_adj, 3),
        }


# ─────────────────────────────────────────────────────────────────────────────
# USAGE RATE RISK
# ─────────────────────────────────────────────────────────────────────────────

def get_usage_risk(player_name: str, team: str,
                   l10_fga: float, ssn_min: float,
                   spread: float, series_engine: BlowoutRiskEngine) -> dict:
    """
    Assesses usage rate risk for a player.

    Returns dict with:
        risk_level: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
        flags: list of warning strings
        usage_note: short summary string
    """
    flags = []
    risk_level = 'NONE'

    abs_spread = abs(spread)
    series = series_engine.get_series_blowouts(team)

    # High usage star on underdog — usage gets suppressed in blowouts
    is_star = ssn_min >= 32 and l10_fga >= 15
    is_role = 6 <= l10_fga <= 14 and 22 <= ssn_min <= 32

    if is_star and spread < -8:
        flags.append(
            f'⚠️  HIGH USAGE STAR on {abs_spread}pt underdog — '
            f'usage suppressed when team falls behind big (sits 4th)'
        )
        risk_level = 'HIGH'
    elif is_star and spread < -5:
        flags.append(
            f'→ Star player on {abs_spread}pt underdog — '
            f'moderate usage risk if game gets out of hand'
        )
        risk_level = 'MEDIUM'

    if is_role:
        flags.append('✅ LOW-VARIANCE ROLE PLAYER — consistent usage regardless of score')
        risk_level = 'LOW' if risk_level == 'NONE' else risk_level

    # Blowout hangover usage note
    if series['last_game_blowout'] and series['last_was_loss'] and is_star:
        flags.append(
            '→ Star was on blowout losing team last game — '
            'expect higher aggression/usage in G2 (desperation)'
        )

    usage_note = (
        f"Usage risk: {risk_level} | "
        f"L10 FGA: {l10_fga:.1f} | "
        f"Min: {ssn_min:.0f} | "
        f"{'Star' if is_star else 'Role player' if is_role else 'Mid-usage'}"
    )

    return {
        'risk_level': risk_level,
        'flags':      flags,
        'usage_note': usage_note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED RISK SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def get_full_risk_summary(player_name: str, team: str, opp_team: str,
                          stat: str, direction: str, line: float,
                          proj: float, spread: float,
                          ssn_min: float, l10_fga: float,
                          series_engine: BlowoutRiskEngine) -> dict:
    """
    Master risk function. Combines blowout, usage, and matchup DRtg.
    Returns complete risk picture for a pick.
    """
    # 1. Blowout risk
    blow = series_engine.get_risk(
        player_name, team, spread, ssn_min, stat, direction
    )

    # 2. Usage risk
    usage = get_usage_risk(
        player_name, team, l10_fga, ssn_min, spread, series_engine
    )

    # 3. Positional DRtg
    pos_delta = get_pos_delta(player_name, opp_team, stat)
    pos_mult  = get_pos_mult(player_name, opp_team, stat)
    pos_label = get_pos_label(player_name, opp_team)
    adj_proj  = round(proj * pos_mult, 1)
    edge_pct  = (adj_proj - line) / line * 100 if line > 0 else 0

    # Overall risk level (worst of the three)
    risk_order = {'NONE':0,'LOW':1,'MEDIUM':2,'HIGH':3,'CRITICAL':4}
    overall = max(
        [blow['risk_level'], usage['risk_level']],
        key=lambda x: risk_order.get(x, 0)
    )

    all_flags = blow['flags'] + usage['flags']
    if pos_delta >= 2.0:
        all_flags.insert(0, f'✅ MATCHUP BOOST: {pos_label}')
    elif pos_delta <= -2.0:
        all_flags.insert(0, f'⚠️  TOUGH MATCHUP: {pos_label}')

    return {
        'approved':     blow['approved'],
        'overall_risk': overall,
        'blowout_risk': blow['risk_level'],
        'usage_risk':   usage['risk_level'],
        'pos_delta':    pos_delta,
        'pos_mult':     pos_mult,
        'pos_label':    pos_label,
        'adj_proj':     adj_proj,
        'edge_pct':     round(edge_pct, 1),
        'min_adj':      blow['min_adj'],
        'usage_adj':    blow['usage_adj'],
        'flags':        all_flags,
    }


if __name__ == '__main__':
    # Demo: PHI@NYK G2 — PHI got blown out by 40 in G1
    print("="*70)
    print("  BLOWOUT RISK DEMO — PHI@NYK G2")
    print("  PHI lost G1 by 40 points (88-128)")
    print("="*70)

    engine = BlowoutRiskEngine()
    engine.record_game('PHI', 'NYK', score_a=88, score_b=128)  # G1 result

    players = [
        ('Tyrese Maxey',  'PHI', 'NYK', 'Points',   19.5, 25.1, -6.5, 36.6, 18.7),
        ('Paul George',   'PHI', 'NYK', 'Points',   10.5, 17.4, -6.5, 30.9, 15.9),
        ('OG Anunoby',    'NYK', 'PHI', 'Points',   13.5, 21.0,  6.5, 33.8, 11.1),
        ('Jalen Brunson', 'NYK', 'PHI', 'Points',   22.5, 27.6,  6.5, 35.9, 19.2),
    ]

    for name, team, opp, stat, line, proj, spread, ssn_min, l10_fga in players:
        risk = get_full_risk_summary(
            name, team, opp, stat, 'OVER', line, proj,
            spread, ssn_min, l10_fga, engine
        )
        print(f"\n  {name} ({team}) — {stat} OVER {line}")
        print(f"    Adj proj: {risk['adj_proj']}  Edge: {risk['edge_pct']:+.1f}%")
        print(f"    Overall risk: {risk['overall_risk']}  |  Approved: {risk['approved']}")
        print(f"    Min adj: {risk['min_adj']}  |  Usage adj: {risk['usage_adj']}")
        for f in risk['flags']:
            print(f"    → {f}")
