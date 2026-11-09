"""Synthetic-only P1-A0 data contract. No real card text or network access."""
from dataclasses import dataclass
from datetime import date

RARITIES = ("N", "R", "SR", "UR")

@dataclass(frozen=True)
class Card:
    canonical_id: str
    konami_id: int
    name: str
    kind: str
    md_rarity: str
    rarity_source: str
    verification: str = "UNVERIFIED_SOURCE"
    craftable: str = "UNKNOWN"
    acquisition: str = "UNKNOWN"
    password_variants: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.canonical_id or self.konami_id <= 0 or not self.name or not self.kind:
            raise ValueError("missing identity")
        if self.md_rarity not in RARITIES or not self.rarity_source.startswith("MD:"):
            raise ValueError("invalid rarity/provenance")
        if self.verification not in ("UNVERIFIED_SOURCE", "GAME_VERIFIED"):
            raise ValueError("invalid verification")
        if self.craftable not in ("YES", "NO", "UNKNOWN"):
            raise ValueError("invalid craftable")
        if self.acquisition not in ("UNKNOWN", "KNOWN_SOURCE"):
            raise ValueError("invalid acquisition")

@dataclass(frozen=True)
class Regulation:
    allowed: int | None
    effective_on: date
    snapshot_id: str
    verified_in_game: bool = False

    def __post_init__(self):
        if self.allowed not in (None, 0, 1, 2, 3) or not self.snapshot_id:
            raise ValueError("invalid regulation")

@dataclass(frozen=True)
class Dataset:
    snapshot_id: str
    source_sha256: str
    cards: tuple[Card, ...]

    def __post_init__(self):
        if not self.snapshot_id or len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise ValueError("invalid snapshot")
        for key in ("canonical_id", "konami_id"):
            values = [getattr(x, key) for x in self.cards]
            if len(values) != len(set(values)):
                raise ValueError("duplicate card identity")

    def select(self, max_rarity="SR", kind=None, verified_only=False):
        if max_rarity not in RARITIES:
            raise ValueError("invalid rarity")
        return tuple(x for x in self.cards if RARITIES.index(x.md_rarity) <= RARITIES.index(max_rarity)
                     and (kind is None or x.kind == kind)
                     and (not verified_only or x.verification == "GAME_VERIFIED"))

def legality_as_of(regulation, day, require_game_verified=True):
    if regulation is None or day < regulation.effective_on:
        return None
    if require_game_verified and not regulation.verified_in_game:
        return None
    return regulation.allowed

def confirmed_new_ur_zero(card, owned_count, wanted):
    if wanted < 0 or (owned_count is not None and owned_count < 0):
        raise ValueError("invalid quantity")
    return card.md_rarity != "UR" or (owned_count is not None and owned_count >= wanted)
