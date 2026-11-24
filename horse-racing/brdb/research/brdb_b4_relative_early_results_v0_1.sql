-- First three actual starts, not first three matching-condition starts.
-- B1 defines first-observed candidate; left-edge/unknown never promoted.
CREATE TEMP TABLE starts AS
SELECT horse_id,race_key,race_date,track_type,distance,age,race_condition_code,eligibility,abnormal_code,finish,
 row_number() OVER(PARTITION BY horse_id ORDER BY race_date,race_key) AS start_no,
 CASE WHEN abnormal_code IN ('0','5') AND finish=1 THEN 1 ELSE 0 END AS win,
 CASE WHEN abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END AS top3
FROM classified WHERE start_status IN ('STARTED_NORMAL','STARTED_ABNORMAL');
CREATE TEMP TABLE pair_history AS
WITH first_obs AS (SELECT * FROM starts WHERE start_no=1)
SELECT p.*,f.race_date AS first_observed_date,
 CASE WHEN f.race_date IS NULL THEN 'NO_PRIOR_OBSERVED_START' WHEN f.eligibility<>'FIRST_OBSERVED_JRA_START_CANDIDATE' THEN 'FIRST_START_UNRESOLVED' ELSE 'FIRST_OBSERVED_CANDIDATE' END AS history_status,
 CASE WHEN f.eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' THEN f.race_date END AS first_date,
 CASE WHEN f.eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' THEN f.race_condition_code END AS first_race_class,
 CASE WHEN f.eligibility='FIRST_OBSERVED_JRA_START_CANDIDATE' THEN f.race_key END AS first_race_key
FROM relative_pairs p LEFT JOIN first_obs f ON p.relative_id=f.horse_id AND f.race_date<p.race_date;
CREATE TEMP TABLE relative_stats AS
WITH expanded AS (
 SELECT p.*,t.track_type AS target_surface,t.distance AS target_distance,t.age AS target_age,scope
 FROM pair_history p JOIN targets t USING(race_key,horse_no,horse_id,race_date)
 CROSS JOIN (VALUES ('ALL'),('SURFACE'),('SURFACE_DISTANCE'),('SURFACE_MONTH'),('SURFACE_AGE')) s(scope)
), matched AS (
 SELECT p.*,h.start_no,h.race_date AS history_date,h.race_key AS history_race_key,h.win,h.top3
 FROM expanded p LEFT JOIN starts h ON p.history_status='FIRST_OBSERVED_CANDIDATE' AND p.relative_id=h.horse_id AND h.start_no<=3 AND h.race_date<p.race_date
 AND (p.scope='ALL' OR (h.track_type=p.target_surface AND (p.scope='SURFACE' OR (p.scope='SURFACE_DISTANCE' AND h.distance=p.target_distance)
 OR (p.scope='SURFACE_MONTH' AND substr(h.race_date,6,2)=substr(p.race_date,6,2)) OR (p.scope='SURFACE_AGE' AND h.age=p.target_age))))
)
SELECT race_key,horse_no,horse_id,race_date,relative_id,paths,relationships,path_count,relative_profile_date,relative_birth_date,relative_profile_source,history_status,first_observed_date,first_date,first_race_class,first_race_key,
 scope,target_surface,target_distance,target_age,count(start_no) FILTER(WHERE start_no=1) AS first_starts,
 coalesce(sum(win) FILTER(WHERE start_no=1),0)::BIGINT AS first_wins,coalesce(sum(top3) FILTER(WHERE start_no=1),0)::BIGINT AS first_top3,
 count(start_no) AS early_starts,coalesce(sum(win),0)::BIGINT AS early_wins,coalesce(sum(top3),0)::BIGINT AS early_top3,
 sum(top3)::DOUBLE/nullif(count(start_no),0) AS early_top3_rate,max(history_date) AS max_history_date,
 list(history_race_key ORDER BY start_no) FILTER(WHERE start_no IS NOT NULL) AS early_history_keys,
 CASE WHEN history_status<>'FIRST_OBSERVED_CANDIDATE' THEN history_status WHEN count(start_no)=0 THEN 'NO_SAMPLE' ELSE 'LOW_SAMPLE' END AS sample_status,
 'STATIC_RELATION_AS_OF_UNVERIFIED' AS parent_temporal_status,false AS prediction_safe,false AS production_authorized
FROM matched GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20;
