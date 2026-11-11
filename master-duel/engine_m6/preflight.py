"""M6-1 read-only SHA-pinned source preflight.

Caller must discover the latest Drive HEAD and supply independently fetched
HEAD bytes before/after analysis; this module performs NO network operations.
No personal inventory rows are logged or written to public GitHub.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile
import json
import sqlite3

from .schema import SCHEMA, validate_inventory_audit, validate_source_pins
from engine_m5.private_bundle import open_sidecar


def _digest(raw):
    if not isinstance(raw, bytes):
        raise ValueError("raw bytes required")
    return sha256(raw).hexdigest()


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid JSON input") from exc


def _zip_db(raw, expected_zip_sha, expected_sqlite_sha):
    if _digest(raw) != expected_zip_sha:
        raise ValueError("snapshot ZIP SHA mismatch")
    try:
        with ZipFile(BytesIO(raw)) as z:
            members = z.infolist()
            if len(members) != 1 or members[0].filename != "master_duel.sqlite":
                raise ValueError("unexpected snapshot ZIP members")
            info = members[0]
            if info.file_size > 100_000_000 or info.compress_size > 100_000_000:
                raise ValueError("oversized private SQLite")
            db = z.read(info)
    except BadZipFile as exc:
        raise ValueError("invalid snapshot ZIP") from exc
    if _digest(db) != expected_sqlite_sha:
        raise ValueError("SQLite raw SHA mismatch")
    return db


def _catalog_optional(raw, expected_sha):
    if raw is None:
        return None
    if _digest(raw) != expected_sha:
        raise ValueError("owned catalog external SHA pin mismatch")
    obj = _json(raw)
    if not isinstance(obj, dict):
        raise ValueError("owned deck catalog invalid")
    return _digest(raw)


def _check_policy(raw, expected_sha):
    if raw is None:
        return None, None, None
    if _digest(raw) != expected_sha:
        raise ValueError("CP policy external SHA pin mismatch")
    policy = _json(raw)
    if policy.get("cp_per_card") != {"N": 30, "R": 30, "SR": 30, "UR": 30}:
        raise ValueError("unexpected per-rarity CP policy")
    if policy.get("verification") != "USER_CONFIRMED":
        raise ValueError("CP policy not user confirmed")
    return _digest(raw), policy["effective_on"], policy["verification"]


def _read_only_audit(db, sqlite_sha, generation, decision_overrides):
    """Return private full inventory decision rows and public-safe summary."""
    with TemporaryDirectory(prefix="md-m6-1-") as tmp:
        file = Path(tmp) / "catalog.sqlite"
        file.write_bytes(db)
        conn = sqlite3.connect(f"file:{file.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity_check failed")
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("SQLite FK check failed")
            card_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            rows = conn.execute("""
                SELECT i.card_id, i.known_state, i.owned_count,
                       c.rarity, i.updated_at
                FROM inventory AS i
                JOIN md_catalog AS c ON c.card_id = i.card_id
                ORDER BY i.card_id
            """).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
            if len(rows) != total:
                raise ValueError("inventory join dropped rows")
            banlist = conn.execute("""
                SELECT snapshot_id, effective_on, verification
                FROM banlist_snapshots WHERE format_id='MD_STANDARD'
                ORDER BY effective_on DESC, snapshot_id DESC
            """).fetchall()
            if len(banlist) != 1:
                raise ValueError("ambiguous or missing MD banlist snapshot")
            sid, effective, verification = banlist[0]
            if verification not in ("UNVERIFIED_SOURCE", "GAME_VERIFIED"):
                raise ValueError("unknown banlist verification")
            restrictions = dict(conn.execute("""
                SELECT card_id, max_copies FROM banlist_entries
                WHERE snapshot_id = ?
            """, (sid,)))
            if not set(restrictions).issubset(
                {row[0] for row in conn.execute("SELECT card_id FROM cards")}):
                raise ValueError("banlist card outside catalog")
            inventory_sha = _digest(json.dumps(
                rows, ensure_ascii=False, separators=(",",":"), allow_nan=False
            ).encode("utf-8"))
            decisions = []
            decision_overrides = {} if decision_overrides is None else decision_overrides
            if not isinstance(decision_overrides, dict):
                raise ValueError("decision_overrides must be object")
            present = {row[0] for row in rows}
            if set(decision_overrides) - present:
                raise ValueError("override contains non-owned/unknown card")
            for card_id, state, owned, rarity, updated in rows:
                custom = decision_overrides.get(card_id)
                if custom is None:
                    disposition, reason, zone, selected = (
                        "REVIEW_REQUIRED", "Theme-dependent decision not yet assessed",
                        "UNKNOWN", 0)
                else:
                    if set(custom) != {"disposition", "reason", "main_or_extra", "selected_quantity"}:
                        raise ValueError("decision override fields invalid")
                    disposition, reason, zone, selected = (
                        custom["disposition"], custom["reason"], custom["main_or_extra"],
                        custom["selected_quantity"])
                limit = restrictions.get(card_id)
                # M3 values are candidate facts only; do not install a
                # provisional banned=0 value as a confirmed restriction.
                if verification != "GAME_VERIFIED":
                    limit = None
                decisions.append({
                    "card_id":card_id, "known_state":state,
                    "owned_quantity":owned, "rarity":rarity or "UNKNOWN",
                    "regulation_limit":limit,
                    "regulation_confidence":verification if card_id in restrictions else "UNKNOWN",
                    "disposition":disposition, "decision_reason":reason,
                    "main_or_extra":zone, "selected_quantity":selected
                })
            all_decided = all(x["disposition"] != "REVIEW_REQUIRED" for x in decisions)
            status = "PASS" if all_decided else "PARTIAL"
            audit = {"schema": SCHEMA, "head_generation": generation,
                     "sqlite_sha": sqlite_sha,
                     "inventory_total_registered": total,
                     "inventory_rows_reviewed":len(decisions),
                     "owned_inventory_decisions":decisions,
                     "preflight_status":status}
            validate_inventory_audit(audit)
            return audit, {
                "card_count":card_count, "registered_count":total,
                "states":{k:sum(r[1] == k for r in rows)
                          for k in ("KNOWN_POSITIVE","KNOWN_ZERO","UNKNOWN")},
                "rarity_types":{k:sum(r[3] == k for r in rows)
                                for k in ("N","R","SR","UR")},
                "inventory_sha256":inventory_sha,
                "inventory_as_of":max((r[4] for r in rows), default=None),
                "m3_snapshot":sid, "m3_effective_on":effective,
                "m3_verification":verification,
                "banlist_candidate_count":len(restrictions),
                "unadjudicated_count":sum(x["disposition"]=="REVIEW_REQUIRED" for x in decisions),
            }
        finally:
            conn.close()


def preflight_from_verified_bytes(*, head_before, head_after, expected_head_sha256,
                                  snapshot_zip, cp_policy_bytes, expected_cp_policy_sha256, m5_zip, m5_manifest,
                                  expected_m5_zip_sha256, expected_m5_manifest_sha256,
                                  owned_deck_catalog_bytes=None,
                                  expected_owned_deck_catalog_sha256=None,
                                  decision_overrides=None, retrieved_at=None):
    """Pure read-only input gate, with independently pinned HEAD and M5 bytes.

    'head_after' must be freshly fetched by caller after snapshot retrieval.
    Discovery/latestness of the Drive HEAD itself is a caller-side requirement.
    Return full private inventory audit plus aggregate summary and source pins.
    """
    if _digest(head_before) != expected_head_sha256 or head_before != head_after:
        raise ValueError("HEAD modified or not externally SHA pinned")
    head = _json(head_before)
    if head.get("scope") != "PRODUCTION" or head.get("system") != "master-duel":
        raise ValueError("not production Master Duel HEAD")
    generation = head.get("generation")
    if type(generation) is not int or generation < 1:
        raise ValueError("invalid production generation")
    snapshot = head.get("current_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("missing production snapshot")
    sqlite_sha = snapshot["db_sha256"]
    db = _zip_db(snapshot_zip,snapshot["zip_sha256"],sqlite_sha)
    cp_sha, cp_date, cp_verification = _check_policy(cp_policy_bytes, expected_cp_policy_sha256)
    if m5_zip is None or m5_manifest is None:
        raise ValueError("M5-C C5 sidecar required for M6-1 integration")
    m5_verified = open_sidecar(
        m5_zip,m5_manifest,
        expected_zip_sha256=expected_m5_zip_sha256,
        expected_manifest_sha256=expected_m5_manifest_sha256,
        expected_master_db_sha256=sqlite_sha)
    audit, stats = _read_only_audit(db,sqlite_sha,generation,decision_overrides)
    now = retrieved_at or datetime.now(timezone.utc).isoformat()
    pins = {
        "head_generation":generation,"head_raw_sha":expected_head_sha256,
        "sqlite_zip_sha":snapshot["zip_sha256"],"sqlite_sha":sqlite_sha,
        "inventory_snapshot":stats["inventory_sha256"],
        "inventory_as_of":stats["inventory_as_of"] or now,
        "m3_snapshot":stats["m3_snapshot"],
        "m3_effective_on":stats["m3_effective_on"],
        "m3_verification":stats["m3_verification"],
        "cp_policy_sha":cp_sha,"cp_effective_on":cp_date,
        "cp_verification":cp_verification,
        "m4_index_sha":None,"m5_a_sha":None,"m5_b_sha":None,
        "m5_c_zip_sha":expected_m5_zip_sha256,
        "m5_c_manifest_sha":expected_m5_manifest_sha256,
        "owned_deck_catalog_sha":_catalog_optional(owned_deck_catalog_bytes, expected_owned_deck_catalog_sha256),
        "readback_at":now,
        "head_zip_generation":generation,"inventory_generation":generation,
        "m3_generation":generation,
    }
    pins["missing_reasons"]={
        key:"NOT_FETCHED_IN_M6_1" for key,value in pins.items()
        if key in ("m4_index_sha","m5_a_sha","m5_b_sha") and value is None}
    if cp_sha is None:
        for key in ("cp_policy_sha","cp_effective_on","cp_verification"):
            pins["missing_reasons"][key]="CP_POLICY_MISSING"
    if owned_deck_catalog_bytes is None:
        pins["missing_reasons"]["owned_deck_catalog_sha"]="NOT_REQUESTED"
    check=validate_source_pins(pins)
    if check["status"]=="BLOCKED":
        raise ValueError("source pin contract blocked")
    return {"schema":"md-m6-1-preflight-v1",
            "audit":audit, "source_pins":pins,
            "source_pin_contract_status":check["status"],
            "stats":stats,
            "m5_knowledge_version":m5_verified["knowledge"]["knowledge_version"],
            "m5_recommendation_eligible":False,
            "current_md_legality_verified":False,
            "owned_deck_counts_are_inventory":False,
            "preflight_status":audit["preflight_status"]}
