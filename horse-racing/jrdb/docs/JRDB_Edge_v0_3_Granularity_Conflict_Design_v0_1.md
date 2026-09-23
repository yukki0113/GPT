# JRDB Edge v0.3 Granularity / Conflict Design v0.1

Status: **DRAFT / SHADOW ONLY**  
Date: 2026-09-24  
Current production comparator: EdgeDB v0.2 STANDARD

## 1. Objective

EdgeDB v0.3は、v0.2の「統計的に有意な条件をRegistry化して当日突合する」仕組みを捨てるものではない。

目的は、元の思想をserving contractへ明示的に戻すことである。

> 市場が見落としている、または条件クロスが複雑・多重でまだ市場に十分反映されていない条件を発見し、出馬表へ自動突合する。

したがってv0.3では、Researchとして有用な広い傾向と、reader-facingなNiche / Market Edgeを分離する。

## 2. Why v0.3 is needed

実運用監査 Issue #1230 / run 35885211521では、3日917runnerに対して:

- Performance +/-一致runner: 751 (81.9%)
- Performance +/- match: 1,922
- + / -同時一致: 269runner
- Performance一致runner内のmixed率: 35.8%
- 3件以上: 320runner
- 5件以上: 68runner
- 6件以上: 32runner
- 複数redundancy group: 562runner
- PRIMARY / CONFLICT相当が複数残る: 541runner

現行redundancy_group内で吸収された追加matchは22件だけだった。

このため、v0.3の中心課題は「Registry rowを減らす」ではなく、**semantic overlapを解き、lower-order effectをContextへ分離し、追加情報だけをNiche servingへ昇格させること**である。

## 3. Four-layer contract

### 3.1 Research Registry

役割:

- candidate discovery
- temporal validation
- multiple-testing guard
- performance / value evidence保存
- broad contextを含む統計知識資産

ここでは件数の多さ自体を異常としない。

### 3.2 Context layer

lower-order / broad effectを保持する層。

例:

- sire × distance
- sire × surface × distance
- course × frame zone
- sire × transition main effect

Contextは子条件を評価するbaselineとして使う。

ContextがPerformance-positiveでも、それだけで「市場が見落としている特注Edge」として前面表示しない。

### 3.3 Incremental / Niche candidate layer

Child / interaction条件が、適切なContext parentで既に説明される効果を超えて追加情報を持つかを評価する。

重要な変更は:

- v0.2: candidate vs broad baseline
- v0.3: candidate vs nearest meaningful parent / parent-complement

である。

### 3.4 Serving / Presentation layer

reader-facingに出すのは、shadow gateを通ったincremental evidenceを中心とする。

同じsemantic clusterのContext / Childを独立票として数えない。

異なる独立軸が正反対なら、無理に加算せずMIXEDを返す。

## 4. Statistical principle: residual before serving

### 4.1 Child vs Parent-complement

Child C が Parent P のsubsetなら、原則として:

- Child outcome
- ParentのうちChildを除いた比較群 P \ C

を比較する。

例:

course × frame_zone = OUTER  
→ course × exact frame = 8

なら、8枠を「同じcourse全体」と再比較するのではなく、同じOUTER zoneの他枠と比較し、exact frame 8に追加効果があるかを見る。

### 4.2 Why parent-complement

Parent全体にはChild自身が含まれるため、Child vs Parent全体は差を自己希釈する。

P \ Cとの比較を基本とし、sampleが不足する場合はfail-close / insufficient evidenceとする。

### 4.3 Performance and Value stay separate

Performance:

- place-rate系の追加効果
- bootstrap CI
- temporal stability
- multiple-testing q

Value:

現行v0.2は place_roi_vs_baseline と absolute place_roi を用いてPerformanceとは独立分類している。

v0.3でも分離を維持し、Value側のbaselineも可能な限りnearest parent / parent-complementへ変更する。

Performance-positiveをMarket-positiveへ読み替えない。

## 5. Initial semantic hierarchy

### 5.1 COURSE_FRAME hierarchy

Parent:

- COURSE_FRAME_V1
- venue × surface × distance × frame_zone

Child:

- COURSE_EXACT_FRAME_V2
- venue × surface × distance × exact frame_no

Canonical mapping:

- frame 1–3 → INNER
- frame 4–6 → MIDDLE
- frame 7–8 → OUTER

実運用では234回共起し、234回すべて同方向だった。

Initial shadow rule:

1. exact-frame childをzone parentの内部で再評価する
2. incremental evidenceが通ればchildをNiche candidate
3. parentはContextへ
4. childが通らなければexact-frameを特注Edgeとして前面表示しない

### 5.2 SIRE_DISTANCE virtual Context

新しいContext-only parent:

- SIRE_DISTANCE_CONTEXT_V3
- sire_name × distance_m

これはreader-facing templateではない。

Children:

- SIRE_SURFACE_DISTANCE_V1
- SIRE_TURN_DISTANCE_V1

理由:

両Templateはsire × distanceを共有し、実運用で59回共起中58回が同方向だった。

現状では同じ距離main effectをsurface軸とturn軸の両方が拾っている可能性を分離できない。

Shadow evaluation:

- sire × surface × distance vs same sire × distance のother surface
- sire × turn × distance vs same sire × distance のother turn

### 5.3 SIRE surface-distance → venue refinement

Parent:

- SIRE_SURFACE_DISTANCE_V1

Child:

- SIRE_VENUE_SURFACE_DISTANCE_V2

実運用では22回共起し:

- same direction: 17
- opposite direction: 5

この5件の方向反転こそ、venue追加による本物の局所差である可能性がある。

したがって「specificだから常にchild優先」ではなく、parent-relative residualを必須とする。

