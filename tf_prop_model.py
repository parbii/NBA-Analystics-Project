"""
tf_prop_model.py
================
TensorFlow regression model for player prop prediction.

Features engineered per game:
  - Rolling 5-game averages (PTS, REB, AST, FGA, FTA, MIN)
  - TS% delta (recent efficiency vs season)
  - Back-to-back flag        (game played night before)
  - Travel flag              (away game after away game, different timezone)
  - Days rest                (days since last game)
  - Opponent defensive rating
  - Home / Away flag

Outputs a predicted PTS, REB, AST for the NEXT game per player,
plus a confidence-adjusted prop signal.

Usage:
  python tf_prop_model.py              # train + predict
  python tf_prop_model.py --predict-only  # load saved model, run predictions
"""

import os, sys, warnings
import numpy as np
import pandas as pd
from datetime import date

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # suppress TF noise

# ── Defensive ratings (update daily or pull from parbs_master_analysis) ──────
DEF_RATINGS = {
    'OKC': 104.9, 'SAS': 108.5, 'BOS': 109.8, 'GSW': 111.1,
    'LAL': 114.4, 'CHI': 115.1, 'UTA': 119.1, 'WAS': 117.8,
    'SAC': 117.6, 'CHO': 112.9, 'NOP': 115.3, 'DET': 121.2,
    'MIL': 118.2, 'ATL': 119.5, 'MIN': 110.3, 'DAL': 113.7,
    'PHX': 116.2, 'DEN': 112.8, 'MEM': 115.9, 'NYK': 111.6,
    'IND': 117.4, 'CLE': 109.1, 'MIA': 113.3, 'ORL': 108.7,
    'TOR': 118.8, 'BKN': 120.1, 'PHI': 114.6, 'WAS': 121.0,
    'POR': 119.3, 'HOU': 116.7, 'NOP': 115.3,
}

# Timezone buckets for travel distance estimation
TEAM_TIMEZONE = {
    'BOS': 'ET', 'NYK': 'ET', 'BKN': 'ET', 'PHI': 'ET', 'TOR': 'ET',
    'MIA': 'ET', 'ORL': 'ET', 'ATL': 'ET', 'CLE': 'ET', 'DET': 'ET',
    'IND': 'ET', 'MIL': 'CT', 'CHI': 'CT', 'MEM': 'CT', 'NOP': 'CT',
    'SAS': 'CT', 'HOU': 'CT', 'DAL': 'CT', 'MIN': 'CT', 'OKC': 'CT',
    'DEN': 'MT', 'UTA': 'MT', 'PHX': 'MT',
    'LAL': 'PT', 'LAC': 'PT', 'GSW': 'PT', 'SAC': 'PT', 'POR': 'PT',
}

MODEL_PATH = "models/prop_model.keras"
SCALER_PATH = "models/scaler.pkl"
TARGET_COLS = ["PTS", "REB", "AST"]
MIN_GAMES = 10  # minimum game history to include a player

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def extract_opponent(matchup: str, home_team: str) -> str:
    """Pull opponent abbreviation from MATCHUP string like 'CHI vs. GSW'."""
    if not isinstance(matchup, str):
        return "AVG"
    parts = matchup.upper().replace("VS.", "VS").replace("@", "VS").split("VS")
    teams = [p.strip() for p in parts if p.strip()]
    for t in teams:
        if t != home_team.upper():
            return t
    return "AVG"

def is_away(matchup: str) -> int:
    """1 if away game (@), 0 if home."""
    return 1 if isinstance(matchup, str) and "@" in matchup else 0

