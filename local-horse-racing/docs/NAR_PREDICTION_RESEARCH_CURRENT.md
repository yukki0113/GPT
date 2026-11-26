# NAR 予想研究 CURRENT / P8・P9設計追補 v1.5

決定日: 2026-11-26 JST。Status: **P95_RESEARCH_COMPLETE / READY_FOR_P10_DESIGN**。

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

## 5. P8A.1 の開始契約（実行済み・歴史的要件）

1. Git mainの本書・v1.0・現行registry・P0.1・共通runtime registryを読み、証跡ZIPをSHA照合、必要入力を実取得またはSHA検証済みcacheから再利用。共通 `data_storage check-deps` を実行（前回は版/SQL smokeのみ）。入力監査を無条件にやり直さず、同一bytes確認を新runに記録する。pilot scriptは再現証跡であり、絶対パス/単一connectionのまま本番研究実装に流用しない。
2. P8A.1のrun_id・入力manifest・候補config・family allowlist・評価cohort定義をfreeze。2017–2023のみ結果を開示。2016は履歴のみ。A0/AC0/ACJ0を複数年で算出、A1の事前登録候補（last 3/5/8 within365、90/180/365日平均、365日内half-life 30/60/90、min2）を個別比較。A2はA1選定窓のmedian/top2 mean等。A1/A2の開発結果でshortlistを固定し、2022–23を比較・選択に使用（全Cartesian探索なし）。詳細はv1.0 §5、§7。候補採否はまだ未実施。
3. 新規実装はhistory builder → feature Freeze（全ENTRY runner・欠損理由・lineage）→ score Freeze（全runner、別工程でpost/rawアクセスなし）→ evaluator（Freeze SHAを確認してから対象結果/control結合）。モデルが対象結果を読めないこと、evaluatorラベルの変異で予想が不変であることを確認。共通cohortと全対象cohortを別々に比較し、棄権・取消/中止/同着/NULLの扱いはv1.0 §4/7に従う。
4. 各候補で時系列・禁止列・identity・thread/prefix/rank gateを通過後に成績を算出。A1/A2は開発と検証を区別し、確認期間は開かない。元のP9候補昇格条件（2024–25の+0.3pp、paired CI下限>0、coverage/副指標等）は変更しない。P8A.1は研究実施でありP8/P9最終昇格ではない。
5. `input_manifest.json`, feature dictionary/lineage, experiment registry/config, leakage audit, feature/prediction freezes, metrics_by_fold/segment, decision ledger（不採用含む）, report, SHA256SUMSをrun別保存。Git（code/config/test/summary）・Drive（詳細）・Library（携帯可能なbundle/引き継ぎ）読み戻し。完了判定後にCURRENTの状態と次工程を更新。保存不能時はHOLDと明記。

## 6. P8以降の進捗

| Phase | Status |
|---|---|
| P8.0 | ACCEPTED_WITH_VERSIONED_BASELINE_REPLACEMENT |
| P8A.1 | COMPLETE: hl60 selected, A2 rejected |
| P8A.2 | COMPLETE_SCOPED: opponent and speed selected; direct class mapping HOLD |
| P8A.3 | COMPLETE: P8-Astar-r1 FROZEN_FOR_P8B |
| P8B.1 | COMPLETE_SCOPED（course/going tested; direct class mapping HOLD） |
| P8B.2 | COMPLETE_SCOPED（draw/style/pressure tested; not promoted） |
| P8B.3 / P8.close | COMPLETE（locked confirmation; Bstar not promoted; Astar selected for P9） |
| P9 | COMPLETE_NO_QUALIFIED_AUXILIARY_CANDIDATE（Astar維持） |
| P9.5 | COMPLETE（WIN=Astar維持、PLACE=JB研究候補） |
| P10 | READY_DESIGN_NOT_EXECUTED（WIN/PLACE別比較・回収率・独立検証） |

P8/P9/P9.5研究完了。P10設計未実施。本番採用・2026評価は未承認。P8未採用familyと保留事項は§10、P9の結果は§11を参照。

## 7. 不変証跡・取得先

