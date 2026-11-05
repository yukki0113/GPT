# BRDB D2 — 12内包血統候補の祖先ID・経路充足率実測

Date: 2026-11-05  
Status: **LOCAL REAL-PARQUET AUDIT COMPLETED / COVERAGE MEASURED / PERSON-ID CROSSWALK UNAVAILABLE / RESEARCH ONLY**

## 0. 結論

- **GPTローカル実行で測定可能**。Work/CodexまたはGitHub Actionsへの代行切替は不要。
- JRDB研究用BRDB世代 `5279af0bd8226cde` の実際の `pedigree_fact.parquet` **132,652行**、`parent_relation.parquet` **397,956行**を使用。ZIP内manifestの両SHA-256と解凍したParquetが一致。
- **12個別祖先（Storm Cat、Tony Bin、Danzig、Sadler's Wells、Kingmambo、Roberto、A.P. Indy、Deputy Minister、Northern Taste、Forty Niner、Halo、Sunday Silence）は、いずれも研究用`pedigree_fact`に馬名完全一致する独立したprofileが存在しない**。従ってcanonical `ancestor_horse_id`の一意な確証は0件。
- 12候補の**5代祖先ID一致率は「0%」ではなく「測定不能／クロスウォーク未整備」**。非一致・血統不存在の意味ではない。
- 一方、父または母父の`sire_name`・`broodmare_sire_name`への完全一致は取得できる。これは**直接関係名の観測代理**であって、3〜5代のID-based祖先検出ではない。
- D3に向けて必要なのは、旧世代の公式血統個体IDを独立した出典で確認し、既存JRDB `horse_id`と**承認済みの一意crosswalk**で対応づけること。名前だけで人物IDを生成・推定してはならない。

## 1. 実測ソース・母集団・実行

- archive: `issue2223_research_generation_v02_5279af0bd8226cde_20261030.zip`
- generation: `5279af0bd8226cde`
- source: `generation/pedigree_fact.parquet`, `generation/parent_relation.parquet`
- 実行: CPython 3.13 + DuckDB 1.1.3、ローカルParquet read-only。
- pedigree / relation両ファイルのSHA-256は研究世代`manifest.json`の`output_sha256`に一致。
- 母集団: `birth_date`の年が2022, 2023, 2024である**血統マスター収録馬**。これは**その年の出走馬・PACI登録馬ではない**。重複horse_idはマスターのunique keyで識別。
- 別途2026-11-01東京5R・8頭を照会したが、**この研究世代には対象horse_idが0件収録**。8頭の0%は祖先未解決率を意味せず、まず対象馬本体がsource generation外。実レース適用可否は別途最新世代の突合が必要。
- 条件は当該静的研究世代の登録済み事実であり、**歴史的に各馬の出走前へ再現可能かは未確認**。`prediction_safe=false`。

## 2. ID経路の世代別充足率

父・母の`parent_relation`に`RESOLVED_EXACT`/`RESOLVED_ALIAS`と`resolved_parent_horse_id`がある場合だけ`S`/`D`で再帰到達。broodmare_sireを第三の親エッジとしては扱わない。欠損した枝のそれより下は未解決とする。

| 出生年 | 収録馬 | 第1世代 | 第2世代 | 第3世代 | 第4世代 | 第5世代 |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 4,920 | 7,163/9,840 = **72.79%** | 8,967/19,680 = **45.56%** | 2,833/39,360 = **7.20%** | 27/78,720 = **0.03%** | 0/157,440 = **0%** |
| 2023 | 4,903 | 7,223/9,806 = **73.66%** | 9,205/19,612 = **46.94%** | 3,392/39,224 = **8.65%** | 64/78,448 = **0.08%** | 0/156,896 = **0%** |
| 2024 | 2,195 | 3,181/4,390 = **72.46%** | 4,175/8,780 = **47.55%** | 2,001/17,560 = **11.40%** | 108/35,120 = **0.31%** | 0/70,240 = **0%** |
| **合計** | **12,018** | **17,567/24,036 = 73.09%** | **22,347/48,072 = 46.49%** | **8,226/96,144 = 8.56%** | **199/192,288 = 0.10%** | **0/384,576 = 0%** |

ここで解決率は`resolved_parent_horse_id`で到達した**経路スロット数÷その世代の理論経路スロット数**。例えば同じ祖先への2つの別経路は2スロットと数える。**12候補に一致した馬の割合ではない**。

全スロット解決馬数（2024生まれ2,195頭に限定）: 深さ1が1,176頭、深さ2が206頭、深さ3が1頭、深さ4・5は0頭。部分グラフと完全グラフを分ける必要がある。

## 3. 12候補 — 母父の名前完全一致の観測数

