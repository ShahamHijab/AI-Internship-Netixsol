
from pathlib import Path
import json, zipfile, shutil
import pandas as pd, numpy as np, joblib
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, f1_score

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"/"afl_datasets.zip"
OUT=ROOT/"models"; OUT.mkdir(exist_ok=True)
FEATURES=["home_win_rate_last3","away_win_rate_last3","home_win_rate_last5","away_win_rate_last5","home_avg_score_last5","away_avg_score_last5","home_avg_margin_last5","away_avg_margin_last5","home_win_streak_before","away_win_streak_before","home_days_rest","away_days_rest","h2h_home_win_rate_before","h2h_games_before","home_ladder_pos_before","away_ladder_pos_before","ladder_pos_diff","form_win_rate_diff","avg_score_diff_last5","avg_margin_diff_last5","rest_diff_days"]

def train():
    ft=ROOT/"data"/"Week3_Day1_feature_table_v1.csv"
    if not ft.exists():
        with zipfile.ZipFile(DATA) as z:
            # This file is optional in the distribution; the repository ships a copy.
            raise FileNotFoundError("Missing data/Week3_Day1_feature_table_v1.csv")
    df=pd.read_csv(ft,parse_dates=["match_date"])
    tr=df[df.year<2025]; ho=df[df.year==2025]
    model=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),LogisticRegression(max_iter=2000))
    model.fit(tr[FEATURES],tr.match_result)
    pred=model.predict(ho[FEATURES])
    ladder=np.where(ho.home_ladder_pos_before<ho.away_ladder_pos_before,"W",
                    np.where(ho.home_ladder_pos_before>ho.away_ladder_pos_before,"L","W"))
    metrics={"holdout_year":2025,"n":len(ho),"accuracy":accuracy_score(ho.match_result,pred),
             "macro_f1":f1_score(ho.match_result,pred,average="macro"),
             "ladder_baseline_accuracy":accuracy_score(ho.match_result,ladder)}
    joblib.dump(model,OUT/"match_winner_model.joblib")
    df.to_csv(OUT/"feature_table.csv",index=False)
    (OUT/"metrics.json").write_text(json.dumps(metrics,indent=2))
    # Player fallback model
    with zipfile.ZipFile(DATA) as z:
        rf=next(x for x in z.namelist() if "round_by_round" in x and x.endswith(".csv"))
        rs=pd.read_csv(z.open(rf),low_memory=False)
    rs["match_date"]=pd.to_datetime(rs.match_date,errors="coerce")
    rs=rs.dropna(subset=["player_id","match_date"]).sort_values(["player_id","match_date","id"])
    rs["prior_disposals"]=rs.groupby("player_id").disposals.shift(1)
    rs["prior_avg_disposals5"]=rs.groupby("player_id").disposals.transform(lambda s:s.shift(1).rolling(5,min_periods=1).mean())
    rs["prior_avg_fantasy5"]=rs.groupby("player_id").fantasy_points.transform(lambda s:s.shift(1).rolling(5,min_periods=1).mean())
    p=rs.dropna(subset=["disposals","prior_disposals","prior_avg_disposals5","prior_avg_fantasy5"]).copy()
    ptrain=p[p.match_date.dt.year<2025]
    preg=make_pipeline(SimpleImputer(strategy="median"),HistGradientBoostingRegressor(max_iter=200,learning_rate=.05,random_state=42))
    preg.fit(ptrain[["prior_disposals","prior_avg_disposals5","prior_avg_fantasy5"]],ptrain.disposals)
    joblib.dump(preg,OUT/"player_disposals_model.joblib")
    p[["player_id","team","match_date","prior_disposals","prior_avg_disposals5","prior_avg_fantasy5"]].to_csv(OUT/"player_candidates.csv",index=False)
    return metrics

if __name__=="__main__":
    print(train())
