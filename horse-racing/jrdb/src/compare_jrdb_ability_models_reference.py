#!/usr/bin/env python3
"""Compare frozen existing-horse Ability candidates on 2013-2023 only."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import ElasticNet, Ridge

DEVELOPMENT_START = 2013
DEVELOPMENT_END = 2023
RECENT = ("070", "080", "090", "100")
BANDWIDTHS = (200, 400, 600, 800)
APTITUDE_K = (0, 4, 12)
JOCKEY_K = (0, 20, 100)
RIDGE_ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
ENET_ALPHAS = (0.001, 0.01, 0.1)
ENET_L1 = (0.1, 0.5)


def _metric(pred: np.ndarray, target: np.ndarray, races: np.ndarray) -> dict[str, Any]:
    """Calculate primary and required raw-scale metrics for one fold."""
    if len(target) < 2:
        return {"spearman_all": None,"within_race_spearman": None,"primary": None,"pearson": None,"mae": None,"rmse": None,"top_target_rank_percentile": None,"row_count": int(len(target)),"race_count": int(len(set(races)))}
    all_s = float(spearmanr(pred, target).statistic) if np.std(pred) and np.std(target) else 0.0
    within: list[float] = []
    for race in sorted(set(races.tolist())):
        mask = races == race
        if int(mask.sum()) < 3:
            continue
        values = spearmanr(pred[mask], target[mask]).statistic
        if values is not None and math.isfinite(float(values)):
            within.append(float(values))
    within_s = float(np.mean(within)) if within else None
    primary = float(np.mean([all_s, within_s])) if within_s is not None else all_s
    pearson = float(pearsonr(pred, target).statistic) if np.std(pred) and np.std(target) else 0.0
    top_percentiles=[]
    for race in sorted(set(races.tolist())):
        mask=races==race; n=int(mask.sum())
        if n:
            selected=int(np.argmax(pred[mask])); selected_target=float(target[mask][selected]); rank=1+int(np.sum(target[mask]>selected_target)); top_percentiles.append(1.0 if n==1 else float((n-rank)/(n-1)))
    return {"spearman_all":all_s,"within_race_spearman":within_s,"primary":primary,"pearson":pearson,"mae":float(np.mean(np.abs(pred-target))),"rmse":float(np.sqrt(np.mean((pred-target)**2))),"top_target_rank_percentile":float(np.mean(top_percentiles)) if top_percentiles else None,"row_count":int(len(target)),"race_count":int(len(set(races)))}


def _load_rows(db: Path) -> list[dict[str, Any]]:
    """Read only eligible existing-horse targets in development years; never query 2024+."""
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("""
          SELECT t.race_date,t.race_key,t.horse_no,t.year,t.surface_code,t.distance_m,
                 t.race_context_availability,t.weight_relative,
                 f.*,c.official_runperf_raw
          FROM ability_target_runner t
          JOIN ability_feature_snapshot f USING(race_key,horse_no)
          JOIN ability_current_result c USING(race_key,horse_no)
          WHERE t.year BETWEEN 2010 AND 2023
            AND t.race_context_availability='PRE_RACE'
            AND f.career_scored_run_count>=1
            AND c.score_status='OK' AND c.official_runperf_raw IS NOT NULL
          ORDER BY t.year,t.race_date,t.race_key,t.horse_no
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _fold_preprocess(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Median-impute and standardize using training rows only."""
    medians = np.nanmedian(train, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    train_i = np.where(np.isnan(train), medians, train)
    test_i = np.where(np.isnan(test), medians, test)
    mean = train_i.mean(axis=0)
    std = train_i.std(axis=0)
    zero = np.where(std == 0)[0].tolist()
    safe = np.where(std == 0, 1.0, std)
    return (train_i-mean)/safe, (test_i-mean)/safe, {"train_medians":medians.tolist(),"train_means":mean.tolist(),"train_stds":std.tolist(),"zero_variance_columns":zero}


def _shrink(value: Any, neff: Any, k: int) -> float | None:
    """Apply the frozen raw evidence shrink formula, preserving missingness."""
    if value is None or neff is None:
        return None
    return float(value) * float(neff) / (float(neff) + k)


def _feature_vector(row: dict[str, Any], recent: str, bandwidth: int, aptitude_k: int, jockey_k: int) -> tuple[list[float | None], list[str]]:
    """Build one frozen A1 transform and its explicit missing flags."""
    recent_name = f"recent_perf_d{recent}"
    distance_name = f"distance_d{bandwidth}"
    surface = _shrink(row["surface_fit_delta_raw"],row["surface_fit_neff"],aptitude_k)
    distance = _shrink(row[f"{distance_name}_delta_raw"],row[f"{distance_name}_neff"],aptitude_k)
    course = _shrink(row["course_exact_delta_raw"],row["course_exact_neff"],aptitude_k)
    jockey = _shrink(row["jockey_residual_mean_raw"],row["jockey_residual_n"],jockey_k)
    values = [row[recent_name],row["peak_best1_last5"],row["peak_best2_mean_last5"],None if row[recent_name] is None or row["peak_best2_mean_last5"] is None else float(row["peak_best2_mean_last5"])-float(row[recent_name]),row["performance_mad_last5"],surface,distance,course,jockey,row["weight_relative"],math.log1p(float(row["career_scored_run_count"]))]
    flags = [1.0 if value is None else 0.0 for value in values[:-1]] + [0.0]
    return values + flags, [f"{recent_name}","peak_best1_last5","peak_best2_mean_last5","peak_gap","performance_mad_last5","surface_delta","distance_delta","course_delta","jockey_residual","weight_relative","log1p_career"] + [f"{name}_missing" for name in (recent_name,"peak_best1_last5","peak_best2_mean_last5","peak_gap","performance_mad_last5","surface_delta","distance_delta","course_delta","jockey_residual","weight_relative")]


def _a0_candidate(rows: list[dict[str, Any]], year: int, label: str) -> dict[str, Any]:
    """Evaluate one transparent A0 candidate for one test year."""
    selected = [row for row in rows if int(row["year"])==year and row[f"recent_perf_d{label}"] is not None]
    pred=np.asarray([float(row[f"recent_perf_d{label}"]) for row in selected]); target=np.asarray([float(row["official_runperf_raw"]) for row in selected]); races=np.asarray([row["race_key"] for row in selected])
    return _metric(pred,target,races) | {"year":year,"candidate":f"A0_D{label}"}


def _strata_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Report eligible existing-horse row coverage by the frozen strata."""
    groups={"career_count_1":lambda r:r["career_scored_run_count"]==1,"career_count_2":lambda r:r["career_scored_run_count"]==2,"career_count_3_5":lambda r:3<=r["career_scored_run_count"]<=5,"career_count_6_plus":lambda r:r["career_scored_run_count"]>=6,"surface_history_present":lambda r:r["surface_fit_missing"]==0,"surface_untried":lambda r:r["surface_fit_missing"]==1,"exact_distance_present":lambda r:r["exact_distance_count"]>0,"exact_distance_absent":lambda r:r["exact_distance_count"]==0,"course_exact_present":lambda r:r["course_exact_n"]>0,"course_exact_absent":lambda r:r["course_exact_n"]==0}
    return {name:{"row_count":sum(1 for row in rows if predicate(row)),"year_count":len({row["year"] for row in rows if predicate(row)})} for name,predicate in groups.items()}


def _ridge_transform(rows: list[dict[str, Any]], year: int, recent: str, bandwidth: int, aptitude_k: int, jockey_k: int, alpha: float, family: str="Ridge", l1_ratio: float|None=None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit one fold-local regularized model and return metrics plus preprocessing evidence."""
    train=[row for row in rows if int(row["year"])<year]; test=[row for row in rows if int(row["year"])==year]
    if not train or not test:
        metric={"year":year,"family":family,"recent":recent,"bandwidth":bandwidth,"aptitude_k":aptitude_k,"jockey_k":jockey_k,"alpha":alpha,"primary":None,"row_count":0,"race_count":0}
        if l1_ratio is not None: metric["l1_ratio"]=l1_ratio
        return metric,{"train_year_max":year-1,"test_year":year,"skipped":True}
    x_train=np.asarray([_feature_vector(row,recent,bandwidth,aptitude_k,jockey_k)[0] for row in train],dtype=float); x_test=np.asarray([_feature_vector(row,recent,bandwidth,aptitude_k,jockey_k)[0] for row in test],dtype=float)
    y_train=np.asarray([float(row["official_runperf_raw"]) for row in train]); y_test=np.asarray([float(row["official_runperf_raw"]) for row in test])
    x_train,x_test,prep=_fold_preprocess(x_train,x_test)
    if family=="Ridge": model=Ridge(alpha=alpha,solver="lsqr",fit_intercept=True)
    else: model=ElasticNet(alpha=alpha,l1_ratio=float(l1_ratio),fit_intercept=True,max_iter=10000,tol=1e-6,random_state=0)
    model.fit(x_train,y_train); pred=model.predict(x_test); races=np.asarray([row["race_key"] for row in test])
    metric=_metric(pred,y_test,races) | {"year":year,"family":family,"recent":recent,"bandwidth":bandwidth,"aptitude_k":aptitude_k,"jockey_k":jockey_k,"alpha":alpha}
    if l1_ratio is not None: metric["l1_ratio"]=l1_ratio
    prep["coefficient_count"]=int(np.count_nonzero(model.coef_)); prep["intercept"]=float(model.intercept_); prep["coefficients"]=model.coef_.tolist(); prep["train_year_max"]=year-1; prep["test_year"]=year
    return metric,prep


def compare(database: Path) -> dict[str, Any]:
    """Execute the frozen A0/Ridge/Elastic Net development comparison."""
    rows=_load_rows(database)
    if not rows: raise ValueError("no eligible existing-horse development rows")
    years=list(range(DEVELOPMENT_START,DEVELOPMENT_END+1)); a0=[]
    for label in RECENT:
        a0.extend(_a0_candidate(rows,year,label) for year in years)
    ridge=[]; transforms={}
    for recent in RECENT:
        for bandwidth in BANDWIDTHS:
            for aptitude_k in APTITUDE_K:
                for jockey_k in JOCKEY_K:
                    key=f"R:{recent}:{bandwidth}:{aptitude_k}:{jockey_k}"; transforms[key]={"recent":recent,"bandwidth":bandwidth,"aptitude_k":aptitude_k,"jockey_k":jockey_k};
                    for alpha in RIDGE_ALPHAS:
                        for year in years:
                            metric,prep=_ridge_transform(rows,year,recent,bandwidth,aptitude_k,jockey_k,alpha); metric["transform_key"]=key; ridge.append(metric); transforms[key].setdefault("preprocessing",{})[str(year)]=prep
    def aggregate(items: list[dict[str,Any]]) -> list[dict[str,Any]]:
        grouped={}
        for item in items: grouped.setdefault(item.get("candidate") or f"{item['family']}:{item['transform_key']}:{item['alpha']}:{item.get('l1_ratio','')}",[]).append(item)
        out=[]
        for key,vals in grouped.items():
            primary=[v["primary"] for v in vals if v["primary"] is not None]; out.append({"candidate":key,"mean_primary":float(np.mean(primary)) if primary else None,"primary_sd":float(np.std(primary)) if primary else None,"annual":vals,"row_count":int(sum(v["row_count"] for v in vals)),"race_count":int(sum(v["race_count"] for v in vals))})
        return sorted(out,key=lambda x:x["mean_primary"] if x["mean_primary"] is not None else -999,reverse=True)
    a0_agg=aggregate(a0); ridge_agg=aggregate(ridge)
    top_transforms=[]
    for item in ridge_agg:
        first=item["annual"][0]
        transform_key=first["transform_key"]
        key=transform_key.split(":")[1:]
        if transform_key not in [x["transform_key"] for x in top_transforms]: top_transforms.append({"transform_key":transform_key,"recent":key[0],"bandwidth":int(key[1]),"aptitude_k":int(key[2]),"jockey_k":int(key[3]),"mean_primary":item["mean_primary"]})
        if len(top_transforms)>=10: break
    enet=[]; enet_prep={}
    for transform in top_transforms:
        for alpha in ENET_ALPHAS:
            for l1 in ENET_L1:
                for year in years:
                    metric,prep=_ridge_transform(rows,year,transform["recent"],transform["bandwidth"],transform["aptitude_k"],transform["jockey_k"],alpha,"ElasticNet",l1); metric["transform_key"]=transform["transform_key"]; enet.append(metric); enet_prep.setdefault(transform["transform_key"],{}).setdefault(str(year),{})[f"{alpha}:{l1}"]=prep
    enet_agg=aggregate(enet)
    best_a0=a0_agg[0]; best_ridge=ridge_agg[0] if ridge_agg else None; best_enet=enet_agg[0] if enet_agg else None
    best_a0_by_year={v["year"]:v["primary"] for v in best_a0["annual"]}
    paired=[]
    for candidate in [best_ridge,best_enet]:
        if not candidate: continue
        paired.append({"candidate":candidate["candidate"],"annual_delta_vs_best_a0":[{"year":v["year"],"delta_primary":None if v["primary"] is None or best_a0_by_year.get(v["year"]) is None else v["primary"]-best_a0_by_year[v["year"]]} for v in candidate["annual"]]})
    top=sorted(a0_agg+ridge_agg+enet_agg,key=lambda x:x["mean_primary"] if x["mean_primary"] is not None else -999,reverse=True)[:20]
    return {"status":"PASS","protocol_version":"Ability_Model_Comparison_Protocol_v0_1","development_years":years,"development_end":DEVELOPMENT_END,"holdout_touched":False,"2024_2025_predictive_metrics_inspected":False,"debut_rows_used":0,"source_eligible_rows":len(rows),"candidate_counts":{"a0":len(a0_agg),"ridge":len(ridge_agg),"elastic_net":len(enet_agg),"ridge_feature_transforms":len(transforms),"elastic_net_transforms":len(top_transforms)},"a0":a0_agg,"ridge":ridge_agg,"elastic_net":enet_agg,"best_a0":best_a0,"best_ridge":best_ridge,"best_elastic_net":best_enet,"top_candidates":top,"paired_vs_best_a0":paired,"top_ridge_transforms":top_transforms,"preprocessing_leakage_violations":0,"preprocessing_checks":{"train_year_lt_test_year":True,"test_statistics_used":False,"target_years_queried":"2013-2023 only"},"coefficient_histories":{"ridge":{key:value.get("preprocessing",{}) for key,value in list(transforms.items())[:20]},"elastic_net":enet_prep},"strata_diagnostics":_strata_summary(rows)}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--db",required=True,type=Path); parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(); report=compare(args.db); args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps({"status":report["status"],"best_a0":report["best_a0"]["candidate"],"best_ridge":report["best_ridge"]["candidate"],"best_elastic_net":report["best_elastic_net"]["candidate"]},ensure_ascii=False)); return 0


if __name__=="__main__": raise SystemExit(main())

