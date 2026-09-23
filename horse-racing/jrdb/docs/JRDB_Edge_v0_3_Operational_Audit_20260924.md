# JRDB Edge v0.2 実運用監査 — v0.3 Granularity / Conflict 再設計前提

Date: 2026-09-24  
Status: **AUDIT PASS / v0.2 semantics unchanged**

## 1. Purpose

EdgeDBの原点は、単に「統計的に差がある条件」を大量に保存することではない。

> 市場が見落としている、または条件クロスが複雑・多重でまだ市場に十分反映されていない条件を自動発見し、当日の出馬表へ自動突合する。

2026-09-12以降の実運用で、1頭に5〜6件以上のEdgeが同時一致し、+ / - が混在してreader-facingな意味が不明瞭になるケースが観測された。本監査は、その問題が偶発例か構造的問題かを、現行v0.2 STANDARD servingの実データで測定する。

この監査ではRegistry status、閾値、candidate template、serving eligibility、matcher、Newspaper表示の意味論を変更しない。

## 2. Formal evidence

Canonical audit:

- Issue: #1230
- workflow: JRDB Edge v0.2 operational audit via Issue
- run_id: 35885211521
- artifact: jrdb-edge-v02-operational-audit-35885211521
- artifact digest: sha256:4b5e687f3a6e9a0ff76f0333bb7db1206051cc75fdb84b007951c3b0f13d2485
- serving profile: STANDARD
- result data used for matching: false

Target days:

- 2026-09-12: frozen pre-result reconstruction, STANDARD
- 2026-09-13: TRUE_FORWARD freeze, STANDARD
- 2026-09-19: same frozen PACI / Analysis Parquet / serving catalogからresult-free replay

2026-09-19のAnalysis SQLite compatibilityとParquet currentのbyte-equivalenceは、Issue #1197 / run 35814265623で別途PASS済み。

## 3. Overall density

3日合計:

| Metric | Result |
|---|---:|
| runner | 917 |
| 何らかのEdge一致 | 763 (83.2%) |
| 全match | 2,009 |
| Performance +/- match | 1,922 |
| Performance + | 1,153 |
| Performance - | 769 |
| Performance +/-一致runner | 751 (81.9%) |

Performance +/-の1頭あたりhit数:

| hit数 | runner |
|---:|---:|
| 0 | 166 |
| 1 | 188 |
| 2 | 243 |
| 3 | 146 |
| 4 | 106 |
| 5 | 36 |
| 6 | 23 |
| 7 | 5 |
| 8 | 3 |
| 9 | 1 |

- 平均: 2.10件
- 中央値: 2件
- 90%点: 4件
- 3件以上: 320頭 (34.9%)
- 5件以上: 68頭 (7.4%)
- 6件以上: 32頭 (3.5%)

したがって「1頭へ5〜6件付く」は例外的な表示事故ではなく、現行STANDARD servingで継続的に発生する構造である。

## 4. + / - conflict

同一runnerでPerformance + と - が同時に存在したrunner:

- 269 / 917 = 29.3%
- Performance +/-が1件以上あるrunnerに限定すると 269 / 751 = **35.8%**

実際に頻出した構成には以下が含まれる。

- +1 / -1: 58頭
- +2 / -1: 57頭
- +2 / -2: 32頭
- +3 / -1: 26頭
- +1 / -2: 24頭
- +1 / -3: 21頭
- +3 / -2: 11頭
- +3 / -3: 6頭

最も密な例では +2 / -7 の9件が同一馬に一致した。

この結果から、EdgeDBを「最終的に+か-かを必ず1符号へ丸めるDB」と解釈するのは不適切である。一方、現在のまま全matched Edgeを同列表示するのもreader-facing servingとして過密である。

## 5. Existing redundancy_group is insufficient

現行matcherは同一 redundancy_group 内ではCONFIRMED / SUGGESTIVE、specificity、signal方向を使ってpresentation roleを整理する。

