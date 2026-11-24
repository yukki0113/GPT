-- Historical research only; static relation IDs are not historically certified.
-- Inputs: B1 joined, B2 cohort, dated_ukc, pedigree_master, parent_master.
CREATE TEMP TABLE profiles AS
WITH observations AS (
 SELECT horse_id,data_date_iso AS observed_date,birth_date_iso AS birth_date,
 horse_name,sex_code,sire_name,sire_birth_year,dam_name,dam_birth_year,
 broodmare_sire_name,broodmare_sire_birth_year,sire_line_code,broodmare_sire_line_code,'DATED_UKC' AS source,1 AS priority FROM dated_ukc
 UNION ALL
 SELECT horse_id,strftime(try_strptime(profile_data_date,'%Y%m%d'),'%Y-%m-%d'),strftime(try_strptime(birth_date,'%Y%m%d'),'%Y-%m-%d'),
 horse_name,sex_code,sire_name,sire_birth_year,dam_name,dam_birth_year,broodmare_sire_name,broodmare_sire_birth_year,sire_line_code,broodmare_sire_line_code,'STATIC_PROFILE_DATE_CHECKED',2 FROM pedigree_master
), chosen AS (
 SELECT * FROM observations WHERE observed_date IS NOT NULL
 QUALIFY row_number() OVER(PARTITION BY horse_id,observed_date ORDER BY priority)=1
)
SELECT horse_id,observed_date,struct_pack(horse_id:=horse_id,observed_date:=observed_date,birth_date:=birth_date,
 horse_name:=horse_name,sex_code:=sex_code,sire_name:=sire_name,sire_birth_year:=sire_birth_year,dam_name:=dam_name,dam_birth_year:=dam_birth_year,
 bms_name:=broodmare_sire_name,bms_year:=broodmare_sire_birth_year,sire_line:=sire_line_code,bms_line:=broodmare_sire_line_code,source:=source) AS p FROM chosen;
CREATE TEMP TABLE exact_edges AS
SELECT child_horse_id,role,resolved_parent_horse_id AS parent_id FROM parent_master
WHERE resolution_status='RESOLVED_EXACT' AND candidate_count=1
 AND ((role='dam' AND guard_result='dam_bms_name_birth_year_lineage_match') OR (role='sire' AND guard_result='lineage_code_match'))
 AND regexp_full_match(child_horse_id,'[0-9]{8}') AND regexp_full_match(resolved_parent_horse_id,'[0-9]{8}') AND child_horse_id<>resolved_parent_horse_id;
CREATE TEMP MACRO dam_guard(ch,pa) AS coalesce(ch.horse_id<>pa.horse_id AND pa.sex_code='2' AND ch.birth_date>pa.birth_date
 AND ch.dam_name=pa.horse_name AND trim(ch.dam_name)<>'' AND ch.dam_birth_year=try_cast(substr(pa.birth_date,1,4) AS INTEGER)
 AND ch.bms_name=pa.sire_name AND trim(ch.bms_name)<>'' AND ch.bms_year=pa.sire_birth_year AND ch.bms_year>0
 AND ch.bms_line=pa.sire_line AND regexp_full_match(ch.bms_line,'[0-9]{4}'),false);
CREATE TEMP MACRO sire_guard(ch,pa) AS coalesce(ch.horse_id<>pa.horse_id AND pa.sex_code='1' AND ch.birth_date>pa.birth_date
 AND ch.sire_name=pa.horse_name AND trim(ch.sire_name)<>'' AND ch.sire_birth_year=try_cast(substr(pa.birth_date,1,4) AS INTEGER)
 AND ch.sire_line=pa.sire_line AND regexp_full_match(ch.sire_line,'[0-9]{4}'),false);
CREATE TEMP TABLE targets AS SELECT DISTINCT race_key,horse_no,horse_id,race_date,track_type,distance,age,ukc_date,sire_id FROM cohort;
CREATE TEMP TABLE target_profiles AS SELECT t.*,q.p AS target_p FROM targets t ASOF LEFT JOIN profiles q ON t.horse_id=q.horse_id AND t.race_date>=q.observed_date;
CREATE TEMP TABLE target_parents AS
WITH candidates AS (
 SELECT t.*,d.parent_id AS dam_candidate,s.parent_id AS sire_candidate FROM target_profiles t
 LEFT JOIN exact_edges d ON t.horse_id=d.child_horse_id AND d.role='dam' LEFT JOIN exact_edges s ON t.horse_id=s.child_horse_id AND s.role='sire'
), observed_dam AS (
 SELECT t.*,q.p AS dam_p FROM candidates t ASOF LEFT JOIN profiles q ON t.dam_candidate=q.horse_id AND t.race_date>=q.observed_date
), observed_sire AS (
 SELECT t.*,q.p AS sire_p FROM observed_dam t ASOF LEFT JOIN profiles q ON t.sire_candidate=q.horse_id AND t.race_date>=q.observed_date
)
SELECT *,CASE WHEN ukc_date IS NULL OR target_p.source IS DISTINCT FROM 'DATED_UKC' OR target_p.observed_date IS DISTINCT FROM ukc_date THEN 'NO_DATED_TARGET_PROFILE'
 WHEN dam_candidate IS NULL THEN 'NO_EXACT_DAM_EDGE' WHEN dam_p IS NULL THEN 'NO_DAM_PROFILE_BY_TARGET'
 WHEN NOT dam_guard(target_p,dam_p) THEN 'DAM_GUARD_MISMATCH' ELSE 'RESOLVED' END AS dam_status,
 CASE WHEN ukc_date IS NOT NULL AND target_p.source='DATED_UKC' AND sire_id=sire_candidate AND sire_guard(target_p,sire_p) THEN sire_candidate END AS target_sire_id FROM observed_sire;