- Git: `NAR_P8_0_REPORT_20261124.md`（historical HOLD）, `../research/p8/preflight.py`, `baseline_guard.py`, `recovery_pilot_tie12.py`（旧提案表記は実行当時の記録）。P8.0保存最終commit a00d5ef89332a7711ee4078dfefad84c534461a1。
- Drive: `/GPT/local-horse-racing/30_analysis/P8/P8.0_20261124/`、Library: `/地方競馬予想/P8/P8.0_20261124/`。
- `NAR_P8_0_REPORT_20261124.md`: SHA256 c6d9d4dbc27c263e42e3dcfe2713e0d454fdcae7a7d826e3fcb84e58895a15de（Drive/Library版。Git版は保存索引追記済）。
- `NAR_P8_0_EVIDENCE_20261124.zip`: SHA256 6c48f8c33cf6f5aa65703f7a876223404820111971692a08a4c1687eef5eae6b。内部SHA256SUMS 24件、旧registry・旧再実行・修正版1/4threadのfreezeを保持。
- canonical input_manifest SHA256 5efafa73f8c6d5ac68d2e77df5001650815bc5a56112003d0618f70c1e51013c; entity audit 910e707dedc8e8b1505fb0877c2e95ceae5b501d352b5fa948676ccb4000025a; tie audit 59a2a68693304d7e342b68cb4f2532e97f09ba3e6e1ca3e3e273a0d350718246; baseline guard 44958233484b15f692d92b569913c61b29b0db698e98f6d3913eb2811589ac0a。
- 新比較基準の証跡: ZIP内 `tie_repair/threads4/pilot_prediction_freeze.parquet` SHA256 da104ae2137eefa141f4bb1ae630d1ce274b175f0802a1615e3dd2feba216669。threads1 SHA256 f46d5d93d911d4f106d04291624c97c1673e0fe2a99def27ad724c62ac792fbb。物理byte SHAは違っても論理再現gateはPASS。原FreezeはRecovery ZIPに不変保持。

## 8. P8A確定・次工程（v1.2）

- P8A.1〜3 実行済み。正式研究候補 `P8-Astar-r1`（`research/p8/a/candidate_config.json` SHA256 bea7046ab28aa1f18c11e387634f18d70e8687f38dd22cea54c5213b9f622bc2）。候補の凍結は研究用であり、P9昇格・本番採用ではない。
- 365日半減期60日加重正規化着順 F、対戦相手の事前A0水準補正 O×0.20、基準タイム Sとの0.30 blend（各2件以上、欠損補正0）。履歴1走のみ (p+1.5)/4、0走/曖昧はUNKNOWN。tie12は不変。クラス直接補正はHOLD、賞金/着差候補は不採用（B2でクラス移動・比較可能性を別途研究）。計算式の厳密な定義はcandidate_configと実行コードを優先。
- 2022–23: 26919 eligible / 26391 scored / 8329 wins / 16808 top1 3rd-or-better / 16310 winner in top3 / 261049 scored runners of 272409. A0 6776 wins / 26314 scored. Common runner cohort: 7669 vs 6776, +3.3936pp, CI [3.0093,3.7691], both years positive. Full cohort and common support differ; no ROI.
- 32 input assets same-byte verified, 939724 ENTRY targets 2017–23, all t1/t4 freezes byte-identical, 7 boundary tests and stage guard PASS. Class mapping unresolved; no full P8 or independent confirmation. 2024–25 locked until both A/B freeze, 2026 excluded. No change to P8 v1.0 promotion criteria or B grids.
- Git report `docs/NAR_P8A_REPORT_20261124.md` and exact code/config `research/p8/a/` saved/read back; evidence commit 1f7cbf9ad6af870d73c1d869aff4c7dea9767e77. Drive folder https://drive.google.com/drive/folders/1SNAOchX5htZrARZwgM-sBjwkq3J9mzEU (13 files, 452509626 bytes, all SHA readback parity). Library `/地方競馬予想/P8/P8A_20261124/` (compact ZIP 224 internal files all verified); report SHA256 669ac59d93cc183d91d2552e2da373e3cc4dc30ad207c673edd0fa94377c1691; portable evidence ZIP SHA256 209bd8ac6f333d5a7710513b21b8ebbc7d325e98a7b325241394abea9783b2dd. Annual Freeze and history-reference ZIP hashes in delivery_manifest.json/SHA256SUMS. Original P8.0 and P8A artifacts unchanged.

