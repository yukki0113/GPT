"""M6-0: contract-only validation for deck-generation inputs and outputs.

No card search, game-rule simulation, network access, inventory inference,
or persistence. Validators reject unsupported certainty claims.
"""
from __future__ import annotations

from datetime import datetime
import re

SCHEMA = "md-m6-v1"
MODES = {"STRICT_NO_UR", "LOW_RARITY_CORE", "OWNED_UR_ONLY", "UR_BUDGET", "CP_BUDGET"}
RARITIES = ("N", "R", "SR", "UR")
VERDICTS = {"PASS", "FAIL", "INDETERMINATE"}
DISPOSITIONS = {"ADOPT", "CONSIDER", "EXCLUDE", "REVIEW_REQUIRED"}
SOURCES = {"REGISTERED_OWNED_DECK", "ARTICLE_RECIPE", "M5C_VARIANT", "ASSEMBLED", "HUMAN_EDITED"}
FINAL = {"STRUCTURAL_CANDIDATE", "PROVISIONAL_RECOMMENDATION", "BLOCKED", "VERIFIED_RECOMMENDATION"}
REVIEW = {"SOURCE_OBSERVED", "HYPOTHESIS", "TEXT_CHECKED", "REVIEWED", "GAME_TESTED", "UNKNOWN", "STALE", "REVIEW_REQUIRED"}
SHA = re.compile(r"[a-f0-9]{64}\Z")
CARD = re.compile(r"konami:[0-9]+\Z")


def fail(message):
    raise ValueError(message)


def obj(value, field):
    if not isinstance(value, dict):
        fail(f"{field}: expected object")
    return value


def rows(value, field):
    if not isinstance(value, list):
        fail(f"{field}: expected list")
    return value


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        fail(f"{field}: empty text")
    return value


def time(value, field):
    text(value, field)
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid ISO timestamp") from exc
    if d.utcoffset() is None:
        fail(f"{field}: timezone required")


