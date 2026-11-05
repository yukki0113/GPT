# BRDB D1 — 地域ルーツ・内包血統候補辞書 v0.1

Status: **CANDIDATE CATALOG CREATED / NO APPROVED MAPPINGS / NO VALIDATED APTITUDE / NO RUNTIME INTERPRETATION**
Date: 2026-11-05
Owner: `horse-racing/brdb/`

## 0. 今回の判断

ユーザーが指定した **①〜③ > ④ >> ⑥⑦** をレビュー文の優先関係として維持。⑥⑦は補足コメント枠であり主評価の加点・予想ランク変更に使わない。

Geminiの資料は`BRDB_GEMINI_PEDIGREE_CLASSIFICATION_RESEARCH_NOTE_20261105.md`で保管済み。しかし**個別Web出典URL・配信時点・検証された公式血統コードの対応一覧がない**ため、Geminiによる例示をJRDBのofficial lineage masterへ自動適用しない。

## 1. D1作成物

| 正本 | 用途 |
|---|---|
| `taxonomy/regional_roots_candidate_v0_1.json` | ⑥日本/米国/欧州/南半球の候補分類4件 |
| `taxonomy/embedded_blood_hypotheses_candidate_v0_1.json` | ⑦Halo、Storm Cat、トニービン、Danzig＋ユーザー例の米国ルーツ×道悪ダートの仮説5件 |
| `src/brdb_d1_catalog.py` | D1辞書の静的整合性・承認状態・曖昧な祖先経路の拒否 |
| `tests/test_brdb_d1_catalog.py` | 候補辞書保護の合成テスト8ケース |

D1段階の確定値：`regional definitions=4`, `hypotheses=5`, `official lineage mappings=0`, `validated aptitudes=0`。

**地域概念や血脈名は調査資料の候補であって、馬の出生国や公式血統IDではない**。辞書が空対応であることは欠陥でなく、誤対応から推測を増幅させないための安全設計。

## 2. ⑥ 辞書の仕様

`region_tag` は `JP_RACING`, `US_RACING`, `EU_RACING`, `SOUTHERN_HEMISPHERE_RACING`。複数タグが可能で、未確認の場合は分類を保留する。

各項目は `definition`, `examples_from_gemini`, `hypothesized_conditions`, `status=CANDIDATE` を含む。ただし辞書の`mappings=[]`であり、**JRDB `sire_line_code`や`broodmare_sire_line_code`の任意の値に地域ラベルを割り当てない**。

公式コードとの突合で必要な追加資料：既存`lineage_code_master_v0_1.csv`の内容・各コードの公式父系名、検証済みの系統枝、独立した地域分類の根拠、適用開始日とtaxonomy version。GitHub上で名称参照は確認できたが、本作業ではその実ファイルを参照・検証できなかったため**対応0のまま**とする。

1系統から「米国色が強い」を生成したり、国籍・出生地を競馬環境ルーツへ読み替えたりすることは不可。将来の複数地域・未解決祖先のcoverage設計は[⑥⑦設計書](BRDB_REGIONAL_ROOTS_EMBEDDED_BLOOD_DESIGN_v0_1_20261105.md)に従う。

## 3. ⑦ 辞書の仕様

5つの候補は**統計的な適性仮説**であり、実際のレース適性を確定しない。

| 仮説ID | 配置 | 例示条件 | 状態 |
|---|---|---|---|
| HYP-HALO-BMS-NAKAYAMA | Haloを母父`DS`に持つ | 中山、小回り特性はコース辞書検証が必要 | CANDIDATE |
| HYP-STORMCAT-BMS-DIRT | Storm Catを母父`DS`に持つ | ダート | CANDIDATE |
| HYP-TONIBIN-ANCESTOR-TOKYO | トニービンを確認済み祖先に持つ（経路別集計を要する） | 東京芝 | CANDIDATE |
| HYP-DANZIG-ANCESTOR-MILE | Danzigを確認済み祖先に持つ（経路別集計を要する） | 1200〜1600m | CANDIDATE |
| HYP-USROOT-WET-DIRT | レビュー済み地域構成 | 重・不良ダート | CANDIDATE |

- 各仮説`ancestor_id=null`, `source_refs`はGemini調査メモ、`effective_from=null`, `validated_cohorts=[]`, `can_assert_aptitude=false`。
- 母父に直接いる`DS`と、母側別経路`DSS`等は別。任意祖先の仮説は`allowed_paths=[]`のままで、D2が確実なIDと具体的な経路を検出するまで実行不能。
- `HYP-USROOT-WET-DIRT`は地域構成に関する仮説であり特定祖先IDとは別の分類。独立の検証済み地域タグが必要。
- `course_geometry=SMALL_TURNS_VERIFICATION_REQUIRED`はコース形状が確認できたという意味ではなく未検証のプレースホルダー。
- 出典メモが「候補」と述べているだけなので、個別URL・公式文書・条件別実測なしに`REVIEWED`/確定扱いへ昇格不可。

## 4. 承認・拡張ゲート

1. JRDB公式コード・系統ラベル・異表記の**正本ファイルを特定**しSHAとバージョンを保存。
2. 候補の血脈ごとにcanonical ancestor horse_id（または検証済みlineage code）を独立に照合。**馬名だけで結合しない**。
3. `mapping`候補として出典URL、対象範囲、親系と枝の差、taxonomy有効開始日を持たせ、別レビューを通過して初めて正式な辞書に移す。D1候補は研究履歴として不変。
4. 血統配置・祖先の経路はD2。未解決経路を「不在」としない。
5. 地域/血脈と条件適性の歴史的統計・時系列検証はD3/D5。適性仮説を直接採点することは禁止。
6. ⑤への接続は後続の互換契約と専用`supplemental_insights`に限定し、①〜④のsummary/confidenceを上書きしない。

## 5. 検証方法・制約

```bash
python horse-racing/brdb/src/brdb_d1_catalog.py \
 --regions horse-racing/brdb/taxonomy/regional_roots_candidate_v0_1.json \
 --hypotheses horse-racing/brdb/taxonomy/embedded_blood_hypotheses_candidate_v0_1.json

python -m unittest discover -s horse-racing/brdb/tests -p test_brdb_d1_catalog.py -v
```

候補辞書は配信済みのJRDB公式taxonomyではない。**コード上での承認拒否は、外部出典の真偽を証明するものではない。** 本作業ではGitHub登録と読み戻しで正本確認するが、完全なCI/ローカルPythonテスト実行は別途結果を示す。

BRDB CURRENT、Blood Review v0.1、⑤統合JSON schema、RaceNote、PWA、新聞、本番workflowは更新しない。
