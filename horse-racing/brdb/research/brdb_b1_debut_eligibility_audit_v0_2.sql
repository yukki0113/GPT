-- BRDB B1 research-only; aggregate audit, not a training cohort or a predictor.
-- Input: verified Analysis v1.4 2016-2025. Canonical data_storage.query view data.
-- SED official code interpretation per BRDB_P0_2_SED_ABNORMAL_STATUS_REVIEW_20261103.md.
-- Prior references resolve by exact horse_id, prior date and race_key, never by name.
WITH base AS (
    SELECT *, CAST(race_date AS DATE) AS d,
      NULLIF(TRIM(prev_result_key_1),'') AS pr,
      NULLIF(TRIM(prev_race_key_1),'') AS pk,
      CASE WHEN abnormal_code IN ('1','2') THEN 'NON_STARTER'
           WHEN abnormal_code='0' AND finish BETWEEN 1 AND 18 THEN 'STARTED_NORMAL'
           WHEN abnormal_code IN ('3','4','5','6') THEN 'STARTED_ABNORMAL'
           ELSE 'UNKNOWN' END AS start_status
    FROM data WHERE race_date >= '2016-01-01' AND race_date < '2026-01-01'
), linked AS (
    SELECT b.*, CASE
      WHEN b.pr IS NULL AND b.pk IS NULL THEN 'NO_PRIOR_KEYS'
      WHEN b.pr IS NULL OR b.pk IS NULL THEN 'INCOMPLETE_KEYS'
      WHEN NOT regexp_full_match(b.pr,'[0-9]{16}') OR substr(b.pr,1,8)<>b.horse_id
           OR try_strptime(substr(b.pr,9,8),'%Y%m%d') IS NULL THEN 'INVALID_RESULT_KEY'
      WHEN try_strptime(substr(b.pr,9,8),'%Y%m%d')::DATE>=b.d THEN 'NONPRIOR_DATE'
      WHEN try_strptime(substr(b.pr,9,8),'%Y%m%d')::DATE<DATE '2016-01-01' THEN 'BEFORE_WINDOW'
      WHEN p.horse_id IS NULL THEN 'UNRESOLVED_IN_WINDOW'
      WHEN p.start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL') THEN 'LINKED_STARTER'
      WHEN p.start_status='NON_STARTER' THEN 'LINKED_NONSTARTER'
      ELSE 'LINKED_UNKNOWN' END AS prior_link
    FROM base b LEFT JOIN base p ON p.horse_id=b.horse_id AND p.race_key=b.pk
      AND p.d=try_strptime(substr(b.pr,9,8),'%Y%m%d')::DATE AND p.d<b.d
), hist AS (
    SELECT *, COUNT(*) FILTER(WHERE start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL')) OVER past AS earlier_starts,
      COUNT(*) FILTER(WHERE start_status='UNKNOWN') OVER past AS earlier_unknown,
      COUNT(*) FILTER(WHERE prior_link NOT IN ('NO_PRIOR_KEYS','LINKED_NONSTARTER')) OVER past AS earlier_prior_uncertainty
    FROM linked WINDOW past AS (PARTITION BY horse_id ORDER BY d GROUPS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
), classified AS (
    SELECT *, CASE
      WHEN start_status='NON_STARTER' THEN 'NON_STARTER'
      WHEN start_status='UNKNOWN' THEN 'UNKNOWN_START_STATUS'
      WHEN earlier_starts>0 OR prior_link='LINKED_STARTER' THEN 'KNOWN_PRIOR_JRA_START'
      WHEN earlier_unknown>0 OR earlier_prior_uncertainty>0 OR prior_link NOT IN ('NO_PRIOR_KEYS','LINKED_NONSTARTER') THEN 'PRIOR_HISTORY_UNRESOLVED'
      WHEN age IS NULL OR age NOT IN (2,3) THEN 'AGE_OR_HISTORY_UNCERTAIN'
      WHEN year=2016 THEN 'LEFT_EDGE_2016'
      ELSE 'FIRST_OBSERVED_JRA_START_CANDIDATE'
    END AS eligibility
    FROM hist
), metrics AS (
    SELECT 'all_start_status' AS section, start_status AS metric, count(*) AS n FROM classified GROUP BY 2
    UNION ALL SELECT 'all_eligibility', eligibility, count(*) FROM classified GROUP BY 2
    UNION ALL SELECT 'A1_start_status',start_status,count(*) FROM classified WHERE race_condition_code='A1' GROUP BY 2
    UNION ALL SELECT 'A1_eligibility',eligibility,count(*) FROM classified WHERE race_condition_code='A1' GROUP BY 2
    UNION ALL SELECT 'A1_prior_link',prior_link,count(*) FROM classified WHERE race_condition_code='A1' GROUP BY 2
    UNION ALL SELECT 'A1_class_race_count','distinct_races',count(DISTINCT race_key) FROM classified WHERE race_condition_code='A1'
    UNION ALL SELECT 'A1_label_names','nonmatching_race_name',count(*) FROM classified WHERE race_condition_code='A1' AND (race_name IS NULL OR NOT contains(race_name,'新馬'))
    UNION ALL SELECT 'first_candidate_class',coalesce(nullif(trim(race_condition_code),''),'MISSING'),count(*) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' GROUP BY 2
    UNION ALL SELECT 'candidate_by_year',cast(year AS VARCHAR),count(*) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' GROUP BY 2
    UNION ALL SELECT 'A1_candidate_by_year',cast(year AS VARCHAR),count(*) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' AND race_condition_code='A1' GROUP BY 2
    UNION ALL SELECT 'A1_candidate', 'unique_horses',count(DISTINCT horse_id) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' AND race_condition_code='A1'
    UNION ALL SELECT 'A1_candidate','missing_condition',count(*) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' AND race_condition_code='A1' AND (track_type IS NULL OR nullif(trim(track_type),'') IS NULL OR distance IS NULL OR distance<=0 OR venue_code IS NULL)
    UNION ALL SELECT 'A1_candidate','missing_blood_fields',count(*) FROM classified WHERE eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' AND race_condition_code='A1' AND (nullif(trim(sire_name),'') IS NULL OR nullif(trim(broodmare_sire_name),'') IS NULL OR nullif(trim(sire_line_code),'') IS NULL OR nullif(trim(broodmare_sire_line_code),'') IS NULL)
    UNION ALL SELECT 'integrity','input_rows',count(*) FROM base
    UNION ALL SELECT 'integrity','classified_rows',count(*) FROM classified
    UNION ALL SELECT 'integrity','invalid_horse_id',count(*) FROM classified WHERE NOT coalesce(regexp_full_match(horse_id,'[0-9]{8}'),false)
    UNION ALL SELECT 'integrity','duplicate_key',count(*)-count(DISTINCT (race_key,horse_no)) FROM classified
    UNION ALL SELECT 'integrity','same_day_multiple',count(*) FROM (SELECT horse_id,d FROM classified GROUP BY 1,2 HAVING count(*)>1)
)
SELECT section,metric,n FROM metrics ORDER BY 1,2;
