# NAR 予想研究 CURRENT / P8設計追補 v1.1

決定日: 2026-11-24 JST。Status: **P8.0_ACCEPTED_WITH_VERSIONED_BASELINE_REPLACEMENT / READY_FOR_P8A.1**。

## 1. 正式研究ルート・適用順位

ユーザー指示により旧v0.1.0/v0.1.1の探索・復元は終了。現行P8 → P9 → P10が正式研究ルート。これは研究開始承認であり、本番予想・買い目・市場Edge・自動運用の承認ではない。旧版番号を再利用しない。

研究再開時は本書を最初に読む。上位のP0.1入力契約 `CANONICAL_DATA_SPEC.md` と共通Git/Storage方針は変更しない。本書は `NAR_P8_RESEARCH_DESIGN_20261124.md` (v1.0, Git blob 008f5c0c9a964e3f363044e338040cd03f16835e, SHA256 8ba456092f52642aa2c8a0a66b0f065e9a5bd83db13bd9a49957c2ca6fc906c5) の順位決定・P8.0完了条件・進捗だけを置換する。その他の設計、候補グリッド、採否閾値は継承する。`../research/p8/experiment_registry.json` が現行機械可読設定。原設計・原監査報告・原Freeze・旧registry（証跡ZIP内）は歴史資料として不変保持し、そのHOLD/PENDINGを現行状態と誤認しない。

## 2. P8.0 採否記録

| 項目 | 判定 |
|---|---|
| 2016–2025年の4テーブル40 partitionの入力監査 | PASS（全70資産ではない） |
| horse_key監査 | PASS_SCOPED（surrogate維持。公式恒久IDではない） |
| 旧pilotの厳密順位再現 | FAIL_STRICT_RANK_PARITY（8/191949行、4 model×race。保存し改変しない） |
| tie12 修正版の1/4 thread比較 | PASS（191949行、キー差0、順位差0、許容誤差超過0、集計一致） |
| baseline history guard | PASS_SCOPED（9年度境界、3291出走馬、prefix/同日/未来注入差0、禁止列7/7拒否） |
| 基準切替 | ACCEPTED_FOR_RESEARCH（ユーザー承認、性能目的の調整なし） |
| P8.0 | ACCEPTED_WITH_VERSIONED_BASELINE_REPLACEMENT |

旧Freezeとの順位差は30行、旧版再実行との差8行とは別の比較。小数点差を許容して旧順位FAILをPASSに読み替えない。修正前後の予想順位は同一ではない。新基準の論理的再現は確認済みだが、任意のデータ・並列数での丸め境界の不変性は保証しない。P8A/Bごとのfeature/score/evaluator隔離や時点名寄せは未検証であり、実行前の必須gateとする。

## 3. 固定ベンチマーク（研究専用）

基準ID `RECOVERY-PILOT-r0.1-tie12`。2025年のみを入力、2025-07-01〜12-31を評価、ダート平地ENTRY、前180日（D-180 <= history_date < D）、有効履歴2走以上。歴史観測はNORMALかつis_model_target、finish_count>1、1<=finish_position<=finish_count、finish_time_seconds>0。p=1-(finish_position-1)/(finish_count-1)。A=mean(p)。AC=A+0.25*n_course/(n_course+3)*(course_mean-A)。ACJ=AC+0.15*n_pair/(n_pair+20)*(pair_mean-0.5)。courseはvenue×distance_m×surface、pairは騎手/調教師のname+affiliation（暫定ID）。補正なしは0、基礎不足はNULL/UNKNOWN。係数・履歴条件は原pilotと同じ。

