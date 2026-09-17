
from pathlib import Path
from datetime import datetime
import json
import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODEL_DIR = HERE / "models"

MATCH_MODEL_PATH = MODEL_DIR / "match_winner_model.joblib"
PLAYER_MODEL_PATH = MODEL_DIR / "top_player_model.joblib"
METADATA_PATH = MODEL_DIR / "model_metadata.json"
MATCH_CONTEXT_PATH = MODEL_DIR / "match_context.csv"
TEAM_CONTEXT_PATH = MODEL_DIR / "team_context_history.csv"
PLAYER_CONTEXT_PATH = MODEL_DIR / "player_context_history.csv"

class AFLPredictionError(ValueError):
    pass

def _load():
    for p in [MATCH_MODEL_PATH, PLAYER_MODEL_PATH, METADATA_PATH,
              MATCH_CONTEXT_PATH, TEAM_CONTEXT_PATH, PLAYER_CONTEXT_PATH]:
        if not p.exists():
            raise FileNotFoundError(
                f"Required model/context file is missing: {p}. "
                "Run the Week 3 Day 2 notebook packaging cell first."
            )
    return (
        joblib.load(MATCH_MODEL_PATH),
        joblib.load(PLAYER_MODEL_PATH),
        json.loads(METADATA_PATH.read_text()),
        pd.read_csv(MATCH_CONTEXT_PATH, parse_dates=["match_date"]),
        pd.read_csv(TEAM_CONTEXT_PATH, parse_dates=["last_match_date"]),
        pd.read_csv(PLAYER_CONTEXT_PATH, parse_dates=["match_date"]),
    )

def _validate_date(date):
    try:
        parsed = pd.Timestamp(date)
    except Exception as exc:
        raise AFLPredictionError(
            f"Invalid date '{date}'. Use YYYY-MM-DD."
        ) from exc

    if pd.isna(parsed):
        raise AFLPredictionError(
            f"Invalid date '{date}'. Use YYYY-MM-DD."
        )

    return parsed.normalize()

def _validate_teams(team_a, team_b, team_context):
    teams = set(team_context["team_clean"].dropna().astype(str))
    if team_a not in teams:
        raise AFLPredictionError(
            f"Unknown team '{team_a}'. Check the normalized AFL team name."
        )
    if team_b not in teams:
        raise AFLPredictionError(
            f"Unknown team '{team_b}'. Check the normalized AFL team name."
        )
    if team_a == team_b:
        raise AFLPredictionError("team_a and team_b must be different teams.")

def _latest_team_row(team, date, team_context):
    rows = team_context[
        (team_context["team_clean"] == team)
        & (team_context["last_match_date"] < date)
    ].sort_values("last_match_date")
    if rows.empty:
        raise AFLPredictionError(
            f"No historical context exists for '{team}' before {date.date()}."
        )
    return rows.iloc[-1]

def _build_future_match_row(team_a, team_b, date, match_context, team_context):
    exact = match_context[
        (match_context["match_date"] == date)
        & (match_context["home_team"] == team_a)
        & (match_context["away_team"] == team_b)
    ]
    if not exact.empty:
        return exact.iloc[0].to_dict()

    h = _latest_team_row(team_a, date, team_context)
    a = _latest_team_row(team_b, date, team_context)

    row = {
        "year": date.year,
        "round": "UNKNOWN",
        "venue": "UNKNOWN",
        "home_team": team_a,
        "away_team": team_b,
        "home_prior_win_rate_5": h["prior_win_rate_5"],
        "away_prior_win_rate_5": a["prior_win_rate_5"],
        "home_prior_score_avg_5": h["prior_score_avg_5"],
        "away_prior_score_avg_5": a["prior_score_avg_5"],
        "home_prior_margin_avg_5": h["prior_margin_avg_5"],
        "away_prior_margin_avg_5": a["prior_margin_avg_5"],
        "home_days_rest": (date - pd.Timestamp(h["last_match_date"])).days,
        "away_days_rest": (date - pd.Timestamp(a["last_match_date"])).days,
        "home_prior_win_streak": h["prior_win_streak"],
        "away_prior_win_streak": a["prior_win_streak"],
        "home_prior_ladder_points": h["prior_ladder_points"],
        "away_prior_ladder_points": a["prior_ladder_points"],
        "home_prior_ladder_pct": h["prior_ladder_pct"],
        "away_prior_ladder_pct": a["prior_ladder_pct"],
        "home_prior_ladder_rank": h["prior_ladder_rank"],
        "away_prior_ladder_rank": a["prior_ladder_rank"],
        "home_prior_h2h_team_wins": 0,
        "away_prior_h2h_team_wins": 0,
        "home_prior_h2h_games": 0,
        "away_prior_h2h_games": 0,
        "home_player_disposals_5_mean": np.nan,
        "home_player_disposals_5_max": np.nan,
        "home_player_goals_5_mean": np.nan,
        "home_player_goals_5_max": np.nan,
        "home_player_fantasy_5_mean": np.nan,
        "home_player_fantasy_5_max": np.nan,
        "away_player_disposals_5_mean": np.nan,
        "away_player_disposals_5_max": np.nan,
        "away_player_goals_5_mean": np.nan,
        "away_player_goals_5_max": np.nan,
        "away_player_fantasy_5_mean": np.nan,
        "away_player_fantasy_5_max": np.nan,
    }

    row["form_diff_5"] = row["home_prior_win_rate_5"] - row["away_prior_win_rate_5"]
    row["score_avg_diff_5"] = row["home_prior_score_avg_5"] - row["away_prior_score_avg_5"]
    row["margin_avg_diff_5"] = row["home_prior_margin_avg_5"] - row["away_prior_margin_avg_5"]
    row["rest_diff"] = row["home_days_rest"] - row["away_days_rest"]
    row["ladder_points_diff"] = row["home_prior_ladder_points"] - row["away_prior_ladder_points"]
    row["ladder_rank_diff"] = row["away_prior_ladder_rank"] - row["home_prior_ladder_rank"]
    row["player_disposals_form_diff"] = np.nan
    row["player_goals_form_diff"] = np.nan
    row["player_fantasy_form_diff"] = np.nan
    return row