def integer(value, field, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        fail(f"{field}: integer outside limits")


def sha(value, field):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail(f"{field}: sha256 required")


def card(value, field):
    if not isinstance(value, str) or not CARD.fullmatch(value):
        fail(f"{field}: canonical card ID required")


def enum(value, choices, field):
    if value not in choices:
        fail(f"{field}: unsupported value")


def exact(value, names, field):
    if set(value) != set(names):
        fail(f"{field}: missing/unexpected fields")


def validate_request(v):
    obj(v, "request")
    exact(v, {"schema", "request_id", "as_of", "theme_query", "use_registered_deck",
              "owned_deck_id", "mode", "mode_origin", "strategy", "constraints",
              "max_variants", "compare_goal"}, "request")
    if v["schema"] != SCHEMA:
        fail("schema mismatch")
    text(v["request_id"], "request_id")
    time(v["as_of"], "as_of")
    if v["theme_query"] is not None:
        text(v["theme_query"], "theme_query")
    if type(v["use_registered_deck"]) is not bool:
        fail("use_registered_deck must be boolean")
    if v["owned_deck_id"] is not None:
        text(v["owned_deck_id"], "owned_deck_id")
    if v["owned_deck_id"] is not None and not v["use_registered_deck"]:
        fail("owned_deck_id requires registered deck request")
    if v["use_registered_deck"] and v["owned_deck_id"] is None and v["theme_query"] is None:
        fail("registered deck lookup requires identifier or query")
    enum(v["mode"], MODES, "mode")
    enum(v["mode_origin"], {"EXPLICIT", "DEFAULTED"}, "mode_origin")
    text(v["strategy"], "strategy")
    obj(v["constraints"], "constraints")
    if set(v["constraints"]) - {"new_ur_max", "new_sr_max", "cp_budget_by_rarity",
                                "main_min", "main_max", "extra_max",
                                "required_card_ids", "excluded_card_ids", "allow_engines"}:
        fail("unexpected constraint")
    c = v["constraints"]
    for key in ("new_ur_max", "new_sr_max"):
        if key in c:
            integer(c[key], key)
    for key,low,high in (("main_min",40,60),("main_max",40,60),("extra_max",0,15)):
        if key in c:
            integer(c[key], key, low, high)
    if c.get("main_min",40) > c.get("main_max",60):
        fail("main_min exceeds main_max")
    if "allow_engines" in c and type(c["allow_engines"]) is not bool:
        fail("allow_engines must be boolean")
    for key in ("required_card_ids", "excluded_card_ids"):
        if key in c:
            seq = rows(c[key], key)
            if len(set(seq)) != len(seq):
                fail(f"{key}: duplicate")
            for x in seq:
                card(x, key)
    if set(c.get("required_card_ids",[])) & set(c.get("excluded_card_ids",[])):
        fail("required card is excluded")
    if "cp_budget_by_rarity" in c:
        budgets=obj(c["cp_budget_by_rarity"],"cp_budget_by_rarity")
        if not set(budgets) <= set(RARITIES):
            fail("unknown CP currency")
        for rarity,n in budgets.items():
            integer(n, f"CP-{rarity}")
    if v["mode"] == "CP_BUDGET" and not c.get("cp_budget_by_rarity"):
        fail("CP_BUDGET requires per-rarity limit")
    if v["mode"] == "UR_BUDGET" and "new_ur_max" not in c:
        fail("UR_BUDGET requires new_ur_max")
    integer(v["max_variants"], "max_variants", 1, 20)
    if v["compare_goal"] is not None:
        text(v["compare_goal"], "compare_goal")
    return {"mode":v["mode"],"origin":v["mode_origin"],"status":"VALID_CONTRACT_ONLY"}


REQUIRED_PINS = {"head_generation","head_raw_sha","sqlite_zip_sha","sqlite_sha",
                 "inventory_snapshot","inventory_as_of","m3_snapshot","m3_effective_on",
                 "m3_verification","cp_policy_sha","cp_effective_on","cp_verification",
                 "m4_index_sha","m5_a_sha","m5_b_sha","m5_c_zip_sha",
                 "m5_c_manifest_sha","owned_deck_catalog_sha","readback_at"}
SHA_PINS = {"head_raw_sha","sqlite_zip_sha","sqlite_sha","cp_policy_sha",
            "m4_index_sha","m5_a_sha","m5_b_sha","m5_c_zip_sha",
            "m5_c_manifest_sha","owned_deck_catalog_sha"}


def validate_source_pins(v, *, registered_deck=False):
    obj(v, "source_pins")
    exact(v, REQUIRED_PINS | {"missing_reasons", "head_zip_generation", "inventory_generation",
                              "m3_generation"}, "source_pins")
    reasons=obj(v["missing_reasons"], "missing_reasons")
    if set(reasons) - REQUIRED_PINS:
        fail("unknown missing_reason field")
    for name in REQUIRED_PINS:
        value=v[name]
        if value is None:
            text(reasons.get(name), f"missing_reason.{name}")
        elif name in reasons:
            fail("present pin cannot have missing reason")
        elif name in SHA_PINS:
            sha(value, name)
        elif name in {"head_generation"}:
            integer(value, name, 1)
        else:
            text(value, name)
    for name in ("head_zip_generation","inventory_generation","m3_generation"):
        if v[name] is not None:
            integer(v[name], name, 1)
    if not isinstance(v["head_generation"], int) or type(v["head_generation"]) is bool:
        return {"status":"BLOCKED","reasons":["HEAD_GENERATION_UNAVAILABLE"]}
    for name in ("head_zip_generation","inventory_generation","m3_generation"):
        if v[name] is not None and v[name] != v["head_generation"]:
            return {"status":"BLOCKED","reasons":["GENERATION_MISMATCH:"+name]}
    hard={"head_raw_sha","sqlite_zip_sha","sqlite_sha","inventory_snapshot","inventory_as_of","readback_at"}
    if any(v[name] is None for name in hard):
        return {"status":"BLOCKED","reasons":["MISSING_ESSENTIAL_PINS"]}
    if registered_deck and v["owned_deck_catalog_sha"] is None:
        return {"status":"BLOCKED","reasons":["MISSING_OWNED_DECK_CATALOG"]}
    if any(v[name] is None for name in ("m5_c_zip_sha","m5_c_manifest_sha")):
        return {"status":"PARTIAL","reasons":["M5_C_MISSING"]}
    if any(v[name] is None for name in REQUIRED_PINS):
        return {"status":"PARTIAL","reasons":["OPTIONAL_PINS_MISSING"]}
    return {"status":"PINS_PRESENT_NOT_BYTES_VERIFIED","reasons":[]}


def validate_inventory_audit(v):
    obj(v, "preflight")
    exact(v, {"schema","head_generation","sqlite_sha","inventory_total_registered",
              "inventory_rows_reviewed","owned_inventory_decisions","preflight_status"}, "preflight")
    if v["schema"] != SCHEMA:
        fail("preflight schema")
    integer(v["head_generation"],"head_generation",1)
    sha(v["sqlite_sha"],"sqlite_sha")
    integer(v["inventory_total_registered"],"inventory_total_registered")
    integer(v["inventory_rows_reviewed"],"inventory_rows_reviewed")
    decisions=rows(v["owned_inventory_decisions"],"owned_inventory_decisions")
    seen=set()
    for row in decisions:
        obj(row,"decision")
        exact(row, {"card_id","known_state","owned_quantity","rarity",
                    "regulation_limit","regulation_confidence","disposition",
                    "decision_reason","main_or_extra","selected_quantity"}, "decision")
        cid=row["card_id"]
        card(cid,"card_id")
        if cid in seen:
            fail("duplicate owned card decision")
        seen.add(cid)
        enum(row["known_state"],{"UNKNOWN","KNOWN_ZERO","KNOWN_POSITIVE"},"known_state")
        count=row["owned_quantity"]
        if row["known_state"]=="UNKNOWN":
            if count is not None:
                fail("UNKNOWN cannot assert owned count")
        else:
            integer(count,"owned_quantity",0)
            if (row["known_state"]=="KNOWN_ZERO") != (count==0):
                fail("KNOWN_ZERO/POSITIVE count contradiction")
        enum(row["rarity"],set(RARITIES)|{"UNKNOWN"},"rarity")
        if row["regulation_limit"] is not None:
            integer(row["regulation_limit"],"regulation_limit",0,3)
        enum(row["regulation_confidence"],{"GAME_VERIFIED","UNVERIFIED_SOURCE","UNKNOWN","STALE"},"regulation_confidence")
        enum(row["disposition"],DISPOSITIONS,"disposition")
        text(row["decision_reason"],"decision_reason")
        enum(row["main_or_extra"],{"MAIN","EXTRA","NONE","UNKNOWN"},"main_or_extra")
        integer(row["selected_quantity"],"selected_quantity",0,3)
        if row["disposition"]!="ADOPT" and row["selected_quantity"]!=0:
            fail("non-adopted item selected")
        if row["selected_quantity"] and row["main_or_extra"] not in {"MAIN","EXTRA"}:
            fail("selected card must have section")
        if row["selected_quantity"] and row["regulation_limit"]==0:
            fail("candidate forbidden card cannot be selected")
    complete=(len(decisions)==v["inventory_total_registered"]==v["inventory_rows_reviewed"])
    if v["preflight_status"] not in {"PASS","PARTIAL","BLOCKED"}:
        fail("invalid preflight_status")
    if not complete and v["preflight_status"]=="PASS":
        fail("partial ownership coverage cannot PASS")
    if v["preflight_status"]=="PASS" and any(
        x["known_state"]=="UNKNOWN" or x["disposition"]=="REVIEW_REQUIRED"
        for x in decisions):
        fail("unknown owned decision cannot PASS")
    return {"status":"COVERAGE_COMPLETE" if complete else "COVERAGE_INCOMPLETE",
            "count":len(decisions)}


def validate_candidate(v):
    obj(v,"candidate")
    exact(v,{"schema","candidate_id","theme","source_kind","lineage",
             "cards","required_core_ids","route_ids","reasons_by_card",
             "reasons_by_omitted_owned_card","m5_status","declared_main",
             "declared_extra"},"candidate")
    if v["schema"]!=SCHEMA:
        fail("candidate schema")
    for key in ("candidate_id","theme"):
        text(v[key],key)
    enum(v["source_kind"],SOURCES,"source_kind")
    obj(v["lineage"],"lineage")
    enum(v["m5_status"],REVIEW,"m5_status")
    grouped={}
    for row in rows(v["cards"],"cards"):
        obj(row,"candidate card")
        exact(row,{"card_id","quantity","section","role","essentiality",
                   "reason","evidence_ids"},"candidate card")
        card(row["card_id"],"card_id")
        integer(row["quantity"],"quantity",1,3)
        enum(row["section"],{"MAIN","EXTRA"},"section")
        for key in ("role","reason"):
            text(row[key],key)
        enum(row["essentiality"],{"CORE","OPTIONAL","ALTERNATIVE","UNKNOWN"},"essentiality")
        if any(not isinstance(x,str) or not x for x in rows(row["evidence_ids"],"evidence_ids")):
            fail("bad evidence_ids")
        key=(row["section"],row["card_id"])
        grouped[key]=grouped.get(key,0)+row["quantity"]
    if any(n>3 for n in grouped.values()):
        fail("aggregated copy cap exceeded")
    sections={}
    for (section,cid) in grouped:
        if cid in sections and sections[cid]!=section:
            fail("same ID in MAIN and EXTRA")
        sections[cid]=section
    main=sum(n for (sec,_),n in grouped.items() if sec=="MAIN")
    extra=sum(n for (sec,_),n in grouped.items() if sec=="EXTRA")
    integer(v["declared_main"],"declared_main")
    integer(v["declared_extra"],"declared_extra")
    if main!=v["declared_main"] or extra!=v["declared_extra"]:
        fail("declared totals mismatch")
    if not 40<=main<=60 or not 0<=extra<=15:
        fail("MAIN/EX size outside limits")
    for name in ("required_core_ids","route_ids"):
        seq=rows(v[name],name)
        if len(set(seq))!=len(seq):
            fail("duplicate requirement")
        for x in seq:
            (card if name=="required_core_ids" else text)(x,name)
    for name in ("reasons_by_card","reasons_by_omitted_owned_card"):
        mapping=obj(v[name],name)
        for cid,why in mapping.items():
            card(cid,name)
            text(why,name)
    if set(v["reasons_by_card"])!=set(sections):
        fail("every candidate ID requires a reason")
    return {"status":"STRUCTURAL_CANDIDATE","main_count":main,
            "extra_count":extra,"distinct_cards":len(sections)}


def validate_evaluation(v):
    obj(v,"evaluation")
    exact(v,{"schema","candidate_id","source_pins","preflight_status",
             "structure","mode_gates","regulation_verified",
             "ownership_verified","craft_cost_verified","gameplay_tested",
             "unknowns","blocking_reasons","proposal_status"},"evaluation")
    if v["schema"]!=SCHEMA:
        fail("evaluation schema")
    text(v["candidate_id"],"candidate_id")
    pin=validate_source_pins(v["source_pins"])
    enum(v["preflight_status"],{"PASS","PARTIAL","BLOCKED"},"preflight_status")
    enum(v["structure"],VERDICTS,"structure")
    gates=obj(v["mode_gates"],"mode_gates")
    exact(gates,{"CORE_UR_ZERO","NEW_UR_CRAFT_ZERO","STRICT_NO_UR"},"mode_gates")
    for name,decision in gates.items():
        enum(decision,VERDICTS,name)
    for field in ("regulation_verified","ownership_verified","craft_cost_verified","gameplay_tested"):
        if type(v[field]) is not bool:
            fail(f"{field} must be boolean")
    for field in ("unknowns","blocking_reasons"):
        if any(not isinstance(x,str) or not x.strip() for x in rows(v[field],field)):
            fail(f"{field} requires reasons")
    enum(v["proposal_status"],FINAL,"proposal_status")
    if v["proposal_status"]=="VERIFIED_RECOMMENDATION":
        if (pin["status"]!="PINS_PRESENT_NOT_BYTES_VERIFIED"
            or v["preflight_status"]!="PASS"
            or v["structure"]!="PASS"
            or any(x!="PASS" for x in gates.values())
            or not all(v[k] for k in ("regulation_verified","ownership_verified","craft_cost_verified","gameplay_tested"))
            or v["unknowns"] or v["blocking_reasons"]):
            fail("unsupported VERIFIED_RECOMMENDATION")
        # M6-0 cannot independently authenticate actual raw bytes nor gameplay.
        fail("M6-0 does not authorize verified recommendation")
    if v["proposal_status"]=="PROVISIONAL_RECOMMENDATION":
        if pin["status"]=="BLOCKED" or v["preflight_status"]=="BLOCKED" or v["structure"]!="PASS" or v["blocking_reasons"]:
            fail("blocked input cannot be provisionally recommended")
    if v["blocking_reasons"] and v["proposal_status"]!="BLOCKED":
        fail("blocking reasons require BLOCKED")
    return {"status":"CONTRACT_VALIDATED_NOT_FACT_VERIFIED",
            "proposal_status":v["proposal_status"]}
