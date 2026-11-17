"""BRDB integrated review v0.3 candidate adapter.

Attaches the accepted D4 research sidecar to an existing v0.2 candidate payload
without modifying any v0.2 evidence, factors, summary, confidence or prediction
boundary. Research-only; no production promotion.
"""
from __future__ import annotations
import copy

V02 = "brdb-integrated-blood-review-v0.2-candidate"
V03 = "brdb-integrated-blood-review-v0.3-candidate"
D4 = "brdb-d4-supplemental-research-v0.1"


class IntegratedV03Error(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise IntegratedV03Error(message)


def _race_equal(base: dict, sidecar: dict) -> bool:
    return (
        base.get("target_date") == sidecar.get("target_date")
        and base.get("venue_code") == sidecar.get("venue_code")
        and base.get("surface_code") == sidecar.get("track_type")
        and base.get("distance_m") == sidecar.get("distance")
        and base.get("field_size") == sidecar.get("field_size")
    )


def merge(base_v02: dict, d4_sidecar: dict) -> dict:
    """Return a v0.3 candidate while preserving v0.2 semantics byte-for-value."""
    require(base_v02.get("contract_version") == V02, "base contract must be v0.2 candidate")
    require(base_v02.get("release_status") == "RESEARCH_CANDIDATE", "base release status drift")
    require("supplemental_research" not in base_v02, "base already contains supplemental research")
    require(d4_sidecar.get("schema_version") == D4, "unsupported D4 sidecar version")
    require(d4_sidecar.get("release_status") == "RESEARCH_SIDECAR_ONLY", "D4 release status drift")
    require(d4_sidecar.get("research_only") is True, "D4 must remain research only")
    require(d4_sidecar.get("prediction_safe") is False, "D4 prediction-safe promotion forbidden")
    require(d4_sidecar.get("historical_asof_status") == "AS_OF_UNVERIFIED", "D4 as-of promotion forbidden")
    require(d4_sidecar.get("no_forecast_or_score") is True, "D4 forecast/score boundary missing")
    require(_race_equal(base_v02.get("race", {}), d4_sidecar.get("race", {})), "race context mismatch")

    base_horses = base_v02.get("horses")
    d4_horses = d4_sidecar.get("horses")
    require(isinstance(base_horses, list) and isinstance(d4_horses, list), "horse arrays required")
    require(len(base_horses) == base_v02["race"]["field_size"], "base field size mismatch")
    require(len(d4_horses) == d4_sidecar["race"]["field_size"], "D4 field size mismatch")

    base_keys = [(h.get("horse_id"), h.get("horse_no")) for h in base_horses]
    d4_keys = [(h.get("horse_id"), h.get("horse_no")) for h in d4_horses]
    require(len(set(base_keys)) == len(base_keys), "duplicate base identity")
    require(len(set(d4_keys)) == len(d4_keys), "duplicate D4 identity")
    require(base_keys == sorted(base_keys, key=lambda x: x[1]), "base horses not horse-number ordered")
    require(d4_keys == sorted(d4_keys, key=lambda x: x[1]), "D4 horses not horse-number ordered")
    require(base_keys == d4_keys, "base and D4 full-field identity mismatch")

    require(d4_sidecar.get("aggregate_coverage", {}).get("field_size") == len(d4_horses),
            "D4 aggregate field size mismatch")
    require(d4_sidecar.get("aggregate_coverage", {}).get("reviewed_horses") == len(d4_horses),
            "D4 reviewed horse count mismatch")

    out = copy.deepcopy(base_v02)
    out["contract_version"] = V03
    out["supplemental_research"] = {
        "sidecar_schema_version": d4_sidecar["schema_version"],
        "base_review_contract": d4_sidecar["base_review_contract"],
        "integrated_review_contract": d4_sidecar["integrated_review_contract"],
        "release_status": d4_sidecar["release_status"],
        "research_only": d4_sidecar["research_only"],
        "prediction_safe": d4_sidecar["prediction_safe"],
        "historical_asof_status": d4_sidecar["historical_asof_status"],
        "no_forecast_or_score": d4_sidecar["no_forecast_or_score"],
        "source_time_guard": d4_sidecar["source_time_guard"],
        "source_generations": copy.deepcopy(d4_sidecar["source_generations"]),
        "provenance": copy.deepcopy(d4_sidecar["provenance"]),
        "aggregate_coverage": copy.deepcopy(d4_sidecar["aggregate_coverage"]),
    }

    for base_horse, d4_horse in zip(out["horses"], d4_horses):
        require("supplemental_status" not in base_horse and "supplemental_insights" not in base_horse,
                "base horse already contains supplemental fields")
        require(d4_horse.get("availability") == "AS_OF_UNVERIFIED", "D4 horse availability promoted")
        require(d4_horse.get("factors") == {"positive": [], "negative": [], "unknown": []},
                "D4 factors must remain empty")
        require(d4_horse.get("summary") is None, "D4 summary must remain null")
        require(d4_horse.get("confidence") == "UNASSESSED", "D4 confidence must remain unassessed")
        insights = d4_horse.get("supplemental_insights")
        require(isinstance(insights, list), "D4 supplemental insights must be an array")
        for item in insights:
            require(item.get("interpretation_status") == "OBSERVATION_ONLY_AS_OF_UNVERIFIED",
                    "supplemental interpretation promoted")
            require(item.get("contribution_to_score") is None, "supplemental score contribution forbidden")
        base_horse["supplemental_status"] = d4_horse["availability"]
        base_horse["supplemental_insights"] = copy.deepcopy(insights)

    return out
