"""M5-C C5: deterministic private knowledge sidecar and M6 input adapter.

No network or Drive writes. Consumer provides read-back bytes and checks
SHA/manifest before requesting any profile. Not an MD legality/CP solver.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from .knowledge_schema import validate_knowledge

K_NAME = "knowledge.json"
V_NAME = "variants.json"
O_NAME = "staleness_overlay.json"
ZIP_SCHEMA = "md-m5c-private-sidecar-v1"
MANIFEST_SCHEMA = "md-m5c-private-sidecar-manifest-v1"
BUNDLE_SCHEMA = "md-m5c-theme-knowledge-bundle-v1"
SHA = re.compile(r"[0-9a-f]{64}\Z")


def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return sha256(raw).hexdigest()


def _assert_sha(s, field):
    if not isinstance(s, str) or not SHA.fullmatch(s):
        raise ValueError(f"invalid {field}")


def _decode_canonical(raw):
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc
    if canonical(value) != raw:
        raise ValueError("noncanonical or altered JSON bytes")
    return value


def _check_variants(knowledge, variants):
    if not isinstance(variants, list):
        raise ValueError("variants must be list")
    recipe_map = {r["recipe_id"]: r for r in knowledge["recipe_refs"]}
    profiles = {p["profile_id"] for p in knowledge["theme_profiles"]}
    seen = set()
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("invalid variant")
        vid = variant.get("variant_id")
        rid = variant.get("source_recipe_id")
        profile = variant.get("source_profile_id")
        if not isinstance(vid, str) or not vid or vid in seen:
            raise ValueError("duplicate/invalid variant")
        seen.add(vid)
        if rid not in recipe_map or profile not in profiles or recipe_map[rid]["profile_id"] != profile:
            raise ValueError("variant source FK mismatch")
        if variant.get("verification") not in {"REVIEW_REQUIRED", "HYPOTHESIS", "TEXT_CHECKED", "REVIEWED"}:
            raise ValueError("variant unexpectedly promoted to completed/game-tested")
        cards = variant.get("candidate_cards")
        if not isinstance(cards, list):
            raise ValueError("missing variant cards")
        counts = Counter()
        for row in cards:
            if not isinstance(row, dict):
                raise ValueError("invalid candidate card")
            cid, section, quantity = row.get("card_id"), row.get("section"), row.get("quantity")
            if not isinstance(cid, str) or not re.fullmatch(r"konami:[0-9]+", cid):
                raise ValueError("unresolved variant card")
            if section not in {"MAIN", "EXTRA"} or type(quantity) is not int or quantity <= 0:
                raise ValueError("invalid candidate quantity")
            if row.get("rarity") not in {"N", "R", "SR", "UR"}:
                raise ValueError("invalid candidate rarity")
            counts[(section, cid)] += quantity
            if counts[(section,cid)] > 3:
                raise ValueError("variant copy cap")
        main = sum(n for (zone, _), n in counts.items() if zone == "MAIN")
        extra = sum(n for (zone, _), n in counts.items() if zone == "EXTRA")
        if not 40 <= main <= 60 or not 0 <= extra <= 15:
            raise ValueError("candidate deck size invalid")
        if main != variant.get("main_count") or extra != variant.get("extra_count"):
            raise ValueError("variant declared totals mismatch")
    return seen


def _check_overlay(knowledge, overlay, knowledge_sha):
    if overlay is None:
        return
    if not isinstance(overlay, dict) or overlay.get("schema") != "md-m5c-c4-staleness-overlay-v1":
        raise ValueError("overlay schema")
    if overlay.get("source_knowledge_sha256") != knowledge_sha or overlay.get("source_knowledge_version") != knowledge["knowledge_version"]:
        raise ValueError("staleness overlay pinned to another knowledge")
    if overlay.get("unchanged_source_data") is not True:
        raise ValueError("overlay claimed to alter source")
    allowed = {"CLAIM": {r["claim_id"] for r in knowledge["claims"]},
               "RECIPE": {r["recipe_id"] for r in knowledge["recipe_refs"]},
               "ROUTE": {r["route_id"] for r in knowledge["combo_routes"]},
               "VARIANT": {r["variant_id"] for r in knowledge.get("c3_variants", [])}}
    seen = set()
    for row in overlay.get("statuses", []):
        key = (row.get("object_type"),row.get("object_id"))
        if key in seen or key[0] not in allowed or key[1] not in allowed[key[0]]:
            raise ValueError("unknown/duplicated staleness object")
        seen.add(key)
        if row.get("status") not in {"STALE", "REVIEW_REQUIRED"}:
            raise ValueError("overlay may only block or request review")


def _fixed_zip(files):
    sink = BytesIO()
    with ZipFile(sink, "w", compression=ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as z:
        for name in sorted(files):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            z.writestr(info, files[name], compress_type=ZIP_DEFLATED, compresslevel=9)
    return sink.getvalue()


def make_sidecar(knowledge, *, variants, upstream_knowledge_sha256, master_db_sha256,
                 overlay=None):
    """Return (zip_bytes, canonical_manifest_bytes). Upload after independent checks."""
    validate_knowledge(knowledge)
    _assert_sha(upstream_knowledge_sha256,"upstream_knowledge_sha256")
    _assert_sha(master_db_sha256,"master_db_sha256")
    if knowledge.get("c2_audit",{}).get("current_master_sqlite_sha256") != master_db_sha256:
        raise ValueError("private master pin differs from source evidence")
    if knowledge.get("c4_audit",{}).get("source_c3_sha256") != upstream_knowledge_sha256:
        raise ValueError("C4 lineage missing or mismatched")
    variants = list(variants)
    _check_variants(knowledge, variants)
    if canonical(variants) != canonical(knowledge.get("c3_variants", [])):
        raise ValueError("candidate variants differ from pinned C4 knowledge")
    k_bytes=canonical(knowledge)
    _check_overlay(knowledge, overlay, digest(k_bytes))
    files = {K_NAME:k_bytes, V_NAME:canonical(variants)}
    if overlay is not None:
        files[O_NAME]=canonical(overlay)
    zipped=_fixed_zip(files)
    manifest = {"schema": MANIFEST_SCHEMA, "package_schema":ZIP_SCHEMA,
       "knowledge_version":knowledge["knowledge_version"],
       "knowledge_sha256":digest(k_bytes),
       "upstream_c3_knowledge_sha256":upstream_knowledge_sha256,
       "master_db_sha256":master_db_sha256,
       "zip_sha256":digest(zipped),"zip_bytes":len(zipped),
       "members": {name:{"sha256":digest(raw),"bytes":len(raw)}
                    for name,raw in sorted(files.items())},
       "status":"PRIVATE_UNVERIFIED_GAME_LEGALITY"}
    return zipped, canonical(manifest)


def open_sidecar(raw_zip, raw_manifest, *, expected_zip_sha256,
                 expected_manifest_sha256, expected_master_db_sha256):
    """Verify *retrieved raw bytes*, no external IO and no mutable HEAD trust."""
    if not isinstance(raw_zip, bytes) or not isinstance(raw_manifest, bytes):
        raise ValueError("raw bytes required")
    _assert_sha(expected_manifest_sha256,"expected_manifest_sha256")
    if digest(raw_manifest) != expected_manifest_sha256:
        raise ValueError("manifest external pin mismatch")
    m=_decode_canonical(raw_manifest)
    if m.get("schema") != MANIFEST_SCHEMA or m.get("package_schema") != ZIP_SCHEMA:
        raise ValueError("unknown manifest schema")
    _assert_sha(expected_zip_sha256,"expected_zip_sha256")
    if digest(raw_zip) != expected_zip_sha256:
        raise ValueError("external ZIP pin mismatch")
    _assert_sha(expected_master_db_sha256,"expected_master_db_sha256")
    if m.get("master_db_sha256") != expected_master_db_sha256:
        raise ValueError("master DB pin mismatch")
    if digest(raw_zip) != m.get("zip_sha256") or len(raw_zip) != m.get("zip_bytes"):
        raise ValueError("sidecar ZIP hash or length mismatch")
    members=m.get("members")
    if not isinstance(members, dict) or set(members) not in ({K_NAME,V_NAME},{K_NAME,V_NAME,O_NAME}):
        raise ValueError("unexpected ZIP member inventory")
    with ZipFile(BytesIO(raw_zip),"r") as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=set(members):
            raise ValueError("extra/duplicate/missing ZIP members")
        decoded={}
        for name in names:
            info=z.getinfo(name)
            if info.file_size > 10_000_000 or info.compress_size > 10_000_000:
                raise ValueError("oversized member")
            data=z.read(name)
            if len(data)!=members[name].get("bytes") or digest(data)!=members[name].get("sha256"):
                raise ValueError("ZIP member failed SHA/length")
            decoded[name]=_decode_canonical(data)
    knowledge=decoded[K_NAME]; variants=decoded[V_NAME]
    validate_knowledge(knowledge)
    if m.get("knowledge_version")!=knowledge["knowledge_version"] or m.get("knowledge_sha256")!=digest(canonical(knowledge)):
        raise ValueError("knowledge pin mismatch")
    _assert_sha(m.get("upstream_c3_knowledge_sha256"),"upstream c3")
    _assert_sha(m.get("master_db_sha256"),"master")
    _check_variants(knowledge,variants)
    if canonical(variants)!=canonical(knowledge.get("c3_variants", [])):
        raise ValueError("variant mismatch")
    if knowledge.get("c4_audit",{}).get("source_c3_sha256")!=m["upstream_c3_knowledge_sha256"]:
        raise ValueError("lineage mismatch")
    if knowledge.get("c2_audit",{}).get("current_master_sqlite_sha256")!=m["master_db_sha256"]:
        raise ValueError("master provenance mismatch")
    overlay=decoded.get(O_NAME)
    _check_overlay(knowledge,overlay,m["knowledge_sha256"])
    return {"manifest":m,"knowledge":knowledge,"variants":variants,"overlay":overlay}


def theme_knowledge_bundle(verified, profile_id):
    """Produce a conservative M6 input; never claim legality or known ownership."""
    k=verified["knowledge"]; m=verified["manifest"]
    profiles=[p for p in k["theme_profiles"] if p["profile_id"]==profile_id]
    if len(profiles)!=1:
        raise ValueError("unknown theme profile")
    claims=[x for x in k["claims"] if x["profile_id"]==profile_id]
    recipes=[x for x in k["recipe_refs"] if x["profile_id"]==profile_id]
    recipe_ids={x["recipe_id"] for x in recipes}
    routes=[x for x in k["combo_routes"] if x["profile_id"]==profile_id]
    route_ids={x["route_id"] for x in routes}
    node_rows=[x for x in k["combo_nodes"] if x["route_id"] in route_ids]
    states={x for n in node_rows for x in (n["before_state_ref"],n["after_state_ref"])}
    for r in routes:
        states.add(r["start_condition_id"]);states.add(r["end_state_id"])
        states.update(r.get("alternative_end_state_ids",[]))
    variants=[v for v in verified["variants"] if v["source_profile_id"]==profile_id]
    status={(x["object_type"],x["object_id"]):x
            for x in (verified["overlay"] or {}).get("statuses",[])}
    affected=[v for key,v in sorted(status.items()) if (key[0]=="CLAIM" and key[1] in {c["claim_id"] for c in claims})
          or (key[0]=="RECIPE" and key[1] in recipe_ids)
          or (key[0]=="ROUTE" and key[1] in route_ids)
          or (key[0]=="VARIANT" and key[1] in {v["variant_id"] for v in variants})]
    # Source-era incomplete recipes and source-only assertions are NOT M6 confirmed.
    issues=[]
    for r in recipes:
        main=sum(c["quantity"] for c in k["recipe_cards"] if c["recipe_id"]==r["recipe_id"] and c["section"]=="MAIN")
        extra=sum(c["quantity"] for c in k["recipe_cards"] if c["recipe_id"]==r["recipe_id"] and c["section"]=="EXTRA")
        if (main,extra)!=(r["main_count"],r["extra_count"]):
            issues.append({"kind":"SOURCE_RECIPE_COUNT_MISMATCH","recipe_id":r["recipe_id"],"observed_main":main,"observed_extra":extra})
    if not recipes:
        issues.append({"kind":"NO_COMPLETE_SOURCE_RECIPE"})
    if affected:
        issues.append({"kind":"STALE_OR_REVIEW_REQUIRED","count":len(affected)})
    if k.get("regulation_date") is None:
        issues.append({"kind":"MD_BANLIST_DATE_UNVERIFIED"})
    return {"schema":BUNDLE_SCHEMA,"profile_id":profile_id,"theme_key":profiles[0]["theme_key"],
      "as_of":k["as_of"],"knowledge_version":k["knowledge_version"],
      "knowledge_sha256":m["knowledge_sha256"],"source_ids":sorted({x["source_id"] for x in claims+recipes+routes}),
      "master_db_sha256":m["master_db_sha256"],"catalog_sha":k.get("catalog_sha"),
      "regulation_date":k["regulation_date"],"verification":"REVIEW_REQUIRED",
      "core_packages":[x for x in k["package_candidates"] if x["profile_id"]==profile_id and x["core_or_optional"]=="CORE"],
      "optional_packages":[x for x in k["package_candidates"] if x["profile_id"]==profile_id and x["core_or_optional"]!="CORE"],
      "claims":claims,"recipe_refs":recipes,
      "recipe_cards":[x for x in k["recipe_cards"] if x["recipe_id"] in recipe_ids],
      "combo_routes":routes,"combo_nodes":node_rows,
      "combo_edges":[x for x in k["combo_edges"] if x["route_id"] in route_ids],
      "resource_states":[x for x in k["resource_states"] if x["state_id"] in states],
      "low_cost_variants":variants,"stale_dependencies":affected,
      "unresolved_claims":[x for x in claims if x["verification"] not in {"CARD_TEXT_CORROBORATED","EXPERT_REVIEWED","GAME_TESTED"}],
      "issues":issues,"M6_required_checks":["M2_OWNERSHIP","M3_MD_BANLIST","CARD_RARITY_AND_CRAFTABILITY","CP_POLICY","ROUTE_GAME_LEGALITY"],
      "deck_complete":False,"regulation_verified":False,"ownership_verified":False,
      "craft_cost_verified":False,"gameplay_tested":False,
      "recommendation_eligible":False}
