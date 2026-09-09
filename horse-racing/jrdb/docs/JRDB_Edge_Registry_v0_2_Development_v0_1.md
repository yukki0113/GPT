# JRDB Edge Registry v0.2 Development

Status: **IMPLEMENTATION IN PROGRESS**  
Established: 2026-09-09

## 1. Goal

v0.1 Full Registryを凍結したまま、次の不足をv0.2で拡張する。

1. PEDIGREE / COURSEの意味のあるクロス条件を増やす。
2. RECENT familyをpre-race情報だけで正式に探索可能にする。
3. HUMAN familyは馬質補正residual baselineが完成するまでraw成績をEdge化しない。
4. 条件追加・改廃をtemplate catalog中心で行える状態を維持する。

## 2. v0.2 first-wave templates

### COURSE
- `COURSE_EXACT_FRAME_V2`: venue + surface + distance × exact frame number

### PEDIGREE
- `SIRE_BROODMARE_SIRE_V2`: sire × broodmare sire
- `SIRE_AGE_V2`: sire × horse age
- `SIRE_VENUE_SURFACE_DISTANCE_V2`: sire × venue × surface × exact distance
- `BROODMARE_SIRE_SURFACE_DISTANCE_V2`: broodmare sire × surface × exact distance
- v0.1 PEDIGREE / TRANSITION templatesも継続

### RECENT

Index Baseに既に存在する開催前KYI情報をFeature Mart v0.2へ投影する。

- `uptrend_code`
- `training_arrow_code`
- `stable_evaluation_code`
- `rotation_interval`
- `pre_idm`
- `training_score`
- `stable_score`
- `body_weight_pre_kg`
- `body_weight_change_pre_kg`

first waveでは、surface + distanceをbaseline anchorにして次を探索する。

- uptrend code
- training arrow
- stable evaluation
- rotation interval

RECENTは `DYNAMIC_RECENT_V2` によりrolling validationする。

## 3. Horse age

`horse_age = race calendar year - birth calendar year` とする。

JRAの競走年齢表示と同じcalendar-age扱いとし、historical martとcurrent factsで同一canonical helperを使う。Future-dated birth/profileは使用しない。

## 4. HUMAN policy

HUMANはv0.2 first waveでも通常templateを有効化しない。

理由:
- raw騎手勝率/複勝率は馬質の影響を強く受ける。
- 「強い馬に多く乗る騎手」を人間Edgeと誤認しないため、pre-race horse-quality adjusted residualが必要。

Index Baseには `pre_idm` 等のpre-race horse-quality proxyがあるため、次工程でhistorical-only / leakage-safe calibrationを設計する。

禁止:
- final odds / final popularityによる馬質補正
- target resultを含む同時点fit
- raw jockey/trainer rateのACTIVE昇格

## 5. Track condition

`父 × 馬場状態` はfirst waveでは実装しない。

SED確定馬場は結果側情報なのでcurrent Edge conditionには使用禁止。将来、Freeze前に取得できるpre-race馬場sourceを正式契約へ追加した場合にtemplate化する。

## 6. Candidate explosion control

v0.2では `max_modifier_count` を2から3へ拡張するが、自由な全組合せ探索はしない。

意味のあるクロスだけをversioned templateとして追加する。

理由:
- sample fragmentation
- mass-search false positive
- FDR burden
- WATCH inflation

統計guard（BH-FDR + race-date cluster bootstrap CI）は維持する。

## 7. WATCH review

ACTIVE閾値はv0.2 first waveで直ちに緩和しない。

まずWATCHを以下に分解して評価する。
- temporal WATCH
- temporal ACTIVE/PROVISIONAL -> statistical guard downgrade WATCH

TRUE_FORWARD蓄積後、ACTIVE gateの再calibrationを別判断する。

## 8. Compatibility

v0.1 publicationは変更しない。

- v0.1 templates / policies / mart schemaは保持
- v0.2は別config / schema / runnerでbuild可能にする
- consumerは明示的にv0.2 publicationへ切り替えるまでv0.1を使用可能

## 9. First-wave implementation files

- `config/jrdb_edge_candidate_templates_v0_2.json`
- `config/jrdb_edge_validation_policies_v0_2.json`
- `schema/jrdb_edge_feature_mart_schema_v0_2.sql`
- `src/jrdb_edge_v02_canonical.py`
- `src/build_jrdb_edge_feature_mart_v0_2.py`
- `src/jrdb_edge_discovery_v0_2.py`
- `src/apply_jrdb_edge_statistical_guard_v0_2.py`
- `src/build_jrdb_edge_current_facts_v0_2.py`
- `src/jrdb_edge_matcher_v0_2.py`
- `src/run_jrdb_edge_match_current_v0_2.py`
- `src/run_jrdb_edge_registry_pipeline_v0_2.py`
- `tests/test_jrdb_edge_v0_2.py`

## 10. Acceptance

first waveは以下を満たしたら完了。

1. v0.1 regressionを壊さない。
2. v0.2 unit tests pass。
3. 2025-only Registry smoke build success。
4. 新templateのcandidateが実データで生成される。
5. RECENT candidateが0件ではないことを確認する。
6. HUMANは0件のままであることを確認する。
7. current matcherがv0.2 fieldsをpre-race PACIから照合できる。
8. Full 2010-2025再build前にcandidate explosion / runtimeを監査する。
