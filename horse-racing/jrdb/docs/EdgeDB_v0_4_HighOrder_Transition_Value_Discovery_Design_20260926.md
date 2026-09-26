# EdgeDB v0.4 High-Order Cross / Transition Value Discovery Design

- Status: DESIGN_FROZEN_FOR_PROTOTYPE
- Date: 2026-09-26
- Scope: JRDB Central Racing EdgeDB research / SHADOW
- Production impact: NONE
- Predecessor: v0.3 Evidence hierarchy / incremental-performance SHADOW
- Canonical research input: JRDB Warehouse / Feature Mart Parquet
- Initial validation target: historical rolling rehearsal + 2026-09-26 PACI collision rehearsal

## 1. 目的

v0.4 の目的は、単純な「○○産駒は芝で強い」「○○産駒は東京芝1600mで強い」だけに留まらず、
JRDB の豊富な事前特徴を機械的に多重クロスし、人間の手集計では見つけにくい局所条件・条件遷移から Market Value 候補を発掘することである。

v0.4 は自動購入ロジックではない。
購入補助・指数材料・新聞PWAでの研究表示に用いる Evidence Discovery 層であり、
単独回収率だけで即廃止・即採用を決めるものではない。

### 1.1 v0.4 が狙うもの

1. High-order Cross
   - 3〜6程度の複数事前条件を組み合わせた局所的な高回収率候補。
   - 例: 種牡馬 × 会場 × 芝ダ × 距離。
   - 例: 父系 × 母父系統 × 距離変化 × 回り × 馬場。

2. Transition Edge
   - 前走→今回で条件が変わるケースを重要な探索軸とする。
   - 例: ダ→芝、芝→ダ、距離短縮、距離延長、会場替わり、クラス変化、休養→復帰、馬具変更。
   - 「芝継続」「ダ継続」は原則として Transition と同格に扱わない。多くの馬にとって通常状態であり、情報量が低いためである。
   - ただし継続条件そのものを全面禁止はしない。多重クロス内で追加的 Value が確認される場合のみ候補になり得る。

3. Pedigree Interaction
   - 種牡馬単体だけでなく、JRDB の血統登録・系統コードを使える利点を活かす。
   - 父系、小系統/大系統、母父、母父系統、父×母父系統、種牡馬×母父系統を候補に含める。
   - 血統 × Transition、血統 × Course Context を重点探索する。

4. Recent / Regime Sensitivity
   - 10年一貫性を必須条件にしない。
   - 直近で強まった偏り、最近のみ発生している局所 Value も研究候補として残す。
   - 一方で「直近だけ高い」こと自体を採用根拠にはせず、再現性・払戻依存・期間分散を併記する。

## 2. 非目的

v0.4 では以下を目的としない。

- 人気薄だけを狙うこと。
- オッズ帯を探索条件にして高回収率を作ること。
- 「6番人気以下」「単勝10倍以上」等の市場価格条件を candidate generation に使うこと。
- 条件深度を浅くすること自体。
- 大サンプルだけを残し、ニッチ条件を消すこと。
- 回収率100%未満を機械的に即廃止すること。
- v0.3 Performance Evidence を置換すること。

## 3. 市場情報の扱い

### 3.1 Candidate generation では禁止

以下は探索条件に使用しない。

- 単勝人気
- 複勝人気
- 単勝オッズ
- 複勝オッズ
- 「穴」「人気薄」など上記から派生する特徴
- 結果確定後にのみ利用できる情報

理由:
回収率を評価軸にしながら市場価格そのものを条件に含めると、
「高配当母集団を先に切り出した結果」なのか「競走条件・血統条件そのものに Value がある」のかを分離できなくなるため。

### 3.2 Evaluation では使用可

市場情報は候補生成後の評価にのみ利用する。

- 単勝回収率
- 複勝回収率
- 勝率 / 複勝率
- 平均単勝オッズ（診断のみ）
- 平均人気（診断のみ）
- 払戻分布
- top1払戻寄与率
- top1除外後ROI
- top3除外後ROI

これらを条件定義へ逆流させてはならない。

