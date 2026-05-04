"""
parbs_ban_list.py
=================
Player ban list — permanently excluded from all pick recommendations.

A player gets banned when they demonstrate a pattern that makes them
unreliable as an investment target:
  - Zero-point games (complete no-shows)
  - Extreme volatility (0 one game, 30 the next — unpredictable)
  - Injury return uncertainty
  - Role/minutes changes mid-series

Banned players are SKIPPED before any filter runs.
To reinstate a player, remove them from BAN_LIST and add a note to REINSTATED.

Usage:
  from parbs_ban_list import is_banned, BAN_LIST
"""

# ── Active ban list ───────────────────────────────────────────────────────────
# Format: 'Player Name': {'reason': str, 'date': str, 'game': str}
BAN_LIST = {
    'Mikal Bridges': {
        'reason': 'Dropped 0 points in a playoff game — complete no-show. '
                  'Extreme volatility makes him unplayable as an investment.',
        'date': '2026-05-04',
        'game': 'PHI @ NYK Round 2 G1',
        'reinstated': False,
    },
}

# ── Reinstated players (removed from ban, kept for audit trail) ───────────────
REINSTATED = {
    # 'Player Name': {'reason': 'Consistent 3-game return', 'date': '2026-XX-XX'}
}


def is_banned(player_name: str) -> bool:
    """Returns True if player is on the active ban list."""
    return player_name in BAN_LIST and not BAN_LIST[player_name].get('reinstated', False)


def get_ban_reason(player_name: str) -> str:
    """Returns the ban reason string, or empty string if not banned."""
    if is_banned(player_name):
        entry = BAN_LIST[player_name]
        return f"BANNED ({entry['date']}): {entry['reason']}"
    return ''


def reinstate(player_name: str, reason: str):
    """Mark a player as reinstated (call manually when confidence returns)."""
    if player_name in BAN_LIST:
        BAN_LIST[player_name]['reinstated'] = True
        REINSTATED[player_name] = {'reason': reason, 'date': 'manual'}
        print(f'  ✅ {player_name} reinstated: {reason}')
    else:
        print(f'  {player_name} not found in ban list.')


if __name__ == '__main__':
    print()
    print('=' * 70)
    print('  PARBS BAN LIST')
    print('=' * 70)
    active = {k: v for k, v in BAN_LIST.items() if not v.get('reinstated', False)}
    if not active:
        print('  No active bans.')
    for player, info in active.items():
        print(f'\n  ✗ {player}')
        print(f'    Banned:  {info["date"]}  ({info["game"]})')
        print(f'    Reason:  {info["reason"]}')
    print()
    print(f'  Total banned: {len(active)}')
    print('=' * 70)
