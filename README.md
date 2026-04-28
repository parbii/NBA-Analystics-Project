# 🏀 Parbs NBA Analytics Engine

A fully automated NBA player prop prediction system built in Python. Pulls live data from multiple sources, applies a multi-layer filter engine, and outputs ranked investment picks with confidence grades — every game night.

---

## What It Does

Every day there are NBA games, the pipeline automatically:

1. Detects tonight's schedule from ESPN (no API key needed)
2. Fetches active rosters — validated against ESPN's live roster to strip traded/waived players
3. Pulls live injury reports from ESPN
4. Fetches last 10 game logs per player via NBA API
5. Scores every player using season avg + L10 avg + regression-to-mean + opponent defensive rating
6. Applies a 10-rule filter engine to eliminate bad picks before publishing
7. Outputs exact prop plays with line, projection, edge %, and confidence grade

---

## The Filter Engine

Every pick passes through 10 rules before being published. If it fails any rule, it's blocked.

| Rule | Description |
|---|---|
| 1 | Minimum 5% edge — no coin flips |
| 2 | PRA props require 15%+ edge |
| 3 | AST/REB props require 10%+ edge |
| 4 | No OVER picks when spread ≥ 6 pts (blowout risk — starters sit) |
| 5 | No OVER on heavy underdogs (spread ≤ -8) |
| 6 | Players averaging < 20 min/game excluded |
| 6b | Usage rate filter: L10 FGA < 5 blocks PTS OVER (player not getting shots) |
| 7 | GTD players flagged — confirm active before betting |
| 8 | UNDER picks get +3% confidence boost (85.7% historical hit rate) |
| 8b | Series desperation block: UNDER on role players blocked when team is down 2+ games in a series |
| 8c | High-total warning: flags UNDER on role players when game total > 220 |
| 9 | Near-line OVER picks (< 6% edge) downgraded to LEAN |

---

## Projection Model

```
Projection = (L10 avg × 0.6 + Season avg × 0.4) × Playoff multiplier (1.08)
```

**Features used per player:**
- Season averages (PTS, REB, AST, FG%, 3P%, MIN)
- Last 10 game averages (rolling form)
- Regression-to-mean delta (hot/cold signal)
- Opponent defensive rating
- Shot attempts (FGA) — usage proxy
- Role boost (star player out = more usage for role players)
- Series context (game number, series deficit)

---

## Data Sources (All Free, No API Keys)

| Source | Used For |
|---|---|
| ESPN hidden API | Schedule, injuries, live scores, active rosters |
| Basketball-Reference | Season per-game averages (primary) |
| NBA API (`nba_api`) | Last 10 game logs, per-game fallback |
| StatMuse scraper | Fallback game log source |

**Roster validation:** Every player is cross-checked against ESPN's live active roster before being included. Traded or waived players are automatically stripped — even if they still appear on Basketball-Reference's season page.

---

## Confidence Grades

| Grade | Edge Required | Description |
|---|---|---|
| 🔥🔥 ELITE | 12%+ | Highest conviction — all signals aligned |
| 🔥 STRONG | 8%+ | Very good edge, consistent data |
| ✅ SOLID | 5%+ | Good value, publishable |
| 📋 LEAN | < 5% | Shown but flagged — small play only |
| SKIP | — | Blocked by filter — do not bet |

---

## Hit Rate (Playoff Picks, Updated Filters)

| Date | Record | Hit Rate | Notes |
|---|---|---|---|
| Apr 17 Play-In | 5/6 | **83%** | 1 near-miss (0.5 pts) |
| Apr 18 G1 | 8/10 | **80%** | KD DNP voided, 1 blowout miss |
| Apr 26 G4 | 3/4 | **75%** | 1 miss by 0.5 pts |
| Clean picks only | 16/18 | **88.9%** | Excluding blowout/near-miss |

*"Clean picks" = picks where the game script matched expectations (no blowouts, no DNPs)*

---

## Project Structure

```
NBA-Analystics-Project/
│
├── parbs_daily_picks.py      # Main engine — runs nightly, outputs picks
├── parbs_prop_filter.py      # Standalone filter module (10 rules)
├── parbs_master_analysis.py  # Full player signal report (injuries + roles)
├── parbs_league_master.py    # Roster fetcher with ESPN validation
├── parbs_investment_engine.py # Investment scoring (0-100 score per player)
├── hit_rate_audit.py         # Automated accuracy tracking vs actual results
├── daily_refresh.py          # Cron-scheduled full pipeline runner
│
├── data_ingestion/
│   ├── bdl_scraper.py        # Ball Don't Lie API scraper
│   ├── bref_scraper.py       # Basketball-Reference Selenium scraper
│   └── sm_scraper.py         # StatMuse HTML scraper
│
├── audit_engine/
│   └── risk_logic.py         # TS% volatility + fatigue detection
│
└── tf_prop_model.py          # TensorFlow regression model (B2B, travel, DRtg)
```

---

## Automated Daily Pipeline

Runs every morning at 9am via cron:

```
ESPN schedule check → Roster fetch + ESPN validation → Injury report →
L10 game logs → Filter engine → Ranked picks → Charts + thumbnails
```

```bash
# Run manually
python3 parbs_daily_picks.py          # tomorrow's games
python3 parbs_daily_picks.py --today  # today's games
```

---

## TensorFlow Model

A regression model trained on historical game logs predicts PTS/REB/AST for the next game.

**Features:** Rolling 5-game averages, TS% delta, back-to-back flag, travel stress (timezone crossing), days rest, opponent DRtg, home/away.

**Training:** Retrained every Monday on fresh data. Huber loss for outlier robustness.

---

## Tech Stack

- **Language:** Python 3.9+
- **Data:** `nba_api`, `requests`, `pandas`, `BeautifulSoup`
- **ML:** TensorFlow, scikit-learn
- **Automation:** cron, Flask API (`api_server.py`)
- **Version Control:** Git / GitHub

---

## Disclaimer

This repository is for data analysis, pattern recognition, and educational purposes only. All picks are model outputs — not financial advice. Always gamble responsibly.
