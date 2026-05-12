# WNBA Analytics Engine

## Status: In Development

## Data Sources
- **PrizePicks API** — `league_id=3` for WNBA lines (goblin/standard/demon)
- **Basketball-Reference** — WNBA game logs and season stats
- **ESPN API** — Schedule, injuries, active rosters

## Planned Features
- Same statistical engine as NBA (t-tests, CIs, regression, hit rates)
- PrizePicks goblin/demon line analysis
- Positional matchup context
- Blowout risk (less relevant in WNBA but still tracked)
- Mixed parlay builder ranked by EV

## Run
```bash
python3 wnba/wnba_engine.py           # today's games
python3 wnba/wnba_engine.py --tomorrow  # tomorrow's games
```

## Key Differences from NBA
- Shorter season (40 games) = smaller sample sizes
- Fewer players per team = more predictable rotations
- Less variance in minutes = more consistent stat lines
- No back-to-back fatigue issues (games less frequent)