## 4. 探索特徴量

探索特徴は、原則として「そのレースの発走前に確定しているもの」に限定する。

### 4.1 Current Race Context

- venue / 場
- surface / 芝・ダ
- distance
- distance_band
- track_turn / 右・左・直
- course / 内外等
- going / 馬場状態
- gate / 枠番
- age
- sex
- class / 条件
- grade
- weight category 等、事前に確定する race context

### 4.2 Pedigree

優先順位を付けず、別dimensionとして保持する。

- sire / 種牡馬
- sire_line_small
- sire_line_large
- broodmare_sire / 母父
- broodmare_sire_line_small
- broodmare_sire_line_large
- sire × broodmare_sire
- sire × broodmare_sire_line
- sire_line × broodmare_sire_line

系統コードは JRDB KEITO master に基づく。
血統登録番号を horse identity / pedigree join の基点として扱う。

### 4.3 Transition

前走→今回の差分特徴を第一級特徴として実装する。

- surface_transition
  - TURF_TO_DIRT
  - DIRT_TO_TURF
  - TURF_TO_TURF
  - DIRT_TO_DIRT
  - その他
- distance_delta_m
- distance_delta_bin
  - SHORTEN_400_PLUS
  - SHORTEN_200_399
  - NEAR_SAME
  - EXTEND_200_399
  - EXTEND_400_PLUS
- venue_change
- venue_pair
- turn_change
- going_change
- class_change
- class_delta
- layoff_days / interval_bin
- first_surface flags
- first_distance / first_course 相当の事前フラグ
- equipment_transition
  - blinkers first / re-use
  - equipment change 等

JRDB では ZED が SED と同一形式、ZKB が SKB と同一形式であるため、
前走→今回差分の再構築に利用できる。
KYI 系には前走キー、枠番、ブリンカー、休養理由、初芝初ダ初障等フラグが存在するため、
pre-race transition feature の補助に用いる。

### 4.4 Horse Style / Prior-run Derived

結果リークを避けるため、「今回レース結果」は使わず、前走以前から確定済みの特徴のみを使う。

候補:
- JRDB 脚質コード
- 前走レース脚質
- 前走位置取り区分
- 前走上がり順位等、前走確定時点で利用可能なもの
- 過去N走から作る stable style feature

これらは Phase 1 では必須ではない。
Transition / pedigree / course context を先に実装し、追加価値を確認してから拡張可。

## 5. クロス探索

### 5.1 深度

v0.4 では「2段まで」の固定上限を設けない。

初期 prototype では 2〜6 dimensions を探索可能とする。
ただし depth が深いほど validation requirement を強くする。

重要:
- depth 自体は価値ではない。
- 4重クロスでも人間が容易に気づく条件はある。
- 2重クロスでも非常に局所的で有用な transition はある。
- 「複雑だから採用」「単純だから除外」は行わない。

### 5.2 条件分類

候補には provenance 上の分類を付ける。

- STATIC_CROSS
- PEDIGREE_CROSS
- TRANSITION_CROSS
- PEDIGREE_TRANSITION_CROSS
- MIXED_CROSS

分類は表示・研究上の説明用であり、採否スコアには直接加点しない。

### 5.3 Candidate generation strategy

全組合せ完全列挙は explosion を起こすため、以下の段階探索を行う。

1. single dimension statistics を作る。
2. 2-way cross を作り、support / entropy / prevalence を把握する。
3. 3-way 以上は Apriori-style prefix expansion または equivalent deterministic expansion を使う。
4. parent candidate が最低 support を満たさない場合、通常は child expansion を止める。
5. ただし Transition 必須branchは別枠で探索し、低prevalenceゆえに早期消滅しすぎないよう threshold を緩める。
6. 最大6 dimensions。
7. 同義・包含関係を canonicalize し、重複定義を除く。

### 5.4 Transition-priority branch

通常branchとは別に、以下のいずれかを含む候補を重点探索する。

- DIRT_TO_TURF
- TURF_TO_DIRT
- meaningful distance change
- class change
- layoff / comeback
- equipment transition
- first-surface / first-distance family

