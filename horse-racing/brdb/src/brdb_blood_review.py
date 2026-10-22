"""BRDB Blood Review v0.1: deterministic, non-scoring evidence review.

Pedigree facts come only through BloodReviewReader. RaceNote P2 statistics
are optional, explicitly supplied as as-of-exclusive descriptive evidence.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Iterable

REVIEW_LOGIC_VERSION = "brdb-blood-review-0.1"
CONTRACT_VERSION = "brdb-review-v0.1"
ALLOWED_SURFACES = {"芝", "ダート", "turf", "dirt"}
P2_ROLES = ("sire", "broodmare_sire")


def _date(value: object) -> dt.date:
    text = str(value or "").replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError("target_date must be YYYYMMDD or YYYY-MM-DD")
    return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def _context(context: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(context, Mapping):
        raise ValueError("target_context must be a mapping")
    date = _date(context.get("target_date"))
    venue = str(context.get("venue") or "").strip()
    surface = str(context.get("surface") or "").strip()
    distance = context.get("distance")
    if not venue or surface not in ALLOWED_SURFACES or isinstance(distance, bool):
        raise ValueError("unsupported target venue/surface/distance")
    try:
        distance_int = int(distance)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid target distance") from exc
    if distance_int < 600 or distance_int > 5000:
        raise ValueError("unsupported target distance")
    return {"target_date": date.isoformat(), "venue": venue,
            "surface": surface, "distance": distance_int}


def _p2_evidence(p2: Mapping[str, object] | None, ctx: Mapping[str, object]) -> dict[str, object] | None:
    if not isinstance(p2, Mapping):
        return None
    stamp = p2.get("as_of_exclusive")
    if not stamp:
        return None
    try:
        as_of = _date(stamp)
    except (ValueError, TypeError):
        return None
    if as_of != dt.date.fromisoformat(str(ctx["target_date"])):
        return None
    result = {}
    for role in P2_ROLES:
        item = p2.get(role)
        if not isinstance(item, Mapping):
            continue
        if item.get("scoring") is True:
            continue
        starts = item.get("starts")
        wins = item.get("wins")
        top3 = item.get("top3")
        if any(isinstance(n, bool) or not isinstance(n, int) for n in (starts, wins, top3)):
            continue
        if not (0 <= wins <= top3 <= starts):
            continue
        result[role] = {
            "starts": starts, "wins": wins, "top3": top3,
            "win_rate": wins / starts if starts else None,
            "top3_rate": top3 / starts if starts else None,
            "as_of_exclusive": as_of.isoformat(),
            "source": item.get("source"),
            "sample_size_band": item.get("sample_size_band"),
        }
    return result or None


class BloodReviewEngine:
    """Applies one shared contract to all horses, without invented scores."""

    def __init__(self, pedigree_reader):
        self.reader = pedigree_reader

    def horse_review(
        self,
        horse_id: str,
        target_context: Mapping[str, object],
        *,
        pedigree_context: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        horse_id = str(horse_id or "").strip()
        meta = self.reader.metadata()
        provenance = {
            "generation_id": meta["generation_id"],
            "pedigree_schema_version": meta["schema_version"],
            "taxonomy_version": None,
            "review_logic_version": REVIEW_LOGIC_VERSION,
            "p2_source": None,
        }
        result = {
            "horse_id": horse_id or None,
            "status": "NO_HORSE_ID" if not horse_id else "NO_PEDIGREE",
            "contract_version": CONTRACT_VERSION,
            "target_context": None,
            "facts": {"sire_name": None, "dam_name": None, "broodmare_sire_name": None},
            "classification": {"sire_line": None, "broodmare_sire_line": None, "regional_type": None},
            "review": {"overall_score": None, "components": [], "positive_factors": [],
                       "negative_factors": [], "summary": None, "pedigree_context": None},
            "coverage": {"status": "NONE", "pedigree_fields": 0, "pedigree_context": "NONE"},
            "confidence": "NONE",
            "provenance": provenance,
        }
        if not horse_id:
            return result
        try:
            ctx = _context(target_context)
        except (ValueError, TypeError):
            result["status"] = "UNSUPPORTED_CONTEXT"
            return result
        result["target_context"] = ctx
        record = self.reader.horse_pedigree(horse_id)
        if record is None:
            return result
        for role, field in (("sire", "sire_name"), ("dam", "dam_name"),
                            ("broodmare_sire", "broodmare_sire_name")):
            result["facts"][field] = record.get(role, {}).get("name")
        for role, field in (("sire", "sire_line"), ("broodmare_sire", "broodmare_sire_line")):
            line = record.get(role, {}).get("lineage")
            if isinstance(line, Mapping):
                result["classification"][field] = {
                    "code": line.get("lineage_code"), "major_name": line.get("major_name"),
                    "minor_name": line.get("minor_name"), "source": line.get("source_name"),
                }
        present = sum(bool(value) for value in result["facts"].values())
        p2 = _p2_evidence(pedigree_context, ctx)
        if p2:
            result["review"]["pedigree_context"] = p2
            result["coverage"]["pedigree_context"] = "PARTIAL" if len(p2) < 2 else "FULL"
            result["provenance"]["p2_source"] = "supplied_RaceNote_P2"
        result["coverage"]["pedigree_fields"] = present
        if present == 0:
            result["status"] = "NO_PEDIGREE"
        elif present == 3 and p2 and len(p2) == 2:
            result["status"] = "AVAILABLE"
        else:
            result["status"] = "PARTIAL"
        result["coverage"]["status"] = "FULL" if present == 3 else ("PARTIAL" if present else "NONE")
        result["confidence"] = "DESCRIPTIVE_ONLY" if present else "NONE"
        result["review"]["summary"] = "血統事実と条件別実績の記述的レビュー。適性判定・採点は未実施。" if p2 else "血統事実のみ確認。条件別実績は未提供。"
        return result

    def reviews_for_horses(
        self, horse_ids: Iterable[str], target_context: Mapping[str, object],
        *, pedigree_contexts: Mapping[str, Mapping[str, object]] | None = None,
    ) -> dict[str, dict[str, object]]:
        contexts = pedigree_contexts or {}
        return {horse_id: self.horse_review(horse_id, target_context,
                pedigree_context=contexts.get(horse_id)) for horse_id in horse_ids}
