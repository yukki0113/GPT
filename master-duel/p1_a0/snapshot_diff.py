"""P1-A0: deterministic differences between synthetic, immutable snapshots.

This module does not fetch sources, persist data, or publish updated states.
All findings are proposals for review, never authorization to promote.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from datetime import date

from catalog_contract import Dataset, Card


@dataclass(frozen=True)
class Change:
    card_id: str
    status: str
    changed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class CardDiff:
    before_snapshot: str
    after_snapshot: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[Change, ...]
    conflicts: tuple[str, ...]
    identical: bool
    report_sha256: str


_FIELDS = ("konami_id", "name", "kind", "md_rarity", "rarity_source",
           "verification", "craftable", "acquisition", "password_variants")


def _fingerprint_card(card: Card) -> tuple:
    return tuple(getattr(card, field) for field in _FIELDS)


def diff_cards(before: Dataset, after: Dataset) -> CardDiff:
    """Reject snapshot-ID reuse; flag every reused or reassigned Konami identity."""
    if not isinstance(before, Dataset) or not isinstance(after, Dataset):
        raise TypeError("Dataset arguments required")
    if before.snapshot_id == after.snapshot_id and before.source_sha256 != after.source_sha256:
        raise ValueError("snapshot ID reused with changed source hash")
    a = {x.canonical_id: x for x in before.cards}
    b = {x.canonical_id: x for x in after.cards}
    before_by_konami = {x.konami_id: x.canonical_id for x in before.cards}
    after_by_konami = {x.konami_id: x.canonical_id for x in after.cards}
    conflicts = []
    for card_id in sorted(a.keys() & b.keys()):
        if a[card_id].konami_id != b[card_id].konami_id:
            conflicts.append(f"CANONICAL_REBOUND:{card_id}")
    for kid in sorted(before_by_konami.keys() & after_by_konami.keys()):
        if before_by_konami[kid] != after_by_konami[kid]:
            conflicts.append(f"KONAMI_REBOUND:{kid}")
    added = tuple(sorted(b.keys() - a.keys()))
    removed = tuple(sorted(a.keys() - b.keys()))
    changes = tuple(Change(key, "CHANGED", tuple(field for field in _FIELDS
                             if getattr(a[key], field) != getattr(b[key], field)))
                    for key in sorted(a.keys() & b.keys()) if _fingerprint_card(a[key]) != _fingerprint_card(b[key]))
    same_data = not (added or removed or changes)
    if before.source_sha256 == after.source_sha256 and not same_data:
        raise ValueError("same source hash with different logical card data")
    payload = {"before": before.snapshot_id, "after": after.snapshot_id,
               "before_sha": before.source_sha256, "after_sha": after.source_sha256,
               "added": added, "removed": removed,
               "changed": [(c.card_id, c.changed_fields) for c in changes],
               "conflicts": tuple(conflicts)}
    digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8")).hexdigest()
    return CardDiff(before.snapshot_id, after.snapshot_id, added, removed,
                    changes, tuple(conflicts), same_data, digest)


@dataclass(frozen=True)
class RegulationDelta:
    before_id: str
    after_id: str
    format_id: str
    before_effective_on: date
    after_effective_on: date
    added: tuple[tuple[int, int], ...]
    removed: tuple[tuple[int, int], ...]
    changed: tuple[tuple[int, int, int], ...]
    status: str


def diff_regulations(before, after) -> RegulationDelta:
    """Compare explicit restrictions, without assuming unlisted means 3."""
    from catalog_search import RegulationSnapshot
    if not isinstance(before, RegulationSnapshot) or not isinstance(after, RegulationSnapshot):
        raise TypeError("RegulationSnapshot arguments required")
    if before.format_id != after.format_id:
        raise ValueError("banlist format mismatch")
    if after.effective_on < before.effective_on:
        raise ValueError("banlist effective date goes backward")
    if before.snapshot_id == after.snapshot_id and (
        before.effective_on != after.effective_on or before.rules != after.rules or
        before.verified_in_game != after.verified_in_game
    ):
        raise ValueError("banlist snapshot ID reused with changed content")
    old, new = dict(before.rules), dict(after.rules)
    added = tuple((cid, new[cid]) for cid in sorted(new.keys() - old.keys()))
    removed = tuple((cid, old[cid]) for cid in sorted(old.keys() - new.keys()))
    changed = tuple((cid, old[cid], new[cid]) for cid in sorted(old.keys() & new.keys())
                    if old[cid] != new[cid])
    status = "REVIEW_REQUIRED" if (added or removed or changed or not after.verified_in_game) else "NO_RULE_CHANGE"
    return RegulationDelta(before.snapshot_id, after.snapshot_id, before.format_id,
                           before.effective_on, after.effective_on, added, removed,
                           changed, status)
