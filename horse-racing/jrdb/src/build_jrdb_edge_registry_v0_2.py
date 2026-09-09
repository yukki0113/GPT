#!/usr/bin/env python3
"""Build Edge Registry v0.2 with v0.2 field and HUMAN residual support."""
from __future__ import annotations

import jrdb_edge_temporal_validator as temporal
from jrdb_edge_human_residual_v0_2 import BASELINE_MODE as HUMAN_BASELINE_MODE, human_metrics

VERSION = "0.2.1"
V02_FIELDS = {
    "frame_no","horse_age","rotation_interval","pre_idm","training_score",
    "stable_score","uptrend_code","training_arrow_code","stable_evaluation_code",
    "body_weight_pre_kg","body_weight_change_pre_kg","track_condition_bucket",
}
temporal.ALLOWED_FIELDS.update(V02_FIELDS)
_ORIG_METRICS = temporal._metrics


def _metrics_v02(connection, values, baseline_values, baseline_mode, *, start_date=None, end_date=None):
    if baseline_mode == HUMAN_BASELINE_MODE:
        return human_metrics(connection, values, start_date=start_date, end_date=end_date)
    return _ORIG_METRICS(
        connection, values, baseline_values, baseline_mode,
        start_date=start_date, end_date=end_date,
    )


temporal._metrics = _metrics_v02

import build_jrdb_edge_registry as base  # noqa: E402


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
