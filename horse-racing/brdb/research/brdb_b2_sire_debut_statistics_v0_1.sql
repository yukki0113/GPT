-- Descriptive historical snapshot. Input: B1 joined rows, singleton cutoff(as_of_date).
-- Same 2017-2025 calendar window for both cohorts; no date >= cutoff.
-- Do not sum cohorts or scopes. Unresolved parent ID is excluded from sire groups,
-- not from the all-cohort comparison denominator. No inferred ID/name grouping.
WITH cohort AS (
    SELECT 'A1_RACE_ACTUAL_STARTERS' AS cohort, j.* FROM joined j, cutoff c
    WHERE j.year BETWEEN 2017 AND 2025 AND j.race_date<c.as_of_date
      AND j.race_condition_code='A1' AND j.start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL')
    UNION ALL
    SELECT 'FIRST_OBSERVED_JRA_START_CANDIDATE', j.* FROM joined j, cutoff c
    WHERE j.year BETWEEN 2017 AND 2025 AND j.race_date<c.as_of_date
      AND j.eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE'
), facts AS (
    SELECT cohort,horse_id,race_key,race_date,sire_id,track_type,distance,age,substr(race_date,6,2) AS month,
           CASE WHEN abnormal_code IN ('0','5') AND finish=1 THEN 1 ELSE 0 END AS win,
           CASE WHEN abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END AS top3,
           CASE WHEN start_status='STARTED_NORMAL' THEN 1 ELSE 0 END AS normal
    FROM cohort
), scopes AS (
    SELECT cohort,horse_id,race_key,race_date,sire_id,win,top3,normal,scope,dimension
    FROM facts
    CROSS JOIN LATERAL (VALUES
       ('ALL','ALL'),('SURFACE',track_type),
       ('SURFACE_DISTANCE',track_type||':'||CAST(distance AS VARCHAR)),
       ('SURFACE_MONTH',track_type||':'||month),
       ('SURFACE_AGE',track_type||':'||CAST(age AS VARCHAR))
    ) AS x(scope,dimension)
    WHERE dimension IS NOT NULL
), baseline AS (
    SELECT cohort,scope,dimension,count(*) AS baseline_starts,count(DISTINCT horse_id) AS baseline_horses,
           sum(win) AS baseline_wins,sum(top3) AS baseline_top3,
           count(*) FILTER(WHERE sire_id IS NOT NULL) AS resolved_starts,
           sum(win) FILTER(WHERE sire_id IS NOT NULL) AS resolved_wins,
           sum(top3) FILTER(WHERE sire_id IS NOT NULL) AS resolved_top3
    FROM scopes GROUP BY 1,2,3
), grouped AS (
    SELECT cohort,scope,dimension,sire_id,count(*) AS starts,count(DISTINCT horse_id) AS horses,
           count(DISTINCT race_key) AS races,sum(win) AS wins,sum(top3) AS top3,sum(normal) AS normal_finishers,
           max(race_date) AS max_history_date
    FROM scopes WHERE sire_id IS NOT NULL GROUP BY 1,2,3,4
)
SELECT g.*,b.baseline_starts,b.baseline_horses,b.baseline_wins,b.baseline_top3,b.resolved_starts,
       b.resolved_wins,b.resolved_top3,
       wins::DOUBLE/starts AS win_rate,top3::DOUBLE/starts AS top3_rate,
       baseline_top3::DOUBLE/baseline_starts AS baseline_top3_rate,
       resolved_top3::DOUBLE/resolved_starts AS resolved_baseline_top3_rate,
       CASE WHEN starts<30 THEN 'LOW_SAMPLE' ELSE 'DESCRIPTIVE' END AS sample_status,
       'STATIC_RELATION_AS_OF_UNVERIFIED' AS parent_temporal_status,false AS prediction_safe,false AS production_authorized
FROM grouped g JOIN baseline b USING(cohort,scope,dimension)
ORDER BY cohort,scope,dimension,sire_id
