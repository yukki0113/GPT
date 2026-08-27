#!/usr/bin/env python3
"""Legacy RaceNote history-enrichment PoC compatibility wrapper.

The validated enrichment implementation now lives in
``racenote_history_engine.py`` and is shared with the production v1.0
entrypoint. This file is retained so historical 8-run / 10-run comparison
commands continue to work without duplicating enrichment logic.
"""
from __future__ import annotations

import racenote_history_engine as engine

DISTANCE_RANGE_DEFINITIONS = engine.DISTANCE_RANGE_DEFINITIONS
enrich = engine.enrich
metrics = engine.metrics


def main() -> None:
    """Run the legacy PoC comparison CLI through the shared engine."""
    engine.main()


if __name__ == "__main__":
    main()