集計対象は2022〜2024出生馬12,018頭。指定した人物名と`broodmare_sire_name`が**完全一致**し、馬ID単位で数えた件数。父名`sire_name`についてはこの期間の12候補全て0頭。

| 優先 | 個別祖先ラベル | 2022出生馬 | 2023出生馬 | 2024出生馬 | 3年合計 | 正式ID一致 |
|---|---|---:|---:|---:|---:|---|
| A | Storm Cat（ストームキャット） | 17 | 11 | 5 | **33** | 未解決 |
| A | Tony Bin（トニービン） | 0 | 0 | 0 | **0** | 未解決 |
| A | Danzig（ダンジグ） | 0 | 0 | 0 | **0** | 未解決 |
| A | Sadler's Wells（サドラーズウェルズ） | 5 | 1 | 1 | **7** | 未解決 |
| A | Kingmambo（キングマンボ） | 10 | 2 | 1 | **13** | 未解決 |
| A | Roberto（ロベルト） | 0 | 0 | 0 | **0** | 未解決 |
| B | A.P. Indy（エーピーインディ） | 3 | 3 | 1 | **7** | 未解決 |
| B | Deputy Minister（デピュティミニスター） | 0 | 0 | 0 | **0** | 未解決 |
| B | Northern Taste（ノーザンテースト） | 0 | 0 | 0 | **0** | 未解決 |
| B | Forty Niner（フォーティナイナー） | 4 | 4 | 1 | **9** | 未解決 |
| B | Halo（ヘイロー） | 0 | 0 | 0 | **0** | 未解決 |
| B | Sunday Silence（サンデーサイレンス） | 16 | 11 | 2 | **29** | 未解決 |

**母父名観測≠祖先ID検出≠適性検証**。母父が文字列で直接記録されても、`parent_relation.role=broodmare_sire`の当該個別馬IDは未解決。特に0頭の祖先が4代前の血統内に存在しないと判断してはならない。

## 4. 12候補と研究用parent relationの突合

12候補全てについて`pedigree_fact.horse_name = exact_label`の該当馬は**0件**、`parent_relation.parent_name=exact_label`における`RESOLVED_EXACT`/`RESOLVED_ALIAS`数は**0件**。ただし未解決名前行はあり、旧血統名の記録自体がないわけではない。

例:
- 母父Storm Cat: 773全マスター行、個別BMS ID確定0。
- 母父Tony Bin: 1,938全マスター行、個別BMS ID確定0。
- 母父Danzig: 654全マスター行、個別BMS ID確定0。
- 母父Sunday Silence: 4,665全マスター行、個別BMS ID確定0。

**JRDB公式系統コード（例: Storm Bird系1108）をStorm Cat本人の`horse_id`代替にしてはいけない**。古い種牡馬の出生・登録年が研究用`pedigree_fact`に含まれないことが主要ボトルネック。

## 5. 再現・改善の次段階

1. 正規ソースJRDBの追加公式UKC・祖先固有ID・登録データの権利/時点を確認し、12馬について一意な外部source IDと `JRDB horse_id`のapproved crosswalkを作る。独立IDが提供されない場合は**名前ベースの母父観測を`DIRECT_BMS_NAME_OBSERVED`として補助情報に限定**する。
2. 2026対象馬のプロフィール自体が研究世代に0件だったので、2026 PACI UKC等のsource dateに対応した現在世代（未登録に限り）と連結する正規経路を評価。ただし現行BRDB CURRENTを黙って変更しない。
3. 3〜5代の完全経路が限られるため、完全な内包血統検出はD3の主要前提にできない。適用対象を`DS`等の**直接名前観測**、または出所と同定が厳密な祖先ID・経路に限定する。
4. 12候補の検証優先はA/Bラベルに固執しない。**同定可能性・観測母数・情報の追加価値**で再計画。0という名前観測数は不適性ではなく、この母集団に限った名義直接例の不在。
5. 今回の結果は`AS_OF_UNVERIFIED` / `prediction_safe=false`、⑤の加点・出力へは未接続。①〜③ ＞ ④ ≫ ⑥⑦を維持する。

## 6. 検証事実と限界

- ローカルduckdb 1.1.3で両Parquetを直接照会し、SHA一致・レコード数を監査。
- 2〜5代の理論分母は`N*2^depth`。親子解決statusがあるエッジのみ再帰探索した。
- 別途監査用JSONを保存し、`cohorts`, `candidates`, `source_sha256`, `manifest_sha256_matches`などを含む。
- 参照元にhistorical availabilityを保証する全時点の祖先系図はない。**このレポートは静的研究世代のcoverage測定であり、未来情報を含まない予測機能ではない。**