しかし実運用では:

- 同一group内の追加match: 22件のみ
- 複数redundancy groupが刺さるrunner: 562頭
- PRIMARY / CONFLICT相当が複数残るrunner: 541頭

つまり、現在の「1頭に多数出る」問題の中心は、同一group内の重複ではなく **groupをまたぐ意味的重複・相関・独立軸の混在** である。

## 6. Literal Parent / Childだけでは解けない

条件field集合がstrict subset / supersetになるpairを機械的に調べると:

- Parent/Child候補を持つrunner: 22頭 (2.4%)
- pair: 22組
- 同方向: 17組
- 逆方向: 5組

したがって、単純にJSON conditionのfield集合だけでParent / Childを作る方法では問題の大部分を説明できない。

v0.3では、field名が異なっていても同じ潜在因子を表す **semantic hierarchy / semantic overlap** が必要である。

## 7. Semantic overlap evidence

3日実運用で主要Template pairの方向を追加監査した。

| Semantic relation | 共起 | 同方向 | 逆方向 |
|---|---:|---:|---:|
| COURSE_FRAME_V1 → COURSE_EXACT_FRAME_V2 | 234 | 234 | 0 |
| SIRE_SURFACE_DISTANCE_V1 ↔ SIRE_TURN_DISTANCE_V1 | 59 | 58 | 1 |
| SIRE_DISTANCE_CHANGE_V1 ↔ SIRE_SURFACE_TRANSITION_V1 | 115 | 80 | 35 |
| SIRE_SURFACE_DISTANCE_V1 → SIRE_VENUE_SURFACE_DISTANCE_V2 | 22 | 17 | 5 |

### 7.1 Course frame hierarchy

COURSE_FRAME_V1 と COURSE_EXACT_FRAME_V2 は234回共起し、**234 / 234が同方向**だった。

frame_noはframe_zoneを決定するため、これは自然な階層関係である。

- course × frame_zone
- course × exact frame_no

を独立票として同時表示するのではなく、exact frameが有効ならzone側をContext / parent evidenceへ吸収する設計候補が強い。

### 7.2 Sire × distance latent effect

SIRE_SURFACE_DISTANCE_V1 と SIRE_TURN_DISTANCE_V1 は59回共起し、58回が同方向だった。

両者はliteral Parent / Childではないが、どちらも sire × distance を共有する。現行templateには sire × distance だけのContext parentがないため、同じ「その父がその距離帯で良い / 悪い」という潜在因子がsurface側とturn側の両方で再検出されている可能性が高い。

v0.3では、servingしないContext parentとして sire × distance を持ち、surface / turnの追加効果をそこから測る設計を検討する。

### 7.3 Transition siblings

SIRE_DISTANCE_CHANGE_V1 と SIRE_SURFACE_TRANSITION_V1 は115回共起したが、35回は逆方向だった。

これはCOURSE frameのような単純重複とは異なる。距離変更と芝ダート変更は独立した臨戦軸として本当に異なる情報を持つ可能性があるため、片方を機械的に消してはならない。

### 7.4 Venue refinement

SIRE_VENUE_SURFACE_DISTANCE_V2 と SIRE_SURFACE_DISTANCE_V1 は22回共起し、17回同方向、5回逆方向だった。

venue追加で方向が反転する例があるため、specific childを常にparentへ吸収するのも誤りである。childがparentに対して追加的・残差的な差を持つかを直接評価する必要がある。

## 8. Template frequency in actual matching

