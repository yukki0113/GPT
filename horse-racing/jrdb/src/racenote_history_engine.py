#!/usr/bin/env python3
"""Shared RaceNote history enrichment engine.

This neutral module owns the enrichment logic shared by production RaceNote v1.0
and the legacy PoC comparison CLI. It intentionally preserves the validated
engine behavior from `racenote_history_enrichment_poc.py` so production output
can be regression-checked without semantic changes.
"""

from racenote_history_enrichment_poc import *  # noqa: F401,F403
