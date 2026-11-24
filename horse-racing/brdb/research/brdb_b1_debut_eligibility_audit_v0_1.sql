-- BRDB B1, research-only data eligibility preflight (2016-2025).
-- Input: manifest-verified JRDB Analysis v1.4 fact_entry_result_lite, view data.
-- A1 = 新馬; A2 = 未出走 (existing JRDB class labels, NOT individual history).
-- first observed entry and first normal finish are proxies, not certified first starts.
-- A previous key is evidence of a prior record, not automatically a completed start.
WITH historical AS (
    SELECT *,
           nullif(trim(prev_result_key_1), '') AS prev_result,
           nullif(trim(prev_race_key_1), '') AS prev_race,
           coalesce(regexp_full_match(horse_id, '[0-9]{8}'), false) AS valid_id,
           coalesce(abnormal_code = '0' AND finish BETWEEN 1 AND 18, false) AS normal_finish
    FROM data
    WHERE race_date >= '2016-01-01' AND race_date < '2026-01-01'
), history AS (
    SELECT *, row_number() OVER (PARTITION BY horse_id ORDER BY race_date, race_key, horse_no) AS entry_order,
           count(*) FILTER (WHERE normal_finish) OVER (
               PARTITION BY horse_id ORDER BY race_date GROUPS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS earlier_normal_finishes,
           try_strptime(substr(prev_result, 9, 8), '%Y%m%d')::DATE AS prev_date
    FROM historical WHERE valid_id
), first_entries AS (
    SELECT * FROM history WHERE entry_order = 1
), first_normal AS (
    SELECT * FROM history WHERE normal_finish AND coalesce(earlier_normal_finishes, 0) = 0
), debut AS (
    SELECT * FROM history WHERE race_condition_code = 'A1'
), metrics AS (
    SELECT 'historical' AS section, 'rows' AS metric, count(*) AS n FROM historical
    UNION ALL SELECT 'historical', 'races', count(DISTINCT race_key) FROM historical
    UNION ALL SELECT 'historical', 'horses', count(DISTINCT horse_id) FROM historical
    UNION ALL SELECT 'historical', 'invalid_horse_id', count(*) FROM historical WHERE NOT valid_id
    UNION ALL SELECT 'historical', 'duplicate_race_horse_key', count(*) - count(DISTINCT (race_key, horse_no)) FROM historical
    UNION ALL SELECT 'historical', 'missing_class', count(*) FROM historical WHERE nullif(trim(race_condition_code), '') IS NULL
    UNION ALL SELECT 'historical', 'missing_age', count(*) FROM historical WHERE age IS NULL
    UNION ALL SELECT 'historical', 'same_day_multiple_horse_groups', count(*) FROM (SELECT horse_id, race_date FROM history GROUP BY 1,2 HAVING count(*) > 1)
    UNION ALL SELECT 'historical', 'missing_sire', count(*) FROM historical WHERE nullif(trim(sire_name), '') IS NULL
    UNION ALL SELECT 'historical', 'missing_bms', count(*) FROM historical WHERE nullif(trim(broodmare_sire_name), '') IS NULL
    UNION ALL SELECT 'historical', 'missing_sire_line', count(*) FROM historical WHERE nullif(trim(sire_line_code), '') IS NULL
    UNION ALL SELECT 'historical', 'missing_bms_line', count(*) FROM historical WHERE nullif(trim(broodmare_sire_line_code), '') IS NULL
    UNION ALL SELECT 'A1', 'entries', count(*) FROM historical WHERE race_condition_code = 'A1'
    UNION ALL SELECT 'A1', 'races', count(DISTINCT race_key) FROM historical WHERE race_condition_code = 'A1'
    UNION ALL SELECT 'A1', 'horses', count(DISTINCT horse_id) FROM debut
    UNION ALL SELECT 'A1', 'normal_finish', count(*) FROM debut WHERE normal_finish
    UNION ALL SELECT 'A1', 'prior_result_key_present', count(*) FROM debut WHERE prev_result IS NOT NULL
    UNION ALL SELECT 'A1', 'prior_race_key_present', count(*) FROM debut WHERE prev_race IS NOT NULL
    UNION ALL SELECT 'A1', 'earlier_observed_entry', count(*) FROM debut WHERE entry_order > 1
    UNION ALL SELECT 'A1', 'earlier_observed_normal_finish', count(*) FROM debut WHERE earlier_normal_finishes > 0
    UNION ALL SELECT 'A1', 'first_observed_entry_no_prior_keys', count(*) FROM debut WHERE entry_order = 1 AND prev_result IS NULL AND prev_race IS NULL
    UNION ALL SELECT 'A1', 'age_2', count(*) FROM debut WHERE age = 2
    UNION ALL SELECT 'A1', 'age_3', count(*) FROM debut WHERE age = 3
    UNION ALL SELECT 'A1', 'missing_parent_or_line', count(*) FROM debut WHERE nullif(trim(sire_name), '') IS NULL OR nullif(trim(broodmare_sire_name), '') IS NULL OR nullif(trim(sire_line_code), '') IS NULL OR nullif(trim(broodmare_sire_line_code), '') IS NULL
    UNION ALL SELECT 'A2', 'entries', count(*) FROM historical WHERE race_condition_code = 'A2'
    UNION ALL SELECT 'first_observed', 'entries', count(*) FROM first_entries
    UNION ALL SELECT 'first_observed', 'prior_result_key_present', count(*) FROM first_entries WHERE prev_result IS NOT NULL
    UNION ALL SELECT 'first_observed', 'prior_date_before_window', count(*) FROM first_entries WHERE prev_date < DATE '2016-01-01'
    UNION ALL SELECT 'first_observed', 'prior_date_within_window', count(*) FROM first_entries WHERE prev_date >= DATE '2016-01-01' AND prev_date < cast(race_date AS DATE)
    UNION ALL SELECT 'first_observed', 'prior_date_nonprior', count(*) FROM first_entries WHERE prev_date >= cast(race_date AS DATE)
    UNION ALL SELECT 'first_observed', 'prior_date_invalid', count(*) FROM first_entries WHERE prev_result IS NOT NULL AND prev_date IS NULL
    UNION ALL SELECT 'first_observed', 'prior_id_mismatch', count(*) FROM first_entries WHERE prev_result IS NOT NULL AND substr(prev_result, 1, 8) <> horse_id
    UNION ALL SELECT 'first_observed', 'no_prior_keys_in_left_edge_year', count(*) FROM first_entries WHERE year = 2016 AND prev_result IS NULL AND prev_race IS NULL
    UNION ALL SELECT 'first_observed_no_prior_keys_by_class', coalesce(race_condition_code, 'MISSING'), count(*) FROM first_entries WHERE prev_result IS NULL AND prev_race IS NULL GROUP BY race_condition_code
    UNION ALL SELECT 'first_normal_finish_by_class', coalesce(race_condition_code, 'MISSING'), count(*) FROM first_normal GROUP BY race_condition_code
    UNION ALL SELECT 'A1_abnormal_code', coalesce(abnormal_code, 'MISSING'), count(*) FROM debut GROUP BY abnormal_code
)
SELECT section, metric, n FROM metrics ORDER BY section, metric;