def travel_stress(prev_matchup: str, curr_matchup: str, team: str) -> int:
    """
    1 if player crossed a timezone boundary between games.
    Proxy for travel fatigue — cross-timezone road trips hit performance.
    """
    prev_opp = extract_opponent(prev_matchup, team)
    curr_opp = extract_opponent(curr_matchup, team)
    prev_tz = TEAM_TIMEZONE.get(prev_opp, "CT")
    curr_tz = TEAM_TIMEZONE.get(curr_opp, "CT")
    return 0 if prev_tz == curr_tz else 1

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a player's full game log (sorted oldest→newest) and returns
    a row-per-game feature matrix ready for training or inference.
    """
    df = df.copy().sort_values("GAME_DATE").reset_index(drop=True)

    # ── Ensure required columns exist ────────────────────────────────────────
    for col in ["PTS", "REB", "AST", "FGA", "FTA", "MIN"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "PLUS_MINUS" not in df.columns:
        df["PLUS_MINUS"] = 0.0
    df["PLUS_MINUS"] = pd.to_numeric(df["PLUS_MINUS"], errors="coerce").fillna(0)

    if "MATCHUP" not in df.columns:
        df["MATCHUP"] = ""
    if "TEAM_ABBREVIATION" not in df.columns:
        df["TEAM_ABBREVIATION"] = "CHI"

    # ── TS% per game ─────────────────────────────────────────────────────────
    denom = 2 * (df["FGA"] + 0.44 * df["FTA"])
    df["TS_PCT"] = np.where(denom > 0, df["PTS"] / denom, 0)

    # ── Days rest ─────────────────────────────────────────────────────────────
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
    df["DAYS_REST"] = df["GAME_DATE"].diff().dt.days.fillna(3).clip(upper=10)

    # ── Back-to-back flag ─────────────────────────────────────────────────────
    df["IS_B2B"] = (df["DAYS_REST"] == 1).astype(int)

    # ── Travel stress ─────────────────────────────────────────────────────────
    team = df["TEAM_ABBREVIATION"].iloc[0] if len(df) > 0 else "CHI"
    df["TRAVEL"] = 0
    for i in range(1, len(df)):
        df.loc[i, "TRAVEL"] = travel_stress(
            df.loc[i - 1, "MATCHUP"], df.loc[i, "MATCHUP"], team
        )

    # ── Home / Away ───────────────────────────────────────────────────────────
    df["IS_AWAY"] = df["MATCHUP"].apply(is_away)

    # ── Opponent defensive rating ─────────────────────────────────────────────
    df["OPP_DRTG"] = df.apply(
        lambda r: DEF_RATINGS.get(
            extract_opponent(r["MATCHUP"], r["TEAM_ABBREVIATION"]), 114.0
        ),
        axis=1,
    )

    # ── Rolling 5-game averages ───────────────────────────────────────────────
    for col in ["PTS", "REB", "AST", "FGA", "FTA", "MIN", "TS_PCT", "PLUS_MINUS"]:
        df[f"ROLL5_{col}"] = (
            df[col].shift(1).rolling(5, min_periods=1).mean().fillna(df[col].mean())
        )

    # ── Season average up to that game (expanding) ────────────────────────────
    for col in ["PTS", "REB", "AST", "TS_PCT"]:
        df[f"SSN_AVG_{col}"] = df[col].shift(1).expanding().mean().fillna(df[col].mean())

    # ── TS% delta: recent form vs season baseline ─────────────────────────────
    df["TS_DELTA"] = df["ROLL5_TS_PCT"] - df["SSN_AVG_TS_PCT"]

    return df

FEATURE_COLS = [
    "ROLL5_PTS", "ROLL5_REB", "ROLL5_AST",
    "ROLL5_FGA", "ROLL5_FTA", "ROLL5_MIN",
    "ROLL5_TS_PCT", "ROLL5_PLUS_MINUS",
    "SSN_AVG_PTS", "SSN_AVG_REB", "SSN_AVG_AST",
    "TS_DELTA",
    "IS_B2B", "TRAVEL", "IS_AWAY",
    "OPP_DRTG", "DAYS_REST",
]

# ─────────────────────────────────────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────────────────────────────────────

def build_model(input_dim: int) -> "tf.keras.Model":
    import tensorflow as tf
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(len(TARGET_COLS)),  # PTS, REB, AST
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="huber",          # robust to outliers (blowout games, injuries)
        metrics=["mae"],
    )
    return model

# ─────────────────────────────────────────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────────────────────────────────────────

def train(master_csv: str = "Bulls_Master_2026.csv"):
    import tensorflow as tf
    import pickle
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split

    print("\n" + "="*60)
    print("  🧠 TF PROP MODEL — TRAINING")
    print("="*60)

    df_raw = pd.read_csv(master_csv)
    df_raw.columns = [c.upper() for c in df_raw.columns]
    df_raw["GAME_DATE"] = pd.to_datetime(df_raw["GAME_DATE"], errors="coerce")
    df_raw = df_raw.dropna(subset=["GAME_DATE", "PLAYER_NAME"])

    all_X, all_y = [], []

    for player, group in df_raw.groupby("PLAYER_NAME"):
        if len(group) < MIN_GAMES:
            continue
        feat_df = build_features(group)
        feat_df = feat_df.dropna(subset=FEATURE_COLS + TARGET_COLS)
        if len(feat_df) < MIN_GAMES:
            continue
        all_X.append(feat_df[FEATURE_COLS].values)
        all_y.append(feat_df[TARGET_COLS].values)
        print(f"  ✅ {player}: {len(feat_df)} training rows")

    if not all_X:
        print("❌ Not enough data to train. Run daily_refresh.py first.")
        return

    X = np.vstack(all_X).astype(np.float32)
    y = np.vstack(all_y).astype(np.float32)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_val, y_train, y_val = train_test_split(
        X_scaled, y, test_size=0.15, random_state=42
    )

    model = build_model(X.shape[1])

    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=15, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(patience=7, factor=0.5, verbose=0),
    ]

    print(f"\n  Training on {len(X_train)} samples, validating on {len(X_val)}...")
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=150,
        batch_size=32,
        callbacks=callbacks,
        verbose=1,
    )

    os.makedirs("models", exist_ok=True)
    model.save(MODEL_PATH)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    val_loss, val_mae = model.evaluate(X_val, y_val, verbose=0)
    print(f"\n  📊 Validation MAE: {val_mae:.2f} | Loss: {val_loss:.4f}")
    print(f"  💾 Model saved → {MODEL_PATH}")
    return model, scaler

# ─────────────────────────────────────────────────────────────────────────────
# PREDICT
# ─────────────────────────────────────────────────────────────────────────────

def predict(master_csv: str = "Bulls_Master_2026.csv"):
    import tensorflow as tf
    import pickle

    print("\n" + "="*60)
    print("  🔮 TF PROP MODEL — NEXT GAME PREDICTIONS")
    print("="*60)

    if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
        print("  ⚠️  No saved model found. Training first...")
        result = train(master_csv)
        if result is None:
            return
        model, scaler = result
    else:
        model = tf.keras.models.load_model(MODEL_PATH)
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)

    df_raw = pd.read_csv(master_csv)
    df_raw.columns = [c.upper() for c in df_raw.columns]
    df_raw["GAME_DATE"] = pd.to_datetime(df_raw["GAME_DATE"], errors="coerce")
    df_raw = df_raw.dropna(subset=["GAME_DATE", "PLAYER_NAME"])

    results = []

    for player, group in df_raw.groupby("PLAYER_NAME"):
        if len(group) < 5:
            continue

        feat_df = build_features(group)
        feat_df = feat_df.dropna(subset=FEATURE_COLS)
        if feat_df.empty:
            continue

        # Use the LAST row as the "next game" feature vector
        last_row = feat_df.iloc[-1]
        X_input = scaler.transform([last_row[FEATURE_COLS].values.astype(np.float32)])
        pred = model.predict(X_input, verbose=0)[0]

        pred_pts, pred_reb, pred_ast = pred[0], pred[1], pred[2]

        # ── Context flags for the prediction ─────────────────────────────────
        is_b2b    = int(last_row["IS_B2B"])
        is_travel = int(last_row["TRAVEL"])
        days_rest = int(last_row["DAYS_REST"])
        opp_drtg  = round(last_row["OPP_DRTG"], 1)
        ts_delta  = round(last_row["TS_DELTA"] * 100, 1)

        # ── Confidence signal ─────────────────────────────────────────────────
        # Penalise predictions when fatigue/travel flags are active
        fatigue_penalty = (is_b2b * 1.5) + (is_travel * 1.0)
        boost = max(0, (opp_drtg - 114) * 0.15)   # weak defense = upside
        confidence = round(min(99, max(50, 75 - fatigue_penalty * 5 + boost + ts_delta * 0.3)), 1)

        if is_b2b and is_travel:
            signal = "⚠️  HIGH RISK (B2B + Travel)"
        elif is_b2b:
            signal = "😴 FADE (Back-to-Back)"
        elif is_travel:
            signal = "✈️  CAUTION (Travel)"
        elif confidence >= 80 and opp_drtg > 116:
            signal = "🔥 SMASH (Weak D + Fresh)"
        elif confidence >= 75:
            signal = "✅ PLAY (Solid)"
        else:
            signal = "➡️  STEADY"

        results.append({
            "Player":       player,
            "Pred_PTS":     round(pred_pts, 1),
            "Pred_REB":     round(pred_reb, 1),
            "Pred_AST":     round(pred_ast, 1),
            "Confidence":   f"{confidence}%",
            "Signal":       signal,
            "B2B":          "YES" if is_b2b else "no",
            "Travel":       "YES" if is_travel else "no",
            "Days_Rest":    days_rest,
            "Opp_DRtg":     opp_drtg,
            "TS_Delta":     f"{ts_delta:+.1f}%",
        })

    if not results:
        print("  ❌ No predictions generated. Check your master CSV.")
        return

    out = pd.DataFrame(results).sort_values("Pred_PTS", ascending=False)

    print("\n" + "="*100)
    print(f"  PARB'S TF PROP PREDICTIONS — {date.today()}")
    print("="*100)
    print(out.to_string(index=False))
    print("="*100)
    print("  B2B/Travel flags reduce confidence. Opp_DRtg > 116 = weak defense = upside.")

    out.to_csv("tf_prop_predictions.csv", index=False)
    print(f"\n  💾 Saved → tf_prop_predictions.csv")
    return out

# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    predict_only = "--predict-only" in sys.argv

    if predict_only:
        predict()
    else:
        train()
        predict()