このbranchでは「希少であること」を理由に早期除外しない。
代わりに後段の anti-overfit / holdout gate で厳しく評価する。

## 6. Value Metrics

各 candidate について少なくとも以下を算出する。

### 6.1 Core

- n
- wins
- places
- win_rate
- place_rate
- win_return_sum
- place_return_sum
- win_roi
- place_roi

### 6.2 Robustness

- unique_race_days
- unique_meetings
- unique_years
- hit_years
- max_single_win_return
- max_single_win_contribution_ratio
- win_roi_ex_top1
- win_roi_ex_top3
- place_roi_ex_top1
- temporal_window metrics

### 6.3 Parent Incrementality

高次クロスは、親条件との差を必ず持つ。

- best_parent_n
- best_parent_win_roi
- delta_win_roi_vs_parent
- delta_place_roi_vs_parent
- delta_win_rate_vs_parent
- child_support_ratio

「子条件のROIが高い」だけでなく、
追加した条件が親に対してどれだけ Value を増やしたかを見る。

複数parentがある場合、全parentを保持し、
weakest / strongest parent comparison を監査できるようにする。

## 7. Recent Trend

Recent を主目的に固定しないが、必須の診断軸とする。

window候補:
- trailing 180d
- trailing 365d
- trailing 730d
- trailing 1095d
- all-history / discovery-history

各windowで n / ROI / hit distribution を保持する。

trend label は補助分類:
- RECENT_ACCELERATING
- RECENT_PERSISTENT
- RECENT_DECAYING
- LONG_ONLY
- UNSTABLE
- INSUFFICIENT_RECENT

label は採否の単独条件にしない。

## 8. Sample Size / Anti-overfit

### 8.1 Sample Size

固定の一律 n cutoff だけで決めない。
ただし n=数件の偶然を同列には扱わない。

初期prototypeでは evidence tier を持つ。

- MICRO
- SMALL
- MEDIUM
- LARGE

具体閾値は Stage A の分布監査後に freeze する。
設計段階で数値を先に固定しない。

### 8.2 Deep cross penalty

depth が増えるほど次を厳しく要求する。

- unique race days
- temporal dispersion
- multiple hits
- top1 dependency
- parent incrementality
- holdout survival

### 8.3 Jackpot dependency

以下は必須診断。

- TOP1_CONTRIBUTION
- ROI_EX_TOP1
- ROI_EX_TOP3
- UNIQUE_WINNERS
- UNIQUE_HIT_DAYS

高ROIでも jackpot dependent なら削除せず、
JACKPOT_DEPENDENT として fail-closed / research-only にできる。

### 8.4 Multiple testing

大量探索であるため multiple-testing 問題を無視しない。
ただし v0.4 は ROI discovery であり、p-value だけで候補を消し切らない。

prototypeでは:
- candidate_count
- depth-wise candidate_count
- empirical permutation/null distribution または bootstrap sensitivity
- holdout survival
を優先する。

正式な FDR policy は prototype 分布を見てから freeze する。

## 9. Validation

### 9.1 Discovery / Holdout

最低でも時系列を分離する。

例:
- Discovery: 過去期間
- Validation: その後の期間
- Recent holdout: さらに直近期間

random split は主評価に使わない。

### 9.2 Rolling Rehearsal

複数の as-of date を切り、
その時点までのデータだけで candidate を生成し、
次期間で Value がどう動いたかを検証する。

これを v0.4 の主要な backtest とする。

### 9.3 Forward / PACI

長期forward蓄積を必須の昇格条件にはしない。
PACI forward は以下の確認用途。

- pre-race feature generation が成立する
- result leakage がない
- candidate matching が operational data で再現できる
- PWA presentation が過密にならない

初回 operational rehearsal は 2026-09-26 PACI を利用可能。

## 10. Newspaper Presentation

v0.4 の研究段階では「1頭最大1〜2件」に固定しない。
まず実際の candidate collision を観察する。

ただし以下は別々に保持する。

1. raw matches
2. research-ranked matches
3. presentation matches

