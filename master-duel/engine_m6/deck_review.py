"""M6-7: private, source-pinned full recipe and rationale for human review.

Never publish returned card-level output in public Git or CI logs.
A reason is a recorded selection rationale, NOT a verified combo.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import sqlite3

from .schema import validate_candidate, validate_inventory_audit


def full_recipe_review(sqlite_path, *, expected_master_sha256, candidate,
                       owned_audit, comparison_item):
    """Return MAIN/EX all rows, registered exclusions and explicit uncertainties.

    The complete raw SQLite SHA must match the candidate and inventory pins.
    Fail closed on unknown card IDs, bad totals, missing reasons or audit mismatch.
    """
    validate_candidate(candidate)
    validate_inventory_audit(owned_audit)
    if not isinstance(expected_master_sha256, str) or len(expected_master_sha256) != 64:
        raise ValueError("source SQLite pin required")
    if (sha256(Path(sqlite_path).read_bytes()).hexdigest() != expected_master_sha256
            or candidate["lineage"].get("source_master_sha256") != expected_master_sha256
            or owned_audit["sqlite_sha"] != expected_master_sha256
            or comparison_item.get("candidate_id") != candidate["candidate_id"]):
        raise ValueError("M6-7 source/candidate pin mismatch")
    decisions = comparison_item["owned_decisions"]["decisions"]
    if (len(decisions) != owned_audit["inventory_total_registered"]
            or len({d["card_id"] for d in decisions}) != len(decisions)):
        raise ValueError("incomplete registered inventory decisions")
    inventory = {d["card_id"]: d for d in decisions}
    ids = sorted({r["card_id"] for r in candidate["cards"]} | set(inventory))
    uri = Path(sqlite_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        metadata = {}
        for cid in ids:
            row = db.execute(
                "SELECT c.name, m.rarity, m.verification "
                "FROM cards c LEFT JOIN md_catalog m ON c.card_id=m.card_id "
                "WHERE c.card_id=?", (cid,)).fetchone()
            if row is None:
                raise ValueError("candidate/inventory card not in pinned DB")
            metadata[cid] = row
    selected = []
    for r in sorted(candidate["cards"], key=lambda x:(x["section"], x["card_id"])):
        cid = r["card_id"]
        d = inventory.get(cid)
        name, rarity, rarity_verification = metadata[cid]
        selected.append({
            "card_id":cid, "name_ja":name, "section":r["section"],
            "quantity":r["quantity"], "rarity":rarity or "UNKNOWN",
            "rarity_verification":rarity_verification or "UNKNOWN",
            "owned_state":d["known_state"] if d else "UNKNOWN",
            "owned_count":d["owned_count"] if d else None,
            "role":r["role"], "essentiality":r["essentiality"],
            "selection_reason":r["reason"],
            "evidence_ids":list(r["evidence_ids"]),
            "gameplay_verified":False,
        })
        if d and (d["disposition"] != "ADOPT" or d["selected_quantity"] != r["quantity"]):
            raise ValueError("selected/inventory disposition mismatch")
    if (sum(r["quantity"] for r in selected if r["section"]=="MAIN") != candidate["declared_main"]
            or sum(r["quantity"] for r in selected if r["section"]=="EXTRA") != candidate["declared_extra"]):
        raise ValueError("deck quantity mismatch")
    omitted = []
    for d in sorted(decisions, key=lambda x:x["card_id"]):
        if d["disposition"] == "ADOPT":
            continue
        cid = d["card_id"]
        name, rarity, _ = metadata[cid]
        omitted.append({
            "card_id":cid, "name_ja":name, "rarity":rarity or "UNKNOWN",
            "owned_state":d["known_state"],"owned_count":d["owned_count"],
            "disposition":d["disposition"],"reason":d["reason"],
            "role_review":d["role_review"],
        })
    return {
        "schema":"md-m6-7-private-full-recipe-review-v1",
        "candidate_id":candidate["candidate_id"],
        "source_master_sha256":expected_master_sha256,
        "main":candidate["declared_main"],"extra":candidate["declared_extra"],
        "selected":selected, "omitted_registered":omitted,
        "registered_decision_count":len(decisions),
        "selected_distinct":len({x["card_id"] for x in selected}),
        "disposition_counts":dict(sorted(Counter(x["disposition"] for x in decisions).items())),
        "review_required":True,"gameplay_verified":False,
        "official_md_legality_verified":False,
        "reason_scope":"RECORDED_PROVISIONAL_RATIONALE_NOT_VERIFIED_SYNERGY",
    }


def recipe_markdown(review):
    """Display the exact persisted rows; never reconstruct card counts by guessing."""
    if review.get("schema") != "md-m6-7-private-full-recipe-review-v1":
        raise ValueError("unknown review schema")
    lines = [f'# 構築候補 {review["candidate_id"]}',
             f'MAIN {review["main"]} / EX {review["extra"]}（実戦・合法性は未検証）']
    for section in ("MAIN", "EXTRA"):
        lines += ["", f'## {section}', "| カード | 枚数 | レア | 所持 | 採用理由 |",
                  "|---|---:|---|---|---|"]
        for x in review["selected"]:
            if x["section"] == section:
                owned = str(x["owned_count"]) if x["owned_count"] is not None else "UNKNOWN"
                reason = x["selection_reason"].replace("|", "／").replace("\n", " ")
                name = x["name_ja"].replace("|", "／")
                lines.append(f'| {name} | {x["quantity"]} | {x["rarity"]} | {owned} | {reason} |')
    lines += ["", "## 登録済み所持カードの見送り・要検討",
              "| カード | 所持 | 判定 | 記録理由 |", "|---|---:|---|---|"]
    for x in review["omitted_registered"]:
        count = str(x["owned_count"]) if x["owned_count"] is not None else "UNKNOWN"
        lines.append(f'| {x["name_ja"].replace("|", "／")} | {count} | '
                     f'{x["disposition"]} | {x["reason"].replace("|", "／")} |')
    return "\n".join(lines) + "\n"
