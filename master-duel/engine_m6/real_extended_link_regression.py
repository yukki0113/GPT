"""Private Gen9, read-only LINK range/race union source-anchor regression.

No private names, IDs, card text, ownership or candidate boards are emitted.
Static candidate probes are not verified summon routes.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .extended_material_eligibility import (
    observe_extended_link_header, diagnose_extended_link_materials,
)


def audit_real_extended_link(db_path, *, expected_sqlite_sha256):
    path = Path(db_path)
    if (not isinstance(expected_sqlite_sha256, str)
            or len(expected_sqlite_sha256) != 64
            or sha256(path.read_bytes()).hexdigest() != expected_sqlite_sha256):
        raise ValueError("EXTENDED_REAL_MASTER_SHA_MISMATCH")
    db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("EXTENDED_REAL_INTEGRITY")
        rows = db.execute(
            "SELECT r.card_id,r.material_header,r.material_header_sha256,"
            "r.source_text_sha256,t.body FROM card_extra_material_requirements r "
            "JOIN card_texts t ON t.card_id=r.card_id AND t.language='ja' "
            "WHERE r.grammar='UNPARSED' AND r.summon_method='LINK' "
            "ORDER BY r.card_id"
        ).fetchall()
        if len(rows) != 385:
            raise ValueError("EXTENDED_REAL_COVERAGE_MISMATCH")
        cards = db.execute(
            "SELECT card_id,race,level,link FROM card_attributes "
            "WHERE kind='MONSTER' ORDER BY card_id"
        ).fetchall()
        summary = Counter()
        for x in rows:
            if (sha256(x["material_header"].encode()).hexdigest()
                    != x["material_header_sha256"]
                or sha256(x["body"].encode()).hexdigest()
                    != x["source_text_sha256"]):
                raise ValueError("EXTENDED_REAL_SOURCE_ANCHOR_MISMATCH")
            spec = observe_extended_link_header(x["material_header"])
            if spec is None:
                summary["not_observed"] += 1
                continue
            summary[spec["grammar"]] += 1
            n = spec["min_materials"]
            link = db.execute(
                "SELECT link FROM card_attributes WHERE card_id=?",
                (x["card_id"],)).fetchone()[0]
            def qualifies(m):
                return (m["link"] is None
                        and (not spec["races"] or m["race"] in spec["races"])
                        and (spec["level"] is None
                             or m["level"] is not None
                             and (m["level"] <= spec["level"]
                                  if spec["operator"] == "以下"
                                  else m["level"] >= spec["level"])))
            def disqualifies(m):
                return (m["link"] is None
                        and ((spec["races"] and m["race"] not in spec["races"])
                             or (spec["level"] is not None
                                 and m["level"] is not None
                                 and (m["level"] > spec["level"]
                                      if spec["operator"] == "以下"
                                      else m["level"] < spec["level"]))))
            good = next((m for m in cards if qualifies(m)), None)
            bad = next((m for m in cards if disqualifies(m)), None)
            if good and n == link:
                status, _ = diagnose_extended_link_materials(
                    db, source_header=x["material_header"],
                    material_card_ids=[good["card_id"]]*n,
                    link_material_ratings=[1]*n, target_link=link)
                if status != "MATCH":
                    raise AssertionError("EXTENDED_REAL_POSITIVE_NOT_MATCHED")
                summary["static_positive"] += 1
            else:
                summary["static_positive_unavailable"] += 1
            if bad:
                ids = [bad["card_id"]] + [
                    (good or bad)["card_id"]
                ]*(n-1)
                status, _ = diagnose_extended_link_materials(
                    db, source_header=x["material_header"],
                    material_card_ids=ids,
                    link_material_ratings=[1]*n, target_link=link)
                if status == "MATCH":
                    raise AssertionError("EXTENDED_REAL_FALSE_MATCH")
                summary["static_adversarial_nonmatch"] += 1
            else:
                summary["static_adversarial_unavailable"] += 1
        if summary["LINK_LEVEL_RANGE_AND_OPTIONAL_RACE_SOURCE_ONLY"] != 14:
            raise ValueError("EXTENDED_REAL_LEVEL_COVERAGE_DRIFT")
        if summary["LINK_RACE_UNION_SOURCE_ONLY"] != 10:
            raise ValueError("EXTENDED_REAL_RACE_COVERAGE_DRIFT")
        return {
            "schema": "md-gen9-extended-link-static-regression-v1",
            "master_sqlite_sha256": expected_sqlite_sha256,
            "source_pins": "PASS",
            "counts": dict(sorted(summary.items())),
            "false_match_probes": 0,
            "authorizing_decisions": 0,
            "private_card_details_emitted": False,
            "warning": "Static candidates from canonical attributes are not summon-route evidence.",
        }
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_real_extended_link(
        args.db_path, expected_sqlite_sha256=args.sha256), indent=2))
