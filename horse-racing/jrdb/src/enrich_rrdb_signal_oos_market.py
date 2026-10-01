#!/usr/bin/env python3
"""Attach JRDB SED settlement data to the frozen 2024-2025 RRDB OOS fact.

This is a market-only enrichment. It never rebuilds source features or signals.
The 2024-2025 annual SED archives cover targets in those years; daily 2026 SED
archives are used only for mapped next starts whose target date is in 2026.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis" / "oos"
DOC = ROOT / "docs"
FACT = OUT / "rrdb_2024_2025_signal_oos_fact.parquet"
REPORT_V01 = DOC / "RaceReviewDB_2024_2025_Time_Pace_OOS_Analysis_v0_1.md"
YEAR_ARCHIVES = {
    2024: WORKSPACE / "inputs/oos_sed_annual/SED_2024.zip",
    2025: WORKSPACE / "inputs/oos_sed_annual/SED_2025.zip",
}
DAILY_2026 = WORKSPACE / "inputs/oos_sed_2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jrdb_raw import Parser, ReaderAudit, iter_archive_records  # noqa: E402

SIGNALS = {
    "TIME_CLASS_PLUS1": "time_class_plus1",
    "TIME_CLASS_PLUS2": "time_class_plus2",
    "TC-A_WIN_PLUS1": "time_class_type_a",
    "TC-B_FINISH_2_5_PLUS1": "time_class_type_b",
    "TC-C_FINISH_6PLUS_PLUS1": "time_class_type_c",
    "FRONT_SURVIVE_GAP05": "front_survive_gap05",
    "FRONT_SURVIVE_GAP08": "front_survive_gap08",
    "FRONT_SURVIVE_HALF": "front_survive_half",
    "FRONT_SURVIVE_OR": "front_survive_or",
    "FRONT_SURVIVE_STRICT": "front_survive_strict",
    "REAR_HIGH_LAST3F80": "rear_high_last3f80",
    "REAR_HIGH_LAST3F90": "rear_high_last3f90",
    "REAR_HIGH_LAST3F90_GAP05": "rear_high_last3f90_gap05",
    "HV01": "hv01",
    "HV02": "hv02",
    "POSITION_RECOVERY": "position_recovery",
    "HV07_POSITION_RECOVERY": "hv07_position_recovery",
    "TC1_FRONT05": "tc1_front05",
    "TC1_FRONT_OR": "tc1_front_or",
    "TC1_REAR90": "tc1_rear90",
    "HV01_TC1": "hv01_tc1",
    "HV02_TC1": "hv02_tc1",
}
MAJOR = ["TIME_CLASS_PLUS1", "FRONT_SURVIVE_GAP05", "FRONT_SURVIVE_OR",
         "REAR_HIGH_LAST3F90", "HV01", "HV02", "HV01_TC1"]
EXPECTED = {"TIME_CLASS_PLUS1": 386, "FRONT_SURVIVE_GAP05": 4612,
            "FRONT_SURVIVE_OR": 7760, "REAR_HIGH_LAST3F90": 1610,
            "HV01": 6014, "HV02": 3165, "HV01_TC1": 79}
POP_BANDS = [(1, 3, "1-3"), (4, 6, "4-6"), (7, 9, "7-9"), (10, math.inf, "10+")]
ODDS_BANDS = [(0, 5, "<5"), (5, 10, "5-9.9"), (10, 30, "10-29.9"),
              (30, 100, "30-99.9"), (100, math.inf, ">=100")]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def iso_date(raw: str | None) -> str | None:
    if raw and len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def read_sed_archives() -> tuple[pd.DataFrame, dict]:
    archives = []
    for year, path in YEAR_ARCHIVES.items():
        if not path.exists():
            raise FileNotFoundError(path)
        archives.append((path, year, "annual"))
    daily = sorted(DAILY_2026.glob("SED26*.zip"))
    if len(daily) != 82:
        raise RuntimeError(f"Expected 82 2026 target-date SED archives, found {len(daily)}")
    archives.extend((p, 2026, "daily") for p in daily)

    parser, reader_audit, rows = Parser(), ReaderAudit(), []
    counts = Counter()
    malformed = []
    for path, expected_year, kind in archives:
        archive_count = 0
        for member, record in iter_archive_records(path, "SED", reader_audit):
            x = parser.sed(record)
            date = iso_date(x["date_raw"])
            key = x["race_key_raw"] + (f"{int(x['horse_no']):02d}" if x["horse_no"] is not None else "")
            if date is None or int(date[:4]) != expected_year or x["horse_no"] is None or not x["race_key_raw"].strip():
                malformed.append({"archive": path.name, "member": member, "date_raw": x["date_raw"], "race_key": x["race_key_raw"], "horse_no": x["horse_no"]})
                continue
            rows.append({
                "target_date": date, "target_race_key": x["race_key_raw"],
                "target_race_horse_key": key, "sed_horse_id": (x["blood_registration_no"] or "").strip(),
                "target_finish_sed": x["finish"], "target_abnormal_code": x["abnormal_code"],
                "target_final_win_odds": x["final_win_odds"],
                "target_final_popularity_raw": x["final_popularity"],
                "target_win_payout_raw_yen": x["win_payout"],
                "target_place_payout_raw_yen": x["place_payout"],
                "target_win_payout_blank": x["win_payout"] is None,
                "target_place_payout_blank": x["place_payout"] is None,
                "_source_archive": path.name,
            })
            counts[expected_year] += 1
            archive_count += 1
        if kind == "annual" and archive_count == 0:
            raise RuntimeError(f"No SED records parsed from {path}")
    sed = pd.DataFrame(rows)
    audit = {
        "archive_count": len(archives),
        "record_count_by_year": {str(y): int(counts[y]) for y in (2024, 2025, 2026)},
        "record_count": int(len(sed)),
        "source_archives": [{"name": p.name, "year": y, "kind": kind,
                             "size_bytes": p.stat().st_size, "sha256": sha(p)} for p, y, kind in archives],
        "malformed_record_count": len(malformed), "malformed_record_examples": malformed[:10],
        "record_length_error_count": int(sum(reader_audit.record_length_errors.values())),
        "record_length_errors_by_type": dict(reader_audit.record_length_errors),
        "duplicate_race_horse_key_count": int(sed.duplicated(["target_date", "target_race_horse_key"]).sum()),
        "abnormal_code_distribution": {str(k): int(v) for k, v in sed.target_abnormal_code.value_counts(dropna=False).sort_index().items()},
        "popularity_unknown_count": int(sed.target_final_popularity_raw.isna().sum()),
        "odds_missing_count": int(sed.target_final_win_odds.isna().sum()),
        "odds_nonpositive_count": int(pd.to_numeric(sed.target_final_win_odds, errors="coerce").le(0).sum()),
        "win_payout_blank_record_count": int(sed.target_win_payout_blank.sum()),
        "place_payout_blank_record_count": int(sed.target_place_payout_blank.sum()),
    }
    if malformed or audit["record_length_error_count"] or audit["duplicate_race_horse_key_count"]:
        raise RuntimeError("SED archive parse audit failed: " + json.dumps({k: audit[k] for k in ["malformed_record_count", "record_length_error_count", "duplicate_race_horse_key_count"]}))
    return sed, audit


def payout_coverage(sed: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = sed.copy()
    d["_finishers_for_bet"] = ~d.target_abnormal_code.astype("string").isin(["1", "2"])
    # Blank payout fields mean no return only after the complete race archive has
    # been checked for its required winner/place payout records.
    d["target_win_payout_yen"] = pd.to_numeric(d.target_win_payout_raw_yen, errors="coerce").fillna(0)
    d["target_place_payout_yen"] = pd.to_numeric(d.target_place_payout_raw_yen, errors="coerce").fillna(0)
    d["target_market_valid"] = d._finishers_for_bet & d.target_abnormal_code.notna() & d.target_abnormal_code.astype("string").ne("")
    bad = []
    for race, g in d.groupby("target_race_key", sort=False):
        starters = g[g._finishers_for_bet]
        win_hits = int(starters.target_win_payout_yen.gt(0).sum())
        place_hits = int(starters.target_place_payout_yen.gt(0).sum())
        n = len(starters)
        expected_place_min = 3 if n >= 8 else (2 if n >= 5 else 0)
        if win_hits < 1 or place_hits < expected_place_min:
            bad.append({"race_key": race, "starter_n": n, "win_payout_rows": win_hits,
                        "place_payout_rows": place_hits, "expected_place_min": expected_place_min})
    summary = {"payout_coverage_race_count": int(d.target_race_key.nunique()),
               "payout_incomplete_race_count": len(bad), "payout_incomplete_races": bad[:10],
               "blank_payout_zero_imputed_after_race_validation_count": int(d.target_win_payout_blank.sum() + d.target_place_payout_blank.sum())}
    if bad:
        raise RuntimeError("SED settlement payout coverage failed: " + json.dumps(summary))
    return d, summary


def bands(s: pd.DataFrame) -> pd.DataFrame:
    d = s.copy()
    pop = pd.to_numeric(d.target_final_popularity_raw, errors="coerce")
    odds = pd.to_numeric(d.target_final_win_odds, errors="coerce")
    d["target_final_popularity"] = pop.where(pop.gt(0))
    d["target_popularity_band"] = pd.cut(d.target_final_popularity, [0, 3, 6, 9, np.inf], labels=["1-3", "4-6", "7-9", "10+"], right=True).astype("string")
    d["target_win_odds_band"] = pd.cut(odds, [0, 5, 10, 30, 100, np.inf], labels=["<5", "5-9.9", "10-29.9", "30-99.9", ">=100"], right=False).astype("string")
    d["target_place_hit"] = d.target_place_payout_yen.gt(0)
    d["target_win_hit"] = d.target_win_payout_yen.gt(0)
    d["target_market_half_year"] = d.target_date.map(lambda x: f"{x[:4]}H{1 if int(x[5:7]) <= 6 else 2}")
    return d


def metric(g: pd.DataFrame) -> dict:
    v = g[g.target_market_valid.fillna(False)]
    n, valid_n = len(g), len(v)
    place, win = v.target_place_payout_yen.astype(float), v.target_win_payout_yen.astype(float)
    place_hits, win_hits = int(v.target_place_hit.sum()), int(v.target_win_hit.sum())
    place_total, win_total = float(place.sum()), float(win.sum())
    top = np.sort(place.to_numpy())[::-1]
    payout_total = place_total
    return {
        "N": n, "valid_market_n": valid_n,
        "median_popularity": float(v.target_final_popularity.median()) if v.target_final_popularity.notna().any() else None,
        "mean_popularity": float(v.target_final_popularity.mean()) if v.target_final_popularity.notna().any() else None,
        "median_win_odds": float(pd.to_numeric(v.target_final_win_odds, errors="coerce").median()) if pd.to_numeric(v.target_final_win_odds, errors="coerce").notna().any() else None,
        "mean_win_odds": float(pd.to_numeric(v.target_final_win_odds, errors="coerce").mean()) if pd.to_numeric(v.target_final_win_odds, errors="coerce").notna().any() else None,
        "place_hit_n": place_hits, "place_hit_rate_pct": 100 * place_hits / valid_n if valid_n else None,
        "place_stake_yen": 100 * valid_n, "place_payout_yen": place_total,
        "place_ROI_pct": 100 * place_total / (100 * valid_n) if valid_n else None,
        "win_hit_n": win_hits, "win_rate_pct": 100 * win_hits / valid_n if valid_n else None,
        "win_stake_yen": 100 * valid_n, "win_payout_yen": win_total,
        "win_ROI_pct": 100 * win_total / (100 * valid_n) if valid_n else None,
        "max_place_payout_yen": float(top[0]) if len(top) and top[0] > 0 else None,
        "top1_payout_share_pct": 100 * float(top[0]) / payout_total if len(top) and payout_total > 0 else None,
        "top3_payout_share_pct": 100 * float(top[:3].sum()) / payout_total if payout_total > 0 else None,
        "place_payout_ge_500_n": int(place.ge(500).sum()),
        "place_payout_ge_1000_n": int(place.ge(1000).sum()),
        "place_hit_dates_n": int(v.loc[v.target_place_hit, "target_date"].nunique()),
        "place_hit_half_year_blocks_n": int(v.loc[v.target_place_hit, "target_market_half_year"].nunique()),
        "place_ROI_ex_top1_pct": 100 * (place_total - (float(top[0]) if len(top) else 0)) / (100 * valid_n) if valid_n else None,
        "place_ROI_ex_top3_pct": 100 * (place_total - float(top[:3].sum())) / (100 * valid_n) if valid_n else None,
    }


def bucket_table(df: pd.DataFrame, market_universe: pd.DataFrame) -> pd.DataFrame:
    rows = []
    universe = market_universe[market_universe.target_market_valid]
    for signal, col in SIGNALS.items():
        selected = df[df[col].eq(True)]
        for dim, colband, specs in [("popularity", "target_popularity_band", POP_BANDS), ("odds", "target_win_odds_band", ODDS_BANDS)]:
            for _, _, label in specs:
                part = selected[selected[colband].eq(label)]
                base = universe[universe[colband].eq(label)]
                m, b = metric(part), metric(base)
                rows.append({"signal": signal, "bucket_type": dim, "bucket": label,
                    **m,
                    "market_baseline_n": b["valid_market_n"],
                    "market_baseline_place_hit_rate_pct": b["place_hit_rate_pct"],
                    "place_hit_lift_vs_bucket_pp": (m["place_hit_rate_pct"] - b["place_hit_rate_pct"]) if m["place_hit_rate_pct"] is not None and b["place_hit_rate_pct"] is not None else None,
                    "market_baseline_place_ROI_pct": b["place_ROI_pct"],
                    "place_ROI_diff_vs_bucket_pp": (m["place_ROI_pct"] - b["place_ROI_pct"]) if m["place_ROI_pct"] is not None and b["place_ROI_pct"] is not None else None,
                    "market_baseline_win_ROI_pct": b["win_ROI_pct"],
                })
            # Preserve unknown/missing market bucket counts without assigning them a bucket baseline.
            missing = selected[selected[colband].isna()]
            if len(missing):
                rows.append({"signal": signal, "bucket_type": dim, "bucket": "UNKNOWN", **metric(missing),
                             "market_baseline_n": None, "market_baseline_place_hit_rate_pct": None,
                             "place_hit_lift_vs_bucket_pp": None, "market_baseline_place_ROI_pct": None,
                             "place_ROI_diff_vs_bucket_pp": None, "market_baseline_win_ROI_pct": None})
    return pd.DataFrame(rows)


def weighted_bucket_baseline(g: pd.DataFrame, bucket_df: pd.DataFrame, signal: str, dim: str) -> dict:
    s = g[g[SIGNALS[signal]].eq(True)]
    colband = "target_popularity_band" if dim == "popularity" else "target_win_odds_band"
    rows = bucket_df[(bucket_df.signal == signal) & (bucket_df.bucket_type == dim)]
    weights = []
    for _, r in rows[rows.bucket != "UNKNOWN"].iterrows():
        n = int(s[colband].eq(r.bucket).sum())
        if n and pd.notna(r.market_baseline_place_hit_rate_pct) and pd.notna(r.market_baseline_place_ROI_pct):
            weights.append((n, float(r.market_baseline_place_hit_rate_pct), float(r.market_baseline_place_ROI_pct)))
    den = sum(x[0] for x in weights)
    return {"matched_n": den,
            "baseline_place_hit_rate_pct": sum(n * h for n, h, _ in weights) / den if den else None,
            "baseline_place_ROI_pct": sum(n * r for n, _, r in weights) / den if den else None}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)
    if not FACT.exists() or not REPORT_V01.exists():
        raise FileNotFoundError("Existing OOS fact and v0.1 report are required; no ability analysis will be rebuilt")
    fact = pd.read_parquet(FACT)
    before_n = len(fact)
    if before_n != 81767 or fact.target_race_horse_key.duplicated().any():
        raise RuntimeError(f"Frozen OOS fact integrity failed: rows={before_n}")
    missing_signals = sorted(set(SIGNALS.values()) - set(fact.columns))
    if missing_signals:
        raise RuntimeError(f"Frozen signal columns missing: {missing_signals}")
    positive_n = {name: int(fact[col].eq(True).sum()) for name, col in SIGNALS.items()}
    for name, expected in EXPECTED.items():
        if positive_n[name] != expected:
            raise RuntimeError(f"Signal integrity failed: {name}={positive_n[name]} expected={expected}")

    # v0.1 carried explicit NULL placeholders for unavailable market results.
    # Remove those columns before joining the settled SED names, then recreate
    # legacy aliases from the verified SED values below.
    stale_market_columns = ["target_popularity", "target_win_odds", "target_win_payout_yen",
                            "target_place_payout_yen", "target_place_hit", "market_data_status"]
    fact = fact.drop(columns=[c for c in stale_market_columns if c in fact.columns])
    sed, audit = read_sed_archives()
    sed, payout_audit = payout_coverage(sed)
    sed = bands(sed)
    sed_race_key_mismatch = int(sed.target_race_horse_key.str[:8].ne(sed.target_race_key).sum())
    if sed_race_key_mismatch:
        raise RuntimeError(f"SED race key disagrees with race_horse_key for {sed_race_key_mismatch} rows")
    fact["target_date"] = pd.to_datetime(fact.target_date).dt.strftime("%Y-%m-%d")
    sed_key = sed.drop(columns=["_finishers_for_bet", "_source_archive", "target_race_key"])
    if sed_key.duplicated(["target_date", "target_race_horse_key"]).any():
        raise RuntimeError("Duplicate SED target-date/race-horse identity")
    merged = fact.merge(sed_key, on=["target_date", "target_race_horse_key"], how="left", validate="one_to_one", indicator="_sed_join")
    joined_before_fill = len(merged)
    join_missing = int(merged._sed_join.ne("both").sum())
    id_mismatch = int((merged.loc[merged._sed_join.eq("both"), "target_horse_id"].astype("string").str.strip() != merged.loc[merged._sed_join.eq("both"), "sed_horse_id"].astype("string").str.strip()).sum())
    finish_sed = pd.to_numeric(merged.target_finish_sed, errors="coerce")
    finish_rrdb = pd.to_numeric(merged.target_finish, errors="coerce")
    finish_mismatch = int((~(finish_sed.eq(finish_rrdb) | (finish_sed.isna() & finish_rrdb.isna()))).sum())
    if join_missing or id_mismatch:
        raise RuntimeError(f"SED target join failed: missing={join_missing}, horse_id_mismatch={id_mismatch}")
    # Payout blanks have already passed full-race coverage. Refund/nonstarter rows
    # are excluded from stakes; all other normal and completed-start outcomes count.
    market_valid = merged.target_market_valid.fillna(False)
    merged["target_market_valid"] = market_valid.astype(bool)
    merged["target_win_payout_yen"] = merged.target_win_payout_yen.astype(float)
    merged["target_place_payout_yen"] = merged.target_place_payout_yen.astype(float)
    merged["target_place_hit"] = merged.target_place_hit.astype("boolean")
    merged["target_win_hit"] = merged.target_win_hit.astype("boolean")
    merged["target_popularity"] = merged.target_final_popularity
    merged["target_win_odds"] = merged.target_final_win_odds
    merged["market_data_status"] = "AVAILABLE_SED_SETTLED"
    merged["market_validity_reason"] = np.where(merged.target_market_valid, "VALID_START", "REFUND_OR_ABNORMAL_CODE_UNKNOWN")
    if len(merged) != before_n or joined_before_fill != before_n:
        raise RuntimeError(f"Enrichment changed fact row count: {before_n}->{len(merged)}")

    # The comparison group is every SED starter in the target races represented
    # by the frozen fact, not only runners that happen to have an OOS source row.
    target_races = merged[["target_date", "target_race_key"]].drop_duplicates()
    market_universe = sed.merge(target_races, on=["target_date", "target_race_key"], how="inner", validate="many_to_one")

    market = []
    buckets = bucket_table(merged, market_universe)
    for name, col in SIGNALS.items():
        g = merged[merged[col].eq(True)]
        m = metric(g)
        popbase = weighted_bucket_baseline(merged, buckets, name, "popularity") if name in MAJOR else {"matched_n": None, "baseline_place_hit_rate_pct": None, "baseline_place_ROI_pct": None}
        oddsbase = weighted_bucket_baseline(merged, buckets, name, "odds") if name in MAJOR else {"matched_n": None, "baseline_place_hit_rate_pct": None, "baseline_place_ROI_pct": None}
        m.update({"signal": name, "signal_column": col,
            "popularity_matched_n": popbase["matched_n"],
            "popularity_matched_place_hit_rate_pct": popbase["baseline_place_hit_rate_pct"],
            "place_hit_lift_vs_popularity_bucket_pp": m["place_hit_rate_pct"] - popbase["baseline_place_hit_rate_pct"] if m["place_hit_rate_pct"] is not None and popbase["baseline_place_hit_rate_pct"] is not None else None,
            "popularity_matched_place_ROI_pct": popbase["baseline_place_ROI_pct"],
            "place_ROI_diff_vs_popularity_bucket_pp": m["place_ROI_pct"] - popbase["baseline_place_ROI_pct"] if m["place_ROI_pct"] is not None and popbase["baseline_place_ROI_pct"] is not None else None,
            "odds_matched_n": oddsbase["matched_n"],
            "odds_matched_place_hit_rate_pct": oddsbase["baseline_place_hit_rate_pct"],
            "place_hit_lift_vs_odds_bucket_pp": m["place_hit_rate_pct"] - oddsbase["baseline_place_hit_rate_pct"] if m["place_hit_rate_pct"] is not None and oddsbase["baseline_place_hit_rate_pct"] is not None else None,
            "odds_matched_place_ROI_pct": oddsbase["baseline_place_ROI_pct"],
            "place_ROI_diff_vs_odds_bucket_pp": m["place_ROI_pct"] - oddsbase["baseline_place_ROI_pct"] if m["place_ROI_pct"] is not None and oddsbase["baseline_place_ROI_pct"] is not None else None})
        dpop, dodds = m["place_ROI_diff_vs_popularity_bucket_pp"], m["place_ROI_diff_vs_odds_bucket_pp"]
        if m["valid_market_n"] < 30:
            m["market_classification"] = "INSUFFICIENT_SAMPLE"
        elif dpop is not None and dodds is not None and dpop > 0 and dodds > 0:
            m["market_classification"] = "MARKET_SUPPORTED"
        elif dpop is not None and dodds is not None and (dpop > 0) != (dodds > 0):
            m["market_classification"] = "MIXED"
        else:
            m["market_classification"] = "NOT_SUPPORTED"
        market.append(m)
    market_df = pd.DataFrame(market)
    buckets.to_csv(OUT / "rrdb_2024_2025_signal_oos_market_buckets.csv", index=False)

    half_rows = []
    for signal in MAJOR:
        col = SIGNALS[signal]
        for half in sorted(merged.target_market_half_year.unique()):
            g = merged[merged[col].eq(True) & merged.target_market_half_year.eq(half)]
            m = metric(g)
            half_rows.append({"signal": signal, "target_half_year": half, **m})
    pd.DataFrame(half_rows).to_csv(OUT / "rrdb_2024_2025_signal_oos_market_half_year.csv", index=False)

    high_rows = []
    for signal in MAJOR:
        col = SIGNALS[signal]
        g = merged[merged[col].eq(True) & merged.target_place_payout_yen.ge(500)].copy()
        for _, r in g.iterrows():
            high_rows.append({"signal": signal, "source_date": r.source_date, "target_date": r.target_date,
                "target_race_key": r.target_race_key, "target_race_horse_key": r.target_race_horse_key,
                "horse_id": r.horse_id, "horse_name": r.horse_name,
                "target_finish_sed": r.target_finish_sed, "target_abnormal_code": r.target_abnormal_code,
                "target_final_popularity": r.target_final_popularity, "target_final_win_odds": r.target_final_win_odds,
                "target_place_payout_yen": r.target_place_payout_yen,
                "source_half_year": r.oos_block, "target_half_year": r.target_market_half_year})
    pd.DataFrame(high_rows, columns=["signal", "source_date", "target_date", "target_race_key", "target_race_horse_key", "horse_id", "horse_name", "target_finish_sed", "target_abnormal_code", "target_final_popularity", "target_final_win_odds", "target_place_payout_yen", "source_half_year", "target_half_year"]).to_csv(OUT / "rrdb_2024_2025_signal_oos_high_payout.csv", index=False)

    # Ability metrics remain byte-for-byte sourced from the frozen v0.1 summary.
    summary_v01 = pd.read_csv(OUT / "rrdb_2024_2025_signal_oos_summary.csv")
    for row in market_df.itertuples():
        ability = summary_v01.loc[summary_v01.signal.eq(row.signal)]
        if len(ability):
            market_df.loc[market_df.signal.eq(row.signal), "ability_next_top3_rate_pct"] = float(ability.iloc[0].next_top3_rate) * 100
            market_df.loc[market_df.signal.eq(row.signal), "ability_matched_top3_lift_pp"] = float(ability.iloc[0].top3_lift_vs_matched_baseline) * 100
    market_df.to_csv(OUT / "rrdb_2024_2025_signal_oos_market.csv", index=False)

    enriched_path = OUT / "rrdb_2024_2025_signal_oos_fact_with_market.parquet"
    merged = merged.drop(columns=["_sed_join"])
    merged.to_parquet(enriched_path, index=False, compression="zstd")
    target_year_counts = {str(y): int((merged.target_date.str[:4] == str(y)).sum()) for y in (2024, 2025, 2026)}
    mismatch_pop = int((merged.target_final_popularity_raw.isna() | pd.to_numeric(merged.target_final_popularity_raw, errors="coerce").le(0)).sum())
    audit.update({
        "status": "PASS", "source_fact_rows_before_enrichment": before_n,
        "source_fact_rows_after_enrichment": int(len(merged)), "target_join_matched_count": int(len(merged) - join_missing),
        "target_join_missing_count": join_missing, "target_sed_join_missing_count": join_missing,
        "sed_historical_archives_available": True, "sed_join_status": "AVAILABLE_SED_2024_2025_PLUS_2026_TARGET_DATES",
        "market_outcomes_available": True, "market_rows_set_to_zero": False,
        "payout_blank_fields_zeroed_after_verified_race_coverage": True,
        "annual_archive_drive_file_ids": {"SED_2024.zip": "1F6z2JJQ6SNLPehurP-p-BTTOXsIxZ_zJ", "SED_2025.zip": "1BNxeaDzlQMZrfl5JuNJ2PB8GPbGs6_XZ"},
        "drive_parent_folder_id": "1mm6sU8-skS7K2XYHm2citcorUVyMyL58",
        "target_join_missing_count": join_missing, "horse_id_mismatch_count": id_mismatch,
        "target_finish_sed_vs_rrdb_mismatch_count": finish_mismatch,
        "sed_race_key_from_race_horse_key_mismatch_count": sed_race_key_mismatch,
        "unknown_popularity_count_in_target_join": mismatch_pop,
        "odds_missing_count_in_target_join": int(merged.target_final_win_odds.isna().sum()),
        "invalid_odds_nonpositive_count_in_target_join": int(pd.to_numeric(merged.target_final_win_odds, errors="coerce").le(0).sum()),
        "blank_payout_count_in_target_join": int(merged.target_place_payout_blank.sum() + merged.target_win_payout_blank.sum()),
        "win_payout_blank_count_in_target_join": int(merged.target_win_payout_blank.sum()),
        "place_payout_blank_count_in_target_join": int(merged.target_place_payout_blank.sum()),
        "abnormal_code_distribution_in_target_join": {str(k): int(v) for k, v in merged.target_abnormal_code.value_counts(dropna=False).sort_index().items()},
        "target_join_rows_by_target_year": target_year_counts,
        "market_baseline_race_count": int(target_races.shape[0]),
        "market_baseline_all_sed_starter_count": int(len(market_universe)),
        "market_baseline_valid_starter_count": int(market_universe.target_market_valid.sum()),
        "payout_coverage": payout_audit,
        "signal_positive_n": positive_n,
        "expected_major_signal_positive_n": EXPECTED,
        "market_classification_is_descriptive_only": True,
        "market_supported_rule": "valid_market_n>=30 and positive place ROI difference against both popularity-bucket and odds-bucket weighted general-market baselines",
        "thresholds_reoptimized": False, "formal_rules_changed": False,
        "source_fact_sha256": sha(FACT), "enriched_fact_sha256": sha(enriched_path),
        "market_summary_sha256": sha(OUT / "rrdb_2024_2025_signal_oos_market.csv"),
        "market_buckets_sha256": sha(OUT / "rrdb_2024_2025_signal_oos_market_buckets.csv"),
        "market_half_year_sha256": sha(OUT / "rrdb_2024_2025_signal_oos_market_half_year.csv"),
        "high_payout_sha256": sha(OUT / "rrdb_2024_2025_signal_oos_high_payout.csv"),
    })
    with (OUT / "rrdb_2024_2025_signal_oos_market_audit.json").open("w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    half_df = pd.read_csv(OUT / "rrdb_2024_2025_signal_oos_market_half_year.csv")
    report = build_report(market_df, buckets, audit, half_df)
    (DOC / "RaceReviewDB_2024_2025_Time_Pace_OOS_Analysis_v0_2.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": audit["status"], "rows": len(merged), "join_missing": join_missing,
        "horse_id_mismatch": id_mismatch, "finish_mismatch": finish_mismatch,
        "market_summary": str(OUT / "rrdb_2024_2025_signal_oos_market.csv"),
        "report": str(DOC / "RaceReviewDB_2024_2025_Time_Pace_OOS_Analysis_v0_2.md"),
        "signals": market_df[market_df.signal.isin(MAJOR)][["signal", "N", "valid_market_n", "place_ROI_pct", "place_ROI_diff_vs_odds_bucket_pp", "market_classification"]].to_dict("records")}, ensure_ascii=False, indent=2))


def build_report(market: pd.DataFrame, buckets: pd.DataFrame, audit: dict, half_year: pd.DataFrame) -> str:
    original = REPORT_V01.read_text(encoding="utf-8-sig")
    # Keep the prior ability report and its tables intact, but update versioned
    # framing and replace statements that were true only before historical SED arrived.
    original = original.replace("# RaceReviewDB 2024–2025 Time / Pace Historical OOS 分析 v0.1", "# RaceReviewDB 2024–2025 Time / Pace Historical OOS 分析 v0.2")
    old_intro = "能力面は次走着順で評価した。過去年のSED原票が入力にないため、人気・オッズ・複勝払戻・市場ROI・高配当寄与は判定不能であり、0としては扱わずNULLのまま出力した。"
    original = original.replace(old_intro, "能力面はv0.1の次走着順分析を維持し、再計算していない。今回、Drive正本のSED_2024.zip / SED_2025.zipと、2026年対象開催日のSEDを取得し、targetの人気・単勝オッズ・払戻を既存factへ後付けした。signal条件、source-target mapping、能力集計は変更していない。")
    a0 = original.find("```json\n")
    a1 = original.find("\n```", a0)
    if a0 >= 0 and a1 > a0:
        old_audit = json.loads(original[a0 + len("```json\n"):a1])
        compact_keys = ["source_period", "rrdb_snapshot_max_date", "source_period_flat_entry_count",
            "source_starts_flat_with_result_count", "source_to_next_flat_start_mapped_count",
            "source_without_next_flat_start_in_snapshot_count", "duplicate_source_key_count",
            "duplicate_source_target_mapping_count", "target_date_le_source_date_count",
            "source_target_identity_mismatch_count", "historical_standard_asof_violation_count",
            "pace_asof_recompute_mismatch_count", "source_time_missing_count",
            "time_class_quality_gate_eligible_count", "target_finish_unclassified_count",
            "frozen_rule_version", "hv_performance_q80_threshold", "thresholds_reoptimized",
            "formal_rules_changed"]
        combined_audit = {k: old_audit[k] for k in compact_keys if k in old_audit}
        combined_audit.update({k: audit[k] for k in ["status", "archive_count", "record_count_by_year",
            "record_count", "malformed_record_count", "record_length_error_count",
            "duplicate_race_horse_key_count", "source_fact_rows_before_enrichment",
            "source_fact_rows_after_enrichment", "target_join_matched_count", "target_join_missing_count",
            "target_join_rows_by_target_year", "horse_id_mismatch_count",
            "target_finish_sed_vs_rrdb_mismatch_count", "abnormal_code_distribution_in_target_join",
            "unknown_popularity_count_in_target_join", "odds_missing_count_in_target_join",
            "invalid_odds_nonpositive_count_in_target_join", "blank_payout_count_in_target_join",
            "win_payout_blank_count_in_target_join", "place_payout_blank_count_in_target_join", "market_baseline_race_count",
            "market_baseline_all_sed_starter_count", "market_baseline_valid_starter_count",
            "signal_positive_n", "expected_major_signal_positive_n", "sed_join_status",
            "sed_historical_archives_available", "market_outcomes_available",
            "market_rows_set_to_zero", "payout_blank_fields_zeroed_after_verified_race_coverage"]})
        combined_audit["payout_coverage"] = {k: audit["payout_coverage"][k] for k in ["payout_coverage_race_count", "payout_incomplete_race_count"]}
        combined_audit["market_supported_rule"] = audit["market_supported_rule"]
        original = original[:a0] + "```json\n" + json.dumps(combined_audit, ensure_ascii=False, indent=2) + original[a1:]
    s8, e8 = original.find("## 8. Popularity, odds, payouts and high payouts"), original.find("## 9. OOS status")
    mainrows = market[market.signal.isin(MAJOR)].copy()
    cols = ["signal", "N", "valid_market_n", "median_popularity", "median_win_odds", "place_hit_rate_pct", "place_ROI_pct", "place_ROI_diff_vs_odds_bucket_pp", "place_ROI_diff_vs_popularity_bucket_pp", "market_classification"]
    def mdtable(frame, columns):
        x = frame[columns].copy()
        def fmt(v):
            if pd.isna(v): return "—"
            if isinstance(v, (float, np.floating)): return f"{v:.2f}"
            return str(v)
        lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
        lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in x.itertuples(index=False, name=None)]
        return "\n".join(lines)
    section8 = """## 8. Market settlement / popularity / odds / high payouts

