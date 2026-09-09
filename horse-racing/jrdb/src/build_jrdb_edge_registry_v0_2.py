#!/usr/bin/env python3
"""Build Edge Registry v0.2 while preserving the frozen v0.1 validator contract.

The v0.1 registry builder is reused, but v0.2 condition fields are explicitly
registered with the temporal validator in this process only.  This keeps v0.1
files unchanged while allowing v0.2 candidates to be re-queried safely.
"""
from __future__ import annotations

import jrdb_edge_temporal_validator as temporal

VERSION = "0.2.0"
V02_FIELDS = {
    "frame_no",
    "horse_age",
    "rotation_interval",
    "pre_idm",
    "training_score",
    "stable_score",
    "uptrend_code",
    "training_arrow_code",
    "stable_evaluation_code",
    "body_weight_pre_kg",
    "body_weight_change_pre_kg",
    "track_condition_bucket",
}

temporal.ALLOWED_FIELDS.update(V02_FIELDS)

import build_jrdb_edge_registry as base  # noqa: E402


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