def predict_match_winner(team_a, team_b, date):
    """Predict team_a as home vs team_b as away.

    Returns a dict with the predicted winner, class probabilities,
    and the model's confidence. For dates not already in the historical
    match table, the function uses the latest pre-date team context.
    """
    match_model, _, metadata, match_context, team_context, _ = _load()
    date = _validate_date(date)
    _validate_teams(team_a, team_b, team_context)

    row = _build_future_match_row(
        team_a, team_b, date, match_context, team_context
    )
    cols = metadata["match_features"]
    X = pd.DataFrame([row])[cols]

    probs = match_model.predict_proba(X)[0]
    classes = list(match_model.classes_)
    best_idx = int(np.argmax(probs))

    return {
        "winner": classes[best_idx],
        "probability": float(probs[best_idx]),
        "probabilities": {
            cls: float(prob) for cls, prob in zip(classes, probs)
        },
        "team_a": team_a,
        "team_b": team_b,
        "date": str(date.date()),
    }

def predict_top_player(
    team_a,
    team_b,
    date,
    stat_type="disposals",
    top_k=5,
    candidate_player_ids=None,
):
    """Rank likely top players for the upcoming team_a vs team_b match.

    The trained model predicts next-match disposals. Candidate players can
    be supplied explicitly; otherwise the latest pre-date player contexts
    for both teams are used. Explicit candidates are recommended when
    confirmed line-ups are available.
    """
    if stat_type != "disposals":
        raise AFLPredictionError(
            "This Week 3 model currently supports stat_type='disposals' only."
        )
    if not isinstance(top_k, int) or top_k < 1:
        raise AFLPredictionError("top_k must be a positive integer.")

    match_model, player_model, metadata, match_context, team_context, player_context = _load()
    date = _validate_date(date)
    _validate_teams(team_a, team_b, team_context)

    match_row = _build_future_match_row(
        team_a, team_b, date, match_context, team_context
    )

    pc = player_context[
        (player_context["match_date"] < date)
        & (player_context["team_clean"].isin([team_a, team_b]))
    ].sort_values("match_date")

    if candidate_player_ids is not None:
        ids = set(candidate_player_ids)
        known_ids = set(player_context["player_id"].dropna().astype(int))
        unknown_ids = sorted(int(pid) for pid in ids if int(pid) not in known_ids)
        if unknown_ids:
            raise AFLPredictionError(
                f"Unknown player_id(s): {unknown_ids}."
            )

        pc = pc[pc["player_id"].isin(ids)]
        if pc.empty:
            raise AFLPredictionError(
                "The supplied player_id(s) are known, but none has usable "
                f"pre-date historical context before {date.date()}."
            )

    latest = pc.groupby("player_id", as_index=False).tail(1).copy()
    latest["home_team"] = team_a
    latest["away_team"] = team_b
    latest["year"] = date.year
    latest["round"] = "UNKNOWN"
    latest["venue"] = "UNKNOWN"
    latest["is_home_player"] = (latest["team_clean"] == team_a).astype(int)

    for c in [
        "home_prior_win_rate_5", "away_prior_win_rate_5",
        "home_prior_score_avg_5", "away_prior_score_avg_5",
        "home_prior_margin_avg_5", "away_prior_margin_avg_5",
        "home_days_rest", "away_days_rest",
        "home_prior_win_streak", "away_prior_win_streak",
        "home_prior_ladder_points", "away_prior_ladder_points",
        "home_prior_ladder_pct", "away_prior_ladder_pct",
        "home_prior_ladder_rank", "away_prior_ladder_rank",
        "home_prior_h2h_team_wins", "away_prior_h2h_team_wins",
        "home_prior_h2h_games", "away_prior_h2h_games",
        "form_diff_5", "score_avg_diff_5", "margin_avg_diff_5",
        "rest_diff", "ladder_points_diff", "ladder_rank_diff",
        "home_player_disposals_5_mean", "home_player_disposals_5_max",
        "home_player_goals_5_mean", "home_player_goals_5_max",
        "home_player_fantasy_5_mean", "home_player_fantasy_5_max",
        "away_player_disposals_5_mean", "away_player_disposals_5_max",
        "away_player_goals_5_mean", "away_player_goals_5_max",
        "away_player_fantasy_5_mean", "away_player_fantasy_5_max",
        "player_disposals_form_diff", "player_goals_form_diff",
        "player_fantasy_form_diff",
    ]:
        latest[c] = match_row.get(c, np.nan)

    # Preserve player-specific team/form columns after assigning match context.
    # The model needs these values from each player's prior context.
    feature_cols = metadata["player_features"]
    X = latest[feature_cols]
    latest["predicted_disposals"] = player_model.predict(X)

    latest = latest.sort_values(
        "predicted_disposals", ascending=False
    ).head(top_k)

    name_map = {}
    if "player_name" in latest.columns:
        name_map = latest.set_index("player_id")["player_name"].to_dict()

    results = []
    for _, r in latest.iterrows():
        results.append({
            "player_id": int(r["player_id"]),
            "player_name": name_map.get(r["player_id"]),
            "team": r["team_clean"],
            "predicted_disposals": float(r["predicted_disposals"]),
        })

    return results
