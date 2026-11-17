#!/usr/bin/env python3
"""Research-only M7 PACI field replay: accepted ①–④ -> v0.2 -> v0.3+D4.

Run only with real canonical PACI and fixed research input files. No scoring,
prediction or production writes. Individual-horse outputs remain outside Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import jsonschema

from brdb_d4_paci_field import extract
from brdb_m7_evidence_adapter import build_v02, M7FieldError, require
from brdb_integrated_review_v03_candidate import merge
from run_brdb_d4_sidecar import PINS

ROOT = Path(__file__).resolve().parents[3]
BRDB = ROOT / "horse-racing/brdb"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validated(schema_file, obj):
    schema = read_json(BRDB / "schema" / schema_file)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()).validate(obj)


def run(*, paci, race_key, sire_bms, d4, output_dir, pairing=None, relatives=None):
    paci = Path(paci).resolve(strict=True)
    input_files = {"sire_bms": Path(sire_bms).resolve(strict=True),
                   "d4": Path(d4).resolve(strict=True)}
    if pairing is not None:
        input_files["pairing"] = Path(pairing).resolve(strict=True)
    if relatives is not None:
        input_files["relatives"] = Path(relatives).resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    require(not output_dir.is_relative_to(ROOT), "private horse-level outputs may not enter Git")
    context, receipt = extract(paci, race_key)
    require(receipt["source_archive_sha256"] == sha(paci.read_bytes()),
            "PACI archive fingerprint mismatch")
    data = {key: read_json(path) for key, path in input_files.items()}
    sidecar = data["d4"]
    require(isinstance(sidecar, dict) and isinstance(sidecar.get("provenance"), dict),
            "missing D4 provenance")
    require(sidecar["provenance"].get("research_field_sha256") == sha(canonical_bytes(context)),
            "D4 and PACI extracted context bytes mismatch")
    for name, expected in PINS.items():
        require(sidecar["provenance"].get("d3_" + name + "_sha256") == expected,
                "D4 frozen D3 SHA mismatch: " + name)

    def compose():
        v02 = build_v02(context, receipt, data["sire_bms"],
                        pairing=data.get("pairing"), relatives=data.get("relatives"))
        validated("brdb_integrated_review_v0_2_candidate.schema.json", v02)
        v03 = merge(v02, sidecar)
        validated("brdb_integrated_review_v0_3_candidate.schema.json", v03)
        require(v03["supplemental_research"]["prediction_safe"] is False,
                "prediction-safe promotion forbidden")
        require(len(v02["horses"]) == len(v03["horses"]) ==
                context["race"]["field_size"], "full-field mismatch")
        return v02, v03

    first = compose()
    second = compose()
    first_bytes = [canonical_bytes(x) for x in first]
    second_bytes = [canonical_bytes(x) for x in second]
    require(first_bytes == second_bytes, "non-deterministic integrated field replay")
    summary = {
        "status": "RESEARCH_FIELD_COMPOSITION_PASS",
        "production_authorized": False, "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "race_key": race_key, "field_size": context["race"]["field_size"],
        "reviewed_horses": len(second[1]["horses"]),
        "inputs_sha256": {"paci": receipt["source_archive_sha256"],
                          **{key: sha(path.read_bytes())
                             for key, path in input_files.items()}},
        "output_sha256": {"v02": sha(second_bytes[0]), "v03": sha(second_bytes[1])},
        "components_supplied": {"sire": True, "broodmare_sire": True,
                                "pairing": "pairing" in data,
                                "relatives": "relatives" in data},
        "supplemental_evidence_items":
            second[1]["supplemental_research"]["aggregate_coverage"]["research_evidence_items"],
        "input_generation": second[0]["source_generations"],
        "schema_validation": ["v0.2", "v0.3"],
        "determinism": "TWO_COMPOSITION_RUNS_BYTE_IDENTICAL",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in zip(("m7_integrated_v02.json", "m7_integrated_v03.json"),
                         second_bytes):
        (output_dir / name).write_bytes(raw)
    (output_dir / "m7_replay_receipt.json").write_bytes(canonical_bytes(summary))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paci", required=True, type=Path)
    p.add_argument("--race-key", required=True)
    p.add_argument("--sire-bms", required=True, type=Path)
    p.add_argument("--pairing", type=Path)
    p.add_argument("--relatives", type=Path)
    p.add_argument("--d4", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()
    summary = run(paci=a.paci, race_key=a.race_key, sire_bms=a.sire_bms,
                  pairing=a.pairing, relatives=a.relatives,
                  d4=a.d4, output_dir=a.output_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
