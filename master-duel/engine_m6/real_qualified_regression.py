"""Private Gen9 read-only real-card static material regression.

The input is a SHA-pinned private SQLite file. This emits aggregate counts
only; never print card IDs, names, effect text, or inventory. These probes
are not sourced summon routes and must NEVER authorize M6-5B acceptance.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .material_eligibility import ATTRIBUTES, RACES, SUPPORTED_TYPES, diagnose_qualified_materials
from .qualified_material_grammar import observe_qualified_header


def audit_real_qualified_eligibility(db_path, *, expected_sqlite_sha256):
    path = Path(db_path)
    if len(expected_sqlite_sha256) != 64 or sha256(path.read_bytes()).hexdigest() != expected_sqlite_sha256:
        raise ValueError("REAL_QUALIFIED_MASTER_SHA_MISMATCH")
    db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("REAL_QUALIFIED_INTEGRITY")
        rows = db.execute(
            "SELECT r.card_id,r.summon_method,r.material_header,"
            "r.material_header_sha256,r.source_text_sha256,t.body "
            "FROM card_extra_material_requirements r JOIN card_texts t "
            "ON t.card_id=r.card_id AND t.language='ja' "
            "WHERE r.grammar='UNPARSED' AND r.summon_method IN ('XYZ','LINK') "
            "ORDER BY r.card_id"
        ).fetchall()
        if len(rows) != 606:
            raise ValueError("REAL_QUALIFIED_EXPECTED_COVERAGE_MISMATCH")
        cards = db.execute(
            "SELECT card_id,kind,attribute,race,level,link FROM card_attributes "
            "WHERE kind='MONSTER' ORDER BY card_id"
        ).fetchall()
        types = {}
        for cid, flag in db.execute("SELECT card_id,monster_type FROM card_monster_types"):
            types.setdefault(cid, set()).add(flag)

        summary = Counter()
        for req in rows:
            method, header = req["summon_method"], req["material_header"]
            if (sha256(header.encode()).hexdigest() != req["material_header_sha256"] or
                    sha256(req["body"].encode()).hexdigest() != req["source_text_sha256"]):
                raise ValueError("REAL_QUALIFIED_SOURCE_PIN_MISMATCH")
            obs = observe_qualified_header(method, header)
            if obs["grammar"] == "UNPARSED":
                summary[(method,"not_observed")] += 1
                continue
            summary[(method,"observed")] += 1
            q = obs["qualifier_source"]
            if q in ATTRIBUTES:
                field, value = "attribute", ATTRIBUTES[q]
            elif q in RACES:
                field, value = "race", RACES[q]
            elif method == "LINK" and q in SUPPORTED_TYPES:
                field, value = "type", SUPPORTED_TYPES[q]
            else:
                summary[(method,"unsupported")] += 1
                # UNKNOWN must be preserved even when plausible IDs are supplied.
                sample = [cards[0]["card_id"]] * obs["min_materials"]
                status, _ = diagnose_qualified_materials(
                    db, method=method, source_header=header,
                    material_card_ids=sample)
                if status != "UNKNOWN":
                    raise AssertionError("UNSUPPORTED_QUALIFIER_PROMOTED")
                continue
            summary[(method,field+"_supported")] += 1

            def qualifies(row):
                if field == "type":
                    basic = value in types.get(row["card_id"], ())
                else:
                    basic = row[field] == value
                return basic and (method != "XYZ" or row["level"] == obs["level_required"])

            good = next((v for v in cards if qualifies(v) and v["link"] is None), None)
            bad = next((v for v in cards if
                        (value not in types.get(v["card_id"], ()) if field == "type"
                         else v[field] != value)
                        and (method != "XYZ" or v["level"] == obs["level_required"])
                        and v["link"] is None), None)
            n = obs["min_materials"]
            target = db.execute(
                "SELECT link FROM card_attributes WHERE card_id=?",
                (req["card_id"],)
            ).fetchone()
            link_value = target["link"] if target else None
            # The deliberately fabricated candidate state is only a static
            # comparator. Without evidence of access/route it is not playable.
            if good is not None and (method == "XYZ" or link_value == n):
                ids = [good["card_id"]] * n
                ratings = [1] * n if method == "LINK" else []
                status, _ = diagnose_qualified_materials(
                    db, method=method, source_header=header,
                    material_card_ids=ids, link_material_ratings=ratings,
                    target_link=link_value)
                if status != "MATCH":
                    raise AssertionError("MATCHING_STATIC_CARD_REJECTED")
                summary[(method,"static_positive_match")] += 1
            else:
                summary[(method,"positive_unavailable")] += 1
            if bad is not None:
                ids = [bad["card_id"]] + ([good["card_id"]] * (n-1)
                                           if good else [bad["card_id"]] * (n-1))
                status, _ = diagnose_qualified_materials(
                    db, method=method, source_header=header,
                    material_card_ids=ids, link_material_ratings=([1]*n if method=="LINK" else []),
                    target_link=link_value)
                if status == "MATCH":
                    raise AssertionError("WRONG_QUALIFIER_FALSE_MATCH")
                summary[(method,"adversarial_nonmatch")] += 1
            else:
                summary[(method,"negative_unavailable")] += 1
        return {
            "schema": "md-gen9-qualified-static-real-regression-v1",
            "master_sqlite_sha256": expected_sqlite_sha256,
            "examined": len(rows),
            "counts": {m: {key: summary[(m,key)] for key in sorted(
                {k for (method,k) in summary if method==m})} for m in ("XYZ","LINK")},
            "source_pins": "PASS",
            "false_positive_in_adversarial_probes": 0,
            "authorizing_decisions": 0,
            "private_card_details_emitted": False,
            "warning": "Synthetic candidate-state probes on real card attributes; not verified routes, ownership, or gameplay.",
        }
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("db_path")
    p.add_argument("--sha256", required=True)
    args = p.parse_args()
    print(json.dumps(audit_real_qualified_eligibility(
        args.db_path, expected_sqlite_sha256=args.sha256), indent=2))
