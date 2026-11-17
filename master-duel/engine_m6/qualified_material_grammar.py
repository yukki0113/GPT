"""Source-anchored, non-authorizing grammar observations for Gen9 EX materials.

This module does NOT decide whether a material card qualifies, whether a
summon is possible, or whether constraints have been satisfied. In particular,
do not feed a 'PARSED_QUALIFIED' observation into a generic M6-5B matcher.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import sqlite3
import unicodedata

SHA = re.compile(r"[0-9a-f]{64}\Z")
XYZ_PREFIX = r"(?:[光闇炎水地風]属性|[^\s+×「」]{1,12}族)"
XYZ_ATTR_RACE = re.compile(
    rf"(?P<qual>{XYZ_PREFIX})レベル(?P<level>[1-9][0-9]?)モンスター×(?P<count>[1-5])\Z")
XYZ_THEME = re.compile(
    r"レベル(?P<level>[1-9][0-9]?)「(?P<theme>[^「」\n]{1,60})」モンスター×(?P<count>[1-5])\Z")
LINK_PREFIX = (
    r"(?:[光闇炎水地風]属性|[^\s+×「」]{1,12}族|"
    r"「[^「」\n]{1,60}」|トークン以外の|通常|効果|"
    r"リバース|P|L|レベル[1-9][0-9]?(?:以下|以上)?の?)"
)
LINK_SINGLE = re.compile(
    rf"(?P<qual>{LINK_PREFIX})モンスター(?P<count>[1-5])体(?P<more>以上)?\Z")
UNSAFE = ("または", "あるいは", "いずれか", "異なる", "同じ",
          "含む", "まで", "最大", "以外のモンスター以外", "＋")


def observe_qualified_header(method: str, header: str) -> dict:
    """Describe a narrow header grammar, never material eligibility.

    The qualifier is an *opaque exact source fragment*, not a verified
    attribute/race/archetype predicate. The returned data cannot authorize
    POSSIBLE_ON_PAPER and is safe to display as candidate-only evidence.
    """
    result = {
        "grammar": "UNPARSED",
        "qualifier_source": None,
        "level_required": None,
        "min_materials": None,
        "max_materials": None,
        "qualification_verified": False,
        "summon_route_verified": False,
        "simultaneous_materials_verified": False,
    }
    if method not in ("XYZ", "LINK") or not isinstance(header, str):
        return result
    norm = unicodedata.normalize("NFKC", header.strip())
    if not norm or any(word in norm for word in UNSAFE):
        return result
    if method == "XYZ":
        match = XYZ_ATTR_RACE.fullmatch(norm) or XYZ_THEME.fullmatch(norm)
        if match:
            result.update(
                grammar="QUALIFIED_XYZ_LEVEL_SOURCE_ONLY",
                qualifier_source=match.groupdict().get("qual") or
                                 "「" + match.group("theme") + "」",
                level_required=int(match.group("level")),
                min_materials=int(match.group("count")),
                max_materials=int(match.group("count")),
            )
    else:
        match = LINK_SINGLE.fullmatch(norm)
        if match:
            result.update(
                grammar="QUALIFIED_LINK_COUNT_SOURCE_ONLY",
                qualifier_source=match.group("qual"),
                min_materials=int(match.group("count")),
                max_materials=None if match.group("more") else int(match.group("count")),
            )
    return result


def audit_source_pinned_qualified_headers(db_path, *, expected_sqlite_sha256):
    """Audit all existing UNPARSED anchors from a verified read-only Gen9 DB.

    Never modifies SQLite, or its canonical grammar column.
    """
    path = Path(db_path)
    if not SHA.fullmatch(expected_sqlite_sha256):
        raise ValueError("QUALIFIED_AUDIT_SHA_INVALID")
    if sha256(path.read_bytes()).hexdigest() != expected_sqlite_sha256:
        raise ValueError("QUALIFIED_AUDIT_SHA_MISMATCH")
    con = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("QUALIFIED_AUDIT_INTEGRITY")
        rows = con.execute(
            """SELECT r.card_id, r.summon_method, r.material_header,
                      r.material_header_sha256, r.source_text_sha256,
                      t.body
               FROM card_extra_material_requirements r
               JOIN card_texts t ON t.card_id=r.card_id AND t.language='ja'
               WHERE r.grammar='UNPARSED' AND r.summon_method IN ('XYZ','LINK')
               ORDER BY r.card_id"""
        ).fetchall()
        count = {"XYZ": {"observed": 0, "remaining": 0},
                 "LINK": {"observed": 0, "remaining": 0}}
        for _, method, header, header_sha, body_sha, body in rows:
            if (sha256(header.encode()).hexdigest() != header_sha or
                    sha256(body.encode()).hexdigest() != body_sha):
                raise ValueError("QUALIFIED_AUDIT_SOURCE_ANCHOR_MISMATCH")
            observation = observe_qualified_header(method, header)
            category = "observed" if observation["grammar"] != "UNPARSED" else "remaining"
            count[method][category] += 1
        return {
            "schema": "md-gen9-qualified-grammar-audit-v1",
            "master_sqlite_sha256": expected_sqlite_sha256,
            "unparsed_xyz_link_examined": len(rows),
            "counts": count,
            "authorizing_decisions": 0,
            "sqlite_modified": False,
            "warning": "Opaque source labels only; NEVER assert material eligibility or summon feasibility.",
        }
    finally:
        con.close()
