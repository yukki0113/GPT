#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deprecated RaceNote finalizer.

This command previously generated forecast prose and decision traces from fixed
horse numbers. That mixed mechanical packaging with forecast reasoning and is
intentionally disabled.

Use racenote_freeze_prepared_forecast.py with model-authored, race-by-race
prepared records instead.
"""
from __future__ import annotations
import argparse

def main() -> int:
    ap=argparse.ArgumentParser(
        description="DEPRECATED: fixed-picks prose generation is disabled."
    )
    ap.add_argument("--prep-root")
    ap.add_argument("--output-root")
    ap.add_argument("--selection-id")
    ap.add_argument("--date")
    ap.add_argument("--turn-id")
    ap.add_argument("--picks-json")
    ap.add_argument("--main-sha")
    ap.parse_args()
    raise SystemExit(
        "racenote_finalize_fixed_picks.py is disabled: forecast marks, prose, "
        "and decision traces must be authored in the reasoning layer. "
        "Use racenote_freeze_prepared_forecast.py for deterministic validation "
        "and archival only."
    )

if __name__=="__main__":
    main()
