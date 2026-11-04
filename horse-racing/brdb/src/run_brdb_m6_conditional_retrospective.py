#!/usr/bin/env python3
"""Conditional retrospective blood-feature study. Not a pre-race frozen forecast.

Requires Python packages duckdb, pandas, numpy, scikit-learn. All JRDB-derived
row-level inputs and predictions MUST stay outside the GitHub repository.
Preconditions: provider equivalence is a stated assumption, NOT byte attestation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time

VERSION = "brdb-m6-conditional-retrospective-paired-v0.1"
SEED = 26041104
BASE = ["venue_code","surface_code","distance_band","race_class_code","horse_no_cat","month"]
BLOOD = ["sire_line_code","broodmare_sire_line_code"]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(1<<20),b""):h.update(part)
    return h.hexdigest()

def read_join(mart,history):
    import duckdb
    db=duckdb.connect()
    try:
        db.execute("CREATE TEMP VIEW mart AS SELECT * FROM read_parquet(?)",[str(mart)])
    except Exception:
        # DuckDB v1.1 binds table-function arguments only in direct SQL calls.
        db.execute(f"CREATE TEMP VIEW mart AS SELECT * FROM read_parquet('{str(mart).replace(chr(39),chr(39)*2)}')")
    db.execute(f"CREATE TEMP VIEW history AS SELECT * FROM read_csv_auto('{str(history).replace(chr(39),chr(39)*2)}', all_varchar=true, header=true)")
    result=db.execute("""SELECT m.race_year,m.race_key,m.horse_no,m.horse_id,m.race_date,
      m.abnormal_code,m.winner,m.normal_finisher,m.venue_code,m.surface_code,
      m.distance_m,m.race_class_code,h.sire_line_code,h.broodmare_sire_line_code,
      h.selection_method,h.ukc_data_date
      FROM mart m JOIN history h ON m.race_key=h.race_key
      AND m.horse_no=CAST(h.horse_no AS BIGINT) AND m.horse_id=h.horse_id
      AND m.race_date=h.target_date""").fetchdf()
    db.close()
    return result

def prep(df):
    import pandas as pd
    if len(df)!=481503 or df.duplicated(["race_key","horse_no"]).any():
        raise ValueError("historical joined candidate differs from pinned M6 scope")
    if (df.ukc_data_date>df.race_date).any():
        raise ValueError("UKC member from future day")
    df=df[df.abnormal_code.isin(["0","1"])].copy()
    byrace=df.groupby("race_key")
    win=byrace["winner"].sum()
    counts=byrace["horse_no"].count()
    permitted=win.index[(win==1)&(counts>=2)]
    df=df[df.race_key.isin(permitted)].copy()
    df["horse_no_cat"]=df.horse_no.astype(int).astype(str)
    df["distance_band"]=((df.distance_m.astype(int)//200)*200).astype(str)
    df["month"]=df.race_date.str.slice(4,6)
    for c in BASE+BLOOD:
        df[c]=df[c].fillna("UNKNOWN").astype(str).replace({"":"UNKNOWN"})
    df["winner"]=df.winner.astype(int)
    return df

def fit_predict(train,test,columns):
    import numpy as np
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    model=Pipeline([("prep",ColumnTransformer([("onehot",OneHotEncoder(handle_unknown="ignore",dtype=np.float64),columns)],remainder="drop")),
                    ("lr",LogisticRegression(C=1.0,solver="liblinear",max_iter=110,tol=1e-4,random_state=SEED))])
    model.fit(train[columns],train.winner)
    return model.predict_proba(test[columns])[:,1]

def losses(df):
    import numpy as np
    y=df.winner.to_numpy(float)
    p0=np.clip(df.p_base.to_numpy(),1e-8,1-1e-8)
    p1=np.clip(df.p_blood.to_numpy(),1e-8,1-1e-8)
    log0=-(y*np.log(p0)+(1-y)*np.log1p(-p0))
    log1=-(y*np.log(p1)+(1-y)*np.log1p(-p1))
    return log0,log1,(y-p0)**2,(y-p1)**2

def score(df):
    import numpy as np
    l0,l1,b0,b1=losses(df)
    return {"entries":len(df),"races":int(df.race_key.nunique()),
            "base_log_loss":float(np.mean(l0)),"blood_log_loss":float(np.mean(l1)),
            "delta_blood_minus_base":float(np.mean(l1-l0)),
            "base_brier":float(np.mean(b0)),"blood_brier":float(np.mean(b1)),
            "delta_brier":float(np.mean(b1-b0))}

def cluster_ci(df,column,reps=800):
    import numpy as np
    import pandas as pd
    l0,l1,_,_=losses(df)
    codes,ids=pd.factorize(df[column],sort=True)
    n=len(ids)
    sums=np.bincount(codes,weights=l1-l0,minlength=n)
    sizes=np.bincount(codes,minlength=n)
    rng=np.random.default_rng(SEED+n)
    estimates=np.empty(reps)
    for i in range(reps):
        weights=rng.multinomial(n,np.full(n,1/n))
        estimates[i]=weights@sums/(weights@sizes)
    return {"clusters":n,"replicates":reps,
            "ci95_quantile":[float(v) for v in np.quantile(estimates,[.025,.975])],
            "bootstrap_mean":float(estimates.mean())}

def run(mart,history,out,mart_sha,history_sha):
    import pandas as pd
    start=time.monotonic()
    if digest(mart)!=mart_sha or digest(history)!=history_sha:
        raise ValueError("source SHA mismatch; do not run on changed private inputs")
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    data=prep(read_join(mart,history))
    if len(data)!=477506 or data.race_key.nunique()!=34482:
        raise ValueError("predeclared winner and actual starter eligibility changed")
    report={"version":VERSION,"status":"PASS_CONDITIONAL_RETROSPECTIVE_ONLY",
      "prediction_safe":False,"provider_equivalence":"USER_REPORTED_EQUIVALENCE_ASSUMED_NOT_INDEPENDENT_BYTE_ATTESTATION",
      "historical_independently_asof_attested_rows":0,
      "source_sha256":{"mart":mart_sha,"ukc_kyi_candidate_gzip":history_sha},
      "baseline_features":BASE,"challenger_extra_features":BLOOD,
      "model":"scikit-learn LogisticRegression(liblinear, C=1, OneHotEncoder, train years only)",
      "denominator":"actual starters abnormal 0 and 1; drop races with non-unique winner or fewer than 2 starters",
      "cohort":{"mart_rows":481627,"candidate_matched_rows":481503,"eligible_starter_rows":len(data),
                "eligible_races":int(data.race_key.nunique()),"unmatched_join_rows":124},
      "caution":"Retrospective newly trained predictions are NOT RaceNote pre-race Prediction Freeze; no prospective P1-7 uplift proven.",
      "folds":[]}
    preds=[]
    for yr in range(2021,2026):
        train=data[data.race_year<yr]
        test=data[data.race_year==yr].copy()
        test["p_base"]=fit_predict(train,test,BASE)
        test["p_blood"]=fit_predict(train,test,BASE+BLOOD)
        metric=score(test)
        metric.update({"test_year":yr,"train_year_min":int(train.race_year.min()),
                       "train_year_max":yr-1,"bootstrap_by_date":cluster_ci(test,"race_date",400),
                       "bootstrap_by_race":cluster_ci(test,"race_key",400)})
        report["folds"].append(metric)
        preds.append(test[["race_key","race_date","race_year","horse_no","horse_id",
                           "winner","p_base","p_blood"]])
    heldout=pd.concat(preds,ignore_index=True)
    report["all_test"]=score(heldout)
    for dimension in ["race_date","race_key","horse_id","race_year"]:
        report["all_test"]["bootstrap_"+dimension]=cluster_ci(heldout,dimension,800)
    # Licensed row-level prediction pairs are PRIVATE ONLY.
    private=out/"PRIVATE_conditional_holdout_predictions.csv.gz"
    heldout.to_csv(private,index=False,compression={"method":"gzip","mtime":0})
    report["private_prediction_sha256"]=digest(private)
    report["runtime_seconds"]=round(time.monotonic()-start,2)
    aggregate=out/"conditional_retrospective_aggregate.json"
    aggregate.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ["mart","history","out","mart-sha","history-sha"]:p.add_argument("--"+x,required=True)
    a=p.parse_args()
    result=run(a.mart,a.history,a.out,a.mart_sha,a.history_sha)
    print(json.dumps({"status":result["status"],"all_test":result["all_test"],
                      "prediction_safe":False},ensure_ascii=False))
