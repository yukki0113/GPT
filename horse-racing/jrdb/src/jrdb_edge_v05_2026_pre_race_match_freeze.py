#!/usr/bin/env python3
"""Build a result-blind 2026 pre-race match freeze for the frozen v0.5 cohort.

All source rows are projected onto an explicit pre-race schema before matching.
SED is used only as a historical start chronology/key source; finish, odds,
popularity, payout, and performance columns are never selected.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_jrdb_edge_current_facts import build_current_facts
from jrdb_edge_canonical import derive_transition_features
from jrdb_raw import ReaderAudit, canonical_members, number_field, raw_field, read_fixed_records

COHORT_SHA256 = "a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9"
WAREHOUSE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
WAREHOUSE_RUN_ID = 37592837881
WAREHOUSE_ARTIFACT_ID = 11468713930
SED_2026_RUN_ID = 37604723913
SED_2026_ARTIFACT_ID = 11474018960
PACI_FOLDER_ID = "1zFajenPU5jxInZCcmqZzkgiaYil3MD8r"
SUPPORTED_CONDITION_KEYS = {
    "distance_m", "frame_no", "going_bucket", "sire_name", "surface_code",
    "venue_code", "distance_change", "surface_transition", "first_dirt",
    "first_turf", "first_blinkers",
}
FACT_COLUMNS = [
    "race_date", "race_key", "race_horse_key", "horse_id", "horse_no",
    "venue_code", "surface_code", "distance_m", "frame_no", "sire_name",
    "distance_change", "surface_transition", "first_dirt", "first_turf",
    "first_blinkers", "going_bucket",
]
MATCH_COLUMNS = [
    "race_date", "race_key", "race_horse_key", "horse_id", "horse_no",
    "candidate_id", "template_id", "family", "condition_fingerprint",
    "memo", "matched_conditions", "pre_race_fact_fingerprint",
]
FORBIDDEN_FIELDS = {
    "finish", "finish_position", "finish_order", "result_rank", "popularity",
    "odds", "base_win_odds", "base_place_odds", "final_win_odds",
    "final_place_odds", "win_payout", "place_payout", "win_return",
    "place_return", "result_hit", "settled", "post_race", "idm", "metrics",
}


class FreezeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_line(row: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(row), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def fingerprint_rows(rows: Iterable[Mapping[str, Any]], sort_key: tuple[str, ...]) -> str:
    ordered = sorted((dict(r) for r in rows), key=lambda r: tuple(str(r.get(k) or "") for k in sort_key))
    h = hashlib.sha256()
    for row in ordered:
        h.update(canonical_line(row))
    return h.hexdigest()


def load_cohort(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != COHORT_SHA256:
        raise FreezeError(f"frozen cohort SHA mismatch: {digest}")
    document = json.loads(raw)
    rows = document.get("candidates")
    if not isinstance(rows, list) or len(rows) != 1620 or document.get("candidate_count") != 1620:
        raise FreezeError("frozen cohort must contain exactly 1,620 candidates")
    seen: set[str] = set()
    unsupported: list[tuple[str, str]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            raise FreezeError("missing or duplicate frozen candidate_id")
        seen.add(candidate_id)
        conditions = row.get("conditions")
        if not isinstance(conditions, dict) or not conditions:
            raise FreezeError(f"invalid conditions: {candidate_id}")
        unsupported.extend((candidate_id, key) for key in conditions if key not in SUPPORTED_CONDITION_KEYS)
    if unsupported:
        candidate_id, key = unsupported[0]
        raise FreezeError(f"unsupported frozen condition key: candidate_id={candidate_id} key={key}")
    return rows, {"candidate_count": len(rows), "cohort_sha256": digest,
                  "unsupported_condition_count": len(unsupported)}


def _norm(key: str, value: Any) -> str | None:
    if value is None:
        return None
    if key in {"first_dirt", "first_turf", "first_blinkers"}:
        if value is True or str(value).strip().lower() == "true":
            return "true"
        if value is False or str(value).strip().lower() == "false":
            return "false"
        return None
    if key in {"distance_m", "frame_no"}:
        try:
            return str(int(float(value)))
        except (TypeError, ValueError, OverflowError):
            return None
    text = str(value).strip()
    return text or None


def condition_matches(conditions: Mapping[str, Any], fact: Mapping[str, Any]) -> bool:
    """Exact equality; unknown/null values never satisfy a frozen condition."""
    extra = set(conditions) - SUPPORTED_CONDITION_KEYS
    if extra:
        raise FreezeError(f"unsupported condition key(s): {sorted(extra)}")
    for key, expected in conditions.items():
        actual = _norm(key, fact.get(key))
        expected_norm = _norm(key, expected)
        if actual is None or expected_norm is None or actual != expected_norm:
            return False
    return True


def validate_match_fact_schema(fact: Mapping[str, Any]) -> None:
    """Fail closed on any non-allowlisted or result/market input field."""
    keys = set(fact)
    forbidden = keys & FORBIDDEN_FIELDS
    allowed = set(FACT_COLUMNS) | {"_blinker_code", "_prev1_race_key"}
    unexpected = keys - allowed
    if forbidden or unexpected:
        raise FreezeError(f"invalid matcher fact schema: forbidden={sorted(forbidden)} unexpected={sorted(unexpected)}")


def derive_first_surface(current_surface: Any, target_surface: str,
                         prior_events: Iterable[Mapping[str, Any]], *,
                         identity: bool, target_ambiguous: bool) -> bool | None:
    """Chronology-safe first surface, with unknown and 2010 left censoring."""
    surface = _clean(current_surface)
    prior = list(prior_events)
    if not identity or surface is None or target_ambiguous:
        return None
    if surface != target_surface:
        return False
    known_prior = any(not e.get("surface_unknown") and _clean(e.get("surface_code")) == target_surface for e in prior)
    uncertain_prior = any(e.get("surface_unknown") for e in prior)
    left_censored = any(str(e.get("race_date", "")).startswith("2010-") for e in prior)
    return False if known_prior else (None if uncertain_prior or left_censored else True)


def derive_first_blinkers(code_value: Any, prior_events: Iterable[Mapping[str, Any]], *,
                          identity: bool, target_ambiguous: bool) -> bool | None:
    """Reconcile KYI first-use code with strictly earlier chronology."""
    code = _clean(code_value)
    prior = list(prior_events)
    if not identity or target_ambiguous or code not in {"", "0", "1", "2", "3"}:
        return None
    if code in {"", "0"}:
        return False
    active_prior = any(not e.get("blinker_unknown") and _clean(e.get("blinker_code")) in {"1", "2", "3"} for e in prior)
    uncertain_prior = any(e.get("blinker_unknown") for e in prior)
    left_censored = any(str(e.get("race_date", "")).startswith("2010-") for e in prior)
    chronology = False if active_prior else (None if uncertain_prior or left_censored else True)
    return chronology if chronology == (code == "1") else None


def _paci_blinker_codes(paci_path: Path) -> dict[tuple[str, str, str], str | None]:
    """Read only the fixed KYI identity and blinker-code fields needed here."""
    audit = ReaderAudit()
    found: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    with zipfile.ZipFile(paci_path) as archive:
        for member in canonical_members(archive, "KYI"):
            for record in read_fixed_records(archive, member, "KYI", audit):
                race_key = raw_field(record, 1, 8)
                horse_no_value = number_field(record, 9, 2)
                horse_id = raw_field(record, 11, 8)
                code = raw_field(record, 171, 1)
                if race_key and horse_no_value is not None and horse_id:
                    found[(race_key, str(int(horse_no_value)), horse_id)].add(code)
    if audit.record_length_errors:
        raise FreezeError(f"KYI record-length errors in {paci_path.name}")
    output: dict[tuple[str, str, str], str | None] = {}
    for key, codes in found.items():
        output[key] = next(iter(codes)) if len(codes) == 1 else None
    return output


def _fact_projection(row: Mapping[str, Any], blinker: str | None) -> dict[str, Any]:
    return {
        "race_date": str(row["race_date"])[:10],
        "race_key": str(row["race_key"]),
        "race_horse_key": str(row["race_horse_key"]),
        "horse_id": _clean(row.get("horse_id")),
        "horse_no": _int(row.get("horse_no")),
        "venue_code": _clean(row.get("venue_code")),
        "surface_code": _clean(row.get("surface_code")),
        "distance_m": _int(row.get("distance_m")),
        "frame_no": _int(row.get("frame_no")),
        "sire_name": _clean(row.get("sire_name")),
        "distance_change": _clean(row.get("distance_change_bucket")),
        "surface_transition": _clean(row.get("surface_transition")),
        "first_dirt": None,
        "first_turf": None,
        "first_blinkers": None,
        # No pre-race canonical going field is exposed by the approved PACI
        # current-facts builder. Unknown stays null and fails exact matching.
        "going_bucket": None,
        "_blinker_code": blinker,
        "_prev1_race_key": _clean(row.get("prev1_race_key")),
    }


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError, OverflowError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def load_paci_facts(paci_files: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for paci in sorted(paci_files, key=lambda p: p.name):
        if not re.fullmatch(r"PACI26\d{4}\.zip", paci.name):
            raise FreezeError(f"unexpected PACI input filename: {paci.name}")
        parsed, summary = build_current_facts(paci)
        blinkers = _paci_blinker_codes(paci)
        for row in parsed:
            key = (str(row["race_key"]), str(int(row["horse_no"])), str(row.get("horse_id") or ""))
            fact = _fact_projection(row, blinkers.get(key))
            facts.append(fact)
        summaries.append({"file": paci.name, "sha256": sha256_file(paci),
                          "races": int(summary["races"]), "rows": int(summary["runner_rows"])})
    facts.sort(key=lambda r: (r["race_date"], r["race_key"], r["race_horse_key"]))
    keys = [r["race_horse_key"] for r in facts]
    if len(keys) != len(set(keys)):
        raise FreezeError("duplicate PACI race_horse_key across 2026 inputs")
    return facts, {"paci_file_count": len(summaries), "paci_files": summaries,
                   "paci_row_count": len(facts), "paci_race_count": len({r['race_key'] for r in facts}),
                   "paci_race_days": len({r['race_date'] for r in facts}),
                   "first_race_date": min(r["race_date"] for r in facts) if facts else None,
                   "latest_race_date": max(r["race_date"] for r in facts) if facts else None}


def load_2026_sed(sed_artifact_root: Path) -> list[dict[str, str]]:
    """Read only SED date, horse identity, horse number, and race key."""
    archive_files = sorted(sed_artifact_root.rglob("SED26????.zip"))
    if not archive_files:
        archive_files = sorted(sed_artifact_root.rglob("*.zip"))
    rows: list[dict[str, str]] = []
    for outer_path in archive_files:
        if not re.fullmatch(r"SED26\d{4}\.zip", outer_path.name):
            continue
        with zipfile.ZipFile(outer_path) as outer:
            for member in outer.namelist():
                if not member.lower().endswith(".txt"):
                    continue
                for record in outer.read(member).splitlines():
                    # SED includes non-runner race blocks. Runner rows are the
                    # 374-byte body; no result-side offsets are read.
                    if len(record) != 374:
                        continue
                    race_key = record[0:8].decode("ascii", errors="strict").strip()
                    horse_no = record[8:10].decode("ascii", errors="strict").strip()
                    horse_id = record[10:18].decode("ascii", errors="strict").strip()
                    race_date = record[18:26].decode("ascii", errors="strict").strip()
                    if race_key and horse_no and horse_id and re.fullmatch(r"20\d{6}", race_date):
                        rows.append({"race_key": race_key, "horse_no": str(int(horse_no)),
                                     "horse_id": horse_id,
                                     "race_date": f"{race_date[:4]}-{race_date[4:6]}-{race_date[6:8]}"})
    return rows


def _asset_paths(warehouse_root: Path) -> tuple[list[Path], list[Path], dict[str, Any]]:
    from aggregate_jrdb_edge_v05_first_history import verify_warehouse
    audit = verify_warehouse(warehouse_root)
    manifest = audit["manifest"]
    lookup = {(str(a["family"]).upper(), int(a["year"])): warehouse_root / a["relative_path"]
              for a in manifest["assets"]}
    sed = [lookup[("SED", year)] for year in range(2010, 2026)]
    kyi = [lookup[("KYI", year)] for year in range(2010, 2026)]
    return sed, kyi, {k: v for k, v in audit.items() if k != "manifest"}


def _parquet_rows(paths: list[Path], sql_columns: str) -> list[tuple[Any, ...]]:
    import duckdb
    con = duckdb.connect(":memory:")
    try:
        path_list = "[" + ",".join("'" + str(p).replace("'", "''") + "'" for p in paths) + "]"
        return con.execute(f"SELECT {sql_columns} FROM read_parquet({path_list})").fetchall()
    finally:
        con.close()


def build_history_index(facts: list[dict[str, Any]], sed_rows: list[dict[str, str]],
                        warehouse_root: Path) -> dict[str, Any]:
    sed_paths, kyi_paths, warehouse_audit = _asset_paths(warehouse_root)
    older_sed = _parquet_rows(sed_paths,
        "trim(CAST(blood_registration_no AS VARCHAR)), trim(CAST(race_key_raw AS VARCHAR)), "
        "trim(CAST(horse_no AS VARCHAR)), CAST(race_date AS VARCHAR), "
        "trim(CAST(surface_code AS VARCHAR)), CAST(distance_m AS BIGINT)")
    older_kyi = _parquet_rows(kyi_paths,
        "trim(CAST(blood_registration_no AS VARCHAR)), trim(CAST(race_key_raw AS VARCHAR)), "
        "trim(CAST(horse_no AS VARCHAR)), trim(CAST(blinker_code AS VARCHAR))")

    # All 2026 target facts are pre-race PACI projections. A SED row contributes
    # only proof that a prior start occurred and its date/key/identity; surface,
    # distance, and blinker status come from the matching earlier PACI fact.
    fact_lookup: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        if fact.get("horse_id"):
            fact_lookup[(fact["race_key"], str(fact["horse_no"]), fact["horse_id"])].append(fact)

    event_groups: dict[tuple[str, str, str], dict[str, set[Any]]] = defaultdict(lambda: {"dates": set(), "surface": set(), "distance": set()})
    identity_date: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in older_sed:
        blood, race, horse_no, date, surface, distance = row
        blood, race, horse_no = str(blood or "").strip(), str(race or "").strip(), str(horse_no or "").strip()
        date = str(date or "")[:10]
        if not (blood and race and horse_no and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date)):
            continue
        key = (blood, race, str(int(horse_no)))
        group = event_groups[key]
        group["dates"].add(date); group["surface"].add(str(surface or "").strip())
        group["distance"].add(_int(distance))
    older_events: list[dict[str, Any]] = []
    sed_conflicts = 0
    sed_duplicates = 0
    for (blood, race, horse_no), group in event_groups.items():
        if len(group["dates"]) != 1:
            sed_conflicts += 1
            continue
        date = next(iter(group["dates"]))
        surface_unknown = len(group["surface"]) != 1
        distance_unknown = len(group["distance"]) != 1
        if surface_unknown or distance_unknown:
            sed_conflicts += 1
        event = {"horse_id": blood, "race_key": race, "horse_no": horse_no,
                 "race_date": date, "surface_code": None if surface_unknown else next(iter(group["surface"])),
                 "distance_m": None if distance_unknown else next(iter(group["distance"])), "blinker_code": None,
                 "surface_unknown": surface_unknown, "blinker_unknown": False}
        older_events.append(event); identity_date[(blood, date)].add(race)

    kyi_groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for blood, race, horse_no, code in older_kyi:
        blood, race, horse_no = str(blood or "").strip(), str(race or "").strip(), str(horse_no or "").strip()
        if blood and race and horse_no:
            kyi_groups[(blood, race, str(int(horse_no)))].add(str(code or "").strip())
    older_event_map = {(e["horse_id"], e["race_key"], e["horse_no"]): e for e in older_events}
    for key, codes in kyi_groups.items():
        event = older_event_map.get(key)
        if event is None:
            continue
        if len(codes) == 1:
            event["blinker_code"] = next(iter(codes))
        else:
            event["blinker_unknown"] = True

    # Resolve 2026 actual starts to their PACI pre-race facts.
    current_events: list[dict[str, Any]] = []
    unjoined_2026 = 0
    for row in sed_rows:
        candidates = fact_lookup.get((row["race_key"], row["horse_no"], row["horse_id"]), [])
        if len(candidates) != 1:
            unjoined_2026 += 1
            current_events.append({**row, "surface_code": None, "distance_m": None,
                                   "blinker_code": None, "surface_unknown": True,
                                   "blinker_unknown": True})
            continue
        fact = candidates[0]
        current_events.append({**row, "surface_code": fact.get("surface_code"),
                               "distance_m": fact.get("distance_m"),
                               "blinker_code": fact.get("_blinker_code"),
                               "surface_unknown": fact.get("surface_code") is None,
                               "blinker_unknown": fact.get("_blinker_code") is None})

    all_events = older_events + current_events
    by_horse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    same_day_races: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in all_events:
        by_horse[event["horse_id"]].append(event)
        same_day_races[(event["horse_id"], event["race_date"])].add(event["race_key"])
    for rows in by_horse.values():
        rows.sort(key=lambda e: (e["race_date"], e["race_key"], e["horse_no"]))

    first_counts = Counter()
    unknown_counts = Counter()
    transitions_resolved = 0
    transitions_missing = 0
    # Current 2026 transition values are resolved strictly from prev1 links:
    # a prior 2026 PACI fact first, otherwise a 2010-2025 SED historical row.
    older_by_link: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in older_events:
        older_by_link[(event["race_key"], event["horse_id"])].append(event)
    current_by_link: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        if fact.get("horse_id"):
            current_by_link[(fact["race_key"], fact["horse_id"])].append(fact)
    for fact in facts:
        hid, target_date = fact.get("horse_id"), fact["race_date"]
        prior_key = fact.get("_prev1_race_key")
        previous: Mapping[str, Any] | None = None
        if hid and prior_key:
            candidates = [x for x in current_by_link.get((prior_key, hid), []) if x["race_date"] < target_date]
            if not candidates:
                candidates = [x for x in older_by_link.get((prior_key, hid), []) if x["race_date"] < target_date]
            if len(candidates) == 1:
                previous = candidates[0]
        if previous:
            features = derive_transition_features(
                current_distance=fact.get("distance_m"), current_surface_code=fact.get("surface_code"),
                current_frame_no=fact.get("frame_no"), previous_distance=previous.get("distance_m"),
                previous_surface_code=previous.get("surface_code"), previous_frame_no=previous.get("frame_no"))
            fact["distance_change"] = features.get("distance_change_bucket")
            fact["surface_transition"] = features.get("surface_transition")
            transitions_resolved += 1
        else:
            fact["distance_change"] = None
            fact["surface_transition"] = None
            transitions_missing += 1

        history = by_horse.get(str(hid or ""), []) if hid else []
        prior_events = [e for e in history if e["race_date"] < target_date]
        ambiguous_prior = any(len(same_day_races[(e["horse_id"], e["race_date"])]) > 1 for e in prior_events)
        target_ambiguous = bool(hid and len(same_day_races[(str(hid), target_date)]) > 1)
        for flag, target_surface in (("first_dirt", "2"), ("first_turf", "1")):
            value = derive_first_surface(fact.get("surface_code"), target_surface, prior_events,
                                         identity=bool(hid), target_ambiguous=target_ambiguous or ambiguous_prior)
            fact[flag] = value
            first_counts[flag] += value is True
            unknown_counts[flag] += value is None

        blink = derive_first_blinkers(fact.get("_blinker_code"), prior_events,
                                      identity=bool(hid), target_ambiguous=target_ambiguous or ambiguous_prior)
        fact["first_blinkers"] = blink
        first_counts["first_blinkers"] += blink is True
        unknown_counts["first_blinkers"] += blink is None

    return {"events_2010_2025": len(older_events), "events_2026": len(current_events),
            "sed_2026_unjoined_to_paci": unjoined_2026, "sed_2010_2025_conflict_groups": sed_conflicts,
            "transitions_resolved": transitions_resolved, "transitions_missing": transitions_missing,
            "first_true_counts": dict(first_counts), "first_unknown_counts": dict(unknown_counts),
            "warehouse": warehouse_audit}


def build_matches(candidates: list[dict[str, Any]], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_shape: dict[tuple[str, ...], dict[tuple[str | None, ...], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for candidate in candidates:
        conditions = candidate["conditions"]
        shape = tuple(sorted(conditions))
        values = tuple(_norm(key, conditions[key]) for key in shape)
        by_shape[shape][values].append(candidate)
    output: list[dict[str, Any]] = []
    for fact in facts:
        for shape, index in by_shape.items():
            values = tuple(_norm(key, fact.get(key)) for key in shape)
            if any(value is None for value in values):
                continue
            for candidate in index.get(values, []):
                conditions = candidate["conditions"]
                if not condition_matches(conditions, fact):
                    continue
                output.append({
                    "race_date": fact["race_date"], "race_key": fact["race_key"],
                    "race_horse_key": fact["race_horse_key"], "horse_id": fact.get("horse_id"),
                    "horse_no": fact.get("horse_no"), "candidate_id": candidate["candidate_id"],
                    "template_id": candidate["template_id"], "family": candidate["family"],
                    "condition_fingerprint": candidate["condition_fingerprint"],
                    "memo": candidate.get("memo"),
                    "matched_conditions": json.dumps(conditions, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                })
    output.sort(key=lambda r: (r["race_date"], r["race_key"], r["race_horse_key"], r["candidate_id"]))
    return output


def read_sed_archive_dates(root: Path) -> set[str]:
    paths = list(root.rglob("SED26????.zip"))
    return {f"20{p.name[5:7]}-{p.name[7:9]}-{p.name[9:11]}" for p in paths}


def _write_parquet(rows: list[dict[str, Any]], columns: list[str], path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    projected = [{key: row.get(key) for key in columns} for row in rows]
    table = pa.Table.from_pylist(projected)
    pq.write_table(table, path, compression="zstd")


def run_freeze(cohort_path: Path, paci_root: Path, sed_root: Path,
               warehouse_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    candidates, cohort_audit = load_cohort(cohort_path)
    paci_files = sorted(paci_root.rglob("PACI26????.zip"))
    facts, paci_audit = load_paci_facts(paci_files)
    sed_rows = load_2026_sed(sed_root)
    sed_dates = {row["race_date"] for row in sed_rows}
    paci_dates = {row["race_date"] for row in facts}
    if not paci_dates.issubset(sed_dates):
        raise FreezeError(f"PACI dates missing from SED chronology: {len(paci_dates-sed_dates)}")
    history_audit = build_history_index(facts, sed_rows, warehouse_root)
    for fact in facts:
        validate_match_fact_schema(fact)
    fact_rows = [{k: f.get(k) for k in FACT_COLUMNS} for f in facts]
    fact_sha = fingerprint_rows(fact_rows, ("race_date", "race_key", "race_horse_key"))
    matches = build_matches(candidates, facts)
    for row in matches:
        row["pre_race_fact_fingerprint"] = fact_sha
    match_sha = fingerprint_rows(matches, ("race_date", "race_key", "race_horse_key", "candidate_id"))
    for row in matches:
        if set(row) != set(MATCH_COLUMNS):
            raise FreezeError("match output schema differs from contract")
    if set(fact_rows[0]) & FORBIDDEN_FIELDS:
        raise FreezeError("forbidden result/market field entered matching facts")

    month_day: dict[str, dict[str, Any]] = {}
    fact_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    match_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in fact_rows:
        fact_by_date[row["race_date"]].append(row)
    for row in matches:
        match_by_date[row["race_date"]].append(row)
    for date in sorted(paci_dates):
        month_day[date] = {"fact_rows": len(fact_by_date[date]), "match_rows": len(match_by_date[date]),
            "fact_sha256": fingerprint_rows(fact_by_date[date], ("race_date", "race_key", "race_horse_key")),
            "match_sha256": fingerprint_rows(match_by_date[date], ("race_date", "race_key", "race_horse_key", "candidate_id"))}

    runner_match_counts = Counter(row["race_horse_key"] for row in matches)
    all_runner_counts = Counter(runner_match_counts.get(row["race_horse_key"], 0) for row in fact_rows)
    density = {"0": sum(1 for r in fact_rows if runner_match_counts.get(r["race_horse_key"], 0) == 0),
               "1": sum(1 for r in fact_rows if runner_match_counts.get(r["race_horse_key"], 0) == 1),
               "2": sum(1 for r in fact_rows if runner_match_counts.get(r["race_horse_key"], 0) == 2),
               "3_plus": sum(1 for r in fact_rows if runner_match_counts.get(r["race_horse_key"], 0) >= 3)}
    family_counts = Counter(row["family"] for row in matches)
    family_path = output_root / "v05_2026_match_counts_by_family.csv"
    with family_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["family", "match_rows"])
        for family, count in sorted(family_counts.items()): writer.writerow([family, count])
    day_path = output_root / "v05_2026_match_counts_by_day.csv"
    with day_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["race_date", "fact_rows", "match_rows", "fact_sha256", "match_sha256"])
        for day, item in sorted(month_day.items()): writer.writerow([day, item["fact_rows"], item["match_rows"], item["fact_sha256"], item["match_sha256"]])
    _write_parquet(fact_rows, FACT_COLUMNS, output_root / "v05_2026_pre_race_facts.parquet")
    _write_parquet(matches, MATCH_COLUMNS, output_root / "v05_2026_match_freeze.parquet")
    missing_days = sorted(sed_dates - paci_dates)
    paci_sed_equal = paci_dates == sed_dates
    recommendation = ("PARTIAL_PRE_RACE_COVERAGE"
        if not paci_sed_equal or history_audit["sed_2026_unjoined_to_paci"] or
           (facts and any(row["going_bucket"] is None for row in facts))
        else "READY_FOR_TURN3_OUTCOME_JOIN")
    audit = {
        "status": "PASS" if facts and paci_sed_equal else "PARTIAL",
        "recommendation": recommendation,
        "production_impact": "NONE",
        "input_provenance": {"cohort": cohort_audit, "paci": paci_audit,
            "paci_drive_folder_id": PACI_FOLDER_ID,
            "paci_source_generation": "Drive PACI folder snapshot, 2026-10-07",
            "sed_2026_run_id": SED_2026_RUN_ID, "sed_2026_artifact_id": SED_2026_ARTIFACT_ID,
            "warehouse_run_id": WAREHOUSE_RUN_ID, "warehouse_artifact_id": WAREHOUSE_ARTIFACT_ID,
            "warehouse_generation": WAREHOUSE_GENERATION},
        "coverage": {"first_race_date": min(paci_dates) if paci_dates else None,
            "latest_race_date": max(paci_dates) if paci_dates else None,
            "race_days": len(paci_dates), "sed_history_days": len(sed_dates),
            "races": paci_audit["paci_race_count"],
            "runners": len(facts), "sed_history_events": len(sed_rows),
            "paci_sed_date_sets_equal": paci_sed_equal, "paci_dates_missing_from_sed": [],
            "paci_dates_unavailable_for_matching": missing_days},
        "leakage_audit": {"result_fields_absent_from_matching_schema": not bool(set(FACT_COLUMNS) & FORBIDDEN_FIELDS),
            "payout_fields_absent": True, "popularity_absent": True, "odds_absent": True,
            "post_race_fields_absent": True,
            "sed_fields_read": ["race_key", "horse_no", "blood_registration_no", "race_date"],
            "warehouse_sed_fields_read": ["race_key_raw", "horse_no", "blood_registration_no", "race_date", "surface_code", "distance_m"],
            "warehouse_kyi_fields_read": ["race_key_raw", "horse_no", "blood_registration_no", "blinker_code"],
            "analysis_2026_fields_read": [], "going_bucket_source": "UNAVAILABLE_IN_CANONICAL_PRE_RACE_FACT_BUILDER"},
        "history_audit": history_audit,
        "cohort_verification": {**cohort_audit, "all_candidates_consumed": True},
        "matching": {"total_match_rows": len(matches), "unique_matched_runners": len(runner_match_counts),
            "runner_match_density": density, "family_counts": dict(family_counts),
            "maximum_matches_on_one_runner": max(runner_match_counts.values(), default=0),
            "candidate_count": len(candidates)},
        "fingerprints": {"pre_race_fact_sha256": fact_sha, "match_sha256": match_sha,
            "day_fingerprints": month_day},
        "unknown_condition_values": {key: sum(row.get(key) is None for row in facts)
            for key in ("sire_name", "distance_change", "surface_transition", "first_dirt", "first_turf", "first_blinkers", "going_bucket")},
    }
    (output_root / "v05_2026_match_freeze_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"schema_version": "edgedb-v05-2026-pre-race-match-freeze/v1",
        "status": audit["status"], "recommendation": recommendation,
        "cohort_sha256": cohort_audit["cohort_sha256"], "candidate_count": len(candidates),
        "pre_race_fact_sha256": fact_sha, "match_sha256": match_sha,
        "fact_row_count": len(fact_rows), "match_row_count": len(matches),
        "first_race_date": audit["coverage"]["first_race_date"],
        "latest_race_date": audit["coverage"]["latest_race_date"],
        "race_days": audit["coverage"]["race_days"], "race_count": audit["coverage"]["races"],
        "source_run_ids": {"turn1_freeze": 37598903743, "sed_2026": SED_2026_RUN_ID,
                           "warehouse": WAREHOUSE_RUN_ID},
        "source_artifact_ids": {"turn1_freeze": 11471917437, "sed_2026": SED_2026_ARTIFACT_ID,
                                "warehouse": WAREHOUSE_ARTIFACT_ID},
        "day_fingerprints": month_day}
    (output_root / "v05_2026_match_freeze_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--paci-root", type=Path, required=True)
    parser.add_argument("--sed-root", type=Path, required=True)
    parser.add_argument("--warehouse-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_freeze(args.cohort, args.paci_root, args.sed_root, args.warehouse_root, args.output_root)
    print(json.dumps({"status": result["status"], "recommendation": result["recommendation"],
                      "coverage": result["coverage"], "matching": result["matching"],
                      "fingerprints": {k: v for k, v in result["fingerprints"].items() if k != "day_fingerprints"}},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