有効scoreは有限値、順位は DuckDB `ORDER BY round(score,12) DESC, horse_no ASC`、NULL/非有限は未評価理由を残す（非有限は異常としてfail-closed）。scoreは丸めず保存し、rank keyのみ丸める。各race×model内でhorse_no一意。今後のすべての研究候補に同じ順位規約を適用。キー/NULL/件数/順位/集計は厳密一致、score/連続特徴量は絶対誤差1e-12以内。1/4 thread、prefix/full、同日・未来注入、丸め境界近傍・同点の回帰テストを各familyで実施。不一致ならHOLD、丸め精度や許容値の事後変更禁止。必要な改善は別バージョン・設計追補・証跡で扱う。

| model | eligible races | scored races | top1 win | top1 3rd-or-better | winner in top3 |
|---|---:|---:|---:|---:|---:|
| A | 7009 | 6810 | 1783 | 3893 | 3462 |
| AC | 7009 | 6810 | 1791 | 3890 | 3489 |
| ACJ | 7009 | 6810 | 1830 | 3937 | 3501 |

これは2025-only既知pilotの固定再現基準。複数年拡張 `P8-A0`, `P8-AC0`, `P8-ACJ0` は同式・同順位規約だが、年を跨ぐ履歴を利用する別run。上記数値を複数年結果として流用しない。ACJ0は参考、P8では新規騎手/厩舎補正最適化をしない。比較時に同一cohort、全対象cohort、分母とcoverageを併記。旧pilotの欠損処理を再現することと、新しい全ENTRY roster freeze要件は区別する。

## 4. 入力と期間ロック（変更なし）

- Canonical `nar_canonical_v1_201601_202512_g20260917`、manifest SHA256 bdc6cc603f5a199fa513bffea3b0450588df828c0bdbac5c52e980f4ab6f926a。P0-01-20261124の指定条件のみ訂正適用。CURRENT/原本/原ledgerは変更しない。再取得時は実SHA/size/row/schema/keyを照合。P8.0監査は対象40資産のみ、P8Bでpost/race_result 10資産を追加検証。
- 2016 warmup、2017–21 development、2022–23 validation、2024–25 locked retrospective（A/B候補両方freeze後に開示）、2026 excluded。2025 H2 pilot既知、旧研究の利用可能性もあるため2024–25は独立未見データではない。2026は別承認・データ拡張・freezeまで使わない。
- ENTRY target rosterはpreの許可列だけから生成。対象control/postを対象抽出やscoreに渡さない。historyは対象日00:00 JSTより前のみ。過去人気/odds/payout/8種PENDING snapshotは禁止。天候/馬場は対象ENTRY禁止、過去条件として利用可。対象馬体重は禁止。全期間identity監査で過去キーを遡及修正しない。

## 5. 次工程 P8A.1 の開始契約

1. Git mainの本書・v1.0・現行registry・P0.1・共通runtime registryを読み、証跡ZIPをSHA照合、必要入力を実取得またはSHA検証済みcacheから再利用。共通 `data_storage check-deps` を実行（前回は版/SQL smokeのみ）。入力監査を無条件にやり直さず、同一bytes確認を新runに記録する。pilot scriptは再現証跡であり、絶対パス/単一connectionのまま本番研究実装に流用しない。
2. P8A.1のrun_id・入力manifest・候補config・family allowlist・評価cohort定義をfreeze。2017–2023のみ結果を開示。2016は履歴のみ。A0/AC0/ACJ0を複数年で算出、A1の事前登録候補（last 3/5/8 within365、90/180/365日平均、365日内half-life 30/60/90、min2）を個別比較。A2はA1選定窓のmedian/top2 mean等。A1/A2の開発結果でshortlistを固定し、2022–23を比較・選択に使用（全Cartesian探索なし）。詳細はv1.0 §5、§7。候補採否はまだ未実施。
3. 新規実装はhistory builder → feature Freeze（全ENTRY runner・欠損理由・lineage）→ score Freeze（全runner、別工程でpost/rawアクセスなし）→ evaluator（Freeze SHAを確認してから対象結果/control結合）。モデルが対象結果を読めないこと、evaluatorラベルの変異で予想が不変であることを確認。共通cohortと全対象cohortを別々に比較し、棄権・取消/中止/同着/NULLの扱いはv1.0 §4/7に従う。
4. 各候補で時系列・禁止列・identity・thread/prefix/rank gateを通過後に成績を算出。A1/A2は開発と検証を区別し、確認期間は開かない。元のP9候補昇格条件（2024–25の+0.3pp、paired CI下限>0、coverage/副指標等）は変更しない。P8A.1は研究実施でありP8/P9最終昇格ではない。
5. `input_manifest.json`, feature dictionary/lineage, experiment registry/config, leakage audit, feature/prediction freezes, metrics_by_fold/segment, decision ledger（不採用含む）, report, SHA256SUMSをrun別保存。Git（code/config/test/summary）・Drive（詳細）・Library（携帯可能なbundle/引き継ぎ）読み戻し。完了判定後にCURRENTの状態と次工程を更新。保存不能時はHOLDと明記。