## 9. P8B.1 開始契約

1. 本書、現行registry、v1.0 §6–9、P8A report/candidate config、P0.1、共通storage contractを読む。保存済みP8A Freezeおよび必要canonicalをSHA照合。P8A候補を再最適化しない。必要時に同式で全ENTRY予想を再生成し、厳密rank parityを確認する。
2. P8Bでは追加post/race_resultの10年分の資産監査とcorner/lap parse feasibilityを行う（実際の2024–25予想評価はまだロック）。B1/B2: Astar-r1を固定基礎として会場・距離・回り・転入/距離移動・条件補正の個別アブレーション。クラスコードの全国等価性を仮定しない。B3/B4は後続。2017–21開発、2022–23比較、2024–25はB統合候補freeze後に一度のみ確認。2026不可。
3. Astar-r1の1走評価は基礎の縮約、0走/曖昧はUNKNOWN。B補正の最低件数と欠損時補正0を独立管理し、能力のない馬を0とみなさない。全候補のfeature/score/evaluator isolation・同日/未来注入・thread/rank gate・coverage監視・run別保存読み戻しを維持。B検証は未着手。

上記§9はP8B.1の実行時契約として保存する。次工程は§10に従う。

## 10. P8B確定・P8.close / P9開始点（v1.3）

- P8B 46候補を2017–21開発、2022–23比較で評価。B1 venue180/k3/w.25を唯一の確認候補に固定、B3 gateは2022年負差のため不採用、統合も不採用。B2 going・B4 style/pressureは開発gateで不採用。クラス直接補正はHOLD。ハロン・正規化上がり・RACE_DAYは未実施/延期。P8Aの係数は不変。
- 10追加post/race_result資産150529件の完全性確認、2016–23の有効104616レースのcorner parse/照合PASS（馬群中間順位近似、地点差あり）、lap coverage 25838。全候補feature/prediction t1/t4 byte parity、同日/未来注入、score-only隔離の scoped PASS。確認期間281378全ENTRY行のFreezeもexact parity、2023 B1 prefix不変、A3/A4 history reference prefix差0、label poison試験PASS。
- 2024–25確認はB候補Git freeze e839575419fa448f96cb70c6dbdd7203964f34a7 後に一度開示。27070 eligible、A0 6893/26432、AC0 6942/26432、Astar8390/26524、Bstar8449/26524。Bstar vs Astar +.222440pp CI [.076645,.362809]、venue-day sensitivity [.079141,.361694]。最低+.3ppに未達でBstar NOT_PROMOTED_MIN_INCREMENT。Astar vs A0共通26432R +3.132567pp CI [2.723288,3.507331]、full wins +1497、coverage/副指標gate PASS。**P9の固定研究基準は P8-Astar-r1（B補正なし）**。Astarは本番採用ではない。2024–25は既知の回顧確認、独立未見検証と称さない。
- Git report `docs/NAR_P8B_REPORT_20261124.md`、handoff `docs/NAR_P9_HANDOFF_20261124.md`、source/config/test `research/p8/b/`（exact UTF-8 executed source bundles + materializer）。候補config SHA 046a10f66cd3d8f1f2ce208e76bb55106edc7154587cdb4eb1db21a154da354e、confirmation result SHA 05bee0c3c56b84df507b22acec4b2935ab1751eba3d70d48fe1b2e0bee54ef41、closure SHA 4cf6d7f49d394b530f81fb516cafbfe3a3fdcdb9d338be14ae6446db5f7ba919。
- Drive `/GPT/local-horse-racing/30_analysis/P8/P8B_20261124/` folder https://drive.google.com/drive/folders/1H2-0ly-ly_6QLlr7NEdKu7xdETu2h5pE（18ファイル559826990 bytes SHA readback parity）、Library `/地方競馬予想/P8/P8B_20261124/`（8ファイルSHA readback parity）。report SHA e9de7bf7eccaeb89eeb18addeef8049946dddb4ad50d89a17960d90af8638b80、compact ZIP SHA c6a578868978c658ab0d7013fea17fdd67c42735c3bfc8dc82f07486ced22a41。P8.close追補・読戻し監査は別途保存。旧P8.0/A/B FreezeやCanonicalは不変。
- P9は設計から開始。補助評価（騎手・厩舎・ライン・血統）の候補・時点名寄せ・縮約・比較基準・期間分割を事前確定。P8の2024–25確認を未見扱いせず、結果に合わせた再調整を禁止。2026は別承認のCanonical拡張とfreezeまで不使用。P10回収率/独立検証・本番運用は未着手。

