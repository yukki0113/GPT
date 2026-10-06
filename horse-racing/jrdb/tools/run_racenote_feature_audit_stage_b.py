#!/usr/bin/env python3
"""Reproducible, descriptive 2023-2025 JRDB pre-race feature audit.

Inputs are the frozen annual BAC/KYI/CHA/CYB/SED ZIPs. SED is kept in an
outcome-only frame and is joined after pre-race coverage has been written.
No feature is filled from SED or from a similarly named field.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
from jrdb_raw import Parser, ReaderAudit, iter_archive_records  # noqa: E402

YEARS = (2023, 2024, 2025)
KINDS = ("BAC", "KYI", "CHA", "CYB", "SED")
STAGE_A = HERE / "docs/racenote/research-work/feature_inventory_stage_a.json"
FROZEN = HERE / "config/jrdb_frozen_raw_inventory_20260918.json"
DEFAULT_OUTPUT = HERE / "docs/racenote/research-work/results/stage_b_2023_2025"
CATALOG: list[dict[str, Any]] = []


def feature(name: str, group: str, source: str, leaf: str, reader: str,
            kind: str = "numeric", direction: str = "high", role: str = "candidate",
            order: list[str] | None = None) -> None:
    CATALOG.append(dict(
        feature_id=name, stage_a_field_id=group, source_record=source,
        source_leaf=leaf, reader_leaf=reader, value_kind=kind,
        stronger_direction=direction, analysis_role=role,
        declared_order=order, target_race_pre_race=True,
    ))


def define_catalog() -> list[dict[str, Any]]:
    if CATALOG:
        return CATALOG
    for key in ("idm", "total_index", "info_index", "jockey_index", "stable_index",
                "longshot_index", "jockey_expected_top2_rate"):
        parent = {
            "idm": "horse.idm", "total_index": "horse.total_index",
            "info_index": "horse.info_index", "jockey_index": "horse.jockey_index",
            "stable_index": "horse.stable_index", "longshot_index": "horse.longshot_index",
            "jockey_expected_top2_rate": "horse.jockey_expected_top2_rate",
        }[key]
        rd = "ability" if key in {"idm", "total_index"} else "jrdb_ratings"
        feature(key, parent, "KYI", key, f"horses[].{rd}.{key}")
    for axis in ("front", "pace", "late", "position"):
        feature(f"pace_{axis}_index", "horse.pace_indices", "KYI",
                f"pace_indices.{axis}", f"horses[].pace.indices.{axis}")
        feature(f"pace_{axis}_rank", "horse.pace_ranks", "KYI",
                f"pace_ranks.{axis}", f"horses[].pace.ranks.{axis}", direction="low")
    for point in ("mid", "last3f", "finish"):
        for index, part in enumerate(("order", "margin", "lane")):
            feature(f"forecast_{point}_{part}", "horse.forecast_positions", "KYI",
                    f"forecast_positions.{point}.{index}",
                    f"horses[].pace.forecast_positions.{point}.{part}",
                    kind="categorical" if part == "lane" else "numeric",
                    direction="low" if part in {"order", "margin"} else "none")
    feature("start_index", "horse.start_index", "KYI", "start_index",
            "horses[].pace.start_index")
    feature("late_break_rate", "horse.late_break_rate", "KYI", "late_break_rate",
            "horses[].pace.late_break_rate", direction="low")
    for name, leaf, reader in (
        ("running_style", "running_style_code", "ability.running_style"),
        ("jrdb_class", "jrdb_class_code", "ability.jrdb_class"),
        ("distance_fit", "distance_fit_code", "ability.distance_fit"),
        ("turf_fit", "turf_fit_code", "ability.surface_fit.turf"),
        ("dirt_fit", "dirt_fit_code", "ability.surface_fit.dirt"),
        ("heavy_track_fit", "heavy_track_fit_code", "ability.heavy_track_fit"),
        ("forecast_pace", "forecast_pace_code", "pace.forecast_pace"),
        ("pace_symbol", "symbol_code", "pace.symbol"),
    ):
        group = "horse.running_style" if name == "running_style" else (
            "horse.jrdb_class" if name == "jrdb_class" else
            "horse.forecast_positions" if name in {"forecast_pace", "pace_symbol"} else
            "horse.surface_fit" if name in {"turf_fit", "dirt_fit"} else
            f"horse.{name}")
        feature(name, group, "KYI", leaf, f"horses[].{reader}",
                kind="categorical", direction="none")
    feature("kyi_training_index", "horse.training_index", "KYI", "training_index",
            "horses[].training.summary.training_index")
    feature("training_arrow", "horse.training_arrow", "KYI", "training_arrow_code",
            "horses[].training.summary.training_arrow", "ordinal", "low",
            order=["1", "2", "3", "4", "5"])
    feature("improvement", "horse.condition", "KYI", "improvement_code",
            "horses[].condition.improvement", "ordinal", "low",
            order=["1", "2", "3", "4"])
    feature("stable_evaluation", "horse.condition", "KYI", "stable_evaluation_code",
            "horses[].condition.stable_evaluation", "ordinal", "low",
            order=["1", "2", "3", "4"])
    feature("farm_rank", "horse.farm", "KYI", "farm_rank",
            "horses[].condition.farm.rank", "categorical", "none")
    feature("farm_index_rank", "horse.farm", "KYI", "farm_index_rank",
            "horses[].condition.farm.index_rank", direction="low")
    for axis in ("front", "middle", "last", "total"):
        feature(f"cha_clock_index_{axis}", "horse.workout", "CHA",
                f"clock_index.{axis}", f"horses[].training.main_workout.clock_index.{axis}")
    for axis in ("front", "middle", "last"):
        feature(f"cha_clock_{axis}", "horse.workout", "CHA", f"clock.{axis}",
                f"horses[].training.main_workout.clock.{axis}", direction="none",
                role="context_only")
    for name, leaf in (
        ("cha_course", "course_code"), ("cha_strength", "strength_code"),
        ("cha_state", "state_code"), ("cha_pair_result", "pair.result_code"),
    ):
        feature(name, "horse.workout_context", "CHA", leaf,
                "horses[].training.main_workout", "categorical", "none", "context_only")
    feature("cha_furlongs", "horse.workout_context", "CHA", "furlongs",
            "horses[].training.main_workout.furlongs", direction="none", role="context_only")
    for name in ("training_index", "condition_index", "one_week_ago_index"):
        feature(f"cyb_{name}", "horse.training_analysis", "CYB", name,
                f"horses[].training.analysis.{name}")
    for axis in ("slope", "wood", "dirt", "turf", "pool", "obstacle", "polytrack"):
        feature(f"cyb_course_count_{axis}", "horse.training_analysis", "CYB",
                f"course_counts.{axis}", f"horses[].training.analysis.course_counts.{axis}",
                direction="none", role="context_only")
    for name, leaf in (
        ("cyb_distance_pattern", "distance_pattern_code"),
        ("cyb_focus", "focus_code"), ("cyb_volume_grade", "volume_grade"),
        ("cyb_training_grade", "training_grade_code"),
    ):
        feature(name, "horse.training_analysis", "CYB", leaf,
                "horses[].training.analysis", "categorical", "none", "context_only")
    for mark in ("total", "idm", "info", "jockey", "stable", "training", "longshot"):
        feature(f"mark_{mark}", "horse.jrdb_marks", "KYI", f"marks.{mark}",
                f"horses[].jrdb_ratings.marks.{mark}", "categorical", "none")
    stage_a_ids = {f["field_id"] for f in json.loads(STAGE_A.read_text(encoding="utf-8"))["fields"]}
    missing = {f["stage_a_field_id"] for f in CATALOG} - stage_a_ids
    if missing:
        raise ValueError(f"catalog parent absent from Stage A: {sorted(missing)}")
    ids = [f["feature_id"] for f in CATALOG]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate scalar feature id")
    return CATALOG


def nested(row: dict[str, Any], path: str) -> Any:
    value: Any = row
    for part in path.split("."):
        if part.isdigit() and isinstance(value, (list, tuple)):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def source_manifest(raw_root: Path) -> list[dict[str, Any]]:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    listed = {a["archive_name"]: a for family in frozen["families"]
              for a in family["archives"]}
    output = []
    for kind, year in itertools.product(KINDS, YEARS):
        name = f"{kind}_{year}.zip"
        path = raw_root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        expected = listed[name]
        actual_size = path.stat().st_size
        if actual_size != expected["size_bytes"]:
            raise ValueError(f"frozen inventory size mismatch: {name}")
        output.append(dict(name=name, kind=kind, year=year,
                           drive_id=expected["drive_id"], size_bytes=actual_size,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return output


def parse_family(raw_root: Path, kind: str, year: int,
                 audit: ReaderAudit) -> tuple[pd.DataFrame, dict[str, int]]:
    parser = Parser(audit)
    method = getattr(parser, kind.lower())
    rows: list[dict[str, Any]] = []
    members: Counter[str] = Counter()
    for member, record in iter_archive_records(raw_root / f"{kind}_{year}.zip", kind, audit):
        basename = Path(member).name
        match = re.fullmatch(rf"{kind}(\d{{2}})(\d{{2}})(\d{{2}})\.txt", basename, re.I)
        if match is None or int(match[1]) != year % 100:
            raise ValueError(f"noncanonical member: {member}")
        target_date = f"{year}-{match[2]}-{match[3]}"
        parsed = method(record)
        if kind in {"BAC", "SED"} and parsed["date_raw"] != target_date.replace("-", ""):
            raise ValueError(f"{kind} date mismatch in {member}")
        key = parsed["race_key_raw"] if kind in {"BAC", "SED"} else parsed["race_horse_key"][:8]
        if key[2:4] != str(year)[2:]:
            raise ValueError(f"{kind} race key year mismatch in {member}: {key}")
        result: dict[str, Any] = {"race_key": key, "target_date": target_date}
        if kind == "BAC":
            result.update(surface_code=parsed["surface_code"],
                          distance_m=pd.to_numeric(parsed["distance_raw"], errors="coerce"),
                          race_class_code=parsed["race_class_code"],
                          grade_code=parsed["grade_code"],
                          field_size=parsed["field_size"])
        elif kind == "KYI":
            result.update(horse_no=parsed["horse_no"],
                          race_horse_key=parsed["race_horse_key"],
                          horse_id=parsed["blood_registration_no"])
        elif kind in {"CHA", "CYB"}:
            result["race_horse_key"] = parsed["race_horse_key"]
            if kind == "CHA":
                result["workout_date_raw"] = parsed["date_raw"]
        else:
            result.update(horse_no=parsed["horse_no"],
                          horse_id_result=parsed["blood_registration_no"],
                          finish=parsed["finish"], abnormal_code=parsed["abnormal_code"],
                          final_win_odds=parsed["final_win_odds"],
                          final_popularity=parsed["final_popularity"],
                          win_payout=parsed["win_payout"],
                          place_payout=parsed["place_payout"])
        for f in CATALOG:
            if f["source_record"] == kind:
                value = nested(parsed, f["source_leaf"])
                if f["feature_id"].startswith("mark_") and value in {"", "0", "7", None}:
                    value = "NONE"
                if f["feature_id"] in {"running_style", "distance_fit"} and value == "0":
                    # RaceNote Normalizer maps these provider zero codes to null.
                    value = None
                result[f["feature_id"]] = value if value != "" else None
        rows.append(result)
        members[basename] += 1
    if not rows:
        raise ValueError(f"{kind}_{year}: no canonical records")
    if audit.record_length_errors[kind]:
        raise ValueError(f"{kind}_{year}: record-length error")
    return pd.DataFrame(rows), dict(sorted(members.items()))


def require_unique(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    dup = frame.duplicated(columns, keep=False)
    if dup.any():
        raise ValueError(f"{label}: duplicate business keys, first={frame.loc[dup, columns].head(3).to_dict('records')}")


def read_pre_race(raw_root: Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    audit = ReaderAudit()
    family_frames: dict[str, list[pd.DataFrame]] = {kind: [] for kind in KINDS}
    member_counts = []
    for kind, year in itertools.product(KINDS, YEARS):
        frame, members = parse_family(raw_root, kind, year, audit)
        family_frames[kind].append(frame)
        member_counts.append(dict(kind=kind, year=year, rows=len(frame),
                                  races=frame.race_key.nunique(),
                                  first_date=frame.target_date.min(),
                                  last_date=frame.target_date.max(),
                                  members=len(members)))
    data = {k: pd.concat(v, ignore_index=True) for k, v in family_frames.items()}
    for kind in KINDS:
        keys = ["race_key"] if kind == "BAC" else ["race_key", "horse_no"] if kind in {"KYI", "SED"} else ["race_horse_key"]
        require_unique(data[kind], keys, kind)
    pre = data["KYI"].merge(data["BAC"].drop(columns="target_date"),
                            on="race_key", how="left", validate="many_to_one",
                            indicator="_bac_join")
    pre["race_context_available"] = pre._bac_join == "both"
    pre.drop(columns="_bac_join", inplace=True)
    for kind in ("CHA", "CYB"):
        addition = data[kind].drop(columns=["race_key", "target_date"])
        pre = pre.merge(addition, on="race_horse_key", how="left", validate="one_to_one")
    # CHA workout date is a pre-target observation; fail closed if any row is
    # dated after its target race, rather than using future training as input.
    date_raw = pre.workout_date_raw.dropna().astype(str)
    valid = date_raw.str.fullmatch(r"\d{8}") & (date_raw <= pre.loc[date_raw.index, "target_date"].str.replace("-", ""))
    if not valid.all():
        raise ValueError(f"CHA future/invalid workout dates: {int((~valid).sum())}")
    results = data["SED"].drop(columns="target_date")
    pre = pre.merge(results, on=["race_key", "horse_no"], how="left",
                    validate="one_to_one", indicator="_sed_join")
    mismatch = (pre._sed_join == "both") & (pre.horse_id != pre.horse_id_result)
    if mismatch.any():
        raise ValueError(f"KYI/SED horse identity mismatch: {int(mismatch.sum())}")
    pre["result_matched"] = pre._sed_join == "both"
    pre.drop(columns="_sed_join", inplace=True)
    return pre, member_counts


def coverage(pre: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f in CATALOG:
        col = f["feature_id"]
        for label, subset in [("2023-2025", pre)] + [(str(y), pre[pre.target_date.str[:4] == str(y)]) for y in YEARS]:
            valid = subset[col].notna()
            if f["value_kind"] in {"categorical", "ordinal"}:
                valid &= subset[col].astype(str).str.len().gt(0)
            observed = subset.loc[valid]
            rows.append(dict(feature_id=col, source_record=f["source_record"], period=label,
                             entries=len(subset), rows_available=int(valid.sum()),
                             races_covered=observed.race_key.nunique(),
                             horses_covered=observed.horse_id.nunique(),
                             missing_pct=round(100 * (1 - valid.mean()), 3) if len(subset) else None,
                             first_date=observed.target_date.min() if len(observed) else None,
                             last_date=observed.target_date.max() if len(observed) else None,
                             strictly_pre_race=True))
    return pd.DataFrame(rows)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8",
                 compression={"method": "gzip", "mtime": 0}, float_format="%.8g")


def write_json(value: Any, path: Path) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(frame: pd.DataFrame) -> dict[str, Any]:
    n = len(frame)
    if not n:
        return dict(sample_size=0, race_count=0, wins=0, top2=0, top3=0,
                    win_rate=None, top2_rate=None, top3_rate=None,
                    win_roi=None, place_roi=None)
    if not frame.top3.eq(frame.finish.le(3)).all():
        raise ValueError("top3 outcome label was modified by a feature transformation")
    return dict(
        sample_size=n, race_count=frame.race_key.nunique(),
        wins=int(frame.win.sum()), top2=int(frame.top2.sum()), top3=int(frame.top3.sum()),
        win_rate=round(100 * frame.win.mean(), 4),
        top2_rate=round(100 * frame.top2.mean(), 4),
        top3_rate=round(100 * frame.top3.mean(), 4),
        win_roi=round(100 * (frame.win_return.sum() / (100 * n) - 1), 4),
        place_roi=round(100 * (frame.place_return.sum() / (100 * n) - 1), 4),
    )


def periods(frame: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    return [("2023-2025", frame)] + [
        (str(year), frame[frame.year == year]) for year in YEARS
    ]


def add_metric(rows: list[dict[str, Any]], fid: str, period: str,
               view: str, bucket: str, frame: pd.DataFrame) -> None:
    rows.append(dict(feature_id=fid, period=period, view=view,
                     bucket=str(bucket), **metric(frame)))


def spearman(a: pd.Series, b: pd.Series) -> float:
    both = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(both) < 3 or both.a.nunique() < 2 or both.b.nunique() < 2:
        return math.nan
    return float(both.a.rank(method="average").corr(both.b.rank(method="average")))


def monotonicity(fid: str, period: str, frame: pd.DataFrame,
                 bucket_name: str, ordered_buckets: list[str]) -> dict[str, Any]:
    rates = []
    counts = []
    for bucket in ordered_buckets:
        cell = frame[frame[bucket_name] == bucket]
        rates.append(float(cell.win.mean()) if len(cell) else math.nan)
        counts.append(len(cell))
    pairs = [(a, b) for a, b in zip(rates, rates[1:])
             if not math.isnan(a) and not math.isnan(b)]
    violations = sum(a + 1e-12 < b for a, b in pairs)
    supported = [i for i, n in enumerate(counts) if n >= 100 and not math.isnan(rates[i])]
    score = (spearman(pd.Series([rates[i] for i in supported]),
                      pd.Series([-i for i in supported]))
        if len(supported) >= 3 else math.nan)
    spread = rates[0] - rates[-1] if not (math.isnan(rates[0]) or math.isnan(rates[-1])) else math.nan
    direction = ("stronger_better" if spread > 0 else "reverse" if spread < 0 else "flat_or_unavailable")
    return dict(feature_id=fid, period=period, ordered_view=bucket_name,
                ordered_buckets="|".join(ordered_buckets),
                bucket_counts="|".join(map(str, counts)),
                bucket_win_rates="|".join("NA" if math.isnan(x) else f"{100*x:.4f}" for x in rates),
                direction=direction, violation_count=violations,
                spearman_bucket_score=score, strongest_minus_weakest_win_rate_pp=100 * spread)


def outcome_frame(pre: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    finish = pd.to_numeric(pre.finish, errors="coerce")
    valid = pre.result_matched & finish.ge(1) & ~pre.abnormal_code.isin(["1", "2", "3", "4"])
    frame = pre.loc[valid].copy()
    frame["year"] = frame.target_date.str[:4].astype(int)
    frame["win"] = (frame.finish == 1).astype(int)
    frame["top2"] = (frame.finish <= 2).astype(int)
    frame["top3"] = (frame.finish <= 3).astype(int)
    win_payout = pd.to_numeric(frame.win_payout, errors="coerce")
    place_payout = pd.to_numeric(frame.place_payout, errors="coerce")
    winner_missing = int(((frame.win == 1) & win_payout.isna()).sum())
    if winner_missing:
        raise ValueError(f"SED winner payout missing: {winner_missing}")
    frame["win_return"] = win_payout.fillna(0.0)
    frame["place_return"] = place_payout.fillna(0.0)
    pop = pd.to_numeric(frame.final_popularity, errors="coerce")
    frame["popularity_stratum"] = pd.cut(pop, bins=[0, 3, 6, 9, np.inf],
                                             labels=["1-3", "4-6", "7-9", "10+"])
    bad_pop = int(frame.popularity_stratum.isna().sum())
    if bad_pop:
        raise ValueError(f"SED final popularity missing/invalid for valid finishes: {bad_pop}")
    quality = dict(
        entries=len(pre), result_joined=int(pre.result_matched.sum()),
        valid_result_rows=len(frame), excluded_abnormal_or_no_finish=len(pre) - len(frame),
        winners=int(frame.win.sum()), winner_payout_missing=winner_missing,
        paid_place_rows=int(place_payout.gt(0).sum()),
        top3_without_place_payout=int(((frame.top3 == 1) & place_payout.fillna(0).eq(0)).sum()),
        market_popularity_available=int(pop.notna().sum()),
        bac_context_missing_entries=int((~pre.race_context_available).sum()),
    )
    return frame, quality


def add_numeric_views(sub: pd.DataFrame, spec: dict[str, Any],
                      metrics: list[dict[str, Any]],
                      monos: list[dict[str, Any]],
                      distributions: list[dict[str, Any]],
                      transformed: list[dict[str, Any]],
                      market: list[dict[str, Any]],
                      rank_compare: list[dict[str, Any]]) -> pd.DataFrame:
    fid = spec["feature_id"]
    sub = sub.copy()
    sub[fid] = pd.to_numeric(sub[fid], errors="coerce")
    sub = sub[sub[fid].notna()].copy()
    if sub.empty:
        return sub
    ascending = spec["stronger_direction"] == "low"
    group = sub.groupby("race_key", sort=False)[fid]
    sub["within_rank"] = group.rank(method="min", ascending=ascending)
    count = group.transform("count")
    sub["within_pct"] = np.where(count > 1, (count - sub.within_rank) / (count - 1), 1.0)
    sub["within_quintile"] = pd.cut(
        sub.within_pct, bins=[-0.001, .2, .4, .6, .8, 1.001],
        labels=["Q5", "Q4", "Q3", "Q2", "Q1"], include_lowest=True,
    ).astype(str)
    sub["median_gap"] = sub[fid] - group.transform("median")
    sub["median_gap_bucket"] = np.select(
        [sub.median_gap > 0, sub.median_gap < 0],
        ["above", "below"], default="equal")
    for n in (1, 3, 5):
        sub[f"feature_top{n}"] = sub.within_rank <= n
    # The runner-up value is calculated within each race, leaving ties intact.
    order = sub.sort_values(["race_key", fid], ascending=[True, ascending])
    first_two = order.groupby("race_key", sort=False).head(2).copy()
    first_two["_ordinal"] = first_two.groupby("race_key", sort=False).cumcount()
    seconds = first_two[first_two._ordinal == 1].set_index("race_key")[fid]
    leaders = sub.loc[sub.feature_top1, ["race_key", fid]].copy()
    leaders["leader_gap_second"] = leaders[fid] - leaders.race_key.map(seconds)
    if ascending:
        leaders["leader_gap_second"] *= -1
    for period, sample in periods(sub):
        add_metric(metrics, fid, period, "all", "all", sample)
        for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
            add_metric(metrics, fid, period, "within_race_quintile", q,
                       sample[sample.within_quintile == q])
        for n in (1, 3, 5):
            for yes in (True, False):
                add_metric(metrics, fid, period, f"top{n}", str(yes),
                           sample[sample[f"feature_top{n}"] == yes])
        for bucket in ("above", "equal", "below"):
            add_metric(metrics, fid, period, "median_gap_sign", bucket,
                       sample[sample.median_gap_bucket == bucket])
        if fid.startswith("pace_") and fid.endswith("_rank"):
            ranks = pd.to_numeric(sample[fid], errors="coerce")
            for bucket in ("1", "2", "3", "4", "5", "6+"):
                mask = ranks.eq(int(bucket)) if bucket != "6+" else ranks.ge(6)
                add_metric(metrics, fid, period, "provider_rank", bucket, sample[mask])
        numeric = sample[fid]
        lead_sample = leaders[leaders.race_key.isin(sample.race_key)]
        distributions.append(dict(feature_id=fid, period=period, sample_size=len(sample),
                                  min=numeric.min(), p05=numeric.quantile(.05),
                                  p25=numeric.quantile(.25), median=numeric.median(),
                                  p75=numeric.quantile(.75), p95=numeric.quantile(.95),
                                  max=numeric.max(), distinct_values=numeric.nunique()))
        transformed.append(dict(
            feature_id=fid, period=period, rank_direction="ascending" if ascending else "descending",
            mean_within_race_rank=sample.within_rank.mean(),
            mean_within_race_percentile=sample.within_pct.mean(),
            top1_count=int(sample.feature_top1.sum()), top3_count=int(sample.feature_top3.sum()),
            top5_count=int(sample.feature_top5.sum()),
            median_gap_p25=sample.median_gap.quantile(.25),
            median_gap_p50=sample.median_gap.median(),
            median_gap_p75=sample.median_gap.quantile(.75),
            leader_gap_second_p25=lead_sample.leader_gap_second.quantile(.25),
            leader_gap_second_p50=lead_sample.leader_gap_second.median(),
            leader_gap_second_p75=lead_sample.leader_gap_second.quantile(.75)))
        if spec["stronger_direction"] != "none":
            monos.append(monotonicity(fid, period, sample, "within_quintile",
                                       ["Q1", "Q2", "Q3", "Q4", "Q5"]))
        pop_corr = spearman(sample.within_pct, sample.final_popularity)
        for stratum in ("1-3", "4-6", "7-9", "10+"):
            cell = sample[sample.popularity_stratum.astype(str) == stratum]
            for label, selection in (("Q1", cell[cell.within_quintile == "Q1"]),
                                     ("Q2-Q5", cell[cell.within_quintile != "Q1"])):
                market.append(dict(feature_id=fid, period=period,
                                   popularity_stratum=stratum, group=label,
                                   feature_rank_vs_final_popularity_spearman=pop_corr,
                                   **metric(selection)))
    if fid.startswith("pace_") and fid.endswith("_rank"):
        counterpart = fid.removesuffix("_rank") + "_index"
        both = sub[[fid, counterpart, "race_key", "year"]].dropna()
        if len(both):
            reconstructed = both.groupby("race_key")[counterpart].rank(
                method="min", ascending=False)
            for period, part in periods(both.assign(reconstructed_rank=reconstructed)):
                rank_compare.append(dict(
                    provider_rank_feature=fid, numeric_feature=counterpart, period=period,
                    sample_size=len(part),
                    exact_match_pct=100 * (part[fid] == part.reconstructed_rank).mean() if len(part) else None,
                    spearman=spearman(part[fid], part.reconstructed_rank)))
    return sub


def add_categorical_views(sub: pd.DataFrame, spec: dict[str, Any],
                          metrics: list[dict[str, Any]],
                          monos: list[dict[str, Any]],
                          market: list[dict[str, Any]]) -> None:
    fid = spec["feature_id"]
    sub = sub[sub[fid].notna()].copy()
    if sub.empty:
        return
    sub[fid] = sub[fid].astype(str)
    declared = spec["declared_order"]
    if declared:
        sub = sub[sub[fid].isin(declared)]
    for period, sample in periods(sub):
        add_metric(metrics, fid, period, "all", "all", sample)
        categories = declared or sorted(sample[fid].unique().tolist())
        for category in categories:
            add_metric(metrics, fid, period, "category", category,
                       sample[sample[fid] == category])
        if declared:
            monos.append(monotonicity(fid, period, sample, fid, declared))
        for stratum in ("1-3", "4-6", "7-9", "10+"):
            cell = sample[sample.popularity_stratum.astype(str) == stratum]
            for category in categories:
                market.append(dict(feature_id=fid, period=period,
                                   popularity_stratum=stratum, group=category,
                                   feature_rank_vs_final_popularity_spearman=None,
                                   **metric(cell[cell[fid] == category])))


def conditional_slices(frame: pd.DataFrame,
                       numeric_subsets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    result: list[dict[str, Any]] = []
    class_code = frame.race_class_code.fillna("")
    frame["distance_band"] = pd.cut(
        frame.distance_m, bins=[0, 1399, 1799, 2499, np.inf],
        labels=["sprint", "mile", "middle", "staying"])
    frame["class_band"] = np.select(
        [class_code.isin(["A1", "A2", "A3"]),
         class_code.isin(["04", "05", "08", "09", "10", "15", "16"]),
         class_code.eq("OP") | frame.grade_code.isin(["1", "2", "3", "4", "5", "6"])],
        ["new_maiden", "allowance", "open_graded"], default="unknown")
    frame["field_size_band"] = pd.cut(frame.field_size, bins=[0, 9, 14, np.inf],
                                      labels=["small_1_9", "medium_10_14", "large_15_plus"])
    for fid, sub in numeric_subsets.items():
        if sub.empty:
            continue
        relevant = frame[["race_key", "horse_no", "distance_band",
                          "class_band", "field_size_band"]]
        local = sub.merge(relevant, on=["race_key", "horse_no"], how="left",
                          validate="one_to_one")
        for slice_name, buckets in (
            ("surface", ("1", "2", "3")),
            ("distance_band", ("sprint", "mile", "middle", "staying")),
            ("class_band", ("new_maiden", "allowance", "open_graded")),
            ("field_size_band", ("small_1_9", "medium_10_14", "large_15_plus")),
        ):
            column = "surface_code" if slice_name == "surface" else slice_name
            for bucket in buckets:
                local_bucket = local[local[column].astype(str) == bucket]
                for period, sample in periods(local_bucket):
                    top = sample[sample.within_quintile == "Q1"]
                    rest = sample[sample.within_quintile != "Q1"]
                    a, b = metric(top), metric(rest)
                    result.append(dict(
                        feature_id=fid, slice_type=slice_name, slice_bucket=bucket,
                        period=period, top_sample_size=a["sample_size"],
                        rest_sample_size=b["sample_size"], race_count=sample.race_key.nunique(),
                        top_win_rate=a["win_rate"], rest_win_rate=b["win_rate"],
                        win_rate_lift_pp=(a["win_rate"] - b["win_rate"])
                        if a["win_rate"] is not None and b["win_rate"] is not None else None,
                        top_win_roi=a["win_roi"], rest_win_roi=b["win_roi"],
                        top_place_roi=a["place_roi"], rest_place_roi=b["place_roi"],
                        adequate_size=a["sample_size"] >= 200 and sample.race_key.nunique() >= 100))
    return pd.DataFrame(result)


def redundancy(numeric_subsets: dict[str, pd.DataFrame],
               frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = frame[["race_key", "horse_no"]].copy()
    for fid, sub in numeric_subsets.items():
        common = common.merge(
            sub[["race_key", "horse_no", "within_pct", "feature_top1", "feature_top3"]].rename(
                columns={"within_pct": f"{fid}__pct", "feature_top1": f"{fid}__top1",
                         "feature_top3": f"{fid}__top3"}),
            on=["race_key", "horse_no"], how="left", validate="one_to_one")
    rows = []
    for a, b in itertools.combinations(numeric_subsets, 2):
        ca, cb = f"{a}__pct", f"{b}__pct"
        shared = common[common[ca].notna() & common[cb].notna()]
        if len(shared) < 1000:
            continue
        rows.append(dict(feature_a=a, feature_b=b, common_entries=len(shared),
                         common_races=shared.race_key.nunique(),
                         spearman_within_race_percentile=spearman(shared[ca], shared[cb]),
                         top1_overlap_jaccard=(shared[f"{a}__top1"].eq(True) & shared[f"{b}__top1"].eq(True)).sum()
                         / max(1, (shared[f"{a}__top1"].eq(True) | shared[f"{b}__top1"].eq(True)).sum()),
                         top3_overlap_jaccard=(shared[f"{a}__top3"].eq(True) & shared[f"{b}__top3"].eq(True)).sum()
                         / max(1, (shared[f"{a}__top3"].eq(True) | shared[f"{b}__top3"].eq(True)).sum())))
    marks = []
    for name in ("total", "idm", "info", "jockey", "stable", "training", "longshot"):
        index = {"total": "total_index", "idm": "idm", "info": "info_index",
                 "jockey": "jockey_index", "stable": "stable_index",
                 "training": "kyi_training_index", "longshot": "longshot_index"}[name]
        fid = f"mark_{name}"
        sub = numeric_subsets.get(index)
        if sub is None or sub.empty:
            continue
        for code, part in sub.groupby(fid, dropna=False):
            marks.append(dict(mark_feature=fid, index_feature=index, mark_code=code,
                              sample_size=len(part), mean_numeric_within_race_percentile=part.within_pct.mean(),
                              numeric_top1_pct=100 * part.feature_top1.mean(),
                              win_rate=100 * part.win.mean()))
    return pd.DataFrame(rows), pd.DataFrame(marks)


def analyze(pre: pd.DataFrame, output: Path) -> None:
    frame, quality = outcome_frame(pre)
    write_json(quality, output / "outcome_quality.json")
    metrics: list[dict[str, Any]] = []
    monos: list[dict[str, Any]] = []
    distributions: list[dict[str, Any]] = []
    transformed: list[dict[str, Any]] = []
    market: list[dict[str, Any]] = []
    rank_compare: list[dict[str, Any]] = []
    numeric_subsets: dict[str, pd.DataFrame] = {}
    for spec in CATALOG:
        fid = spec["feature_id"]
        sub = frame[frame[fid].notna()]
        if spec["value_kind"] == "numeric":
            analyzed_numeric = add_numeric_views(
                sub, spec, metrics, monos, distributions, transformed,
                market, rank_compare)
            if spec["analysis_role"] == "candidate":
                numeric_subsets[fid] = analyzed_numeric
        else:
            add_categorical_views(sub, spec, metrics, monos, market)
        print(f"analyzed {fid}: {len(sub)}", flush=True)
    table = pd.DataFrame(metrics)
    write_csv(table[table.period == "2023-2025"], output / "overall_metrics.csv.gz")
    write_csv(table[table.period != "2023-2025"], output / "yearly_metrics.csv.gz")
    write_csv(pd.DataFrame(monos), output / "monotonicity.csv.gz")
    write_csv(pd.DataFrame(distributions), output / "raw_distributions.csv.gz")
    write_csv(pd.DataFrame(transformed), output / "numeric_transform_summary.csv.gz")
    write_csv(pd.DataFrame(market), output / "market_strata.csv.gz")
    write_csv(pd.DataFrame(rank_compare), output / "provider_rank_comparison.csv.gz")
    redundant, mark_overlap = redundancy(numeric_subsets, frame)
    write_csv(redundant, output / "redundancy_pairs.csv.gz")
    write_csv(mark_overlap, output / "mark_index_overlap.csv.gz")
    write_csv(conditional_slices(frame, numeric_subsets),
              output / "conditional_slices.csv.gz")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--preflight-only", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    define_catalog()
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(CATALOG, args.output / "scalar_feature_catalog.json")
    manifest = source_manifest(args.raw_root)
    write_json(manifest, args.output / "source_manifest.json")
    pre, family_counts = read_pre_race(args.raw_root)
    write_json(family_counts, args.output / "source_coverage.json")
    cov = coverage(pre)
    write_csv(cov, args.output / "coverage.csv.gz")
    summary = dict(entries=len(pre), races=pre.race_key.nunique(),
                   bac_context_missing_entries=int((~pre.race_context_available).sum()),
                   bac_context_missing_races=pre.loc[~pre.race_context_available, "race_key"].nunique(),
                   result_matched=int(pre.result_matched.sum()),
                   by_year=pre.groupby(pre.target_date.str[:4]).size().to_dict())
    write_json(summary, args.output / "cohort.json")
    print(json.dumps(summary, ensure_ascii=False))
    if args.preflight_only:
        return 0
    analyze(pre, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
