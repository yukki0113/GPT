#!/usr/bin/env python3
"""v0.2 Edge matcher compatibility layer for additional condition fields.

``track_condition_bucket`` is accepted at registry-load time so historical
track-condition Edges can coexist with ordinary Edges.  Current facts do not
populate this field until a pre-race track-condition source is contracted, so
those Edges fail closed in current matching.
"""
from __future__ import annotations

import jrdb_edge_matcher as base

VERSION = "0.2.1"
V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
}
base.CONDITION_FIELDS.update(V02_FIELDS)

load_registry = base.load_registry
edge_matches_runner = base.edge_matches_runner
match_runner = base.match_runner