## 11. P9確定・P10開始点（v1.4 / 2026-11-25）

- P9設計 `docs/NAR_P9_RESEARCH_DESIGN_20261125.md` commit 3c1e8c44cead92e27c3b723bc5cbdbeb7008e267 事前固定、P8-Astar-r1の全ENTRY予想Freezeを再利用。騎手/厩舎/ライン/父/母父の過去Astar順位残差を縮約・同馬除外して32候補検証。全40 canonical資産同一bytes/row、P8年度別9 archive内部SHA一致、2017–23 939724 ENTRY、880805残差、騎手同race重複46行除外。5family×7年度境界prefix/注入差0、1/4 thread特徴量論理一致・全候補順位一致、score-only隔離/label poison PASS。一括1thread timeout後family別照合（byte一致主張なし）。
- 開発64876 eligible/63863 scored Astar20820勝。騎手・厩舎全候補不採用。父・母父・pairをshortlist freeze commit 6be1bfb6af7044aa945266a5abf28f00cdf54778。比較2022–23 26919 eligible/26391 scored: Astar8329、父8331（年差-8/+10）、母父8332（+14/-11）、pair8329（-4/+4）、父+母父8346（+7/+10）、3項目8339（-4/+14）。統合も個別family gate不合格、父+母父 +0.064416pp CI [-0.072377,+0.200980]。全候補棄権/coverage同一。**P9新規候補なし、P8-Astar-r1をP10の研究基準として維持（Bstarも追加しない）**。P9確認はNOT_APPLICABLE_NO_QUALIFIED_CANDIDATE、2024–25のP9 outcome未開示、P8では既に開示済み。2026未使用。過去の採否を変更しない。
- Git: `docs/NAR_P9_REPORT_20261125.md`、`docs/NAR_P10_HANDOFF_20261125.md`、`research/p9/` code/config/closure、source/report保存commit d8a60e236b33159a82d99f827a7d88768664a9a2。
- Drive `/GPT/local-horse-racing/30_analysis/P9/P9_20261125/` https://drive.google.com/drive/folders/1MrH3jSAqKfGy7alio70sy9qmKwZcesum（17ファイル348723252 bytes SHA readback parity）。Library `/地方競馬予想/P9/P9_20261125/`（8ファイルSHA readback parity）。
- report SHA 00367ce4911af819e46160003d699d3633a494af829a02d9f8cd2c821e9907fc、compact ZIP SHA 506a60106048f281225bafdb7b8554c9c3751f5826159372ec93224d6fdaa45a、fallback decision config SHA 129668ac2065221d5570ab319e601c146d2a3b66a32e6e2731cdc25eb9ee1e8e、closure SHA 923382f1e36733b109b5a601ab65dca62a18d1596613659b1ec1cf9c3a1154cd。
- P10は設計から開始。能力スコアを勝率と同一視しない。購入ルール・評価対象・費用・払戻評価専用境界を事前確定。2024–25は既知であり独立未見検証ではない、後付けの買い目選択/係数最適化は禁止。2026は別途明示承認されたCanonical拡張と候補freezeまで使わない。P10の収益性・本番運用未承認。

## 12. P9.5確定・P10開始点（v1.5 / 2026-11-26）

