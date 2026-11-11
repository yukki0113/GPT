#!/usr/bin/env python3
"""Independent, human-authored W/R/U/D research shadow; never changes canonical Confidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "racenote-v056-wrud-shadow-0.1"
DAY_RE = re.compile(r"BTDAY-\d{4}")
STANDARD = {"A", "B", "C"}
GRADES = STANDARD | {"Z"}
FIELDS = ("winning_route", "rival_relative_advantage", "uncertainty_defeat_test", "distinctive_evidence", "shadow_reason")


def fail(message):
    raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bytes_canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_root(root):
    root = Path(root)
    if not (root.name == "v056" and root.parent.name.isdigit() and len(root.parent.name) == 8
            and DAY_RE.fullmatch(root.parent.parent.name or "")):
        fail("root must be an immutable BTDAY-xxxx/YYYYMMDD/v056 directory")
    return root


def verify_sources(root):
    root = canonical_root(root)
    summary = load(root / "turn2_summary.json")
    ph = load(root / "frozen" / "day_handoff.json")
    ch = load(root / "confidence_frozen" / "day_handoff.json")
    if summary.get("status") != "TURN2_COMPLETE" or summary.get("prediction_status") != "PREDICTION_FROZEN_CLEAN_BLIND" or summary.get("confidence_status") != "CONFIDENCE_FROZEN_CLEAN_BLIND":
        fail("official two-phase Freeze incomplete")
    if summary.get("result_opened") is not False or summary.get("target_market_opened") is not False:
        fail("source Freeze has been marked result/market-opened")
    if ph.get("status") != "PREDICTION_FROZEN_CLEAN_BLIND" or ch.get("status") != "CONFIDENCE_FROZEN_CLEAN_BLIND":
        fail("official day handoffs not sealed")
    if ch.get("result_opened") is not False or ch.get("target_market_opened") is not False:
        fail("confidence handoff not blind")
    if ch.get("selection_id") != summary.get("selection_id"):
        fail("selection id differs")
    if ch.get("target_date") != summary.get("target_date"):
        fail("target date differs")
    pred_path = root / "frozen" / "records.json"
    conf_path = root / "confidence_frozen" / "records.json"
    pred_hash, conf_hash = digest(pred_path), digest(conf_path)
    for obj in (summary, ch):
        if obj.get("prediction_records_sha256") != pred_hash or obj.get("confidence_records_sha256") != conf_hash:
            fail("canonical source SHA256 mismatch")
    if ph.get("records_sha256") != pred_hash:
        fail("prediction handoff SHA256 mismatch")
    predictions = load(pred_path)
    confidences = load(conf_path)
    pmap = {(x["venue"], x["race_no"]): x for x in predictions}
    cmap = {(x["venue"], x["race_no"]): x for x in confidences}
    if len(pmap) != len(predictions) or len(cmap) != len(confidences) or set(pmap) != set(cmap) or len(pmap) != summary.get("record_count"):
        fail("official race roster count/key mismatch")
    for key in pmap:
        if pmap[key]["decision_core"]["marks"][0] != cmap[key]["honmei"]:
            fail("official frozen honmei mismatch: " + str(key))
        if cmap[key]["confidence"] not in GRADES:
            fail("unexpected official grade: " + str(key))
    return summary, predictions, confidences


def template(root):
    summary, predictions, confidences = verify_sources(root)
    rows = []
    for x in confidences:
        grade = x["confidence"]
        z = dict(venue=x["venue"], race_no=x["race_no"], honmei=x["honmei"],
                 official_confidence=grade, shadow_confidence=grade if grade == "Z" else None)
        z.update({field: None for field in FIELDS})
        rows.append(z)
    return dict(schema_version=SCHEMA, selection_id=summary["selection_id"], target_date=summary["target_date"],
                prediction_records_sha256=summary["prediction_records_sha256"],
                confidence_records_sha256=summary["confidence_records_sha256"],
                evidence_attestation={"result_not_accessed_by_reviewer": False,
                                      "target_market_not_accessed_by_reviewer": False,
                                      "review_authored_before_result_query": False,
                                      "attested_by": ""},
                records=rows)


def validate(root, draft):
    summary, predictions, confidences = verify_sources(root)
    data = load(draft) if isinstance(draft, (str, Path)) else draft
    if data.get("schema_version") != SCHEMA or data.get("selection_id") != summary["selection_id"] or data.get("target_date") != summary["target_date"]:
        fail("shadow schema, BTDAY or date differs from Freeze")
    for field in ("prediction_records_sha256", "confidence_records_sha256"):
        if data.get(field) != summary.get(field):
            fail("shadow source SHA mismatch " + field)
    att = data.get("evidence_attestation") or {}
    for x in ("result_not_accessed_by_reviewer", "target_market_not_accessed_by_reviewer",
              "review_authored_before_result_query"):
        if att.get(x) is not True:
            fail("human provenance attestation missing: " + x)
    if not isinstance(att.get("attested_by"), str) or not att["attested_by"].strip():
        fail("explicit human reviewer id/handle is required")
    rows = data.get("records")
    if not isinstance(rows, list) or len(rows) != len(confidences):
        fail("all races, including Z, must have one review row each")
    mmap = {(x["venue"], x["race_no"]): x for x in confidences}
    used = set()
    for row in rows:
        key = (row.get("venue"), row.get("race_no"))
        if key in used or key not in mmap:
            fail("duplicate or unknown shadow race: " + str(key))
        used.add(key)
        official = mmap[key]
        if row.get("honmei") != official["honmei"] or row.get("official_confidence") != official["confidence"]:
            fail("shadow attempts to alter official honmei/grade: " + str(key))
        shadow = row.get("shadow_confidence")
        if official["confidence"] == "Z":
            if shadow != "Z" or any(row.get(f) is not None for f in FIELDS):
                fail("Z must remain out-of-scope, with null research evidence")
            continue
        if shadow not in STANDARD:
            fail("shadow A/B/C must be authored on all standard-flat races")
        claims = []
        for field in FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or len(value.strip()) < 15:
                fail("missing substantive human-authored " + field + " for " + str(key))
            claims.append(value.strip())
        if len(set(claims)) != len(claims):
            fail("W/R/U/D and rationale must have distinct content: " + str(key))
    if used != set(mmap):
        fail("shadow missed one or more official races")
    return dict(selection_id=summary["selection_id"], records=len(rows),
                official_counts={x: sum(1 for r in rows if r["official_confidence"] == x) for x in ("A", "B", "C", "Z")},
                shadow_counts={x: sum(1 for r in rows if r["shadow_confidence"] == x) for x in ("A", "B", "C", "Z")})


def freeze(root, draft):
    root = canonical_root(root)
    result = validate(root, draft)
    base = root / "research" / "wrud"
    output = base / "frozen"
    if output.exists() or (base / "seal.json").exists():
        fail("shadow already frozen; no overwrite, use a separate research version")
    raw = Path(draft).read_bytes()
    data = json.loads(raw)
    normalized = bytes_canonical(data)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "records.json"
    frozen.write_bytes(normalized)
    receipt = dict(schema_version=SCHEMA, status="WRUD_SHADOW_FROZEN",
                   source_prediction_records_sha256=data["prediction_records_sha256"],
                   source_confidence_records_sha256=data["confidence_records_sha256"],
                   reviewed_before_result_query_attested=True,
                   evidence_provenance_is_human_attestation_not_independent_proof=True,
                   records_sha256=hashlib.sha256(normalized).hexdigest(), **result)
    (output / "seal.json").write_bytes(bytes_canonical(receipt))
    return receipt


def self_test():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "BTDAY-9999" / "20250101" / "v056"
        (root / "frozen").mkdir(parents=True)
        (root / "confidence_frozen").mkdir()
        p = [dict(venue="中京", race_no=1, decision_core={"marks": [1, 2, 3, 4, 5]}),
             dict(venue="中京", race_no=2, decision_core={"marks": [3, 1, 2, 4, 5]})]
        c = [dict(venue="中京", race_no=1, honmei=1, confidence="B"),
             dict(venue="中京", race_no=2, honmei=3, confidence="Z")]
        pp, cp = root / "frozen" / "records.json", root / "confidence_frozen" / "records.json"
        pp.write_bytes(bytes_canonical(p)); cp.write_bytes(bytes_canonical(c))
        summary = dict(status="TURN2_COMPLETE", prediction_status="PREDICTION_FROZEN_CLEAN_BLIND",
                       confidence_status="CONFIDENCE_FROZEN_CLEAN_BLIND", result_opened=False,
                       target_market_opened=False, selection_id="BTDAY-9999", target_date="2025-01-01",
                       record_count=2, prediction_records_sha256=digest(pp), confidence_records_sha256=digest(cp))
        (root / "turn2_summary.json").write_bytes(bytes_canonical(summary))
        (root / "frozen" / "day_handoff.json").write_bytes(bytes_canonical(dict(status="PREDICTION_FROZEN_CLEAN_BLIND", records_sha256=digest(pp))))
        (root / "confidence_frozen" / "day_handoff.json").write_bytes(bytes_canonical(dict(
            status="CONFIDENCE_FROZEN_CLEAN_BLIND", selection_id="BTDAY-9999", target_date="2025-01-01",
            result_opened=False, target_market_opened=False,
            prediction_records_sha256=digest(pp), confidence_records_sha256=digest(cp))))
        draft = template(root)
        draft["evidence_attestation"] = dict(result_not_accessed_by_reviewer=True,
                                             target_market_not_accessed_by_reviewer=True,
                                             review_authored_before_result_query=True, attested_by="test-reviewer")
        draft["records"][0].update(shadow_confidence="A",
            winning_route="今回の芝1800で前を取って最後まで加速する勝ち筋を確認",
            rival_relative_advantage="○2の同舞台連対と比べて◎1には現級勝利の直接性がある",
            uncertainty_defeat_test="○2が先行した場合は危険だが◎1には後方から差す代替経路がある",
            distinctive_evidence="直近二戦の条件一致と相手の実走履歴を個別に照合した",
            shadow_reason="相手の具体的な勝利経路を超える十分な優位性を確認できる")
        validate(root, draft)
        broken = json.loads(json.dumps(draft)); broken["records"][0]["honmei"] = 99
        try:
            validate(root, broken)
            fail("negative test failed to reject changed honmei")
        except ValueError:
            pass
        broken = json.loads(json.dumps(draft)); broken["evidence_attestation"]["result_not_accessed_by_reviewer"] = False
        try:
            validate(root, broken)
            fail("negative test failed to reject no attestation")
        except ValueError:
            pass
        draft_path = root / "review.json"
        draft_path.write_bytes(bytes_canonical(draft))
        sealed = freeze(root, draft_path)
        if sealed["shadow_counts"]["A"] != 1:
            fail("shadow count test failed")
        try:
            freeze(root, draft_path)
            fail("negative test failed to reject replay")
        except ValueError:
            pass
        return "PASS: template, valid review, changed-honmei rejection, attestation rejection, seal and replay rejection"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("template", "validate", "freeze", "self-test"))
    parser.add_argument("--root")
    parser.add_argument("--draft")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.mode == "self-test":
        print(self_test()); return
    if not args.root:
        parser.error("--root is required")
    if args.mode == "template":
        result = template(args.root)
        if not args.output:
            parser.error("--output required for template")
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            fail("template output exists; no overwrite")
        out.write_bytes(bytes_canonical(result))
        print(json.dumps({"status": "TEMPLATE_ONLY", "output": str(out), "records": len(result["records"])}, ensure_ascii=False))
    elif args.mode == "validate":
        if not args.draft:
            parser.error("--draft required")
        print(json.dumps({"status": "VALID", **validate(args.root, args.draft)}, ensure_ascii=False))
    else:
        if not args.draft:
            parser.error("--draft required")
        print(json.dumps(freeze(args.root, args.draft), ensure_ascii=False))


if __name__ == "__main__":
    main()
