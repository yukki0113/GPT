# B1 debut eligibility — PARTIAL (2026-11-24 JST)

Research only. No training population, prediction, publication or production authorization.

## Reproduction

Run ../research/brdb_b1_debut_eligibility_audit_v0_1.sql via the common tools/data-storage data_storage.query.execute_query with manifest-verified JRDB Analysis v1.4 fact_entry_result_lite exposed as view data. Use wheel-first approved runtime. Restrict to 2016-2025. SQL SHA-256 c23f19b418914c3741be76b6e7ca3a84f013af28e8731a0daebccea2a09db702; Git blob 29b3a6386b0b5cbbfeb0cbfd14bd2cbbde116ea9. Analysis manifest SHA-256 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d. 11/11 annual assets verified. No raw parser replacement.

Existing class labels A1=新馬, A2=未出走, A3=未勝利 are confirmed in jrdb_newspaper_build.py and racenote_paci_context_v1.py. Class labels are race attributes; they do not certify individual career history. First observed entry and first observed normal finish are separate proxies. Nonempty prior keys establish prior records, not necessarily actual starts. A normal finish proxy uses abnormal_code=0 and finish 1..18; it is not a verified all-starter denominator.

## Aggregate observed metrics

| Section | Metric | Count |
|---|---|---:|
| A1 | age_2 | 32223 |
| A1 | age_3 | 7731 |
| A1 | earlier_observed_entry | 118 |
| A1 | earlier_observed_normal_finish | 0 |
| A1 | entries | 39954 |
| A1 | first_observed_entry_no_prior_keys | 39832 |
| A1 | horses | 39837 |
| A1 | missing_parent_or_line | 0 |
| A1 | normal_finish | 39637 |
| A1 | prior_race_key_present | 122 |
| A1 | prior_result_key_present | 122 |
| A1 | races | 2955 |
| A1_abnormal_code | 0 | 39637 |
| A1_abnormal_code | 1 | 81 |
| A1_abnormal_code | 2 | 84 |
| A1_abnormal_code | 3 | 149 |
| A1_abnormal_code | 5 | 3 |
| A2 | entries | 0 |
| first_normal_finish_by_class | 05 | 2790 |
| first_normal_finish_by_class | 10 | 980 |
| first_normal_finish_by_class | 16 | 408 |
| first_normal_finish_by_class | A1 | 39637 |
| first_normal_finish_by_class | A3 | 9474 |
| first_normal_finish_by_class | MISSING | 122 |
| first_normal_finish_by_class | OP | 951 |
| first_observed | entries | 54508 |
| first_observed | no_prior_keys_in_left_edge_year | 4529 |
| first_observed | prior_date_before_window | 6389 |
| first_observed | prior_date_invalid | 0 |
| first_observed | prior_date_nonprior | 0 |
| first_observed | prior_date_within_window | 1114 |
| first_observed | prior_id_mismatch | 0 |
| first_observed | prior_result_key_present | 7503 |
| first_observed_no_prior_keys_by_class | 05 | 27 |
| first_observed_no_prior_keys_by_class | A1 | 39832 |
| first_observed_no_prior_keys_by_class | A3 | 7020 |
| first_observed_no_prior_keys_by_class | MISSING | 123 |
| first_observed_no_prior_keys_by_class | OP | 3 |
| historical | duplicate_race_horse_key | 0 |
| historical | horses | 54508 |
| historical | invalid_horse_id | 0 |
| historical | missing_age | 108 |
| historical | missing_bms | 108 |
| historical | missing_bms_line | 112 |
| historical | missing_class | 735 |
| historical | missing_sire | 108 |
| historical | missing_sire_line | 111 |
| historical | races | 34548 |
| historical | rows | 481627 |
| historical | same_day_multiple_horse_groups | 0 |

## Interpretation and remaining gates

- 122 A1 rows have prior keys; 118 have an earlier observed entry, none an earlier observed normal finish. Do not label these as 122 previously raced horses.
- 7,503 first-observed horses have prior result keys; 6,389 before 2016 and 1,114 within the observation window. Investigate prior-key match/coverage and official abnormal code semantics before classifying actual first starts.
- 4,529 first-observed horses in 2016 have no prior keys: left censoring remains unresolved. Local/overseas history and missing class codes must remain explicit unknowns until verified.
- Nonempty sire/BMS and lineage names/codes do not establish canonical parent ID resolution or historical as-of availability.
- Establish separate confirmed actual-first-start and new-race cohort eligibility, exclusions, unknowns, coverage by year and as-of provenance before B2/B3. No predictive claims.
- Private aggregate receipt and SQL retained in personal Library /BRDB/Development_B1_20261124/. No horse-level data in Git.

Dependency report: {"missing_packages":[],"packages":{"duckdb":{"available":true,"required_version":"2.0.1","version":"2.0.1"},"pyarrow":{"available":true,"required_version":null,"version":"25.0.1"}},"python_version":"3.13.5","status":"success","version_mismatches":[]}.
