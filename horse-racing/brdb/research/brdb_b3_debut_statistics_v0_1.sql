-- Input: B2 exact cohort CTE (materialized as cohort), verified lineage_master.
-- Cohorts, dimensions and lanes overlap. Never sum across them.
-- Ordered pair keys: key1=sire, key2=BMS. Single key2 is empty, not a parent ID.
WITH facts AS (
 SELECT c.*, substr(race_date,6,2) AS month,
   CASE WHEN abnormal_code IN ('0','5') AND finish=1 THEN 1 ELSE 0 END AS win,
   CASE WHEN abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END AS top3,
   CASE WHEN start_status='STARTED_NORMAL' THEN 1 ELSE 0 END AS normal,
   CASE WHEN ukc_date<=race_date AND regexp_full_match(dated_sire_line,'[0-9]{4}') AND sl.lineage_code IS NOT NULL THEN dated_sire_line END AS sire_line,
   CASE WHEN ukc_date<=race_date AND regexp_full_match(dated_bms_line,'[0-9]{4}') AND bl.lineage_code IS NOT NULL THEN dated_bms_line END AS bms_line
 FROM cohort c LEFT JOIN lineage_master sl ON sl.lineage_code=c.dated_sire_line
 LEFT JOIN lineage_master bl ON bl.lineage_code=c.dated_bms_line
), scopes AS (
 SELECT cohort,horse_id,race_key,horse_no,race_date,win,top3,normal,sire_id,bms_id,sire_line,bms_line,scope,dimension
 FROM facts CROSS JOIN LATERAL (VALUES
 ('ALL','ALL'),('SURFACE',track_type),('SURFACE_DISTANCE',track_type||':'||CAST(distance AS VARCHAR)),
 ('SURFACE_MONTH',track_type||':'||month),('SURFACE_AGE',track_type||':'||CAST(age AS VARCHAR))) x(scope,dimension)
 WHERE dimension IS NOT NULL
), lanes AS (
 SELECT s.*,lane,key1,key2, key1 IS NOT NULL AND key2 IS NOT NULL AS eligible
 FROM scopes s CROSS JOIN LATERAL (VALUES
 ('SIRE_ID',sire_id,''),('BMS_ID',bms_id,''),('PARENT_ID_PAIR',sire_id,bms_id),('LINEAGE_CODE_PAIR',sire_line,bms_line)) l(lane,key1,key2)
), baseline AS (
 SELECT cohort,scope,dimension,lane,count(*) baseline_starts,count(DISTINCT horse_id) baseline_horses,
 sum(win) baseline_wins,sum(top3) baseline_top3,count(*) FILTER(WHERE eligible) resolved_starts,
 coalesce(sum(win) FILTER(WHERE eligible),0) resolved_wins,coalesce(sum(top3) FILTER(WHERE eligible),0) resolved_top3
 FROM lanes GROUP BY 1,2,3,4
), grouped AS (
 SELECT cohort,scope,dimension,lane,key1,key2,count(*) starts,count(DISTINCT horse_id) horses,
 count(DISTINCT race_key) races,sum(win) wins,sum(top3) top3,sum(normal) normal_finishers,max(race_date) max_history_date
 FROM lanes WHERE eligible GROUP BY 1,2,3,4,5,6
), left_marginal AS (
 SELECT cohort,scope,dimension,lane,key1,sum(starts) n,sum(wins) wins,sum(top3) top3 FROM grouped
 WHERE lane IN ('PARENT_ID_PAIR','LINEAGE_CODE_PAIR') GROUP BY 1,2,3,4,5
), right_marginal AS (
 SELECT cohort,scope,dimension,lane,key2,sum(starts) n,sum(wins) wins,sum(top3) top3 FROM grouped
 WHERE lane IN ('PARENT_ID_PAIR','LINEAGE_CODE_PAIR') GROUP BY 1,2,3,4,5
)
SELECT b.*,g.key1,g.key2,coalesce(g.starts,0) starts,coalesce(g.horses,0) horses,coalesce(g.races,0) races,
 coalesce(g.wins,0) wins,coalesce(g.top3,0) top3,coalesce(g.normal_finishers,0) normal_finishers,g.max_history_date,
 g.wins::DOUBLE/nullif(g.starts,0) win_rate,g.top3::DOUBLE/nullif(g.starts,0) top3_rate,
 b.baseline_top3::DOUBLE/b.baseline_starts baseline_top3_rate,b.resolved_top3::DOUBLE/nullif(b.resolved_starts,0) resolved_baseline_top3_rate,
 lm.n left_marginal_starts,lm.wins left_marginal_wins,lm.top3 left_marginal_top3,
 rm.n right_marginal_starts,rm.wins right_marginal_wins,rm.top3 right_marginal_top3,
 lm.top3::DOUBLE/nullif(lm.n,0) left_marginal_top3_rate,rm.top3::DOUBLE/nullif(rm.n,0) right_marginal_top3_rate,
 CASE WHEN g.starts IS NULL THEN 'NO_RESOLVED_GROUP' WHEN g.starts<30 THEN 'LOW_SAMPLE' ELSE 'DESCRIPTIVE' END sample_status,
 CASE WHEN b.lane='LINEAGE_CODE_PAIR' THEN 'DATED_UKC_CLASSIFICATION_NOT_INDIVIDUAL_ID' ELSE 'STATIC_RELATION_AS_OF_UNVERIFIED' END identity_scope,
 'USER_ACCEPTED_PROVIDER_EQUIVALENCE' source_equivalence_policy,false prediction_safe,false production_authorized
FROM baseline b LEFT JOIN grouped g USING(cohort,scope,dimension,lane)
LEFT JOIN left_marginal lm ON (g.cohort,g.scope,g.dimension,g.lane,g.key1)=(lm.cohort,lm.scope,lm.dimension,lm.lane,lm.key1)
LEFT JOIN right_marginal rm ON (g.cohort,g.scope,g.dimension,g.lane,g.key2)=(rm.cohort,rm.scope,rm.dimension,rm.lane,rm.key2)
ORDER BY cohort,scope,dimension,lane,key1,key2
