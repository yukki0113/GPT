"""M6-5B conservative first-line EXTRA material screening.

Only exact source-text opening requirements are parsed. Rank alone does not
prove materials; a candidate is "ON_PAPER" only against explicitly supplied
board capability evidence. It remains unverified for game execution.
"""
from __future__ import annotations
import re
import unicodedata

CARD=re.compile(r"konami:[0-9]+\Z")


def screen_extra_materials(effect_bundle, *, extra_card_ids, board_capabilities):
    """Compare source text with explicitly documented potential board states.

    Each capability is {kind: LEVEL_MONSTERS|NAMED_MONSTERS,
      level: number|null, count: int, distinct_names: bool,
      evidence_ids: nonempty list[str], verification: ...}.
    This establishes only that a claimed material pool is numerically compatible.
    It is NOT proof the pool can be produced in one turn or that summons resolve.
    """
    if not isinstance(extra_card_ids,(list,tuple)) or len(extra_card_ids)>120 or len(set(extra_card_ids))!=len(extra_card_ids):
        raise ValueError("bounded distinct EXTRA IDs required")
    if not isinstance(board_capabilities,(list,tuple)) or len(board_capabilities)>40:
        raise ValueError("bounded board capabilities required")
    if not isinstance(effect_bundle,dict) or effect_bundle.get("schema")!="md-m6-5b-effect-anchors-v1":
        raise ValueError("pinned text bundle required")
    cards=effect_bundle["cards"]
    for capability in board_capabilities:
        if not isinstance(capability,dict) or set(capability)!={"kind","level","count","distinct_names","evidence_ids","verification"}:
            raise ValueError("capability contract")
        if capability["kind"] not in {"LEVEL_MONSTERS","NAMED_MONSTERS"}:
            raise ValueError("unsupported capability")
        if type(capability["count"]) is not int or not 1<=capability["count"]<=5:
            raise ValueError("material count range")
        if capability["kind"]=="LEVEL_MONSTERS" and (type(capability["level"]) is not int or not 1<=capability["level"]<=12):
            raise ValueError("level capability")
        if capability["kind"]=="NAMED_MONSTERS" and capability["level"] is not None:
            raise ValueError("named monster level must be unspecified")
        if type(capability["distinct_names"]) is not bool:
            raise ValueError("distinct names must be bool")
        if not isinstance(capability["evidence_ids"],list) or not capability["evidence_ids"] or not all(isinstance(x,str) and x for x in capability["evidence_ids"]):
            raise ValueError("material pool evidence required")
        if capability["verification"] not in {"SOURCE_OBSERVED","TEXT_CHECKED","REVIEWED"}:
            raise ValueError("unknown board verification")
    rows=[]
    for cid in extra_card_ids:
        if not isinstance(cid,str) or not CARD.fullmatch(cid) or cid not in cards:
            raise ValueError("EXTRA not in current source text")
        card=cards[cid]
        first=unicodedata.normalize("NFKC",card["text"].splitlines()[0]).strip()
        rank_match=re.fullmatch(r"(?:[\w属性]+)?レベル([0-9]{1,2})モンスター[×x]([0-9]{1,2})(?:体(?:以上)?)?",first)
        link_match=re.fullmatch(r"(カード名が異なる)?モンスター([0-9]{1,2})体(?:以上)?",first)
        if rank_match:
            lv,n=map(int,rank_match.groups())
            if "属性" in first or n>5:
                kind="SPECIALIZED_XYZ_REQUIREMENT"
                applicable=[]
            else:
                kind="GENERIC_LEVEL_XYZ"
                applicable=[p for p in board_capabilities if p["kind"]=="LEVEL_MONSTERS" and p["level"]==lv and p["count"]>=n]
        elif link_match:
            different,n=link_match.groups()
            kind="DISTINCT_NAME_LINK" if different else "GENERIC_LINK"
            applicable=[p for p in board_capabilities
                        if p["count"]>=int(n) and
                        (not different or p["distinct_names"])]
        else:
            kind="UNPARSED_MATERIAL_REQUIREMENT"
            applicable=[]
        rows.append({"card_id":cid,"name":card["name"],
                     "first_line":first,
                     "material_class":kind,
                     "matched_capability_evidence_ids":sorted({
                         ref for p in applicable for ref in p["evidence_ids"]}),
                     "screen":"POSSIBLE_ON_PAPER" if applicable else "REQUIRES_REVIEW",
                     "source_text_sha256":card["text_sha256"],
                     "gameplay_compatibility_verified":False,
                     "materials_simultaneously_available_verified":False,
                     "official_md_legality_verified":False})
    return {"schema":"md-m6-5b-material-screen-v1",
            "master_sqlite_sha256":effect_bundle["master_sqlite_sha256"],
            "results":rows,
            "gameplay_verified":False,
            "warning":"Textual material matching is not proof of summonability; locks and dependencies require route review."}