## 6. P8以降の進捗

| Phase | Status |
|---|---|
| P8.0 | ACCEPTED_WITH_VERSIONED_BASELINE_REPLACEMENT |
| P8A.1 | READY_NOT_EXECUTED |
| P8A.2 | WAIT_P8A.1（class/opponent/speed feasibility） |
| P8A.3 | WAIT（A*候補freeze） |
| P8B.1 / P8B.2 | WAIT（course/class, draw/pace・追加資産監査） |
| P8B.3 / P8.close | WAIT（統合候補freeze後2024–25確認、採否・保存） |
| P9 | WAIT_P8_CLOSE（補助評価） |
| P10 | WAIT_P9（統合・精度/回収率・独立検証） |

P8A.1以降の新規成績は未計算。P8終了、production promotion、2026評価、全family漏洩監査完了とはしない。

## 7. 不変証跡・取得先

- Git: `NAR_P8_0_REPORT_20261124.md`（historical HOLD）, `../research/p8/preflight.py`, `baseline_guard.py`, `recovery_pilot_tie12.py`（旧提案表記は実行当時の記録）。P8.0保存最終commit a00d5ef89332a7711ee4078dfefad84c534461a1。
- Drive: `/GPT/local-horse-racing/30_analysis/P8/P8.0_20261124/`、Library: `/地方競馬予想/P8/P8.0_20261124/`。
- `NAR_P8_0_REPORT_20261124.md`: SHA256 c6d9d4dbc27c263e42e3dcfe2713e0d454fdcae7a7d826e3fcb84e58895a15de（Drive/Library版。Git版は保存索引追記済）。
- `NAR_P8_0_EVIDENCE_20261124.zip`: SHA256 6c48f8c33cf6f5aa65703f7a876223404820111971692a08a4c1687eef5eae6b。内部SHA256SUMS 24件、旧registry・旧再実行・修正版1/4threadのfreezeを保持。
- canonical input_manifest SHA256 5efafa73f8c6d5ac68d2e77df5001650815bc5a56112003d0618f70c1e51013c; entity audit 910e707dedc8e8b1505fb0877c2e95ceae5b501d352b5fa948676ccb4000025a; tie audit 59a2a68693304d7e342b68cb4f2532e97f09ba3e6e1ca3e3e273a0d350718246; baseline guard 44958233484b15f692d92b569913c61b29b0db698e98f6d3913eb2811589ac0a。
- 新比較基準の証跡: ZIP内 `tie_repair/threads4/pilot_prediction_freeze.parquet` SHA256 da104ae2137eefa141f4bb1ae630d1ce274b175f0802a1615e3dd2feba216669。threads1 SHA256 f46d5d93d911d4f106d04291624c97c1673e0fe2a99def27ad724c62ac792fbb。物理byte SHAは違っても論理再現gateはPASS。原FreezeはRecovery ZIPに不変保持。

本書と現行registryが研究再開の正本。次回はP8A.1から開始し、旧版探索や同点修正版の再承認は不要。
