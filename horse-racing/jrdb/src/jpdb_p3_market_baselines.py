#!/usr/bin/env python3
"""JPDB P3 retrospective market-adjustment research core.

Requires a caller-created, SHA-verified p3_all DuckDB view from accepted SED
2023-2025 and 2026 P1.2 daily ZIPs. Do not treat archived FINAL odds as
attested pre-race features. Outputs are descriptive, never rider ability.
"""
from __future__ import annotations

SCHEMA = "jpdb-p3-market-research-v0.1"
WINNER = "abnormal_code IN ('0','') AND finish=1 AND field_size>=1"
NORMAL = "abnormal_code IN ('0','') AND finish BETWEEN 1 AND field_size AND field_size>=1"
BUCKET = """CASE WHEN final_popularity=1 THEN '01'
 WHEN final_popularity<=3 THEN '02_03'
 WHEN final_popularity<=6 THEN '04_06'
 WHEN final_popularity<=10 THEN '07_10' ELSE '11_PLUS' END"""


def prepare(db, target_date: str) -> None:
    """Build research tables with D-exclusive race and previous-year training.

    Required p3_all:
      race_date, race_key_raw, horse_no, jockey_code, surface_code,
      abnormal_code, finish, field_size, final_win_odds,
      final_popularity, venue_code.

    A whole race is rejected for missing market observations, unknown results,
    demotion, bad finish ordinals, or a nonunique recorded winner.
    """
    db.execute("""CREATE TEMP TABLE p3_source AS SELECT *,
      CASE WHEN abnormal_code IN ('0','','3') THEN 1 ELSE 0 END AS is_starter,
      CASE WHEN """ + WINNER + """ THEN 1 ELSE 0 END AS win,
      CASE WHEN abnormal_code IN ('0','') AND finish BETWEEN 1 AND 3
             AND field_size>=1 THEN 1 ELSE 0 END AS top3,
      CASE WHEN abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3')
             OR (abnormal_code IN ('0','') AND
                (finish IS NULL OR field_size IS NULL OR field_size<1
                 OR finish NOT BETWEEN 1 AND field_size))
             THEN 1 ELSE 0 END AS bad_status
      FROM p3_all
      WHERE surface_code IN ('1','2') AND race_date < ?""", [target_date])

    db.execute("""CREATE TEMP TABLE p3_race AS
      SELECT race_key_raw, MIN(race_date) AS race_date, COUNT(*) AS entries,
        SUM(is_starter) AS starts, SUM(win) AS winners,
        SUM(bad_status) AS bad_statuses,
        SUM(CASE WHEN is_starter=1 AND
           (final_win_odds IS NULL OR NOT isfinite(final_win_odds)
            OR final_win_odds<1 OR final_popularity IS NULL
            OR final_popularity<1 OR final_popularity>field_size)
            THEN 1 ELSE 0 END) AS bad_market,
        SUM(CASE WHEN is_starter=1 THEN 1.0/NULLIF(final_win_odds,0)
                 ELSE 0 END) AS sum_inverse_odds,
        COUNT(DISTINCT race_date) AS distinct_dates
      FROM p3_source GROUP BY race_key_raw""")

    db.execute("""CREATE TEMP TABLE p3_eligible AS
      SELECT s.race_date,s.race_key_raw,s.jockey_code,s.surface_code,
        s.venue_code,s.final_popularity,s.final_win_odds,s.win,s.top3,
        1.0/s.final_win_odds/r.sum_inverse_odds AS market_p,
        SUBSTR(s.race_date,1,4) AS event_year,
        """ + BUCKET + """ AS popularity_bucket
      FROM p3_source s JOIN p3_race r USING (race_key_raw)
      WHERE s.is_starter=1 AND r.starts>=2 AND r.winners=1
        AND r.bad_statuses=0 AND r.bad_market=0
        AND r.distinct_dates=1 AND r.sum_inverse_odds>0""")

    db.execute("""CREATE TEMP TABLE p3_pop_training AS
      SELECT event_year,surface_code,popularity_bucket,jockey_code,
        COUNT(*) AS n,SUM(win) AS wins,SUM(top3) AS top3
      FROM p3_eligible GROUP BY 1,2,3,4""")

    # For target year Y, references use year < Y, never Y or later.
    # Leave the evaluated jockey's own previous-year observations out.
    db.execute("""CREATE TEMP TABLE p3_oot AS
      SELECT e.*, tr.n_train,tr.wins_train,
        (tr.wins_train-own.wins_own) /
          NULLIF((tr.n_train-own.n_own),0) AS p_prior_loo,
        (tr.top3_train-own.top3_own) /
          NULLIF((tr.n_train-own.n_own),0) AS p_prior_top3_loo,
        (tr.n_train-own.n_own) AS n_prior_peer
      FROM p3_eligible e
      LEFT JOIN LATERAL (
        SELECT SUM(t.n)::DOUBLE AS n_train,
          SUM(t.wins)::DOUBLE AS wins_train,
          SUM(t.top3)::DOUBLE AS top3_train
        FROM p3_pop_training t
        WHERE t.event_year<e.event_year
          AND t.surface_code=e.surface_code
          AND t.popularity_bucket=e.popularity_bucket
      ) tr ON TRUE
      LEFT JOIN LATERAL (
        SELECT COALESCE(SUM(t.n),0)::DOUBLE AS n_own,
          COALESCE(SUM(t.wins),0)::DOUBLE AS wins_own,
          COALESCE(SUM(t.top3),0)::DOUBLE AS top3_own
        FROM p3_pop_training t
        WHERE t.event_year<e.event_year
          AND t.surface_code=e.surface_code
          AND t.popularity_bucket=e.popularity_bucket
          AND t.jockey_code=e.jockey_code
      ) own ON TRUE""")

    db.execute("""CREATE TEMP TABLE p3_eval AS
      SELECT *,
        CASE WHEN n_prior_peer>=100 AND p_prior_loo BETWEEN 0 AND 1
          THEN p_prior_loo ELSE NULL END AS empirical_prior_p,
        CASE WHEN n_prior_peer>=100 AND p_prior_top3_loo BETWEEN 0 AND 1
          THEN p_prior_top3_loo ELSE NULL END AS empirical_prior_top3_p
      FROM p3_oot""")


def validate(db, target_date: str, expected_total: int = 184922) -> dict:
    """Independent high-level invariants; must be run after prepare()."""
    total = db.execute("SELECT COUNT(*) FROM p3_all").fetchone()[0]
    if total != expected_total:
        raise ValueError(f"changed immutable SED population: {total}")
    n, races, wins, expected, leak = db.execute("""
      SELECT COUNT(*),COUNT(DISTINCT race_key_raw),
        SUM(win),SUM(market_p),
        COUNT(*) FILTER (WHERE race_date>=?)
      FROM p3_eval""", [target_date]).fetchone()
    if leak or wins != races or abs(expected-races)>1e-5:
        raise ValueError("P3 target leakage or market probability conservation failed")
    if db.execute("""SELECT COUNT(*) FROM p3_eval
        WHERE event_year='2023' AND empirical_prior_p IS NOT NULL""").fetchone()[0]:
        raise ValueError("2023 has no earlier-year model training")
    return {
        "status": "RESEARCH_DIAGNOSTIC_PASS",
        "research_only": True,
        "prediction_safe": False,
        "strict_asof_certified": False,
        "target_date_exclusive": target_date,
        "source_rows": total,
        "market_eligible_rows": n,
        "market_eligible_races": races,
        "observed_wins": wins,
        "market_expected_wins": float(expected),
    }
