"""D3 read-only deck lookup using independently fetched private Drive bytes.

The caller MUST discover the current catalog in the canonical Drive folder and
fetch the referenced snapshot from Drive. No network access or Drive writes occur.
"""
from __future__ import annotations

import json
from .catalog import canonical, resolve, sha256, validate, validate_snapshot_pointer
from .__main__ import check as check_snapshot


def select_deck(catalog_raw: bytes, query: str, version: int | None = None) -> dict:
    """Return a pointer or a well-defined ambiguity/absence response."""
    if not isinstance(catalog_raw, bytes):
        raise ValueError("catalog must be raw downloaded bytes")
    catalog = json.loads(catalog_raw)
    info = validate(catalog)
    if canonical(catalog) != catalog_raw:
        raise ValueError("catalog not canonical; cannot pin exact source")
    result = resolve(catalog, query)
    status = result["status"]
    response = {"status": status, "catalog_generation": info["generation"],
                "catalog_sha256": info["sha256"], "matches": result["matches"],
                "selected": None}
    if status in ("NOT_FOUND", "AMBIGUOUS", "STAGED_ONLY"):
        return response
    match = result["matches"][0]
    deck = next(d for d in catalog["decks"] if d["deck_id"] == match["deck_id"])
    if version is None:
        pointer = match["confirmed"]
    else:
        if type(version) is not int or version < 1 or version > len(deck["versions"]):
            raise ValueError("requested version unavailable")
        pointer = deck["versions"][version - 1]
    response["status"] = "READY" if pointer["state"] == "CONFIRMED" else "STAGED_ONLY"
    response["selected"] = {"deck_id": deck["deck_id"], "name": deck["name"],
                            "variant": deck.get("variant"), **pointer}
    return response


def verify_and_render(catalog_raw: bytes, selection: dict, snapshot_raw: bytes,
                      db_path: str | None = None) -> dict:
    """Verify exact snapshot bytes and return MAIN/EX entries without inferring ownership.

    Requires the same pinned catalog bytes used at selection time. A caller
    should separately re-discover/re-fetch the current catalog for each request.
    """
    if selection.get("status") != "READY" or not isinstance(selection.get("selected"), dict):
        raise ValueError("no unique confirmed snapshot selected")
    if not isinstance(snapshot_raw, bytes):
        raise ValueError("snapshot must be raw downloaded bytes")
    catalog = json.loads(catalog_raw)
    report = validate(catalog)
    if canonical(catalog) != catalog_raw or selection["catalog_sha256"] != report["sha256"] or selection["catalog_generation"] != report["generation"]:
        raise ValueError("catalog changed or source pin mismatch")
    selected = selection["selected"]
    snapshot = json.loads(snapshot_raw)
    if canonical(snapshot) != snapshot_raw:
        raise ValueError("snapshot not canonical")
    pointer = validate_snapshot_pointer(catalog, snapshot, selected["deck_id"], selected["version"])
    if pointer != {k: selected[k] for k in ("version", "state", "snapshot_sha256", "drive_file_id", "supersedes")}:
        raise ValueError("selected pointer mismatch")
    if pointer["state"] != "CONFIRMED":
        raise ValueError("selected version is not confirmed")
    summary = check_snapshot(snapshot, db_path)
    if db_path is None:
        # Effect/rarity/regulation and independent ID resolution are explicitly
        # unverified until the current master database is available.
        id_status = "NOT_RECHECKED_AGAINST_CURRENT_MASTER"
    else:
        id_status = "CARD_IDS_EXIST_IN_SUPPLIED_MASTER"
    sections = {"MAIN": [], "EXTRA": []}
    for entry in snapshot["entries"]:
        sections[entry["section"]].append({"card_id": entry["card_id"],
                                           "spoken_name": entry["spoken_name"],
                                           "quantity": entry["quantity"]})
    return {"status": "READY", "deck_id": snapshot["deck_id"], "name": snapshot["name"],
            "version": snapshot["version"], "state": snapshot["state"], "sections": sections,
            "main_count": summary["main"], "extra_count": summary["extra"],
            "catalog_generation": report["generation"], "catalog_sha256": report["sha256"],
            "snapshot_sha256": sha256(snapshot), "drive_file_id": pointer["drive_file_id"],
            "card_id_verification": id_status,
            "inventory_verification": "NOT_PERFORMED",
            "md_regulation_verification": "NOT_PERFORMED"}
