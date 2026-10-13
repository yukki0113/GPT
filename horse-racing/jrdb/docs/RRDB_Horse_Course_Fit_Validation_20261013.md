# RRDB Horse Course Fit v0.1 実装・検証報告

検証日: 2026-10-13。全件生成・監査・再実行確認はPASS。RRDB v0.3は未変更。

## 検証証跡

- 調査・再生成元main: `73ce7238f89027d9c7c54e4c1eb0cefacf17a03f`
- 実装・実データ検証Git SHA: `45ffa9dca52c410fc90334933533cb3ed3240528`
- [検証run 38370479179](https://github.com/yukki0113/GPT/actions/runs/38370479179)
- [PR #2004](https://github.com/yukki0113/GPT/pull/2004)
- [全成果物ZIP（170,365,515 bytes）](https://github.com/yukki0113/GPT/actions/runs/38370479179/artifacts/11799761734)
- 全成果物ZIP SHA-256: `18570ef9c366f78b2f8bb60c380e24b70f1b80e070ddf1961acaed7bde35627d`
- [manifest・audit・レポートZIP](https://github.com/yukki0113/GPT/actions/runs/38370479179/artifacts/11800215769)
- レポートZIP SHA-256: `04be626d6a2ff4cc42d9de088073c145da29256f9cb6cbfb6a66aacc51904d61`

## 入力と集計期間

- Historical Warehouse: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`。既存レビュー済みmanifestのBAC 16 asset・SED 16 assetをSHA-256／サイズ照合。
- RRDB: accepted `rrdb-current-ready-20261013`（run `38327108923`, artifact `11780924435`）。元ZIP digest: `ea1d4e1f3f0efdebee512a3ba09f7f9fd253a3851b42c562698bc11102fb011a`。各RRDB Parquetもmanifest照合。
- 正本performance: `jrdb_recommendation_signals.performance_signal`による `-horse_adjusted_delta_per_1000m`。代替指数なし。
- Base履歴: 2010-01-05〜2025-12-28。`as_of_date=2026-01-01`。
- Fit window: `2023-01-01 <= race_date < 2026-01-01`。対象windowは142,737走。
- baselineは各走以前3暦年の直近最大10 actual start、利用可能performanceが3走以上で単純平均。既存prior3平均とは件数／期間が異なるため、その処理の無変更流用はしない。
- 物理属性: canonical `physical_valid_from=2023-01-01`。開始日・exclusive endを検査。Transitionでは直前actual startと今回の双方をassert。未検証期間の属性はNULL・物理Fitから除外。

## 実装・変更ファイル

すべて追加ファイル。既存source、CourseMaster builder、CourseStats、RRDB v0.3運用ファイルの変更なし。

- `horse-racing/jrdb/src/jrdb_horse_course_fit.py`
- `horse-racing/jrdb/src/run_rrdb_horse_course_fit_validation.py`
- `horse-racing/jrdb/tests/test_jrdb_horse_course_fit.py`
- `.github/workflows/rrdb_horse_course_fit_validation.yml`
- `horse-racing/jrdb/docs/RRDB_Horse_Course_Fit_v0_1.md`
- 本報告 `horse-racing/jrdb/docs/RRDB_Horse_Course_Fit_Validation_20261013.md`

## CourseMaster再生成結果

Phase1: BAC latest 55,215 race、433 course combination、course correction mismatch 0。Phase3: 177 CourseMaster（平地138／障害39）、57 geometry、433 mapping。最終直線坂は57件に設定、course sizeは50件に設定・非周回／複合layoutの7件は正当なNULL。physical_valid_from／versionの存在・期間・Master伝播を検証しPASS。障害のroute ambiguityによるmapping未解決8件は補完せず保持。

## Base / 残差集計

| 指標 | 件数 |
| --- | ---: |
| Base runner | 781,161 |
| race | 55,268 |
| horse | 82,215 |
| baseline算出可能 | 551,381 |
| baseline不足 | 229,780 |
| 物理期間／属性未検証（Base保持） | 642,670 |
| 障害等の非対象（Base保持） | 24,814 |
| 平地course identity未解決 | 0 |
| RRDB入力未対応 | 0 |

## Fit各軸とsupport

| family / feature | record | horse | n min / median / max | shrunk_delta p05 / median / p95 | MEDIUM以上 | HIGH |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| ABSOLUTE / COURSE_SIZE | 17,940 | 11,240 | 2 / 4.0 / 37 | -0.351326 / -0.039513 / 0.249264 | 9,022 | 5,061 |
| ABSOLUTE / FINAL_SLOPE | 18,284 | 11,381 | 2 / 4.0 / 32 | -0.352532 / -0.040426 / 0.256506 | 9,431 | 5,173 |
| ABSOLUTE / FINAL_STRAIGHT_BUCKET | 19,236 | 10,780 | 2 / 3.0 / 33 | -0.340886 / -0.035844 / 0.246353 | 8,603 | 4,351 |
| ABSOLUTE / LAYOUT | 16,818 | 11,545 | 2 / 4.0 / 38 | -0.366569 / -0.041949 / 0.257013 | 8,676 | 5,187 |
| ABSOLUTE / PACE_PROFILE | 21,335 | 10,579 | 2 / 3.0 / 19 | -0.340911 / -0.034694 / 0.257196 | 8,795 | 3,651 |
| ABSOLUTE / TURN_DIRECTION | 18,045 | 11,211 | 2 / 3.0 / 36 | -0.353104 / -0.043079 / 0.252079 | 8,992 | 5,119 |
| TRANSITION / COURSE_GEOMETRY_CHANGE | 6,627 | 3,782 | 2 / 2.0 / 18 | -0.285231 / -0.016076 / 0.224358 | 676 | 171 |
| TRANSITION / COURSE_SIZE_CHANGE | 17,625 | 9,039 | 2 / 3.0 / 30 | -0.313993 / -0.028953 / 0.229019 | 5,851 | 2,422 |
| TRANSITION / DISTANCE_CHANGE | 18,219 | 9,267 | 2 / 3.0 / 26 | -0.314036 / -0.033429 / 0.228723 | 6,423 | 2,861 |
| TRANSITION / FINAL_SLOPE_CHANGE | 18,612 | 9,333 | 2 / 3.0 / 26 | -0.314322 / -0.030337 / 0.234261 | 6,327 | 2,509 |
| TRANSITION / FINAL_STRAIGHT_CHANGE | 19,385 | 8,992 | 2 / 3.0 / 19 | -0.311919 / -0.033378 / 0.227209 | 7,241 | 2,642 |
| TRANSITION / GOING_CHANGE | 18,710 | 9,422 | 2 / 3.0 / 25 | -0.320533 / -0.033420 / 0.228774 | 6,517 | 2,880 |
| TRANSITION / GOING_RAW_CHANGE | 12,525 | 7,326 | 2 / 2.0 / 22 | -0.291555 / -0.022983 / 0.224722 | 3,062 | 1,384 |
| TRANSITION / LAYOUT_CHANGE | 14,816 | 9,750 | 2 / 3.0 / 37 | -0.343223 / -0.037252 / 0.240391 | 5,947 | 3,514 |
| TRANSITION / TURN_DIRECTION_CHANGE | 18,065 | 9,172 | 2 / 3.0 / 28 | -0.317968 / -0.033172 / 0.230735 | 6,032 | 2,716 |

各support_levelの件数は `fit/reports/support_summary.csv`、NULL率は `feature_coverage.csv`／`transition_coverage.json`、ゼロ件の軸を含むinventoryは `feature_inventory.json` に記録。

## 全stage成果物

| artifact（course-fit-output/fit/配下） | row count | 初回stage秒 |
| --- | ---: | ---: |
| `base/horse_race_course_ledger.parquet` | 781,161 | 419.872 |
| `base/horse_performance_residual.parquet` | 781,161 | 4.391 |
| `base/horse_course_transition_ledger.parquet` | 781,161 | 5.678 |
| `absolute_fit/horse_turn_direction_fit.parquet` | 18,045 | 0.123 |
| `absolute_fit/horse_final_slope_fit.parquet` | 18,284 | 0.119 |
| `absolute_fit/horse_final_straight_bucket_fit.parquet` | 19,236 | 0.122 |
| `absolute_fit/horse_course_size_fit.parquet` | 17,940 | 0.114 |
| `absolute_fit/horse_layout_fit.parquet` | 16,818 | 0.108 |
| `absolute_fit/horse_pace_profile_fit.parquet` | 21,335 | 0.123 |
| `transition_fit/horse_distance_change_fit.parquet` | 18,219 | 0.121 |
| `transition_fit/horse_turn_direction_change_fit.parquet` | 18,065 | 0.154 |
| `transition_fit/horse_final_slope_change_fit.parquet` | 18,612 | 0.149 |
| `transition_fit/horse_final_straight_change_fit.parquet` | 19,385 | 0.132 |
| `transition_fit/horse_course_size_change_fit.parquet` | 17,625 | 0.140 |
| `transition_fit/horse_layout_change_fit.parquet` | 14,816 | 0.139 |
| `transition_fit/horse_going_change_fit.parquet` | 18,710 | 0.127 |
| `transition_fit/horse_going_raw_change_fit.parquet` | 12,525 | 0.121 |
| `transition_fit/horse_course_geometry_change_fit.parquet` | 6,627 | 0.125 |
| `research/candidate_fit_view.parquet` | 256,242 | 0.826 |
| `research/distance_change_same_surface_view.parquet` | 17,721 | 0.102 |

加えて `course-fit-output/course_master/` のPhase1 audit、CourseMaster／mapping／geometry JSONL、Phase3 summary、`course-fit-output/reports/` のinput validation・Master validation・restartability・result、および `course-fit-output/fit/manifest.json`／`audit.json` を保存。manifestにはGit SHA、module SHA、全入力fingerprint、Parquet SHA-256・row count・schema hash・elapsed・stage dependency・定数・going mappingを記録。

## 監査と再実行

- focused regression: 8 tests PASS。対象日除外・3年window・baseline上限・物理valid-to exclusive・両側物理gate・前走欠損時の非スキップ・surface扱い・再利用・RRDB/SED correction不一致fail-closedを検証。
- 全件audit PASS。baseline／Fitの未来・window違反0、source availability違反0、物理属性リーク0、平地identity未解決0、数式／confidence範囲違反0。
- 物理属性5 Absolute軸、6 Transition軸の今回・前走各assertもすべて0違反。
- 同日複数actual startの異常group 0。
- 20 Parquetすべてが再実行後に同一SHA-256。20 stageすべてREUSED。`reports/restartability.json`に列挙。
- Goingは同一surfaceのみ、surface別集計。Distanceはsurface change flagを分離し、同一surface viewも生成。Raw goingコード・連続距離／直線delta・両側endpointはTransition Ledgerに保持。
- shrinkage k=5、confidence sample denominator=8、STORE_MIN_SAMPLE=2、SIGNAL_MIN_SAMPLE=4。production signal追加なし。

## 実行コマンド

```bash
python horse-racing/jrdb/src/audit_jra_course_profile_phase1.py --input-root /tmp/course-fit-input/warehouse --output /tmp/course-fit-output/course_master/phase1_audit.json
python horse-racing/jrdb/src/build_jra_course_profile_phase3.py --phase1-audit /tmp/course-fit-output/course_master/phase1_audit.json --official-config horse-racing/jrdb/config/course_profile/official_current_course_geometry_v0_1.json --output-dir /tmp/course-fit-output/course_master
python horse-racing/jrdb/src/run_rrdb_horse_course_fit_validation.py --warehouse-root /tmp/course-fit-input/warehouse --rrdb-artifact-root /tmp/course-fit-input/rrdb --output-dir /tmp/course-fit-output --as-of-date 2026-01-01
python -m pytest horse-racing/jrdb/tests/test_jrdb_horse_course_fit.py -q
```

通常CLIは `jrdb_horse_course_fit.py --rrdb-root EXTRACTED_CURRENT_ROOT --warehouse-root WAREHOUSE --course-master-dir PHASE3_OUTPUT --as-of-date YYYY-MM-DD --output-dir OUTPUT`。`--stage`と`--feature`で個別再実行可能。検証runnerは全stageを2回実行し、SHA同一・再利用をassertする。

## 制約とreplayへの引き継ぎ

- 実データ検証snapshotは2026-01-01。2026日次分を含む別as-ofには、対応するcanonical入力を取得する。Historical Warehouseだけで2026日次coverageを満たしたと解釈しない。
- 2023以前の歴史的course_versionは未復元。現行物理属性を過去へ投影せず除外。
- course_sizeは周長分類であり、turn radius／tight turnの因果指標とはしない。
- SED source_member_dateをavailability evidenceとして使用。過去correction vintageを再現する場合は整合するRRDB snapshotが必要。不一致時の別ロジックfallbackなし。
- CourseStatsは未変更。PACE_PROFILEはcanonical SED H/M/Sを使い、2010–2025 CourseStatsの未来含みJOINや独自Draw分類は行わない。
- Straight SIMILAR toleranceは事前固定5m。canonical rail差の1.5/2.2/2.4/2.6/2.7/3/5/5.5/7.7mを確認した。5m以下の小さいrail差をSIMILARとし、outcomeを見て変更していない。実データのstraight deltaは中央値0m、p25=-46.5m、p75=45.9m。
- `candidate_fit_view`は256,242 record。同一surface Distance viewは17,721 record。候補該当数・勝率・馬券内率・単複ROI・v0.3重複率・v0.3非該当馬成績は次の独立replay研究で評価し、今回の数値から本番推奨へ自動追加しない。
- GitHub成果物はproviderの保存期限（2027-01-11）あり。長期Drive保存は現在未実施。170MBの生成済みZIPを `GPT/horse-racing/20_mart/rrdb_course_fit/v0_1/` へ保存する操作が自動承認レビューで拒否された。作成済みフォルダは親からリンク所持者全員writer権限を継承しているため、payloadと共有範囲の明示承認が必要。公開／共有範囲は変更していない。
- 元RRDB sourceの分割再アップロード案も自動承認レビューで拒否され、撤回済み。元データ再公開を行わず既存Actions内で全件検証を完了した。
