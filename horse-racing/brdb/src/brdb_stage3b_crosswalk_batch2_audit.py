"""Five-subject guarded JRDB↔JBIS identity audit (research only).

Input JRDB rows must originate from the immutable research pedigree source.
Source corroboration URLs are preserved, not fetched or trusted as horse IDs.
The audit only counts three incremental externally linked ancestor-name slots.
"""
from __future__ import annotations

import json
from pathlib import Path


class CrosswalkAuditError(ValueError):
    """Fail closed on an inconsistent individual or pedigree path."""


def _require(condition: bool, reason: str) -> None:
    """Reject invalid identity, lineage or pedigree evidence."""
    if not condition:
        raise CrosswalkAuditError(reason)


def audit(registry: dict, bridge: dict, profiles: list[dict],
          top50: dict, baseline: dict) -> dict:
    """Validate five JRDB subject identities and three incremental paths."""
    _require(registry.get("schema_version") ==
             "brdb-stage3b-person-identity-crosswalk-candidate-v0.2",
             "unsupported crosswalk registry")
    _require(registry.get("source_generation") == "5279af0bd8226cde",
             "wrong JRDB source generation")
    _require(registry.get("historical_asof_status") == "AS_OF_UNVERIFIED"
             and registry.get("prediction_safe") is False,
             "unapproved historical availability")
    _require(top50.get("research_only") is True
             and top50.get("prediction_safe") is False
             and top50.get("source_generation") == registry["source_generation"],
             "unverified top50 research snapshot")
    _require(bridge.get("schema_version") ==
             "brdb-stage3b-priority4-bridge-candidate-v0.4"
             and bridge.get("prediction_safe") is False,
             "unexpected bridge version")
    identities = registry.get("approved_research_crosswalks", [])
    _require(len(identities) == 5 and
             registry.get("still_pending_anchor_count") == 26,
             "expected five research identities, 26 under review")
    source_profiles = {}
    for p in profiles:
        ident = p.get("horse_id")
        _require(ident not in source_profiles, "duplicate JRDB horse_id")
        source_profiles[ident] = p
    anchors = {x["jrdb_horse_id"]: x for x in bridge["anchors"]}
    _require(len(anchors) == 31, "wrong source-bridge cohort")
    ancestors = {x["external_subject_key"]: x
                 for x in bridge["external_ancestor_subjects"]}
    paths = {(e["jrdb_child_horse_id"], e["path"]): e
             for e in bridge["external_parent_edges"]}
    _require(len(paths) == 48, "source bridge path collisions")
    subjects = {x["name"]: x for x in top50["subjects"]}
    _require(len(top50["subjects"]) == 50, "wrong ranked cohort")
    matched = []
    seen_jbis = set()
    for identity in identities:
        jrdb_id = identity["jrdb_horse_id"]
        jbis_id = identity["jbis_horse_id"]
        external_key = "JBIS:" + jbis_id
        _require(external_key not in seen_jbis, "repeated JBIS person ID")
        seen_jbis.add(external_key)
        _require(identity["external_subject_key"] == external_key and
                 identity["jbis_source_url"] ==
                 "https://www.jbis.or.jp/horse/" + jbis_id + "/",
                 "JBIS identity URL mismatch")
        _require(identity["person_resolution_status"] ==
                 "RESEARCH_MULTI_GUARD_VERIFIED"
                 and identity["review_use_allowed"] is False
                 and identity["source_time_asof_verified"] is False,
                 "person identity promoted to publication")
        p = source_profiles.get(jrdb_id)
        a = anchors.get(jrdb_id)
        s = subjects.get(identity["name"])
        _require(p is not None and a is not None and s is not None,
                 "canonical source identity unavailable")
        _require(s["jrdb_horse_id"] == jrdb_id and
                 a["external_jbis_subject_key"] == external_key and
                 a["observed_jrdb_name"] == identity["name"] and
                 a["observed_birth_year"] ==
                 int(identity["birth_date"][:4]),
                 "top50/JBIS subject identity conflict")
        keys = ("horse_id", "horse_name", "birth_date", "sex_code",
                "sire_name", "sire_birth_year", "dam_name",
                "dam_birth_year", "sire_line_code")
        values = (
            jrdb_id, identity["name"], identity["birth_date"].replace("-", ""),
            identity["sex_code"], identity["jrdb_sire_name"],
            identity["jrdb_sire_birth_year"], identity["jrdb_dam_name"],
            identity["jrdb_dam_birth_year"], identity["jrdb_sire_line_code"],
        )
        for key, value in zip(keys, values):
            _require(p.get(key) == value,
                     "pinned JRDB fact conflict: " + key)
        _require(a["observed_jrdb_lineage_code"] ==
                 identity["jrdb_sire_line_code"] and
                 identity["sex_code"] == "1", "lineage or sex conflict")
        _require(identity["additional_independent_source_url"].startswith(
                     ("https://www.jra.go.jp/", "https://sp.jra.jp/")),
                 "independent external corroboration is missing")
        for link in identity["parent_links"]:
            role = link["path"]
            source = paths.get((jrdb_id, role))
            _require(source is not None and
                     source["external_ancestor_key"] ==
                     link["external_ancestor_key"],
                     "person path is not in independently sourced bridge")
            ancestor = ancestors.get(link["external_ancestor_key"])
            _require(ancestor is not None and
                     ancestor["label_jp"] == link["parent_name_jp"] and
                     ancestor["jrdb_horse_id"] is None,
                     "external ancestor person not independently verified")
            observed = [node for node in s["paths"]
                        if node["path"] == role and
                        node["name"] == ancestor["label_jp"] and
                        node["id"] is None]
            _require(len(observed) == 1, "unconfirmed top50 ancestor slot")
            matched.append((identity["name"], role))
    _require(len(matched) == 7, "two original S/D pairs plus three new paths")
    old = {(x["stallion_name"], x["path"]) for x in baseline["paths"]}
    pending = {(x["stallion_name"], x["path"])
               for x in baseline["still_pending"]}
    _require(len(old) == 26 and len(pending) == 22
             and old.isdisjoint(pending), "original audit is inconsistent")
    new = set(matched) - old
    _require(len(new) == 3 and new <= pending and
             len(old | new) == 29, "unapproved path promotion")
    return {
        "version": "brdb-stage3b-crosswalk-batch2-audit-v0.1",
        "research_only": True, "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "source_generation": registry["source_generation"],
        "individual_crosswalks": 5,
        "original_hybrid_paths": 26,
        "additional_hybrid_paths": 3,
        "combined_hybrid_paths": 29,
        "source_observed_priority_paths": 48,
        "pending_person_provenance_paths": 19,
        "new_canonical_jrdb_ancestor_ids": 0,
        "new_paths": [
            {"stallion_name": name, "path": path}
            for name, path in sorted(new)
        ],
    }


def main() -> None:
    """Read pinned research inputs and write a non-production audit result."""
    import argparse
    parser = argparse.ArgumentParser()
    for flag in ("registry", "bridge", "profiles",
                 "top50", "baseline", "output"):
        parser.add_argument("--" + flag, required=True, type=Path)
    args = parser.parse_args()
    sources = [json.loads(getattr(args, item).read_text(encoding="utf-8"))
               for item in ("registry", "bridge", "profiles",
                            "top50", "baseline")]
    result = audit(*sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
