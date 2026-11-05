#!/usr/bin/env python3
"""Research-only prospective paired probabilities; never declares an attested forecast.

Consumes already validated, *private*, pre-race feature rows produced by JRDB
readers (not a BRDB reparser). The stored output is a CANDIDATE until an
independent GitHub/Drive time and source-provenance audit establishes that it
existed before the first off time. Never publish licensed target rows to Git.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from audit_brdb_m6_v056_freeze_evidence import PAIR_SCHEMA, check
from run_brdb_m6_conditional_retrospective import (
    BASE, BLOOD, digest, fit_predict, prep, read_join,
)

VERSION = "brdb-m6-prospective-pair-candidate-v0.1"
REQUIRED = {
    "target_date", "venue", "race_no", "race_key", "horse_no", "horse_id",
    "venue_code", "surface_code", "distance_m", "race_class_code",
    "sire_line_code", "broodmare_sire_line_code", "ukc_data_date",
}
FORBIDDEN = {
    "winner", "finish", "finish_position", "result", "result_opened",
    "abnormal_code", "normal_finisher", "actual_starter", "payout", "odds",
    "win_odds", "popularity", "market_snapshot",
}


def checked_features(frame, handoff):
    """Validate canonical IDs, source date, and *exact* frozen horse roster."""
    import pandas as pd

    cols = set(frame.columns)
    if missing := REQUIRED - cols:
        raise ValueError(f"missing target columns: {sorted(missing)}")
    if leaked := FORBIDDEN & cols:
        raise ValueError(f"outcome/market fields forbidden: {sorted(leaked)}")
    day = handoff["target_date"]
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", day) or day <= "2025-12-31":
        raise ValueError("target must be a future out-of-training race day")
    expected = {}
    for race in handoff["race_roster"]:
        key = (race["venue"], int(race["race_no"]))
        if key in expected:
            raise ValueError("duplicate race in Freeze")
        expected[key] = set(race["horse_nos"])
    if not expected:
        raise ValueError("empty Freeze roster")

    clean = frame.copy()
    if clean.isna().any().any():
        raise ValueError("target missing values; never impute licensed source fields")
    for col in ("target_date", "venue", "race_key", "horse_id", "ukc_data_date"):
        clean[col] = clean[col].astype(str)
    if not (clean.target_date == day).all():
        raise ValueError("target day mismatch")
    if not clean.horse_id.map(lambda x: bool(re.fullmatch(r"[0-9]{8}", x))).all():
        raise ValueError("invalid JRDB canonical horse_id")
    if not clean.race_key.map(lambda x: bool(re.fullmatch(r"[A-Za-z0-9]{8}", x))).all():
        raise ValueError("invalid race_key")
    if not clean.ukc_data_date.map(lambda x: bool(re.fullmatch(r"20\d{6}", x))).all():
        raise ValueError("invalid UKC observation date")
    if (clean.ukc_data_date > day.replace("-", "")).any():
        raise ValueError("future UKC observation in race features")
    for col in ("horse_no", "race_no", "distance_m"):
        try:
            numeric = pd.to_numeric(clean[col], errors="raise")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid positive integer: {col}") from exc
        if not (numeric.map(lambda v: math.isfinite(float(v)) and float(v).is_integer() and float(v) > 0)).all():
            raise ValueError(f"invalid positive integer: {col}")
        clean[col] = numeric.astype(int)
    if clean.duplicated(["race_key", "horse_no"]).any() or clean.duplicated(["venue", "race_no", "horse_no"]).any():
        raise ValueError("duplicate target race-horse identity")

    observed = {}
    for rec in clean.itertuples(index=False):
        key = (rec.venue, rec.race_no)
        if key not in expected or rec.horse_no not in expected[key]:
            raise ValueError("target horse outside frozen RaceNote roster")
        observed.setdefault(key, set()).add(rec.horse_no)
    if observed != expected or len(clean) != sum(map(len, expected.values())):
        raise ValueError("incomplete frozen target roster")
    if any(len(v) < 2 for v in expected.values()):
        raise ValueError("cannot score singleton races as 0<p<1")

    clean["horse_no_cat"] = clean.horse_no.astype(str)
    clean["distance_band"] = ((clean.distance_m // 200) * 200).astype(str)
    clean["month"] = clean.target_date.str.slice(5, 7)
    for col in BASE + BLOOD:
        clean[col] = clean[col].astype(str).replace({"": "UNKNOWN"})
    return clean


def normalized_pairs(train, target):
    """Same fitted family and fixed features as M6 retrospective, race-normalized."""
    import numpy as np

    d = target.copy()
    d["p_baseline"] = fit_predict(train, d, BASE)
    d["p_blood_challenger"] = fit_predict(train, d, BASE + BLOOD)
    for col in ("p_baseline", "p_blood_challenger"):
        if not np.isfinite(d[col].to_numpy(dtype=float)).all() or not (d[col] > 0).all():
            raise ValueError("nonpositive or nonfinite model probabilities")
        denom = d.groupby(["venue", "race_no"])[col].transform("sum")
        if not (denom > 0).all():
            raise ValueError("invalid race normalization")
        d[col] /= denom
        if not ((d[col] > 0) & (d[col] < 1)).all():
            raise ValueError("invalid normalized probability")
    return [
        {"venue": r.venue, "race_no": int(r.race_no), "horse_no": int(r.horse_no),
         "horse_id": r.horse_id, "p_baseline": float(r.p_baseline),
         "p_blood_challenger": float(r.p_blood_challenger)}
        for r in d.sort_values(["venue", "race_no", "horse_no"]).itertuples(index=False)
    ]


def run(mart, mart_sha, history, history_sha, target, target_sha, v056_root, out):
    import pandas as pd

    sources = [(mart, mart_sha), (history, history_sha), (target, target_sha)]
    for path, expected in sources:
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(path) != expected:
            raise ValueError(f"input SHA mismatch: {Path(path).name}")
    # The existing RaceNote read-only check never attests a remote commit time.
    freeze_audit = check(v056_root)
    handoff = json.loads((Path(v056_root) / "frozen" / "day_handoff.json").read_text())
    target_df = checked_features(pd.read_csv(target, dtype=str, keep_default_na=False), handoff)
    train = prep(read_join(mart, history))
    if len(train) != 477506 or train.race_key.nunique() != 34482:
        raise ValueError("training cohort diverged from pinned M6 research scope")
    if not (train.race_year.astype(int) <= 2025).all():
        raise ValueError("training includes future race results")
    entries = normalized_pairs(train, target_df)
    obj = {
        "schema_version": PAIR_SCHEMA,
        "target_date": handoff["target_date"],
        "prediction_safe": False,
        "source_freeze_records_sha256": handoff["records_sha256"],
        "entries": entries,
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pairs_file = out / "PRIVATE_prospective_pair_candidate.json"
    pairs_file.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    verified = check(v056_root, pairs_file)
    audit = {
        "version": VERSION,
        "status": "PAIRS_GENERATED_RESEARCH_CANDIDATE_ONLY",
        "prediction_safe": False,
        "p1_7_log_loss_evaluable": False,
        "paired_entries": len(entries),
        "races": freeze_audit["race_count"],
        "input_sha256": {"mart": mart_sha, "history": history_sha, "target": target_sha},
        "freeze_records_sha256": freeze_audit["freeze_records_sha256"],
        "pair_sha256": digest(pairs_file),
        "review": verified["status"],
        "model": "two independently fitted M6 v0.1 logistic models, per-race probability normalized",
        "blockers": ["External pre-off-time commit and data-provenance audit",
                     "Historical provider equivalence independent attestation",
                     "Race results and paired dependent inference in unseen races"],
        "note": "Never treat a self-entered timestamp or generated prediction as pre-race attestation.",
    }
    (out / "prospective_pair_candidate_audit.json").write_text(json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("mart", "history", "target"):
        p.add_argument("--" + key, type=Path, required=True)
        p.add_argument("--" + key + "-sha", required=True)
    p.add_argument("--v056-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.mart, a.mart_sha, a.history, a.history_sha,
                         a.target, a.target_sha, a.v056_root, a.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
