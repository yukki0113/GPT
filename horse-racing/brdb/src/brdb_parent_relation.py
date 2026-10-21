#!/usr/bin/env python3
"""Deterministic parent-relation resolution for BRDB pedigree facts.

A parent name + birth year pair is a candidate key, not a canonical identity.
Resolution is accepted only when independent JRDB pedigree facts are consistent.
No fuzzy matching is performed. Name aliases must be explicitly supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

ROLE_SIRE = "sire"
ROLE_DAM = "dam"
ROLE_BROODMARE_SIRE = "broodmare_sire"
ROLES = {ROLE_SIRE, ROLE_DAM, ROLE_BROODMARE_SIRE}

STATUS_RESOLVED_EXACT = "RESOLVED_EXACT"
STATUS_RESOLVED_ALIAS = "RESOLVED_ALIAS"
STATUS_NO_CANDIDATE = "NO_CANDIDATE"
STATUS_MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
STATUS_INSUFFICIENT_KEY = "INSUFFICIENT_KEY"
STATUS_INSUFFICIENT_GUARD = "INSUFFICIENT_GUARD"
STATUS_CONFLICT = "CONFLICT"

METHOD_EXACT_NAME_BIRTH_YEAR = "UKC_EXACT_NAME_BIRTH_YEAR"
METHOD_ALIAS_NAME_BIRTH_YEAR = "UKC_ALIAS_NAME_BIRTH_YEAR"

EXPECTED_SEX = {
    ROLE_SIRE: "1",
    ROLE_DAM: "2",
    ROLE_BROODMARE_SIRE: "1",
}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _year(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _birth_year(profile: Mapping[str, object]) -> int | None:
    value = _year(profile.get("birth_year"))
    if value is not None:
        return value
    birth_date = _text(profile.get("birth_date"))
    if len(birth_date) >= 4 and birth_date[:4].isdigit():
        return int(birth_date[:4])
    return None


@dataclass(frozen=True)
class NameAlias:
    observed_name: str
    canonical_name: str
    birth_year: int
    lineage_code: str
    alias_version: str
    evidence_type: str = ""


class AliasIndex:
    """Explicit, versioned alias equivalence. Never infers fuzzy aliases."""

    def __init__(self, aliases: Iterable[NameAlias] = ()):
        self._neighbors: dict[tuple[str, int, str], set[str]] = {}
        for alias in aliases:
            left = (
                alias.observed_name.strip(),
                int(alias.birth_year),
                alias.lineage_code.strip(),
            )
            right = (
                alias.canonical_name.strip(),
                int(alias.birth_year),
                alias.lineage_code.strip(),
            )
            self._neighbors.setdefault(left, set()).add(right[0])
            self._neighbors.setdefault(right, set()).add(left[0])

    def equivalent(
        self,
        left: object,
        right: object,
        *,
        birth_year: object,
        lineage_code: object,
    ) -> bool:
        left_text = _text(left)
        right_text = _text(right)
        year = _year(birth_year)
        line = _text(lineage_code)
        if not left_text or not right_text or year is None or not line:
            return False
        if left_text == right_text:
            return True
        return right_text in self._neighbors.get((left_text, year, line), set())

    def candidate_names(
        self,
        name: object,
        *,
        birth_year: object,
        lineage_code: object,
    ) -> set[str]:
        name_text = _text(name)
        year = _year(birth_year)
        line = _text(lineage_code)
        if not name_text or year is None:
            return set()
        names = {name_text}
        if line:
            names.update(self._neighbors.get((name_text, year, line), set()))
        return names


class HorseMasterIndex:
    """Exact horse-master lookup by horse name + birth year."""

    def __init__(self, profiles: Iterable[Mapping[str, object]]):
        self._by_name_year: dict[tuple[str, int], list[Mapping[str, object]]] = {}
        for profile in profiles:
            name = _text(profile.get("horse_name"))
            year = _birth_year(profile)
            if not name or year is None:
                continue
            self._by_name_year.setdefault((name, year), []).append(profile)

    def candidates(
        self,
        *,
        name: object,
        birth_year: object,
        lineage_code: object,
        expected_sex: str,
        aliases: AliasIndex,
    ) -> tuple[list[Mapping[str, object]], bool]:
        year = _year(birth_year)
        if year is None:
            return [], False
        exact_name = _text(name)
        names = aliases.candidate_names(
            exact_name,
            birth_year=year,
            lineage_code=lineage_code,
        )
        output: list[Mapping[str, object]] = []
        used_alias = False
        seen: set[str] = set()
        for candidate_name in sorted(names):
            for profile in self._by_name_year.get((candidate_name, year), ()):
                if _text(profile.get("sex_code")) != expected_sex:
                    continue
                horse_id = _text(profile.get("horse_id"))
                dedupe_key = horse_id or repr(sorted(profile.items()))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                if candidate_name != exact_name:
                    used_alias = True
                output.append(profile)
        return output, used_alias


@dataclass(frozen=True)
class ParentResolution:
    role: str
    status: str
    requested_name: str
    requested_birth_year: int | None
    requested_lineage_code: str
    resolved_horse_id: str | None = None
    resolved_horse_name: str | None = None
    resolution_method: str | None = None
    candidate_count: int = 0
    guard: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status in {STATUS_RESOLVED_EXACT, STATUS_RESOLVED_ALIAS}


def _requested_parent(
    child: Mapping[str, object],
    role: str,
) -> tuple[str, int | None, str]:
    if role == ROLE_SIRE:
        return (
            _text(child.get("sire_name")),
            _year(child.get("sire_birth_year")),
            _text(child.get("sire_line_code")),
        )
    if role == ROLE_DAM:
        return (
            _text(child.get("dam_name")),
            _year(child.get("dam_birth_year")),
            _text(child.get("broodmare_sire_line_code")),
        )
    if role == ROLE_BROODMARE_SIRE:
        return (
            _text(child.get("broodmare_sire_name")),
            _year(child.get("broodmare_sire_birth_year")),
            _text(child.get("broodmare_sire_line_code")),
        )
    raise ValueError(f"unsupported role: {role}")


def _line_guard(
    candidate: Mapping[str, object],
    requested_line: str,
) -> tuple[bool | None, str]:
    candidate_line = _text(candidate.get("sire_line_code"))
    if not requested_line or not candidate_line:
        return None, "lineage_code_missing"
    if candidate_line != requested_line:
        return False, f"lineage_code_conflict:{candidate_line}!={requested_line}"
    return True, "lineage_code_match"


def resolve_parent(
    child: Mapping[str, object],
    role: str,
    *,
    master: HorseMasterIndex,
    aliases: AliasIndex | None = None,
) -> ParentResolution:
    """Resolve one parent relation with fail-closed guards."""
    if role not in ROLES:
        raise ValueError(f"unsupported role: {role}")
    aliases = aliases or AliasIndex()
    name, birth_year, lineage_code = _requested_parent(child, role)
    if not name or birth_year is None:
        return ParentResolution(
            role=role,
            status=STATUS_INSUFFICIENT_KEY,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            guard="parent_name_or_birth_year_missing",
        )

    candidates, candidate_lookup_used_alias = master.candidates(
        name=name,
        birth_year=birth_year,
        lineage_code=lineage_code,
        expected_sex=EXPECTED_SEX[role],
        aliases=aliases,
    )
    if not candidates:
        return ParentResolution(
            role=role,
            status=STATUS_NO_CANDIDATE,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=0,
            guard="no_exact_or_approved_alias_candidate",
        )
    if len(candidates) != 1:
        return ParentResolution(
            role=role,
            status=STATUS_MULTIPLE_CANDIDATES,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=len(candidates),
            guard="candidate_not_unique",
        )

    candidate = candidates[0]

    if role in {ROLE_SIRE, ROLE_BROODMARE_SIRE}:
        line_ok, guard = _line_guard(candidate, lineage_code)
        if line_ok is None:
            return ParentResolution(
                role=role,
                status=STATUS_INSUFFICIENT_GUARD,
                requested_name=name,
                requested_birth_year=birth_year,
                requested_lineage_code=lineage_code,
                candidate_count=1,
                guard=guard,
            )
        if not line_ok:
            return ParentResolution(
                role=role,
                status=STATUS_CONFLICT,
                requested_name=name,
                requested_birth_year=birth_year,
                requested_lineage_code=lineage_code,
                candidate_count=1,
                guard=guard,
            )
        alias_used = (
            candidate_lookup_used_alias
            or _text(candidate.get("horse_name")) != name
        )
        return ParentResolution(
            role=role,
            status=STATUS_RESOLVED_ALIAS if alias_used else STATUS_RESOLVED_EXACT,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            resolved_horse_id=_text(candidate.get("horse_id")) or None,
            resolved_horse_name=_text(candidate.get("horse_name")) or None,
            resolution_method=(
                METHOD_ALIAS_NAME_BIRTH_YEAR
                if alias_used
                else METHOD_EXACT_NAME_BIRTH_YEAR
            ),
            candidate_count=1,
            guard="lineage_code_match",
        )

    child_bms_name = _text(child.get("broodmare_sire_name"))
    child_bms_year = _year(child.get("broodmare_sire_birth_year"))
    child_bms_line = _text(child.get("broodmare_sire_line_code"))
    candidate_sire_name = _text(candidate.get("sire_name"))
    candidate_sire_year = _year(candidate.get("sire_birth_year"))
    candidate_sire_line = _text(candidate.get("sire_line_code"))

    if not child_bms_name or child_bms_year is None or not child_bms_line:
        return ParentResolution(
            role=role,
            status=STATUS_INSUFFICIENT_GUARD,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=1,
            guard="child_bms_guard_missing",
        )
    if candidate_sire_year != child_bms_year:
        return ParentResolution(
            role=role,
            status=STATUS_CONFLICT,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=1,
            guard=f"bms_birth_year_conflict:{candidate_sire_year}!={child_bms_year}",
        )
    if candidate_sire_line != child_bms_line:
        return ParentResolution(
            role=role,
            status=STATUS_CONFLICT,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=1,
            guard=f"bms_lineage_conflict:{candidate_sire_line}!={child_bms_line}",
        )

    name_exact = candidate_sire_name == child_bms_name
    name_alias = aliases.equivalent(
        candidate_sire_name,
        child_bms_name,
        birth_year=child_bms_year,
        lineage_code=child_bms_line,
    )
    if not (name_exact or name_alias):
        return ParentResolution(
            role=role,
            status=STATUS_CONFLICT,
            requested_name=name,
            requested_birth_year=birth_year,
            requested_lineage_code=lineage_code,
            candidate_count=1,
            guard="bms_name_conflict",
        )

    alias_used = candidate_lookup_used_alias or not name_exact
    return ParentResolution(
        role=role,
        status=STATUS_RESOLVED_ALIAS if alias_used else STATUS_RESOLVED_EXACT,
        requested_name=name,
        requested_birth_year=birth_year,
        requested_lineage_code=lineage_code,
        resolved_horse_id=_text(candidate.get("horse_id")) or None,
        resolved_horse_name=_text(candidate.get("horse_name")) or None,
        resolution_method=(
            METHOD_ALIAS_NAME_BIRTH_YEAR
            if alias_used
            else METHOD_EXACT_NAME_BIRTH_YEAR
        ),
        candidate_count=1,
        guard="dam_bms_name_birth_year_lineage_match",
    )


def resolve_first_generation(
    child: Mapping[str, object],
    *,
    master: HorseMasterIndex,
    aliases: AliasIndex | None = None,
) -> dict[str, ParentResolution]:
    """Resolve sire, dam and broodmare sire independently."""
    aliases = aliases or AliasIndex()
    return {
        role: resolve_parent(child, role, master=master, aliases=aliases)
        for role in (ROLE_SIRE, ROLE_DAM, ROLE_BROODMARE_SIRE)
    }
