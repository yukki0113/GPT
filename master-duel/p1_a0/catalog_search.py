"""P1-A0 synthetic-only filtering and dated regulation snapshot selection.

Never treats a nonofficial vector or an absent rule as verified game legality.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import unicodedata

from catalog_contract import Card, Dataset, Regulation, RARITIES


def normalize_name(value: str) -> str:
    """Lookup normalization only; do not mutate original display spelling."""
    if not isinstance(value, str):
        raise TypeError("name must be a string")
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


@dataclass(frozen=True)
class SearchCriteria:
    query: str | None = None
    max_rarity: str | None = None
    kind: str | None = None
    craftable: str | None = None
    acquisition: str | None = None
    game_verified_only: bool = False

    def __post_init__(self) -> None:
        if self.max_rarity is not None and self.max_rarity not in RARITIES:
            raise ValueError("invalid max_rarity")
        if self.craftable is not None and self.craftable not in ("YES", "NO", "UNKNOWN"):
            raise ValueError("invalid craftable")
        if self.acquisition is not None and self.acquisition not in ("KNOWN_SOURCE", "UNKNOWN"):
            raise ValueError("invalid acquisition")
        if self.query is not None and not isinstance(self.query, str):
            raise ValueError("invalid query")
        if self.kind is not None and (not isinstance(self.kind, str) or not self.kind):
            raise ValueError("invalid kind")


def search_cards(dataset: Dataset, criteria: SearchCriteria) -> tuple[Card, ...]:
    """Filter synthetic cards with AND semantics, stable input order."""
    if not isinstance(dataset, Dataset) or not isinstance(criteria, SearchCriteria):
        raise TypeError("Dataset and SearchCriteria expected")
    q = normalize_name(criteria.query) if criteria.query is not None else ""
    max_rank = RARITIES.index(criteria.max_rarity) if criteria.max_rarity is not None else None
    return tuple(card for card in dataset.cards
                 if (not q or q in normalize_name(card.name))
                 and (max_rank is None or RARITIES.index(card.md_rarity) <= max_rank)
                 and (criteria.kind is None or card.kind == criteria.kind)
                 and (criteria.craftable is None or card.craftable == criteria.craftable)
                 and (criteria.acquisition is None or card.acquisition == criteria.acquisition)
                 and (not criteria.game_verified_only or card.verification == "GAME_VERIFIED"))


@dataclass(frozen=True)
class RegulationSnapshot:
    """Whole-mode effective date. Absence of card ID does not imply 3 copies."""
    snapshot_id: str
    effective_on: date
    format_id: str
    rules: tuple[tuple[int, int], ...]
    verified_in_game: bool = False

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.format_id or not isinstance(self.effective_on, date):
            raise ValueError("snapshot_id, format_id, date required")
        ids = []
        for cid, copies in self.rules:
            if not isinstance(cid, int) or isinstance(cid, bool) or cid <= 0 or type(copies) is not int or copies not in (0, 1, 2, 3):
                raise ValueError("invalid regulation row")
            ids.append(cid)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate card regulation")


@dataclass(frozen=True)
class LimitResolution:
    status: str
    allowed: int | None
    snapshot_id: str | None
    effective_on: date | None


def resolve_limit(snapshots: tuple[RegulationSnapshot, ...], *, konami_id: int,
                  as_of: date, format_id: str, require_game_verified: bool = True) -> LimitResolution:
    """Resolve latest date <= as_of; fail closed on unverifiable or omitted cards.

    A newer unverified snapshot blocks fallback to an older verified one.
    Different versions with same effective date are ambiguous and fail closed.
    """
    if type(konami_id) is not int or konami_id <= 0 or not isinstance(as_of, date) or not format_id:
        raise ValueError("invalid query")
    applicable = [s for s in snapshots if s.format_id == format_id and s.effective_on <= as_of]
    if not applicable:
        return LimitResolution("NO_APPLICABLE_SNAPSHOT", None, None, None)
    newest = max(s.effective_on for s in applicable)
    latest = [s for s in applicable if s.effective_on == newest]
    if len(latest) != 1:
        return LimitResolution("AMBIGUOUS_SNAPSHOT", None, None, newest)
    s = latest[0]
    if require_game_verified and not s.verified_in_game:
        return LimitResolution("UNVERIFIED_SNAPSHOT", None, s.snapshot_id, s.effective_on)
    found = [copies for cid, copies in s.rules if cid == konami_id]
    if not found:
        return LimitResolution("UNLISTED_UNKNOWN", None, s.snapshot_id, s.effective_on)
    return LimitResolution("VERIFIED" if s.verified_in_game else "CANDIDATE_ONLY", found[0], s.snapshot_id, s.effective_on)
