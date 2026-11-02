from jrdb_edge_statistical_guard import (
    Cluster,
    apply_fdr,
    benjamini_hochberg,
    cluster_bootstrap_ci,
    finalize_gate,
    two_proportion_pvalue,
    welch_mean_pvalue,
)


def test_bh_monotone_and_original_order():
    q = benjamini_hochberg([0.01, 0.04, 0.03, None])
    assert q[0] <= q[2] <= q[1]
    assert q[3] is None
    assert abs(q[0] - 0.03) < 1e-9


def test_directional_performance_pvalue():
    p = two_proportion_pvalue(40, 100, 20, 100, "POSITIVE")
    assert p is not None and p < 0.01
    wrong = two_proportion_pvalue(40, 100, 20, 100, "NEGATIVE")
    assert wrong is not None and wrong > 0.99


def test_welch_return_pvalue():
    p = welch_mean_pvalue(120, 160, 100, 80, 96, 100, "POSITIVE")
    assert p is not None and p < 0.05


def test_cluster_bootstrap_is_deterministic_and_directional():
    clusters = [Cluster(10, 5, 12, 18, 20, 4, 14, 18) for _ in range(20)]
    first = cluster_bootstrap_ci(clusters, samples=100, seed=123)
    second = cluster_bootstrap_ci(clusters, samples=100, seed=123)
    assert first == second
    assert first["performance_ci_low"] > 0
    assert first["value_ci_low"] > 0


def test_fdr_and_gate_downgrade():
    rows = [
        {
            "candidate_id": "a",
            "hypothesis_family": "T",
            "temporal_status": "ACTIVE",
            "performance_signal": "POSITIVE",
            "value_signal": "NEUTRAL",
            "performance_p_value": 0.001,
            "value_p_value": None,
            "performance_ci_low": 0.02,
            "performance_ci_high": 0.10,
            "value_ci_low": None,
            "value_ci_high": None,
        },
        {
            "candidate_id": "b",
            "hypothesis_family": "T",
            "temporal_status": "ACTIVE",
            "performance_signal": "POSITIVE",
            "value_signal": "NEUTRAL",
            "performance_p_value": 0.8,
            "value_p_value": None,
            "performance_ci_low": -0.02,
            "performance_ci_high": 0.10,
            "value_ci_low": None,
            "value_ci_high": None,
        },
    ]
    apply_fdr(rows)
    assert finalize_gate(rows[0])["statistical_status"] == "ACTIVE"
    assert finalize_gate(rows[1])["statistical_status"] == "WATCH"