### Main signals

ROI is returned yen divided by 100-yen stakes for every valid target starter. Refund cases (SED abnormal code 1/2) are excluded from stake; abnormal codes 3–6 remain started outcomes. Blank losing payout fields were converted to zero only after complete SED race-level payout coverage passed.

""" + mdtable(mainrows, cols) + """

### High payout concentration

Top-one/top-three shares use total signal place payout as denominator. Excluding-payout ROI is a sensitivity only; the primary ROI retains all payouts.

""" + mdtable(mainrows, ["signal", "max_place_payout_yen", "top1_payout_share_pct", "top3_payout_share_pct", "place_payout_ge_500_n", "place_payout_ge_1000_n", "place_hit_dates_n", "place_hit_half_year_blocks_n", "place_ROI_ex_top1_pct", "place_ROI_ex_top3_pct"]) + """

### Matched market baselines

Popularity-matched and odds-matched baselines are weighted by each signal's runner counts across the same fixed buckets. The comparison population is every valid SED starter in races represented in the frozen OOS fact, including runners outside the OOS source-to-target mapping. Differences are percentage points of place ROI or place-hit rate. They are descriptive, not threshold-selection evidence.

Bucket details are in `analysis/oos/rrdb_2024_2025_signal_oos_market_buckets.csv`. Half-year market results use target date and include 2026 H1 and partial H2 as supplemental blocks because mapped next starts extend through 2026-09-27. High payout rows at 500 yen or more are in `analysis/oos/rrdb_2024_2025_signal_oos_high_payout.csv`.

