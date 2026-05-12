# MLB Analytics Engine

## Status: In Development

## Data Sources
- **PrizePicks API** — `league_id=2` for MLB lines (goblin/standard/demon)
- **Baseball-Reference** — Player game logs, season stats, splits
- **ESPN API** — Schedule, probable pitchers, injuries
- **pybaseball** — Python library for MLB stats (Statcast, FanGraphs)

## Planned Features

### Hitter Props
- Hits, Total Bases, RBIs, Runs, Home Runs
- L10 game logs with hit rate analysis
- Pitcher matchup context (LHP vs RHP splits)
- Ballpark factors (Coors Field boost, etc.)
- Platoon advantage (lefty/righty splits)

### Pitcher Props
- Strikeouts, Outs Recorded, Earned Runs Allowed
- Recent form (L5 starts)
- Opponent team batting stats (K%, OBP, SLG)
- Home/away splits

### Key Differences from NBA
- **Daily variance is MUCH higher** — baseball is inherently more random
  - NBA: star scores 20+ in 90% of games
  - MLB: star gets 0 hits in 30% of games (normal)
- **Pitcher matchup is everything** — same hitter can be 4/4 or 0/4 based on pitcher
- **Platoon splits matter** — LHB vs LHP is a completely different player
- **Ballpark factors** — Coors Field inflates all stats by 15-20%
- **Sample sizes are larger** — 162 games vs 82 (more data = better stats)

### Filters (adapted from NBA)
- Minimum line thresholds (Hits≥0.5, TB≥1.0, K≥3.5)
- Pitcher matchup multiplier (replaces positional DRtg)
- Platoon advantage flag
- Ballpark factor adjustment
- Recent form weight (L10 vs season)

## Run
```bash
python3 mlb/mlb_engine.py              # today's games
python3 mlb/mlb_engine.py --tomorrow   # tomorrow's games
```

## Dependencies
```
pip install pybaseball  # MLB stats library (free, no API key)
```