### 5.4 TRANSITION siblings

- SIRE_DISTANCE_CHANGE_V1
- SIRE_SURFACE_TRANSITION_V1
- SIRE_FRAME_TRANSITION_V1

は初期段階ではParent / Childにしない。

距離変更とsurface transitionは115回共起し35回が逆方向で、単純な重複吸収には向かない。

これらは独立臨戦軸としてshadow servingへ残す。

将来の研究候補:

- sire × distance_change × surface_transition
- sire × distance_change × frame_transition
- sire × surface_transition × frame_transition

ただしmulti-cross childは、各single-axis parentに対するincremental effectを確認してからNiche候補にする。

## 6. Other current templates

初期v0.3で以下を機械的に削除しない。

- SIRE_AGE_V2
- SIRE_BROODMARE_SIRE_V2
- BROODMARE_SIRE_SURFACE_DISTANCE_V2
- SIRE_TRACK_CONDITION_V2
- RECENT_* V2
- JOCKEY_VENUE_DISTANCE_V2
- SIRE_LINE_TURN_DISTANCE_V1

これらはまずUNRESOLVED / ORTHOGONALとしてshadow監査する。

SIRE_LINE_TURN_DISTANCE_V1とsire-specific条件の関係は、canonical sire → sire_line mappingを使った別のsemantic hierarchyが必要であり、文字列field subsetでは扱わない。

## 7. Shadow classification

v0.3 shadowでは各evidenceを以下へ分類する。

### CONTEXT_ONLY

- lower-order effect
- child baselineとして有用
- incremental / market blind spotをまだ示さない
- 通常の特注Edge表示には出さない

### INCREMENTAL_PERFORMANCE

- parent-relative Performance追加効果が統計gateを通る
- Valueは未確認またはNONE

### INCREMENTAL_VALUE

- parent-relative Value追加効果がgateを通る
- Performanceは未確認またはNONE

### INCREMENTAL_DUAL

- Performance / Valueの両channelがincremental

### ORTHOGONAL

- 現時点でparent hierarchyを定義していない独立軸
- v0.2 evidenceをそのまま保持してshadow観測

### INSUFFICIENT

- parent / complement sample不足
- temporal / bootstrap / multiple-testing gate不足
- servingしない

## 8. Conflict contract

### 8.1 Same semantic cluster

同一cluster内で:

- Parent + / Child + → Childがincremental PASSならChildのみreader-facing
- Parent - / Child - → 同上
- Parent + / Child - → Childがincremental PASSならREVERSALとして重要evidence
- Parent - / Child + → 同上
- Childがincremental FAIL → ChildをContextへ吸収

### 8.2 Independent clusters

例:

- course niche +
- transition niche -

のように独立clusterで方向が割れる場合:

- total scoreへ足し引きしない
- MIXEDを返す
- primary positive axis / primary negative axisを個別表示する

## 9. Market-underreflection contract

「Nicheで細かい」だけではEdgeDBの最終目的を満たさない。

最終的なNiche Serving候補では少なくとも:

1. incremental Performance evidence
2. market / Value evidence
3. またはその両方

を区別して返す。

Market evidenceは現行Value channelを起点にするが、v0.3ではnearest parent-relative ROI / price residualへ寄せる。

固定のROI 100%だけを万能gateにしない。標本数、return concentration、temporal stability、multiple testingを維持する。

## 10. No arbitrary net score

v0.3初期段階では以下を禁止する。

- CONFIRMED=1.0 / SUGGESTIVE=0.6等の任意weight
- lift × weightの単純加算
- +Edge数 - -Edge数
- PerformanceとValueの合算
- overlapping child / parent metricの加算

予測モデルがevidenceを使う場合も、EdgeDBは構造化evidenceとprovenanceを渡す側に留める。

## 11. Shadow implementation plan

### Stage A — semantic map

新規configで:

- virtual Context
- Parent / Child
- deterministic derivation
- sibling / orthogonal group

を明示する。

Production v0.2 matcherには接続しない。

### Stage B — parent-relative metric audit

Historical Feature Mart / canonical historyから:

- parent n
- child n
- parent-complement n
- place rate
- place ROI
- incremental lift / difference
- bootstrap CI
- temporal slices
- concentration
- multiple-testing q

をshadow出力する。

既存v0.2 thresholdを勝手に流用して昇格させず、まず分布を監査する。

### Stage C — shadow serving catalog

edge_serving_catalog_v0_3_shadow.jsonl を別artifactとして作る。

v0.2 STANDARDは変更しない。

### Stage D — operational replay

少なくとも2026-09-12 / 09-13 / 09-19を同じCurrent Factsで再突合し、v0.2との比較を行う。

Primary comparison:

- Performance Edge一致runner率
- 1頭あたりmatch数
- 3+ / 5+ / 6+率
- mixed率
- semantic cluster数
- Contextとして吸収された件数
- reversal niche件数
- Value evidence残存数

「件数が少ないほど正しい」ではなく、元の市場盲点思想へ近づきつつ独立情報を落としていないかを確認する。

### Stage E — forward shadow

Historical replayで設計を固定した後、未来日をshadow freezeする。

Target resultを見てからhierarchy / thresholdを調整しない。

## 12. Promotion boundary

v0.3をSTANDARDへ昇格するには:

- v0.2をrollback可能な状態で保持
- parent-relative metricの再現性
- no leakage
- multiple-testing / temporal guard
- operational density改善
- MIXED説明可能性
- market evidence分離
- future shadow blockでの安定性

をすべて満たすこと。

現時点では **v0.3はshadow research only** であり、Newspaper / RaceNote production outputを変更しない。
