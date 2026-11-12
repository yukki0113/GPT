"""M6-6 private integration entry point, fail-closed and read-only.

This orchestrates actual M6-1..M6-5C functions against the same externally
SHA-pinned private source. A structural candidate remains REVIEW_REQUIRED;
no automated gameplay or official MD banlist certification is performed.
Public CI must use synthetic inputs only. Private results must never be
committed to the public repository.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from engine_m5.private_bundle import open_sidecar, theme_knowledge_bundle
from .preflight import preflight_from_verified_bytes
from .candidate_pool import build_candidate_pool
from .assemble import assemble_candidates
from .discovery import search_cards
from .effect_review import load_effect_anchors, audit_effect_routes
from .material_screen import screen_extra_materials
from .recompose import recompose_portfolio
from .evaluate import evaluate_structural_candidate
from .reasoning import plan_reconstruction, audit_reconstruction
from .report import compare_candidates
from .deck_review import full_recipe_review, recipe_markdown, make_private_review_archive
from .proposal_store import make_proposal_archive, verify_proposal_archive
from .schema import validate_request


def integrate_private_deck(*, head_before, head_after, expected_head_sha256,
                           snapshot_zip, master_sqlite_path,
                           cp_policy_bytes, expected_cp_policy_sha256,
                           sidecar_zip, sidecar_manifest,
                           expected_sidecar_zip_sha256,
                           expected_sidecar_manifest_sha256,
                           request, profile_id,
                           discovery_queries=(), annotations=(),
                           extra_card_ids=(), board_capabilities=(),
                           engine_packages=(), effect_claims=(), route_claims=(),
                           max_solutions=None,decision_policy=None):
    """Return private, not-yet-game-certified portfolio and ZIP proposal bytes.

    Source bytes supplied by caller must be independently fetched and HEAD
    must be re-fetched at the end. The two HEAD args must have same externally
    pinned SHA; the caller is responsible for obtaining head_after *after*
    snapshot retrieval. No production DB write or optimistic self-certification.
    """
    validate_request(request)
    pre=preflight_from_verified_bytes(
        head_before=head_before, head_after=head_after,
        expected_head_sha256=expected_head_sha256,
        snapshot_zip=snapshot_zip,
        cp_policy_bytes=cp_policy_bytes,
        expected_cp_policy_sha256=expected_cp_policy_sha256,
        m5_zip=sidecar_zip, m5_manifest=sidecar_manifest,
        expected_m5_zip_sha256=expected_sidecar_zip_sha256,
        expected_m5_manifest_sha256=expected_sidecar_manifest_sha256)
    pins=pre["source_pins"]
    raw_master=Path(master_sqlite_path).read_bytes()
    if sha256(raw_master).hexdigest()!=pins["sqlite_sha"]:
        raise ValueError("integrated master SQLite raw SHA mismatch")
    verified=open_sidecar(
        sidecar_zip,sidecar_manifest,
        expected_zip_sha256=expected_sidecar_zip_sha256,
        expected_manifest_sha256=expected_sidecar_manifest_sha256,
        expected_master_db_sha256=pins["sqlite_sha"])
    bundle=theme_knowledge_bundle(verified,profile_id)
    if request["theme_query"] not in (None,bundle["theme_key"]):
        raise ValueError("profile and request theme mismatch")
    pool=build_candidate_pool(
        bundle, expected_knowledge_sha256=bundle["knowledge_sha256"],
        expected_master_db_sha256=pins["sqlite_sha"],
        owned_audit=pre["audit"])
    assembled=assemble_candidates(request,bundle,pool)
    summary={"schema":"md-m6-6-private-integration-v1",
             "profile_id":profile_id,"theme":bundle["theme_key"],
             "head_generation":pins["head_generation"],
             "master_sqlite_sha256":pins["sqlite_sha"],
             "preflight_status":pre["preflight_status"],
             "owned_inventory_rows":pre["audit"]["inventory_rows_reviewed"],
             "source_candidate_count":assembled["candidate_count"],
             "source_assembly_status":assembled["status"],
             "source_rejected_count":len(assembled["rejected"]),
             "new_candidate_count":0,
             "new_status":"INSUFFICIENT_EVIDENCE",
             "recommendation_eligible":False,
             "gameplay_verified":False,
             "official_md_legality_verified":False}
    if not assembled["candidates"]:
        return {"summary":summary,"preflight":pre,"source_assembly":assembled,
                "portfolio":None,"evaluations":[],"comparisons":None,
                "archive":None,"manifest_raw":None,
                "full_reviews":[],"review_markdowns":[],
                "review_archive":None,"review_manifest_raw":None,
                "decision_audits":[]}
    # A new real-data deck must not silently fall back to the old
    # owned-first / priority-only selection when evaluation evidence is absent.
    if decision_policy is None:
        raise ValueError("COMPETITIVE_POLICY_REQUIRED_FOR_NEW_DECK_REVIEW")
    # A teacher-origin source variant is a structural starting point only.
    reference=next(
        (x["candidate"] for x in assembled["candidates"]
         if x["candidate"]["source_kind"]=="M5C_VARIANT"),
        assembled["candidates"][0]["candidate"])
    if len(discovery_queries)>30:
        raise ValueError("bounded discovery queries required")
    # Explicit research targets are searched even when no teacher recipe
    # mentions them. Names are source-name candidates, not guaranteed effects.
    research_queries=list(discovery_queries)
    if decision_policy is not None:
        names=decision_policy.get("required_review_names",[])
        if names:
            research_queries.extend([
                {"section":"MAIN","theme_terms":list(names),"limit":300},
                {"section":"EXTRA","theme_terms":list(names),"limit":300},
            ])
        # A level-4 pair calls for *both* rank-4 and link-2 research.
        # Null/unknown link-rating cards still require explicit source review.
        if any(
            isinstance(board,dict) and board.get("kind")=="LEVEL_MONSTERS"
            and board.get("level")==4 and board.get("count",0)>=2
            for board in board_capabilities
        ):
            research_queries.extend([
                {"section":"EXTRA","ranks":[4],"limit":300},
                {"section":"EXTRA","links":[2],"limit":300},
            ])
    if len(research_queries)>40:
        raise ValueError("bounded competitive research queries required")
    discoveries=[]
    for query in research_queries:
        if not isinstance(query,dict):
            raise ValueError("discovery query must be an object")
        discoveries.append(search_cards(
            master_sqlite_path,expected_sqlite_sha256=pins["sqlite_sha"],
            **query))
    if not isinstance(extra_card_ids,(list,tuple)):
        raise ValueError("EXTRA IDs required")
    anchors=load_effect_anchors(
        master_sqlite_path,expected_sqlite_sha256=pins["sqlite_sha"],
        card_ids=list(extra_card_ids))
    materials=screen_extra_materials(
        anchors,extra_card_ids=extra_card_ids,
        board_capabilities=board_capabilities)
    portfolio=recompose_portfolio(
        request,reference,discovery_results=discoveries,
        annotations=annotations,material_screen=materials,
        engine_packages=engine_packages,max_solutions=max_solutions,
        decision_policy=decision_policy)
    summary["new_candidate_count"]=portfolio["solution_count"]
    summary["new_status"]=portfolio["status"]
    summary["competitive_policy_applied"]=portfolio["competitive_policy_applied"]
    summary["competitive_policy_coverage"]=portfolio["policy_coverage_status"]
    summary["required_names_missing"]=len(portfolio["required_name_gaps"])
    summary["automatic_comparative_searches"]=len(research_queries)-len(discovery_queries)
    summary["selection_policy"]="EVIDENCE_SCORED" if decision_policy is not None else "LEGACY_HEURISTIC_REVIEW_REQUIRED"
    evaluated=[]
    compare_items=[]
    for option in portfolio["solutions"]:
        candidate=option["candidate"]
        # Pinned texts establish only quoted claims, not a successful route.
        effects=audit_effect_routes(
            candidate,anchors,claims=effect_claims,
            routes=route_claims,packages=engine_packages,
            selected_package_ids=option["selected_packages"])
        evaluation=evaluate_structural_candidate(
            master_sqlite_path,candidate,request,source_pins=pins,
            cp_policy_bytes=cp_policy_bytes)
        trace=plan_reconstruction(
            request,candidate,
            teacher_card_ids=[r["card_id"] for r in reference["cards"]])
        # Only report lanes with demonstrated execution; do not invent a
        # theme-understanding review or source evidence for package combos.
        documented={
            "THEME_INTERNAL_LOW_RARITY":any(
                q.get("theme_terms") or q.get("exact_card_ids") for q in
                research_queries if q.get("section")=="MAIN"),
            "EXTRA_FROM_AVAILABLE_MATERIALS":bool(extra_card_ids),
            "MAIN_EXTRA_ITERATION":bool(
                extra_card_ids and
                any(q.get("section")=="MAIN" for q in research_queries)),
            "OWNED_GENERIC_FINISH":any(
                q.get("section")=="MAIN" and q.get("owned_only")
                for q in research_queries),
            "FINAL_COST_AND_LEGALITY_REVIEW":True,
        }
        for task in trace["tasks"]:
            if documented.get(task["lane"],False):
                task["status"]="SEARCHED"
                task["query_evidence_ids"]=[
                    "M6-6:PINNED-CURRENT-SOURCE:"+task["lane"]]
                task["reason"]="Actual read-only module executed; no duel legality established."
            else:
                task["status"]="BLOCKED"
                task["reason"]="No complete verified evidence on current source."
        for family in trace["families"]:
            family["status"]="SEARCHED" if (
                family["kind"]==option["family"]) else "BLOCKED"
            family["reason"]="Compared only the source-backed available portfolio; no unsupported engine promotion."
        audit=audit_reconstruction(
            request,candidate,evaluation,trace,
            registered_inventory_count=pre["audit"]["inventory_total_registered"],
            reviewed_inventory_count=pre["audit"]["inventory_rows_reviewed"])
        evaluated.append({"candidate_id":candidate["candidate_id"],
                          "family":option["family"],
                          "main":candidate["declared_main"],
                          "extra":candidate["declared_extra"],
                          "mode_gate":evaluation["requested_mode_gate"],
                          "new_ur_upper":evaluation[
                              "new_needed_upper_by_rarity"]["UR"],
                          "effect_status":effects["status"],
                          "exploration_status":audit["status"],
                          "review_reasons":audit["review_reasons"],
                          "recommendation_eligible":False})
        compare_items.append({"candidate":candidate,
                              "evaluation":evaluation,
                              "owned_audit":pre["audit"]})
    archive=None
    manifest_raw=None
    comparison=None
    full_reviews=[]
    review_markdowns=[]
    review_archive=None
    review_manifest_raw=None
    decision_audits=[]
    if compare_items:
        comparison=compare_candidates(compare_items)
        by_id={item['candidate_id']:item for item in comparison['items']}
        for entry in compare_items:
            review=full_recipe_review(
                master_sqlite_path, expected_master_sha256=pins['sqlite_sha'],
                candidate=entry['candidate'], owned_audit=entry['owned_audit'],
                comparison_item=by_id[entry['candidate']['candidate_id']])
            full_reviews.append(review)
            review_markdowns.append(recipe_markdown(review))
        audit_by_id={option["candidate"]["candidate_id"]:option
                     for option in portfolio["solutions"]}
        decision_audits=[]
        for review in full_reviews:
            option=audit_by_id[review["candidate_id"]]
            decision_audits.append({
                "schema":"md-m6-7-competitive-decisions-v1",
                "candidate_id":review["candidate_id"],
                "source_master_sha256":pins["sqlite_sha"],
                "policy_as_of":decision_policy["as_of"],
                "policy_coverage_status":portfolio["policy_coverage_status"],
                "required_name_gaps":portfolio["required_name_gaps"],
                "policy_assessment_gaps":portfolio["policy_assessment_gaps"],
                "policy_source_gaps":portfolio["policy_source_gaps"],
                "truncated_source_searches":portfolio["truncated_source_searches"],
                "comparisons":option["competitive_candidate_comparisons"],
                "selected_marginal_scores":option["competitive_decisions"],
                "gameplay_verified":False,
            })
        review_archive,review_manifest_raw=make_private_review_archive(
            full_reviews,review_markdowns,decision_audits=decision_audits)
        archive,manifest_raw=make_proposal_archive(
            comparison,source_master_sha256=pins["sqlite_sha"])
        verify_proposal_archive(
            archive,manifest_raw,
            expected_archive_sha256=sha256(archive).hexdigest(),
            expected_manifest_sha256=sha256(manifest_raw).hexdigest(),
            expected_master_sha256=pins["sqlite_sha"])
    return {"summary":summary,"preflight":pre,
            "source_assembly":assembled,"portfolio":portfolio,
            "evaluations":evaluated,"comparisons":comparison,
            "archive":archive,"manifest_raw":manifest_raw,
            "full_reviews":full_reviews,"review_markdowns":review_markdowns,
            "review_archive":review_archive,"review_manifest_raw":review_manifest_raw,
            "decision_audits":decision_audits}