- P9.5はユーザー指示による追加研究。P8/P9.1–4の不採用・未昇格結果は変更しない。`docs/NAR_P95_RESEARCH_DESIGN_20261126.md` commit 3c11f6deebd09bbcdeb184e3d5120ef4ae46ef3b 事前固定。過去Astar順位残差の条件別4セル相互作用・厩舎内騎手差・同馬前後残差を検証。全18候補、2017–21開発、2022–23比較、2024–25は既知回顧確認。相手候補選択（PLACE）の独立評価を追加したが、P8/P9のWIN gateは変更しない。2026不使用、production未承認。
- 開発64876 eligible/63863 scored、Astar20820勝、102015上位3頭内の実3着内馬。WIN tb_w10 +32勝、PLACE jb_w20 -23勝、+112純増、1921 gross拾上げ。shortlist commit c9ed323a0faeb8558e708d570e4cbecbb4379e7e。比較2022–23 26919 eligible/26391 scored、Astar8329勝/41539 hits、WIN8340勝（0/+11）不採用、PLACE8309勝/41653 hits（+56/+58、gross850）。候補freeze commit 61e311b070f0b2d86e43c00c33a682dc826667e3。
- 確認2024–25 27070 eligible/26524 scored、Astar8390勝/41602 hits、JB8378勝/41700 hits（+98純増、+60/+38、gross856）、winner3 +64、top1 top3 同数、coverage不変。gross +3.227266/100R CI [3.017871,3.440367]、net +.369477/100R CI [.138729,.615807]、win -.045242pp CI [-.168115,.079189]。全PLACE gate通過。grossは基礎4位以下から新たに上位3頭へ選んだ実3着以内馬の件数、純増ではない。**WIN基準 P8-Astar-r1、別建てPLACE研究候補 P95-PLACE-JB-r1**。勝馬予測の優越を主張しない。馬券戦略・収益性・独立未見検証は未実施。
- `research/p95/candidate_config.json` SHA be719a743c5773c941c81baf08fdff6a3f981def6b4b8e46c843f5acdcba6c78。365d、同馬除外、騎手×Astar相対順位3分割の4セル差、joint min20、other30/30/100、clip[-1,1]、shrink n/(n+100)、weight .20、欠損補正0、基礎UNKNOWN維持、tie12。能力スコアは確率でない。
- 9family全行t1/t4 byte一致（NumPy整数prefixはsingle-thread、DuckDB read threads 1/4）、63年度境界、同日/未来注入・独立直接集計差0、全予想rank parity、score列7拒否・label poison PASS。初回一括timeout/3並列memory killを家族別checkpointに変更、数式不変。40 canonical資産確認再照合、P9履歴/対象/2017–23 JB全行prefix不変。脚質は2017–23 P8B時点特徴量のみ、確認期はJBのみ。
- Git `docs/NAR_P95_REPORT_20261126.md`, `docs/NAR_P10_HANDOFF_20261126.md`, `research/p95/` exact source bundle/config/decision/confirmation. 保存commit 27728f016944fd00bf40d43a522dfb912f63d8e5。Drive `/GPT/local-horse-racing/30_analysis/P9/P95_20261126/` https://drive.google.com/drive/folders/1F0KwiqbZj2aCaoZXgVzKkln6gWxSTWDX（22ファイル664529141 bytes SHA parity）、Library `/地方競馬予想/P9/P95_20261126/`（10ファイルSHA parity）。
- report SHA 82bbd179f1f664ffb164b2091c25264b5327473bb9eb58a37a63bb175cfb58d9; compact ZIP SHA 00b54f542d78c494d43f951e5771e86628b7efb26afce871436033d7fe19a377; confirmation SHA d84e247e9b80743c984a2b9765570d99d8cfea405df809964c4ea57cc7966997; closure SHA d10b835981c27229f338eff2580e8e8d9e2a13824e96b001b3ccf7a2f6cb445d.
- P10開始時は最新 `docs/NAR_P10_HANDOFF_20261126.md` を優先。固定WINと別建てPLACEを独立の買い目/相手候補評価として事前登録し、比較・選択と払戻評価の境界を保持。既知期間の成績を見た再調整禁止。2026は別途明示承認のCanonical拡張と候補freezeまで使わない。本番運用・ROI未承認。旧P10 handoffは歴史資料として保持。
