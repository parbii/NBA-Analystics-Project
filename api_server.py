"""
api_server.py
=============
Flask API that serves Parbs picks data as JSON for the Lovable frontend.

Endpoints:
  GET /api/picks        — Investment scored picks (parbs_investment_picks.csv)
  GET /api/report       — Full player report with signals (parbs_picks_global_report.csv)
  GET /api/games        — Tonight's schedule from ESPN
  GET /api/injuries     — Live injury report from ESPN
  GET /api/rtm          — Regression-to-mean L10 vs season comparison
  GET /health           — Health check

Run locally:
  python3 api_server.py

Deploy to Render/Railway:
  Push this file + requirements.txt to GitHub, connect repo to Render.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import requests
import os
from datetime import date

app = Flask(__name__)
CORS(app)  # Allow Lovable frontend to call this API

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

# ── Helper ────────────────────────────────────────────────────────────────────
def safe_read(filename):
    """Read a CSV safely, return empty list if file missing."""
    try:
        df = pd.read_csv(filename)
        # Replace NaN with None so JSON serializes cleanly
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient='records')
    except Exception as e:
        return {'error': str(e)}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'date': str(date.today())})

@app.route('/api/picks')
def picks():
    """
    Investment scored picks — the main dashboard data.
    Columns: PLAYER, TEAM, OPP, OPP_DRTG, SSN_PTS, L10_PTS, PTS_DELTA,
             L10_PRA, SSN_FG%, L10_FG%, GTD, SCORE, TIER, NOTES, GAME
    """
    data = safe_read('parbs_investment_picks.csv')
    if isinstance(data, list):
        # Sort by score descending
        data.sort(key=lambda x: float(x.get('SCORE', 0) or 0), reverse=True)
    return jsonify(data)

@app.route('/api/report')
def report():
    """
    Full player signal report — all roles, all teams.
    Columns: PLAYER, TEAM, OPP, PPG, MPG, FG%, 3P%, SIGNAL, INJ_FLAG, STARS_OUT
    """
    data = safe_read('parbs_picks_global_report.csv')
    return jsonify(data)

@app.route('/api/rtm')
def rtm():
    """
    Regression-to-mean comparison — L10 vs season averages.
    """
    data = safe_read('last10_avgs.csv')
    return jsonify(data)

@app.route('/api/games')
def games():
    """
    Tonight's NBA schedule from ESPN (live).
    """
    try:
        today = date.today().strftime('%Y%m%d')
        url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today}'
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get('events', [])

        games_list = []
        for e in events:
            comp = e['competitions'][0]
            home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
            away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
            notes = comp.get('notes', [])
            games_list.append({
                'id':        e['id'],
                'away':      away['team']['abbreviation'],
                'away_name': away['team']['displayName'],
                'away_score':away.get('score', '-'),
                'home':      home['team']['abbreviation'],
                'home_name': home['team']['displayName'],
                'home_score':home.get('score', '-'),
                'status':    e['status']['type']['shortDetail'],
                'note':      notes[0].get('headline', 'Regular Season') if notes else 'Regular Season',
                'time':      e['date'],
            })
        return jsonify(games_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/injuries')
def injuries():
    """
    Live injury report from ESPN.
    """
    try:
        r = requests.get(
            'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries',
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        result = []
        for team in r.json().get('injuries', []):
            team_abbr = team.get('team', {}).get('abbreviation', '')
            for player in team.get('injuries', []):
                result.append({
                    'player': player.get('athlete', {}).get('displayName', ''),
                    'team':   team_abbr,
                    'status': player.get('status', ''),
                    'detail': player.get('shortComment', '')[:80],
                })
        # Only return meaningful statuses
        result = [p for p in result if p['status'] in ('Out', 'Doubtful', 'Questionable', 'Day-To-Day')]
        result.sort(key=lambda x: x['status'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary')
def summary():
    """
    Dashboard summary stats — counts by tier, top play of the day.
    """
    try:
        data = safe_read('parbs_investment_picks.csv')
        if not isinstance(data, list):
            return jsonify(data)

        tiers = {'ELITE': 0, 'STRONG': 0, 'SOLID': 0, 'LEAN': 0}
        for row in data:
            t = row.get('TIER', '')
            if t in tiers:
                tiers[t] += 1

        top = data[0] if data else {}
        return jsonify({
            'date':       str(date.today()),
            'total':      len(data),
            'tiers':      tiers,
            'top_play':   top,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
