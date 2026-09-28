
from __future__ import annotations
from pathlib import Path
import json, joblib, numpy as np, pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor

MATCH_FEATURES = [
"home_win_rate_last3","away_win_rate_last3","home_win_rate_last5","away_win_rate_last5",
"home_avg_score_last5","away_avg_score_last5","home_avg_margin_last5","away_avg_margin_last5",
"home_win_streak_before","away_win_streak_before","home_days_rest","away_days_rest",
"h2h_home_win_rate_before","h2h_games_before","home_ladder_pos_before","away_ladder_pos_before",
"ladder_pos_diff","form_win_rate_diff","avg_score_diff_last5","avg_margin_diff_last5","rest_diff_days"
]
ROOT = Path(__file__).resolve().parents[1]

class MatchPredictor:
    def __init__(self, model_dir: Path):
        self.model = joblib.load(model_dir/"match_winner_model.joblib")
        self.feature_table = pd.read_csv(model_dir/"feature_table.csv", parse_dates=["match_date"])
        self.teams = sorted(set(self.feature_table.home_team) | set(self.feature_table.away_team))

    def _features(self, home, away, date):
        d = pd.Timestamp(date)
        hist = self.feature_table[self.feature_table.match_date < d]
        def side(team):
            rows = hist[(hist.home_team==team)|(hist.away_team==team)].sort_values("match_date")
            rows = rows.tail(5)
            if rows.empty: raise ValueError("No prior team history.")
            wins = []
            scores, margins, rest = [], [], []
            for _,r in rows.iterrows():
                is_home = r.home_team == team
                res = r.match_result
                wins.append(1 if (is_home and res=="W") or ((not is_home) and res=="L") else 0)
                scores.append(r.home_avg_score_last5 if is_home else r.away_avg_score_last5)
                margins.append(r.home_avg_margin_last5 if is_home else r.away_avg_margin_last5)
                rest.append(r.home_days_rest if is_home else r.away_days_rest)
            prior = rows.iloc[-1]
            ladder = prior.home_ladder_pos_before if prior.home_team==team else prior.away_ladder_pos_before
            return {"win_rate":float(np.mean(wins)),"score":float(np.nanmean(scores)),
                    "margin":float(np.nanmean(margins)),"rest":float(np.nanmean(rest)),
                    "ladder":float(ladder)}
        h,a = side(home),side(away)
        # H2H before date
        pair = hist[((hist.home_team==home)&(hist.away_team==away))|((hist.home_team==away)&(hist.away_team==home))]
        h2h = []
        for _,r in pair.iterrows():
            if (r.home_team==home and r.match_result=="W") or (r.away_team==home and r.match_result=="L"): h2h.append(1)
            elif r.match_result=="D": h2h.append(.5)
            else: h2h.append(0)
        return pd.DataFrame([{
            "home_win_rate_last3":h["win_rate"],"away_win_rate_last3":a["win_rate"],
            "home_win_rate_last5":h["win_rate"],"away_win_rate_last5":a["win_rate"],
            "home_avg_score_last5":h["score"],"away_avg_score_last5":a["score"],
            "home_avg_margin_last5":h["margin"],"away_avg_margin_last5":a["margin"],
            "home_win_streak_before":0,"away_win_streak_before":0,
            "home_days_rest":h["rest"],"away_days_rest":a["rest"],
            "h2h_home_win_rate_before":float(np.mean(h2h)) if h2h else .5,
            "h2h_games_before":len(h2h),
            "home_ladder_pos_before":h["ladder"],"away_ladder_pos_before":a["ladder"],
            "ladder_pos_diff":h["ladder"]-a["ladder"],
            "form_win_rate_diff":h["win_rate"]-a["win_rate"],
            "avg_score_diff_last5":h["score"]-a["score"],
            "avg_margin_diff_last5":h["margin"]-a["margin"],
            "rest_diff_days":h["rest"]-a["rest"],
        }], columns=MATCH_FEATURES)

    def predict(self, home, away, date):
        X=self._features(home,away,date)
        probs=self.model.predict_proba(X)[0]
        classes=list(self.model.classes_)
        ix=int(np.argmax(probs))
        label=classes[ix]
        return {"predicted_label":label,"probability":float(probs[ix]),
                "probabilities":{c:float(p) for c,p in zip(classes,probs)},
                "key_inputs":["recent five-game win rate","pre-match ladder position","recent scoring/margin form"]}

class PlayerPredictor:
    def __init__(self, model_dir: Path):
        self.model=joblib.load(model_dir/"player_disposals_model.joblib")
        self.players=pd.read_csv(model_dir/"player_candidates.csv",parse_dates=["match_date"])
    def predict(self, home, away, date, top_k=5):
        d=pd.Timestamp(date)
        p=self.players[self.players.match_date<d]
        p=p[(p.team==home)|(p.team==away)].sort_values("match_date").groupby("player_id").tail(1)
        if p.empty: raise ValueError("No player history before requested date.")
        X=p[["prior_disposals","prior_avg_disposals5","prior_avg_fantasy5"]]
        p=p.copy(); p["predicted_disposals"]=self.model.predict(X)
        top=p.sort_values("predicted_disposals",ascending=False).head(top_k)
        return {"stat":"disposals","players":[{"player_id":int(r.player_id),"team":r.team,
                 "predicted_disposals":round(float(r.predicted_disposals),2)} for _,r in top.iterrows()],
                "disclaimer":"Predicted probability, not a certainty."}
