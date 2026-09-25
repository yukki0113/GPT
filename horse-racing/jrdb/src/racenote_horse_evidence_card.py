#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build RaceNote Horse Evidence Cards from RaceReviewDB evidence.

v0.1 is intentionally a historical-review slice of the wider Horse Evidence
Card architecture. It converts deterministic RaceReviewDB evidence into
auditable positive, negative, mixed, repeatability, and uncertainty items.

The builder never reads market information and never assigns a prediction
score. Candidate hidden-strength / fragile-form signals describe the relation
between visible historical results and reconstructed running content only.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

CARD_SCHEMA_VERSION = "RaceNote-Horse-Evidence-Card-0.1"
CARD_LOGIC_VERSION = "RaceReview-Card-v0.1"
EXPECTED_REVIEW_EVIDENCE_SCHEMA = "RaceReview-Evidence-0.1"

FRONT_THIRD_THRESHOLD = 2.0 / 3.0
REAR_THIRD_THRESHOLD = 1.0 / 3.0
TOP_HALF_THRESHOLD = 0.5
PODIUM_FINISH_MAX = 3

FRONT_LOADED_PACES = {
    "FRONT_LOADED",
    "VERY_FRONT_LOADED",
}
BACK_LOADED_PACES = {
    "BACK_LOADED",
    "VERY_BACK_LOADED",
}

HIDDEN_STRENGTH_CODES = {
    "RESULT_UNDERRATES_TIME",
    "PACE_POSITION_AGAINST_GOOD_RUN",
    "LOSS_WITH_FASTEST_LAST3F",
    "REPEATED_ABOVE_CLASS_PERFORMANCE",
    "REPEATED_RESULT_UNDERRATES_TIME",
    "REPEATED_PACE_POSITION_AGAINST",
    "REPEATED_FASTEST_LAST3F",
}
FRAGILE_FORM_CODES = {
    "RESULT_OVERRATES_TIME",
    "PACE_POSITION_AIDED_RESULT",
    "REPEATED_BELOW_CLASS_PERFORMANCE",
    "REPEATED_RESULT_OVERRATES_TIME",
    "REPEATED_PACE_POSITION_AIDED",
}

PRIORITY_ORDER = {
    "REPEATABILITY": 0,
    "DIRECT_PERFORMANCE": 1,
    "CONTEXTUAL": 2,
}
STRENGTH_ORDER = {
    "STRONG": 0,
    "MEDIUM": 1,
    "WEAK": 2,
}


class HorseEvidenceCardError(RuntimeError):
    """Raised when a RaceReview evidence sidecar violates card contracts."""