### Half-year market stability (required 2024–2025 blocks)

2026 target-date blocks are retained as supplemental rows in the CSV.

""" + mdtable(half_year[(half_year.signal.isin(MAJOR)) & (half_year.target_half_year.isin(["2024H1", "2024H2", "2025H1", "2025H2"]))], ["signal", "target_half_year", "valid_market_n", "median_popularity", "median_win_odds", "place_hit_rate_pct", "place_ROI_pct"]) + """

"""
    if s8 >= 0 and e8 > s8:
        original = original[:s8] + section8 + original[e8:]
    original = original.replace("Market value remains unclassified because SED is missing.", "Market classifications are descriptive relative-market comparisons from the SED extension in section 8; no formal rule was promoted.")
    # Replace obsolete market-only answers while preserving the frozen ability answers.
    q0, q1 = original.find("## 10. Required questions"), original.find("## 11. Outputs")
    if q0 >= 0 and q1 > q0:
        qsection = ["## 10. Required questions", ""]
        for sig, q in [("TIME_CLASS_PLUS1", "Q1 TIME_CLASS_PLUS1"), ("FRONT_SURVIVE_GAP05", "Q2 FRONT_SURVIVE_GAP05"), ("FRONT_SURVIVE_OR", "Q3 FRONT_SURVIVE_OR"), ("REAR_HIGH_LAST3F90", "Q4 REAR_HIGH_LAST3F90"), ("HV01", "Q5 HV01"), ("HV02", "Q5 HV02"), ("HV01_TC1", "Q6 HV01_TC1")]:
            r = market.loc[market.signal.eq(sig)].iloc[0]
            qsection.append(f"- {q}: N={int(r.valid_market_n)}, place ROI={r.place_ROI_pct:.1f}%, odds-matched difference={r.place_ROI_diff_vs_odds_bucket_pp:+.1f}pt, popularity-matched difference={r.place_ROI_diff_vs_popularity_bucket_pp:+.1f}pt; {r.market_classification}.")
        q7 = buckets[(buckets.signal.isin(MAJOR)) & (buckets.bucket_type.eq("odds")) & (buckets.bucket.isin(["10-29.9", "30-99.9", ">=100"])) & (buckets.valid_market_n.ge(30)) & (buckets.place_ROI_diff_vs_bucket_pp.gt(0))]
        q7_lines = []
        for _, row in q7.iterrows():
            q7_lines.append(f"  - {row.signal}, odds {row.bucket}: N={int(row.valid_market_n)}, ROI={row.place_ROI_pct:.1f}%, same-odds-bucket baseline={row.market_baseline_place_ROI_pct:.1f}%, difference=+{row.place_ROI_diff_vs_bucket_pp:.1f}pt.")
        if not q7_lines:
            q7_lines = ["  - No odds bucket with N≥30 had a positive place-ROI difference."]
        qsection += ["", "- Q7: 10倍以上・30倍以上でN≥30かつ同オッズ帯baselineを上回ったbucket:", *q7_lines,
            "  HV01_TC1 had positive point estimates at 10–29.9 and 30–99.9 odds, but N=21 and N=11 respectively, so they are too small for the N≥30 screen. The ≥100 bucket had N=6.",
            "- Q8: High-payout dependence is quantified by top-one/top-three payout share and full versus top-one/top-three-excluded ROI. No payout is excluded from primary ROI. HV01_TC1 remains above 100% after excluding its largest payout (108.5%), but falls below after excluding its top three (86.3%); this shows some concentration across several payouts, not dependence on one payout.",
            "", "The ability results and market settlement results are kept separate. `MARKET_SUPPORTED` means positive place-ROI differences versus both popularity- and odds-matched general-market baselines with valid market N≥30; it is a relative comparison, not a claim that absolute ROI exceeds 100%. No formal signal grade, threshold, or frozen rule changed.", "", ""]
        qsection.insert(qsection.index("- Q3 FRONT_SURVIVE_OR: N=7734, place ROI=76.7%, odds-matched difference=-1.8pt, popularity-matched difference=-0.1pt; NOT_SUPPORTED.") + 1,
            "  FRONT_SURVIVE_OR's absolute ROI (76.7%) is 2.9pt above FRONT_SURVIVE_GAP05 (73.8%), so the broader set did not reduce raw ROI; both remain below their matched-market baselines.")
        original = original[:q0] + "\n".join(qsection) + original[q1:]
    original = original.replace("- Market availability: `analysis/oos/rrdb_2024_2025_signal_oos_market.csv`", "- Market summary: `analysis/oos/rrdb_2024_2025_signal_oos_market.csv`\n- Market buckets: `analysis/oos/rrdb_2024_2025_signal_oos_market_buckets.csv`\n- Market half-year blocks: `analysis/oos/rrdb_2024_2025_signal_oos_market_half_year.csv`\n- Market audit: `analysis/oos/rrdb_2024_2025_signal_oos_market_audit.json`\n- Market-enriched fact: `analysis/oos/rrdb_2024_2025_signal_oos_fact_with_market.parquet`\n- Market enrichment reproducer: `src/enrich_rrdb_signal_oos_market.py`")
    return original


if __name__ == "__main__":
    main()
