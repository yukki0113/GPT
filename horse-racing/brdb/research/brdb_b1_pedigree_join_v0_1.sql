-- Input views: classified (B1 v0.2), dated_ukc (verified Warehouse),
-- pedigree_master and parent_master (accepted immutable BRDB generation).
-- Read-only research crosswalk: no newly inferred parent relation, no name fallback.
WITH dated AS (
    SELECT c.*, u.data_date_iso AS ukc_date, u.horse_symbol_code AS ukc_symbol,
           u.source_archive_sha256 AS ukc_archive_sha, u.source_member_sha256 AS ukc_member_sha,
           u.sire_name AS dated_sire, u.sire_birth_year AS dated_sire_year, u.sire_line_code AS dated_sire_line,
           u.broodmare_sire_name AS dated_bms, u.broodmare_sire_birth_year AS dated_bms_year,
           u.broodmare_sire_line_code AS dated_bms_line
    FROM classified c ASOF LEFT JOIN dated_ukc u
      ON c.horse_id=u.horse_id AND c.race_date>=u.data_date_iso
), guarded AS (
    SELECT d.*, m.horse_id IS NOT NULL AS child_master_present,
           m.profile_data_date AS child_master_date,
           s.resolution_status AS static_sire_status, b.resolution_status AS static_bms_status,
           CASE WHEN ukc_date IS NULL THEN 'NO_DATED_PROFILE'
                WHEN s.child_horse_id IS NULL THEN 'NO_STATIC_RELATION'
                WHEN s.resolution_status<>'RESOLVED_EXACT' OR s.resolution_status IS NULL THEN coalesce(s.resolution_status,'UNKNOWN_STATUS')
                WHEN s.guard_result IS DISTINCT FROM 'lineage_code_match' OR s.candidate_count IS DISTINCT FROM 1
                     OR NOT coalesce(regexp_full_match(s.resolved_parent_horse_id,'[0-9]{8}'),false)
                     OR sp.horse_id IS NULL OR m.horse_id IS NULL THEN 'INVALID_STATIC_GUARD'
                WHEN dated_sire IS NULL OR trim(dated_sire)='' OR dated_sire_year IS NULL OR dated_sire_year<=0
                     OR NOT coalesce(regexp_full_match(dated_sire_line,'[0-9]{4}'),false)
                     OR s.parent_name IS DISTINCT FROM dated_sire OR s.parent_birth_year IS DISTINCT FROM dated_sire_year
                     OR s.parent_lineage_code IS DISTINCT FROM dated_sire_line THEN 'DATED_FACT_MISMATCH'
                ELSE 'MATCHED_GUARDED_STATIC_ID' END AS sire_join_status,
           CASE WHEN ukc_date IS NULL THEN 'NO_DATED_PROFILE'
                WHEN b.child_horse_id IS NULL THEN 'NO_STATIC_RELATION'
                WHEN b.resolution_status<>'RESOLVED_EXACT' OR b.resolution_status IS NULL THEN coalesce(b.resolution_status,'UNKNOWN_STATUS')
                WHEN b.guard_result IS DISTINCT FROM 'lineage_code_match' OR b.candidate_count IS DISTINCT FROM 1
                     OR NOT coalesce(regexp_full_match(b.resolved_parent_horse_id,'[0-9]{8}'),false)
                     OR bp.horse_id IS NULL OR m.horse_id IS NULL THEN 'INVALID_STATIC_GUARD'
                WHEN dated_bms IS NULL OR trim(dated_bms)='' OR dated_bms_year IS NULL OR dated_bms_year<=0
                     OR NOT coalesce(regexp_full_match(dated_bms_line,'[0-9]{4}'),false)
                     OR b.parent_name IS DISTINCT FROM dated_bms OR b.parent_birth_year IS DISTINCT FROM dated_bms_year
                     OR b.parent_lineage_code IS DISTINCT FROM dated_bms_line THEN 'DATED_FACT_MISMATCH'
                ELSE 'MATCHED_GUARDED_STATIC_ID' END AS bms_join_status,
           s.resolved_parent_horse_id AS static_sire_id, b.resolved_parent_horse_id AS static_bms_id
    FROM dated d
    LEFT JOIN pedigree_master m ON m.horse_id=d.horse_id
    LEFT JOIN parent_master s ON s.child_horse_id=d.horse_id AND s.role='sire'
    LEFT JOIN parent_master b ON b.child_horse_id=d.horse_id AND b.role='broodmare_sire'
    LEFT JOIN pedigree_master sp ON sp.horse_id=s.resolved_parent_horse_id
    LEFT JOIN pedigree_master bp ON bp.horse_id=b.resolved_parent_horse_id
)
SELECT * EXCLUDE (static_sire_id,static_bms_id),
       CASE WHEN sire_join_status='MATCHED_GUARDED_STATIC_ID' THEN static_sire_id END AS sire_id,
       CASE WHEN bms_join_status='MATCHED_GUARDED_STATIC_ID' THEN static_bms_id END AS bms_id,
       'USER_ACCEPTED_PROVIDER_EQUIVALENCE' AS source_equivalence_policy,
       'STATIC_RELATION_AS_OF_UNVERIFIED' AS parent_temporal_status,
       false AS prediction_safe, false AS production_authorized
FROM guarded