| Template | Performance +/- match |
|---|---:|
| COURSE_EXACT_FRAME_V2 | 328 |
| COURSE_FRAME_V1 | 327 |
| SIRE_DISTANCE_CHANGE_V1 | 250 |
| SIRE_LINE_TURN_DISTANCE_V1 | 215 |
| SIRE_SURFACE_TRANSITION_V1 | 179 |
| BROODMARE_SIRE_SURFACE_DISTANCE_V2 | 163 |
| SIRE_AGE_V2 | 148 |
| SIRE_SURFACE_DISTANCE_V1 | 129 |
| SIRE_TURN_DISTANCE_V1 | 99 |
| SIRE_VENUE_SURFACE_DISTANCE_V2 | 43 |
| SIRE_BROODMARE_SIRE_V2 | 30 |
| SIRE_FRAME_TRANSITION_V1 | 11 |

Family:

- PEDIGREE: 827
- COURSE: 655
- TRANSITION: 440

現行の過密は単一Templateだけではなく、COURSE / PEDIGREE / TRANSITIONをまたいで発生している。

## 9. Diagnosis against the original EdgeDB philosophy

### Confirmed problem

現行v0.2 STANDARDは「統計的に保持する知識カタログ」としては機能しているが、reader-facingな「市場が見落としやすい特注条件」servingとしては広すぎる。

81.9%のrunnerへPerformance +/-が付く状態は、Edgeを「稀で見落とされやすい追加情報」として使う思想と緊張する。

### The problem is not simply 2,773 rows

2,773 Performance +/- Edgeを物理削除すればよい、という結論ではない。

問題は:

1. Research / Context knowledgeとNiche Servingが同じsurfaceへ出ている
2. lower-order effectを説明した後のincremental effectを見ていないTemplateがある
3. semantic overlapが現行redundancy_groupをまたいでいる
4. 独立した+ / -軸をreaderへ構造化せず列挙している

ことである。

## 10. v0.3 design decision

v0.2は比較・rollback用にfreezeし、直接破壊しない。

v0.3はshadowとして次の順序で設計する。

1. **Context layer**
   - broad / lower-order effectを保持する
   - discovery / explanationのparentとして使う
   - 原則として「特注Edge」として前面表示しない

2. **Incremental / Residual Edge layer**
   - child / interaction条件はglobal baselineではなく適切なparent条件と比較する
   - parentで既に説明できる効果を差し引いた追加情報を検証する

3. **Market layer**
   - PerformanceとValueを引き続き分離する
   - 「走りやすい」だけで市場Edgeと呼ばない
   - market-underreflectionはValue / price residual側で別途確認する

4. **Semantic overlap layer**
   - frame_no → frame_zoneのような決定的階層
   - sire × distanceを共有するsibling群のようなlatent parent
   - literal field subsetだけではなく意味上の関係を定義する

5. **Serving / presentation**
   - 同一semantic cluster内の重複は代表evidenceへ整理する
   - 独立clusterで+ / -が残れば無理に加算せずMIXEDとして返す
   - raw evidenceは監査用に保持する

## 11. Explicit non-goals

v0.3の初期設計では以下を行わない。

- +件数 - -件数でnet scoreを作る
- CONFIRMED / SUGGESTIVE / lift / ROI / qを任意weightで加算する
- broad Edgeを一括削除する
- specificityだけでNiche判定する
- Performance-positiveをValue-positiveへ読み替える
- v0.2 servingを上書きする

## 12. Next implementation gate

次の実装単位は、既存v0.2 Registry / Feature Martを変えずに作る **v0.3 semantic parent map + incremental shadow audit** とする。

最初に少なくとも以下を定義する。

- COURSE_FRAME_V1 → COURSE_EXACT_FRAME_V2
- SIRE_DISTANCE_CONTEXT（新規Context-only parent） → SIRE_SURFACE_DISTANCE_V1
- SIRE_DISTANCE_CONTEXT → SIRE_TURN_DISTANCE_V1
- SIRE_SURFACE_DISTANCE_V1 → SIRE_VENUE_SURFACE_DISTANCE_V2

TRANSITION siblingsは独立候補として残し、統計監査なしに吸収しない。

shadow auditで「parentに対する追加効果」と「市場Value channel」を確認した後にだけ、v0.3 serving catalog候補を作る。