PWAへは presentation matches を流す。
raw/research を失わない。

### 10.1 表示項目

最低限:
- candidate id
- cross conditions
- family (STATIC / PEDIGREE / TRANSITION / MIXED)
- depth
- n
- win ROI
- place ROI
- wins / places
- parent ROI / delta
- recent window ROI
- jackpot dependency
- evidence tier
- validation status

### 10.2 表示件数

prototype では表示上限を先に固定しない。
0926突合を見て、
- 過密
- 同義重複
- 親子重複
- 人間にとって意味が薄い表示
をレビューした後で presentation policy を freeze する。

## 11. v0.3 との関係

v0.4 は v0.3 を削除しない。

- v0.3: Evidence hierarchy / incremental Performance / semantic cleanup
- v0.4: High-order interaction / Transition / Market Value discovery

初期prototypeでは v0.4 を独立 SHADOW catalog として生成し、
v0.3 production/shadow catalog を変更しない。

将来の統合候補:

Feature Mart Parquet
  -> v0.3 Performance Evidence
  -> v0.4 Value Discovery
  -> combined presentation layer
  -> Newspaper PWA

Performance と Value は別laneとして provenance を残す。

## 12. 初期実装ステージ

### Stage A — Feature Feasibility / Search-space Audit

目的:
実データ上で探索可能な事前特徴を確定し、cardinality / null / coverage / year availability を監査する。

対象:
- course context
- pedigree
- pedigree lineage
- surface/distance transition
- venue/class/interval transition
- equipment flags

成果物:
- feature_inventory.parquet/json
- cardinality audit
- coverage by year
- leakage classification
- canonical feature definitions

### Stage B — Candidate Generator

- deterministic candidate ids
- 2〜6-way expansion
- transition-priority branch
- no popularity/odds filters
- candidate provenance

### Stage C — ROI / Robustness Evaluator

- win/place ROI
- parent delta
- top1/top3 exclusion
- temporal dispersion
- recent windows

### Stage D — Historical Rolling Validation

- as-of generation
- validation/holdout
- survival metrics
- candidate drift

### Stage E — v0.4 Shadow Catalog

- discovery candidates
- validated candidates
- research-ranked candidates
- no production serving change

### Stage F — 2026-09-26 PACI Collision Rehearsal

- pre-race matching
- raw/research/presentation counts
- Newspaper PWA compatible output
- user review

## 13. Prototype の成功条件

v0.4 prototype は、単に高ROI条件を大量生成しただけでは成功としない。

最低条件:

1. Popularity / odds を candidate generation に使っていない。
2. result leakage がない。
3. pedigree × transition を実際に探索できる。
4. 4〜6-way cross を生成できる。
5. parent incrementality を追跡できる。
6. jackpot dependence を可視化できる。
7. rolling holdout を再現できる。
8. 0926 PACI に対して pre-race match を再現できる。
9. PWA上で条件・n・ROI・parent差・robustnessを人間がレビューできる。
10. v0.3 / v0.2 production serving を変更しない。

## 14. 意図的に未固定の項目

以下は、机上で固定せず prototype 分布と0926表示を見て決める。

- minimum n の具体値
- depthごとのminimum n
- ROI採用閾値
- recent window の重み
- parent delta の必要量
- jackpot contribution のfail threshold
- holdout survival threshold
- presentation表示件数
- Static / Transition / Pedigree の優先順位
- 最終rank score

これは設計不足ではなく、
先に閾値を決めると、欲しい結果に合わせて探索空間を歪めることを避けるための意図的な保留である。

## 15. 設計上のレビュー前提

v0.4 は初回から100%完成思想を目指さない。
まず上記ルールで実装し、historical candidate と 2026-09-26 PACI の実突合を PWA で確認する。
その後、ユーザーレビューを基に以下を変更可能とする。

- 探索特徴
- cross depth
- transition definition
- validation gate
- ranking
- presentation policy

v0.4 の第一目的は「設計思想を議論だけで最適化すること」ではなく、
実際に機械探索した条件を見て、欲しかったEdgeと違う部分を具体化できる状態を作ることである。