CREATE TEMP TABLE family_targets AS
WITH g AS (SELECT t.*,e.parent_id AS granddam_candidate FROM target_parents t LEFT JOIN exact_edges e ON t.dam_status='RESOLVED' AND t.dam_candidate=e.child_horse_id AND e.role='dam'),
 obs AS (SELECT g.*,q.p AS granddam_p FROM g ASOF LEFT JOIN profiles q ON g.granddam_candidate=q.horse_id AND g.race_date>=q.observed_date)
SELECT *,CASE WHEN dam_status<>'RESOLVED' THEN 'DAM_UNRESOLVED' WHEN granddam_candidate IS NULL THEN 'NO_EXACT_GRANDDAM_EDGE'
 WHEN granddam_p IS NULL THEN 'NO_GRANDDAM_PROFILE_BY_TARGET' WHEN NOT dam_guard(dam_p,granddam_p) THEN 'GRANDDAM_GUARD_MISMATCH' ELSE 'RESOLVED' END AS granddam_status FROM obs;
CREATE TEMP TABLE relative_paths AS
WITH paths AS (
 SELECT t.race_key,t.horse_no,t.horse_id,t.race_date,t.target_p,t.target_sire_id,'SAME_DAM' AS path,e.child_horse_id AS relative_id,t.dam_p AS shared_parent_p
 FROM family_targets t JOIN exact_edges e ON t.dam_status='RESOLVED' AND e.role='dam' AND e.parent_id=t.dam_candidate WHERE e.child_horse_id<>t.horse_id
 UNION ALL
 SELECT t.race_key,t.horse_no,t.horse_id,t.race_date,t.target_p,t.target_sire_id,'MATERNAL_AUNT_UNCLE',e.child_horse_id,t.granddam_p
 FROM family_targets t JOIN exact_edges e ON t.granddam_status='RESOLVED' AND e.role='dam' AND e.parent_id=t.granddam_candidate WHERE e.child_horse_id NOT IN (t.horse_id,t.dam_candidate)
), obs AS (SELECT x.*,q.p AS relative_p FROM paths x ASOF LEFT JOIN profiles q ON x.relative_id=q.horse_id AND x.race_date>=q.observed_date),
 sire_candidates AS (SELECT x.*,e.parent_id AS relative_sire_candidate FROM obs x LEFT JOIN exact_edges e ON x.relative_id=e.child_horse_id AND e.role='sire'),
 sire_obs AS (SELECT x.*,q.p AS relative_sire_p FROM sire_candidates x ASOF LEFT JOIN profiles q ON x.relative_sire_candidate=q.horse_id AND x.race_date>=q.observed_date)
SELECT *,CASE WHEN relative_p IS NULL THEN 'NO_RELATIVE_PROFILE_BY_TARGET' WHEN relative_p.birth_date IS NULL OR target_p.birth_date IS NULL THEN 'UNKNOWN_BIRTH_DATE'
 WHEN relative_p.birth_date>=target_p.birth_date THEN 'NOT_OLDER' WHEN NOT dam_guard(relative_p,shared_parent_p) THEN 'RELATIVE_DAM_GUARD_MISMATCH' ELSE 'RESOLVED' END AS path_status,
 CASE WHEN path='MATERNAL_AUNT_UNCLE' THEN path WHEN target_sire_id IS NOT NULL AND sire_guard(relative_p,relative_sire_p) THEN
 CASE WHEN target_sire_id=relative_sire_candidate THEN 'FULL_SIBLING' ELSE 'MATERNAL_HALF_SIBLING' END ELSE 'SAME_DAM_SIRE_UNVERIFIED' END AS relationship FROM sire_obs;
-- Preserve each path; deduplicate only within a target-relative for history.
CREATE TEMP TABLE relative_pairs AS
SELECT race_key,horse_no,horse_id,race_date,relative_id,list(path ORDER BY path) AS paths,list(relationship ORDER BY path) AS relationships,
 count(*) AS path_count,min(relative_p.observed_date) AS relative_profile_date,min(relative_p.birth_date) AS relative_birth_date,min(relative_p.source) AS relative_profile_source
FROM relative_paths WHERE path_status='RESOLVED' GROUP BY 1,2,3,4,5;
