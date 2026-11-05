"""Validate registered Stage-2 JBIS identity and observed pedigree references.

Research-only: no JRDB identity mapping, aptitude inference or production write.
Use this for deterministic seed validation before a future generation builder.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse


class Stage2RegistryError(ValueError):
    """Invalid identity, source, or unapproved pedigree assertion."""


def load_json(path: str | Path) -> dict:
    """Read a UTF-8 JSON source without inferring missing pedigree fields."""
    with Path(path).open("r", encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise Stage2RegistryError("expected JSON object")
    return data


def _check(condition: bool, reason: str) -> None:
    """Raise for any unsafe registry assertion."""
    if not condition:
        raise Stage2RegistryError(reason)


def _source_id_from_url(url: str) -> str:
    """Extract the ten-digit external JBIS page identifier without network use."""
    _check(isinstance(url, str), "source URL must be a string")
    parsed = urlparse(url)
    _check(parsed.scheme == "https" and parsed.netloc == "www.jbis.jp",
           "source must be a canonical JBIS https URL")
    match = re.fullmatch(r"/horse/([0-9]{10})/", parsed.path)
    _check(match is not None and not parsed.query and not parsed.fragment,
           "source URL must identify one JBIS horse")
    return match.group(1)


def validate_registry(registry: dict, shortlist: dict, observations: dict) -> dict:
    """Validate twelve subjects, parent evidence, code observations, and paths.

    Name-only observations remain external identifiers unresolved as JRDB IDs.
    The result is a count-only audit and cannot be passed off as a review.
    """
    _check(isinstance(registry, dict), "registry must be an object")
    _check(registry.get("schema_version") ==
           "brdb-stallion-master-stage2-external-profiles-v0.1",
           "unsupported registry schema")
    _check(registry.get("research_only") is True, "research boundary missing")
    _check(registry.get("generated_date") == "2026-11-05", "unexpected source snapshot date")
    _check(shortlist.get("version") ==
           "brdb-embedded-blood-research-shortlist-v0.2-candidate",
           "unexpected shortlist version")
    _check(observations.get("version") ==
           "brdb-jrdb-observed-ancestor-lineage-v0.1-candidate",
           "unexpected lineage observation version")

    wanted = {row["candidate_id"] for row in shortlist.get("candidates", [])}
    _check(len(wanted) == 12, "expected twelve distinct shortlist candidates")
    rows = registry.get("subjects")
    _check(isinstance(rows, list) and len(rows) == 12,
           "expected twelve external subjects")
    official_codes = {
        row["lineage_code"]
        for row in observations.get("official_codes_subset", [])
    }
    observed_pairs = {
        row["label"]: row for row in observations.get("observed_label_code_pairs", [])
    }
    seen_candidates = set()
    by_key = {}
    total_parent_refs = 0
    verified_links = set()

    # Guard each source-native person identity and both immediate parent labels.
    for subject in rows:
        _check(isinstance(subject, dict), "subject must be an object")
        candidate_id = subject.get("candidate_id")
        _check(candidate_id in wanted and candidate_id not in seen_candidates,
               "unknown or repeated candidate")
        seen_candidates.add(candidate_id)
        key = subject.get("subject_key")
        _check(isinstance(key, str) and
               re.fullmatch(r"JBIS:[0-9]{10}", key) is not None,
               "subject key is not a source-native JBIS key")
        _check(key not in by_key, "duplicate external identity")
        identity = subject.get("identity", {})
        _check(identity.get("namespace") == "JBIS", "identity namespace changed")
        source_id = _source_id_from_url(identity.get("source_url"))
        _check(key == f"JBIS:{source_id}" and
               identity.get("external_id") == source_id,
               "external ID mismatch")
        _check(identity.get("identity_status") == "EXTERNAL_PROFILE_VERIFIED",
               "unreviewed subject identity")
        _check(identity.get("jrdb_horse_id") is None and
               identity.get("jrdb_crosswalk_status") == "UNRESOLVED" and
               identity.get("name_only_merge_forbidden") is True,
               "JBIS ID cannot be promoted to JRDB")
        _check(isinstance(subject.get("display_name_en"), str) and
               isinstance(subject.get("birth_year"), int),
               "display name or birth year missing")
        _check(subject.get("historical_asof_status") == "AS_OF_UNVERIFIED",
               "historic as-of self-certification forbidden")
        _check(subject.get("regional_roots") == [] and
               subject.get("aptitude_claims") == [] and
               subject.get("approved_for_review") is False,
               "unvalidated classification/review approval")
        line = subject.get("observed_jrdb_lineage", {})
        code = line.get("lineage_code")
        _check(code in official_codes and
               line.get("verified_person_to_lineage") is False and
               line.get("mapping_status") ==
               "CODE_OBSERVED_ON_MATCHING_PARENT_LABEL_ONLY",
               "code cannot become an individual identity")
        observed = observed_pairs.get(subject.get("display_name_jp"))
        _check(observed is not None, "Japanese candidate has no research observation")
        observed_codes = {
            code_row["code"] for code_row in observed["observed_sire_line_codes"]
        } | {
            code_row["code"] for code_row in observed["observed_bms_line_codes"]
        }
        _check(code in observed_codes, "lineage code contradicts research observation")
        parent_refs = subject.get("immediate_parent_observations")
        _check(isinstance(parent_refs, list) and len(parent_refs) == 2,
               "both direct parent observations required")
        _check({ref.get("path") for ref in parent_refs} == {"S", "D"},
               "S and D roles must remain distinct")
        for ref in parent_refs:
            _check(isinstance(ref.get("parent_name_as_displayed"), str) and
                   bool(ref["parent_name_as_displayed"]),
                   "parent display evidence missing")
            _check(ref.get("source_url") == identity.get("source_url"),
                   "parent relation source mismatch")
            _check(ref.get("as_of_status") == "AS_OF_UNVERIFIED",
                   "parent as-of assurance unsupported")
            parent_id = ref.get("parent_external_id")
            if parent_id is None:
                _check(ref.get("status") ==
                       "PARENT_NAME_OBSERVED_ID_UNRESOLVED" and
                       ref.get("person_id_verified") is False,
                       "name-only edge misrepresented as identity")
            else:
                _check(re.fullmatch(r"[0-9]{10}", parent_id) is not None and
                       ref.get("status") == "EXTERNAL_ID_DIRECT_LINK" and
                       ref.get("person_id_verified") is True,
                       "unverified external edge")
                verified_links.add((key, ref["path"], f"JBIS:{parent_id}"))
            total_parent_refs += 1
        by_key[key] = subject

    # A linked parent must be a separate, verified source person with matching name.
    for child, path, ancestor in verified_links:
        _check(ancestor in by_key, "linked ancestor subject missing")
        row = by_key[child]
        ref = next(ref for ref in row["immediate_parent_observations"]
                   if ref["path"] == path)
        _check(ref["parent_name_as_displayed"] ==
               by_key[ancestor]["display_name_en"],
               "linked parent name conflicts with profile")

    edges = registry.get("verified_ancestor_edges")
    _check(isinstance(edges, list), "verified edges must be a list")
    by_edges = set()
    for edge in edges:
        _check(edge.get("depth") == 1 and edge.get("path") in ("S", "D"),
               "D2 deeper ancestor paths require separate evidence")
        key = (edge.get("subject_key"), edge.get("path"),
               edge.get("ancestor_subject_key"))
        _check(key not in by_edges and key in verified_links,
               "unsourced or duplicate person path")
        by_edges.add(key)
        _check(edge.get("verification") == "EXTERNAL_PERSON_ID_PATH_VERIFIED" and
               edge.get("historical_asof_status") == "AS_OF_UNVERIFIED",
               "unverified person path or as-of claim")
        _check(edge.get("source_url") ==
               by_key[key[0]]["identity"]["source_url"] and
               edge.get("ancestor_source_url") ==
               by_key[key[2]]["identity"]["source_url"],
               "edge source mismatch")
    _check(by_edges == verified_links, "missing independently linked person edge")
    flags = registry.get("release_policy", {})
    for name in ("can_merge_to_jrdb_by_name", "can_autofill_region",
                 "can_autofill_blood_aptitude", "can_publish_to_racenote",
                 "can_publish_to_pwa"):
        _check(flags.get(name) is False, f"unsafe release policy: {name}")
    return {
        "status": "STAGE2_RESEARCH_SEED_VALID",
        "subject_profiles_verified": len(by_key),
        "parent_name_observations": total_parent_refs,
        "verified_external_direct_paths": len(by_edges),
        "jrdb_identity_crosswalks": 0,
        "review_safe": False,
    }


def main() -> None:
    """Validate the three explicitly supplied, versioned registry sources."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--shortlist", required=True)
    parser.add_argument("--observations", required=True)
    args = parser.parse_args()
    result = validate_registry(load_json(args.registry),
                               load_json(args.shortlist),
                               load_json(args.observations))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