def _text(value: object) -> str:
    """Return stripped text or an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    """Return a finite float or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _positive_int(value: object, field: str) -> int:
    """Return a positive integer and fail closed otherwise."""
    if isinstance(value, bool):
        raise HorseEvidenceCardError(
            f"{field} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise HorseEvidenceCardError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1:
        raise HorseEvidenceCardError(
            f"{field} must be a positive integer"
        )
    return number


def _date_text(value: object) -> str:
    """Normalize one date-like value to YYYY-MM-DD."""
    text = _text(value)
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 8:
        raise HorseEvidenceCardError(f"invalid race date: {value!r}")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """Require one mapping."""
    if not isinstance(value, Mapping):
        raise HorseEvidenceCardError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    """Require one list."""
    if not isinstance(value, list):
        raise HorseEvidenceCardError(f"{field} must be an array")
    return value


def _tags(run: Mapping[str, object]) -> set[str]:
    """Return normalized deterministic Review tags."""
    raw_tags = run.get("review_tags")
    if not isinstance(raw_tags, list):
        return set()
    result: set[str] = set()
    for raw_tag in raw_tags:
        tag = _text(raw_tag).upper()
        if tag:
            result.add(tag)
    return result


def _run_ref(run: Mapping[str, object]) -> str:
    """Return a stable historical run reference."""
    race_key = _text(run.get("race_key"))
    race_date = _date_text(run.get("race_date"))
    if not race_key:
        raise HorseEvidenceCardError("historical run has no race_key")
    return f"{race_key}@{race_date}"


def _field_size(run: Mapping[str, object]) -> int | None:
    """Return a valid field size when available."""
    value = run.get("field_size")
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 2:
        return None
    return number


def _finish(run: Mapping[str, object]) -> int | None:
    """Return a positive finishing rank when available."""
    value = run.get("finish")
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 1:
        return None
    return number


def _result_frontness(run: Mapping[str, object]) -> float | None:
    """Normalize finish so 1.0 is winner and 0.0 is last."""
    finish = _finish(run)
    field_size = _field_size(run)
    if finish is None or field_size is None:
        return None
    if finish > field_size:
        return None
    return 1.0 - float(finish - 1) / float(field_size - 1)


def _family(
    run: Mapping[str, object],
    name: str,
) -> Mapping[str, object]:
    """Return one RaceReview evidence family or an empty mapping."""
    families = run.get("families")
    if not isinstance(families, Mapping):
        return {}
    value = families.get(name)
    if not isinstance(value, Mapping):
        return {}
    return value


def _evidence_id(
    horse_no: int,
    code: str,
    source_refs: list[str],
) -> str:
    """Return deterministic evidence identity."""
    suffix = "PROFILE"
    if source_refs:
        suffix = "+".join(source_refs)
    return f"HEC:{horse_no}:{code}:{suffix}"


def _item(
    *,
    horse_no: int,
    code: str,
    family: str,
    direction: str,
    priority: str,
    strength: str,
    evidence_quality: str,
    source_refs: list[str],
    facts: Mapping[str, object],
    redundancy_group_id: str,
) -> dict[str, object]:
    """Create one generic Evidence Card item."""
    return {
        "evidence_id": _evidence_id(horse_no, code, source_refs),
        "code": code,
        "family": family,
        "direction": direction,
        "priority": priority,
        "strength": strength,
        "evidence_quality": evidence_quality,
        "redundancy_group_id": redundancy_group_id,
        "source_run_refs": list(source_refs),
        "facts": dict(facts),
    }


def _time_result_item(
    horse_no: int,
    run: Mapping[str, object],
) -> dict[str, object] | None:
    """Detect visible-result versus time-class disagreement."""
    finish = _finish(run)
    if finish is None:
        return None

    tags = _tags(run)
    run_ref = _run_ref(run)
    ability = _family(run, "ability")

    if finish > PODIUM_FINISH_MAX:
        if "TIME_ABOVE_DECLARED_CLASS" in tags:
            return _item(
                horse_no=horse_no,
                code="RESULT_UNDERRATES_TIME",
                family="ABILITY",
                direction="POSITIVE",
                priority="DIRECT_PERFORMANCE",
                strength="MEDIUM",
                evidence_quality="MIXED",
                source_refs=[run_ref],
                facts={
                    "finish": finish,
                    "declared_class_group": ability.get(
                        "declared_class_group"
                    ),
                    "time_class_equivalent": ability.get(
                        "time_class_equivalent"
                    ),
                },
                redundancy_group_id=f"TIME_CLASS:{run_ref}",
            )
        return None

    if "TIME_BELOW_DECLARED_CLASS" in tags:
        return _item(
            horse_no=horse_no,
            code="RESULT_OVERRATES_TIME",
            family="ABILITY",
            direction="NEGATIVE",
            priority="DIRECT_PERFORMANCE",
            strength="MEDIUM",
            evidence_quality="MIXED",
            source_refs=[run_ref],
            facts={
                "finish": finish,
                "declared_class_group": ability.get(
                    "declared_class_group"
                ),
                "time_class_equivalent": ability.get(
                    "time_class_equivalent"
                ),
            },
            redundancy_group_id=f"TIME_CLASS:{run_ref}",
        )
    return None


def _fastest_last3f_item(
    horse_no: int,
    run: Mapping[str, object],
) -> dict[str, object] | None:
    """Retain a losing fastest-last3F observation as support evidence."""
    finish = _finish(run)
    if finish is None or finish <= PODIUM_FINISH_MAX:
        return None

    tags = _tags(run)
    if "FASTEST_LAST3F" not in tags:
        return None

    run_ref = _run_ref(run)
    finish_family = _family(run, "finish")
    return _item(
        horse_no=horse_no,
        code="LOSS_WITH_FASTEST_LAST3F",
        family="FINISH",
        direction="POSITIVE",
        priority="DIRECT_PERFORMANCE",
        strength="MEDIUM",
        evidence_quality="GOOD",
        source_refs=[run_ref],
        facts={
            "finish": finish,
            "last3f_rank": finish_family.get("last3f_rank"),
            "last3f_speed_percentile": finish_family.get(
                "last3f_speed_percentile"
            ),
            "closing_gain_sec": finish_family.get("closing_gain_sec"),
        },
        redundancy_group_id=f"LAST3F:{run_ref}",
    )


def _move_then_fade_item(
    horse_no: int,
    run: Mapping[str, object],
) -> dict[str, object] | None:
    """Keep move-then-fade as mixed context rather than a positive vote."""
    tags = _tags(run)
    if "MOVE_THEN_FADE" not in tags:
        return None

    run_ref = _run_ref(run)
    position = _family(run, "position")
    return _item(
        horse_no=horse_no,
        code="MOVE_THEN_FADE",
        family="POSITION",
        direction="MIXED",
        priority="CONTEXTUAL",
        strength="WEAK",
        evidence_quality="MIXED",
        source_refs=[run_ref],
        facts={
            "early_position_gain": position.get("early_position_gain"),
            "middle_position_gain": position.get(
                "middle_position_gain"
            ),
            "late_position_gain": position.get("late_position_gain"),
        },
        redundancy_group_id=f"POSITION_MOVE:{run_ref}",
    )


def _pace_position_item(
    horse_no: int,
    run: Mapping[str, object],
) -> dict[str, object] | None:
    """Describe whether observed pace and fourth-corner position aligned.

    This is deliberately a coarse research interpretation. Front/rear thirds
    use normalized fourth-corner frontness; positive against-pace evidence
    additionally requires a top-half finish. An aided-result concern requires
    a top-three finish. No numeric score is produced.
    """
    pace = _family(run, "pace")
    position = _family(run, "position")
    pace_shape = _text(pace.get("pace_shape")).upper()
    corner4 = _finite(position.get("corner4_frontness"))
    finish = _finish(run)
    result_frontness = _result_frontness(run)
    if not pace_shape or corner4 is None or finish is None:
        return None

    run_ref = _run_ref(run)
    is_front = corner4 >= FRONT_THIRD_THRESHOLD
    is_rear = corner4 <= REAR_THIRD_THRESHOLD

    against = False
    aided = False

    if pace_shape in FRONT_LOADED_PACES:
        if is_front:
            if result_frontness is not None:
                if result_frontness >= TOP_HALF_THRESHOLD:
                    against = True
        if is_rear and finish <= PODIUM_FINISH_MAX:
            aided = True

    if pace_shape in BACK_LOADED_PACES:
        if is_rear:
            if result_frontness is not None:
                if result_frontness >= TOP_HALF_THRESHOLD:
                    against = True
        if is_front and finish <= PODIUM_FINISH_MAX:
            aided = True

    facts = {
        "finish": finish,
        "field_size": _field_size(run),
        "result_frontness": result_frontness,
        "pace_shape": pace_shape,
        "corner4_frontness": corner4,
    }

    if against:
        return _item(
            horse_no=horse_no,
            code="PACE_POSITION_AGAINST_GOOD_RUN",
            family="PACE_POSITION",
            direction="POSITIVE",
            priority="CONTEXTUAL",
            strength="MEDIUM",
            evidence_quality="MIXED",
            source_refs=[run_ref],
            facts=facts,
            redundancy_group_id=f"PACE_POSITION:{run_ref}",
        )

    if aided:
        return _item(
            horse_no=horse_no,
            code="PACE_POSITION_AIDED_RESULT",
            family="PACE_POSITION",
            direction="NEGATIVE",
            priority="CONTEXTUAL",
            strength="MEDIUM",
            evidence_quality="MIXED",
            source_refs=[run_ref],
            facts=facts,
            redundancy_group_id=f"PACE_POSITION:{run_ref}",
        )

    return None


def _direct_items(
    horse_no: int,
    runs: list[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build deterministic per-run card evidence."""
    result: list[dict[str, object]] = []
    builders = (
        _time_result_item,
        _fastest_last3f_item,
        _move_then_fade_item,
        _pace_position_item,
    )
    seen: set[str] = set()

    for run in runs:
        for builder in builders:
            item = builder(horse_no, run)
            if item is None:
                continue
            evidence_id = _text(item.get("evidence_id"))
            if evidence_id in seen:
                continue
            seen.add(evidence_id)
            result.append(item)
    return result


def _pattern_count(
    profile: Mapping[str, object],
    code: str,
) -> int:
    """Read one adapter tag count."""
    raw = profile.get("pattern_counts")
    if not isinstance(raw, Mapping):
        return 0
    value = raw.get(code)
    if value is None or isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    if number < 0:
        return 0
    return number


def _source_refs_for_tag(
    runs: list[Mapping[str, object]],
    tag: str,
) -> list[str]:
    """Return run references containing one deterministic adapter tag."""
    refs: list[str] = []
    for run in runs:
        if tag in _tags(run):
            refs.append(_run_ref(run))
    return refs


def _repeatability_item(
    *,
    horse_no: int,
    code: str,
    direction: str,
    source_refs: list[str],
    facts: Mapping[str, object],
    family: str,
) -> dict[str, object]:
    """Create one repeated-pattern evidence item."""
    return _item(
        horse_no=horse_no,
        code=code,
        family=family,
        direction=direction,
        priority="REPEATABILITY",
        strength="STRONG",
        evidence_quality="MIXED",
        source_refs=source_refs,
        facts=facts,
        redundancy_group_id=f"REPEATABILITY:{code}",
    )


def _adapter_repeatability_items(
    horse_no: int,
    runs: list[Mapping[str, object]],
    profile: Mapping[str, object],
) -> list[dict[str, object]]:
    """Promote repeated raw Review patterns into non-additive card evidence."""
    result: list[dict[str, object]] = []
    specifications = (
        (
            "TIME_ABOVE_DECLARED_CLASS",
            "REPEATED_ABOVE_CLASS_PERFORMANCE",
            "POSITIVE",
            "ABILITY",
        ),
        (
            "TIME_BELOW_DECLARED_CLASS",
            "REPEATED_BELOW_CLASS_PERFORMANCE",
            "NEGATIVE",
            "ABILITY",
        ),
        (
            "FASTEST_LAST3F",
            "REPEATED_FASTEST_LAST3F",
            "POSITIVE",
            "FINISH",
        ),
        (
            "MOVE_THEN_FADE",
            "REPEATED_MOVE_THEN_FADE",
            "MIXED",
            "POSITION",
        ),
    )

    for tag, code, direction, family in specifications:
        count = _pattern_count(profile, tag)
        if count < 2:
            continue
        refs = _source_refs_for_tag(runs, tag)
        result.append(
            _repeatability_item(
                horse_no=horse_no,
                code=code,
                direction=direction,
                source_refs=refs,
                facts={
                    "source_tag": tag,
                    "count": count,
                },
                family=family,
            )
        )
    return result


def _repeated_composite_items(
    horse_no: int,
    direct_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Promote repeated card composites without treating them as extra votes."""
    by_code: dict[str, list[dict[str, object]]] = {}
    for item in direct_items:
        code = _text(item.get("code"))
        by_code.setdefault(code, []).append(item)

    specifications = {
        "RESULT_UNDERRATES_TIME": (
            "REPEATED_RESULT_UNDERRATES_TIME",
            "POSITIVE",
            "ABILITY",
        ),
        "RESULT_OVERRATES_TIME": (
            "REPEATED_RESULT_OVERRATES_TIME",
            "NEGATIVE",
            "ABILITY",
        ),
        "PACE_POSITION_AGAINST_GOOD_RUN": (
            "REPEATED_PACE_POSITION_AGAINST",
            "POSITIVE",
            "PACE_POSITION",
        ),
        "PACE_POSITION_AIDED_RESULT": (
            "REPEATED_PACE_POSITION_AIDED",
            "NEGATIVE",
            "PACE_POSITION",
        ),
    }

    result: list[dict[str, object]] = []
    for source_code, specification in specifications.items():
        items = by_code.get(source_code, [])
        refs: list[str] = []
        for item in items:
            raw_refs = item.get("source_run_refs")
            if not isinstance(raw_refs, list):
                continue
            for raw_ref in raw_refs:
                ref = _text(raw_ref)
                if ref and ref not in refs:
                    refs.append(ref)
        if len(refs) < 2:
            continue

        code, direction, family = specification
        result.append(
            _repeatability_item(
                horse_no=horse_no,
                code=code,
                direction=direction,
                source_refs=refs,
                facts={
                    "source_code": source_code,
                    "count": len(refs),
                },
                family=family,
            )
        )
    return result


def _sort_key(item: Mapping[str, object]) -> tuple[int, int, str]:
    """Sort evidence without turning ordering into a numeric score."""
    priority = _text(item.get("priority"))
    strength = _text(item.get("strength"))
    code = _text(item.get("code"))
    priority_rank = PRIORITY_ORDER.get(priority, 99)
    strength_rank = STRENGTH_ORDER.get(strength, 99)
    return priority_rank, strength_rank, code


def _partition(
    items: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Partition evidence and choose primary positives by distinct family."""
    positive: list[dict[str, object]] = []
    negative: list[dict[str, object]] = []
    mixed: list[dict[str, object]] = []

    for item in items:
        direction = _text(item.get("direction"))
        if direction == "POSITIVE":
            positive.append(item)
        elif direction == "NEGATIVE":
            negative.append(item)
        elif direction == "MIXED":
            mixed.append(item)

    positive.sort(key=_sort_key)
    negative.sort(key=_sort_key)
    mixed.sort(key=_sort_key)

    primary: list[dict[str, object]] = []
    support: list[dict[str, object]] = []
    primary_families: set[str] = set()

    for item in positive:
        family = _text(item.get("family"))
        if len(primary) < 2 and family not in primary_families:
            primary.append(item)
            primary_families.add(family)
        else:
            support.append(item)

    return {
        "primary_positive": primary,
        "supporting_positive": support,
        "concerns": negative,
        "mixed_context": mixed,
    }


def _signal(
    items: list[dict[str, object]],
    codes: set[str],
) -> dict[str, object]:
    """Summarize one candidate signal without using scores."""
    selected: list[dict[str, object]] = []
    for item in items:
        if _text(item.get("code")) in codes:
            selected.append(item)

    if not selected:
        return {
            "status": "NONE",
            "confidence": "NONE",
            "reason_codes": [],
            "evidence_ids": [],
            "source_run_refs": [],
        }

    reason_codes: list[str] = []
    evidence_ids: list[str] = []
    source_refs: list[str] = []
    repeated = False

    for item in sorted(selected, key=_sort_key):
        code = _text(item.get("code"))
        evidence_id = _text(item.get("evidence_id"))
        priority = _text(item.get("priority"))

        if code and code not in reason_codes:
            reason_codes.append(code)
        if evidence_id and evidence_id not in evidence_ids:
            evidence_ids.append(evidence_id)
        if priority == "REPEATABILITY":
            repeated = True

        raw_refs = item.get("source_run_refs")
        if isinstance(raw_refs, list):
            for raw_ref in raw_refs:
                ref = _text(raw_ref)
                if ref and ref not in source_refs:
                    source_refs.append(ref)

    confidence = "LOW"
    if len(source_refs) >= 2:
        confidence = "MEDIUM"
    if repeated:
        confidence = "HIGH"

    return {
        "status": "CANDIDATE",
        "confidence": confidence,
        "reason_codes": reason_codes,
        "evidence_ids": evidence_ids,
        "source_run_refs": source_refs,
    }


def _contradiction(
    hidden_strength: Mapping[str, object],
    fragile_form: Mapping[str, object],
    items: list[dict[str, object]],
) -> dict[str, object]:
    """Record explicit mixed historical evidence."""
    conflict_codes: list[str] = []

    if (
        hidden_strength.get("status") == "CANDIDATE"
        and fragile_form.get("status") == "CANDIDATE"
    ):
        conflict_codes.append("HIDDEN_AND_FRAGILE_EVIDENCE_COEXIST")

    codes = {_text(item.get("code")) for item in items}
    if (
        "REPEATED_ABOVE_CLASS_PERFORMANCE" in codes
        and "REPEATED_BELOW_CLASS_PERFORMANCE" in codes
    ):
        conflict_codes.append("MIXED_REPEATED_TIME_CLASS")

    status = "NONE"
    if conflict_codes:
        status = "MIXED"

    return {
        "status": status,
        "conflict_codes": conflict_codes,
    }


def _uncertainties(
    horse: Mapping[str, object],
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build explicit uncertainty records."""
    result: list[dict[str, object]] = []
    history_status = _text(horse.get("history_status"))
    profile = horse.get("profile")
    coverage_status = ""
    if isinstance(profile, Mapping):
        coverage_status = _text(profile.get("coverage_status"))

    if history_status == "NO_HORSE_ID":
        result.append(
            {
                "code": "NO_HORSE_ID",
                "severity": "HIGH",
            }
        )
    elif history_status == "NO_HISTORY":
        result.append(
            {
                "code": "NO_RACEREVIEW_HISTORY",
                "severity": "HIGH",
            }
        )

    if coverage_status == "PARTIAL":
        result.append(
            {
                "code": "PARTIAL_RACEREVIEW_HISTORY",
                "severity": "MEDIUM",
            }
        )

    if not items and history_status == "AVAILABLE":
        result.append(
            {
                "code": "NO_CARD_LEVEL_COMPOSITE_EVIDENCE",
                "severity": "MEDIUM",
            }
        )

    return result


def _comment_evidence(
    partitioned: Mapping[str, list[dict[str, object]]],
    uncertainties: list[dict[str, object]],
) -> dict[str, object]:
    """Select codes for a future renderer; do not generate prose here."""
    positive_codes: list[str] = []
    concern_codes: list[str] = []
    mixed_codes: list[str] = []
    source_ids: list[str] = []

    positive_items = list(partitioned.get("primary_positive", []))
    positive_items.extend(partitioned.get("supporting_positive", []))
    for item in positive_items[:3]:
        code = _text(item.get("code"))
        evidence_id = _text(item.get("evidence_id"))
        if code:
            positive_codes.append(code)
        if evidence_id:
            source_ids.append(evidence_id)

    for item in partitioned.get("concerns", [])[:2]:
        code = _text(item.get("code"))
        evidence_id = _text(item.get("evidence_id"))
        if code:
            concern_codes.append(code)
        if evidence_id and evidence_id not in source_ids:
            source_ids.append(evidence_id)

    for item in partitioned.get("mixed_context", [])[:1]:
        code = _text(item.get("code"))
        evidence_id = _text(item.get("evidence_id"))
        if code:
            mixed_codes.append(code)
        if evidence_id and evidence_id not in source_ids:
            source_ids.append(evidence_id)

    status = "READY"
    if uncertainties:
        status = "LIMITED"
    if not positive_codes and not concern_codes and not mixed_codes:
        status = "INSUFFICIENT"

    return {
        "status": status,
        "positive_codes": positive_codes,
        "concern_codes": concern_codes,
        "mixed_codes": mixed_codes,
        "source_evidence_ids": source_ids,
        "prose_generation_status": "NOT_GENERATED_V0_1",
    }


def _validate_sidecar(sidecar: Mapping[str, object]) -> None:
    """Validate the minimum adapter boundary required by the card builder."""
    if (
        _text(sidecar.get("evidence_schema_version"))
        != EXPECTED_REVIEW_EVIDENCE_SCHEMA
    ):
        raise HorseEvidenceCardError(
            "unsupported RaceReview evidence schema"
        )

    policy = _mapping(sidecar.get("policy"), "policy")
    if policy.get("as_of_exclusive") is not True:
        raise HorseEvidenceCardError(
            "RaceReview evidence must be as-of-exclusive"
        )
    if policy.get("name_fallback") is not False:
        raise HorseEvidenceCardError(
            "RaceReview evidence must forbid name fallback"
        )
    if policy.get("stable_fields_only") is not True:
        raise HorseEvidenceCardError(
            "RaceReview evidence must use stable fields only"
        )


def _horse_card(
    horse: Mapping[str, object],
    target_date: str,
) -> dict[str, object]:
    """Build one RaceReview-backed Horse Evidence Card."""
    horse_no = _positive_int(horse.get("horse_no"), "horse.horse_no")
    raw_runs = _list(horse.get("runs"), "horse.runs")
    runs: list[Mapping[str, object]] = []

    for index, raw_run in enumerate(raw_runs, start=1):
        run = _mapping(raw_run, f"horse.runs[{index}]")
        race_date = _date_text(run.get("race_date"))
        if race_date >= target_date:
            raise HorseEvidenceCardError(
                "Horse Evidence Card received non-exclusive history: "
                f"horse_no={horse_no} race_date={race_date} "
                f"target_date={target_date}"
            )
        runs.append(run)

    profile = _mapping(horse.get("profile"), "horse.profile")
    direct_items = _direct_items(horse_no, runs)
    repeated_items = _adapter_repeatability_items(
        horse_no,
        runs,
        profile,
    )
    repeated_items.extend(
        _repeated_composite_items(
            horse_no,
            direct_items,
        )
    )

    items = direct_items + repeated_items
    items.sort(key=_sort_key)
    partitioned = _partition(items)

    hidden_strength = _signal(items, HIDDEN_STRENGTH_CODES)
    fragile_form = _signal(items, FRAGILE_FORM_CODES)
    contradiction = _contradiction(
        hidden_strength,
        fragile_form,
        items,
    )
    uncertainties = _uncertainties(horse, items)
    comment = _comment_evidence(partitioned, uncertainties)

    return {
        "horse_no": horse_no,
        "horse_name": _text(horse.get("horse_name")),
        "horse_id": _text(horse.get("horse_id")),
        "history_status": _text(horse.get("history_status")),
        "card_scope": "RACEREVIEW_HISTORY_V0_1",
        **partitioned,
        "profile": {
            "hidden_strength": hidden_strength,
            "fragile_form": fragile_form,
            "contradiction": contradiction,
            "repeatability_source": "RACEREVIEW_HISTORY",
        },
        "uncertainties": uncertainties,
        "comment_evidence": comment,
    }


def build_horse_evidence_cards(
    racereview_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Build deterministic Horse Evidence Cards from one Review sidecar."""
    _validate_sidecar(racereview_evidence)

    target = _mapping(racereview_evidence.get("target"), "target")
    target_date = _date_text(target.get("date"))
    source = _mapping(racereview_evidence.get("source"), "source")
    raw_horses = _list(racereview_evidence.get("horses"), "horses")
    if not raw_horses:
        raise HorseEvidenceCardError("RaceReview evidence has no horses")

    cards: list[dict[str, object]] = []
    seen_horse_nos: set[int] = set()
    for index, raw_horse in enumerate(raw_horses, start=1):
        horse = _mapping(raw_horse, f"horses[{index}]")
        card = _horse_card(horse, target_date)
        horse_no = int(card["horse_no"])
        if horse_no in seen_horse_nos:
            raise HorseEvidenceCardError(
                f"duplicate horse_no in evidence cards: {horse_no}"
            )
        seen_horse_nos.add(horse_no)
        cards.append(card)

    cards.sort(key=lambda card: int(card["horse_no"]))

    return {
        "card_schema_version": CARD_SCHEMA_VERSION,
        "card_logic_version": CARD_LOGIC_VERSION,
        "target": {
            "date": target_date,
            "venue": _text(target.get("venue")),
            "race_no": _positive_int(
                target.get("race_no"),
                "target.race_no",
            ),
            "race_name": _text(target.get("race_name")),
        },
        "source": {
            "kind": "RaceReviewDB",
            "generation_id": _text(source.get("generation_id")),
            "review_schema_version": _text(
                source.get("review_schema_version")
            ),
            "review_logic_version": _text(
                source.get("review_logic_version")
            ),
            "baseline_version": _text(source.get("baseline_version")),
            "adapter_version": _text(
                racereview_evidence.get("adapter_version")
            ),
            "evidence_schema_version": _text(
                racereview_evidence.get("evidence_schema_version")
            ),
        },
        "policy": {
            "market_visibility_status": "HIDDEN_NOT_CONSUMED",
            "jrdb_current_consensus_status": "HIDDEN_NOT_CONSUMED",
            "training_edge_status": "NOT_CONSUMED",
            "score_status": "NO_ADDITIVE_SCORE",
            "comment_prose_status": "NOT_GENERATED",
            "hidden_strength_semantics": (
                "HISTORICAL_RESULT_VS_CONTENT_ONLY"
            ),
            "fragile_form_semantics": (
                "HISTORICAL_RESULT_VS_CONTENT_ONLY"
            ),
        },
        "horses": cards,
    }


def main() -> int:
    """Build Horse Evidence Card JSON from one RaceReview sidecar."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--racereview-evidence",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sidecar = json.loads(
        args.racereview_evidence.read_text(encoding="utf-8")
    )
    cards = build_horse_evidence_cards(sidecar)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "card_schema_version": CARD_SCHEMA_VERSION,
                "horse_count": len(cards["horses"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
