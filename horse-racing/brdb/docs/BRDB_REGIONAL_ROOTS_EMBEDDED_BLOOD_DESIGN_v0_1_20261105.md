# BRDB ⑥地域ルーツ・⑦内包血統 補足レビュー設計 v0.1

- 日付: 2026-11-05
- 状態: **DESIGN ONLY / 未実装 / 未検証 / NOT FOR PRODUCTION**
- 目的: ⑤の総合血統レビューに、①〜④の主要な条件別観測では表現しきれない**条件付きの補足的可能性**を付与する。
- 参考正本: `BRDB_GEMINI_PEDIGREE_CLASSIFICATION_RESEARCH_NOTE_20261105.md`、`BRDB_FUTURE_APTITUDE_SIMILARITY_SEGMENT_DESIGN_v0_1.md`、`BRDB_ANCESTOR_CROSS_SIMILARITY_v0_1.md`、`BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md`。
- Gemini調査は**仮説候補**であり、原資料に個別Web URL・日時・独立検証がない。観測された因果効果・公式地域分類・統計的検証済み適性として扱わない。

## 1. ⑤との責務および優先順

**判断優先度: ①父の産駒実績 ≒ ②母父の傾向 ≒ ③父系×母父系の組合せ ＞ ④兄姉・近親 ≫ ⑥地域ルーツ・⑦内包血統。**

これは**出力・解釈の優先順位**であり、1/2/3/4/6/7の加重平均係数・確率・加点比率ではない。①〜③の内部相対重み、根拠の独立性、条件一致度は今後検証する。④は主に補強・反証の材料であり、直接の近親実績が豊富でも機械的に固定順位を逆転させない。

- ⑤はまず①〜④を根拠付きで記述する。①〜③の不足・未検証は隠さない。
- ⑥⑦は**`supplemental_insights`** として条件付きの情報を添える。血統全体の総評、`confidence`、評価順位、予想勝率を**自動的に上書き・加点しない**。
- ①〜④が不十分でも⑥⑦を観測事実として提示できる。ただし主要判断の穴埋めとして偽装しない。
- ⑥⑦と①〜④が矛盾しても両者を残す。想定例: 「同条件の父産駒実績は低調。一方、母方の米国競馬背景から別条件で変わる可能性という仮説がある。ただし当条件の実測裏付けは不足」。
- RaceNoteは受け取ったレビューを予想へ使うか判断し、BRDBで出走馬の予想印・買い目・勝率を生成しない。

## 2. 根拠の4層（混同禁止）

| 層 | 意味 | 返せる言い方 |
|---|---|---|
| `PEDIGREE_FACT` | 正式に同定した祖先ID・S/D経路・血統役割、観測時点 | 「母父に○○を確認」 |
| `REVIEWED_CLASSIFICATION` | 事前定義された出典・有効日付きの地域/系譜タグ | 「確認範囲に米国競馬系の血脈が複数」 |
| `UNVALIDATED_HYPOTHESIS` | Gemini資料等が指摘した条件適性候補 | 「道悪ダートで変わる可能性が論点」 |
| `CONDITIONALLY_VALIDATED_TREND` | 事前定義した条件・母集団で時系列検証を通過した観測傾向 | 「○○を当該位置に持つ集団は、検証期間で条件差を示した」 |

未検証仮説と検証済みの適性判断を同一statusで配信しない。`CONDITIONALLY_VALIDATED_TREND` は本設計時点では**ゼロ件**。資料からの推測で昇格させない。

## 3. ⑥ 地域ルーツ分析

### 3.1 分類体系

候補: `JP_RACING`, `US_RACING`, `EU_RACING`, `SOUTHERN_HEMISPHERE_RACING`, `UNKNOWN`。必要時は複数ラベル。`JP`等は**馬の出生地・生産地・競走国・国籍ではなく、血統分類辞書が定義した「発展した競馬環境との関係」**である。

同じNorthern Dancer系でもSadler's Wells/Storm Cat/Danzigの枝は別単位で扱う。単独祖先の原産地だけで子孫すべてのルーツを確定しない。公式JRDB系統コードと地域タグは同一ではない。

### 3.2 分類辞書の契約案

`taxonomy_version`, `taxonomy_entry_id`, `canonical_ancestor_id` または検証済み`lineage_code`, `lineage_branch_id`, `region_tag`, `basis`（競走環境に関する定義文）, `source_refs`, `effective_from`, `review_status`（`CANDIDATE`/`REVIEWED`/`REJECTED`）, `ambiguity_notes`。

- ⑥の正式タグは、独立の出典照合と辞書レビュー後にのみ `REVIEWED`。
- 複数地域ルーツがある場合はすべて保持。父側・母側を別々に示す。
- 不明な祖先を0%として計算しない。`observed_paths`、`expected_paths`、`coverage`、`unknown_paths` を返す。
- `US_RACING` の祖先が1頭だけでは「米国色が強い」としない。**強さの定量基準は未定義**であり、確認範囲に偏りがあるときは「確認できた部分に米国ルーツを含む」とのみ記述。
- 世代の近さを使う寄与度候補（例: 1/2^depth）は**記述的な観測経路の指標候補**であって遺伝割合や予測能力の確定推定ではない。祖先の繰返し・欠損・母方選択偏りで上振れする。正式な強弱ラベルとスコアは検証後に限る。

### 3.3 出力例（仮想）

`root_evidence`: `horse_id`, `side`（SIRE/MATERNAL）, `region_tag`, `supporting_ancestor_ids`, `observed_paths`, `depths`, `taxonomy_version`, `coverage`, `classification_status`, `source_refs`, `as_of_status`。

**ルーツ構成そのものは競走適性の証拠ではない。** 「米国色→渋ったダートで上昇」の文は、さらに⑥×馬場状態の独立検証が必要。

## 4. ⑦ 内包血統・祖先配置・クロス

### 4.1 検出単位

- `ancestor_horse_id`（真正のcanonical ID）
- `paths`: 父方/母方を含む`S`（父）、`D`（母）の順序列（例 `D S` = 母の父、機械値は`DS`）
- `depth`: 1..5
- `role`: SIRE / BMS / SIRE_SIDE_ANCESTOR / MATERNAL_SIDE_ANCESTOR
- `occurrences`, `cross_paths`, `max_depth`, `resolved_paths`, `expected_paths`, `completeness`
- `source_generation`, `profile_asof`, `resolution_status`

同一の固有祖先IDが2経路以上に出れば、観測できた範囲でのクロス事実（例: `3×4`）を返す。`no observed cross` は祖先が全枝解決されない限り「クロスなし」を意味しない。馬名の部分一致、未確認別表記、同一系統コードを同一祖先IDの代わりに使わない。

既存の `src/brdb_ancestor_graph.py` / `src/brdb_ancestor_evidence.py` のgraph/path/cross APIを再利用。**5代全経路が完全に解決していない**ことは明示し、深さ1〜2の既知血統だけで始める。

### 4.2 血脈適性仮説辞書

Gemini資料にある候補は `UNVALIDATED_HYPOTHESIS` として管理する。例:
- Halo（母父などの**配置指定**）×中山・阪神・小回り、機敏さ。
- Storm Cat（父/BMS/祖先など配置区別）×初速、ダート/高速芝。
- トニービン（経路指定）×東京・広いコース、左回り、持続力。
- Danzig（経路指定）×1200〜1600m、道悪・洋芝。

辞書は `hypothesis_id`, `ancestor_id`, `allowed_paths_or_role`, `target_condition_predicate`, `claim_text`, `source_refs`, `status`, `tested_cohorts`, `valid_from` を保持。**「Halo持ち」という曖昧な全馬横断検索は禁止**。同一固有祖先の別経路・別世代を混ぜない。

## 5. 条件文生成のゲート

⑥⑦のレビュー文は最長でも**1〜2件の短い補足**を目安とし、①〜④の主文より後ろに表示。候補が多い場合は検証されたもの、対象条件が一致するもの、欠損が少ないものを優先する。ただし、それを予測重みへ変換しない。

| 状況 | `insight_status` | 許容文例 |
|---|---|---|
| 祖先確認 + taxonomy確認のみ | `FACT_ONLY` | 「母父に○○を確認。条件適性への影響は未検証。」 |
| 仮説辞書に一致、適性検証なし | `HYPOTHESIS_ONLY` | 「母父○○の小回り適性は検証候補。今回の中山での上積みは未確認。」 |
| 条件別の独立検証あり | `OBSERVED_CONDITION_TREND` | 「同配置の馬の検証期間では中山○○条件で傾向が観測された。対象馬への適用は不確実。」 |
| 系図が未解決 | `UNKNOWN` | 「母方3〜5代の祖先未確認につき、内包血統の傾向は判断保留。」 |
| 対象条件・馬場が未確定 | `CONDITION_UNVERIFIED` | 「ダート重・不良なら検証対象となる仮説だが、現在の馬場条件は未確定。」 |

- **「米国色が強く渋ったダートなら上昇可能性あり」**という希望表現は、(a)米国地域タグがレビュー済み、(b)「強い」の計算基準が承認済み、(c)ダート重/不良・対象条件が明示され、(d)時点安全な条件別成績で追加価値を検証、という要件が揃った場合の**限定付き文面**。それ以前は「米国競馬系のルーツを確認。ただし重いダートでの上昇は仮説段階。」と返す。
- **「母父○○なので今回の中山で小回り適性が発揮されるかも」**は、母父が確定し、その配置×中山の検証とコース形態辞書（小回り判定）が確認できた場合のみ条件付きで許容。未検証なら「母父○○は小回り適性の仮説と関連づけられるが、中山での上積みは未検証」。
- `going`（良/稍重/重/不良）、`course_geometry`（小回り等）、`turn_direction` は対象レースのsourceと事前承認済みコース辞書で照合。**競馬場名だけから一律のコース形状や馬場を推定しない**。
- ①〜④のサンプル不足、`AS_OF_UNVERIFIED` は⑥⑦によって帳消しにされない。

## 6. 条件別データ検証計画

探索と検証を分ける。⑥⑦を「数値上有利」と言えるようにするには、次を満たす。

1. 祖先経路・地域タグを**対象レースより前**に確定できる血統情報から生成する（現在のsnapshotで過去を回想しない）。
2. 血統条件に一致する過去馬を定義し、①〜④と同じ実出走定義、芝ダの混入防止、距離/競馬場/馬場・クラス・年を揃えた比較母集団を作る。
3. `horse_id`単位の重複出走と、同一父の産駒への集中、複数検定による偶然の好成績を測定。標本不足なら `INSUFFICIENT_EVIDENCE`。
4. 登録した仮説条件で**時系列ホールドアウト**を実施。人気・馬齢・クラス・競走条件などによる差を検討する。
5. ①〜④がすでに説明する情報に対して、⑥⑦で**追加の説明価値があるか**を検証する。①〜④と同じ血統事実を別表現で重複加点しない。
6. 条件に合うものだけ後から拾った場合は探索的結果のまま。外部出典が存在しても観測的な適性差の再現検証は別途必要。

## 7. ⑤ candidateへの受け渡し契約案（未実装）

既存`brdb-integrated-blood-review-v0.2-candidate`の4必須componentを**破壊的に変更しない**。正式採用時は**別の互換バージョン**を定義し、以下をoptional追加する。

```json
{
  "supplemental_insights": [
    {
      "insight_id": "ROOTS-001",
      "source_component": "regional_roots",
      "insight_status": "HYPOTHESIS_ONLY",
      "claim": "確認済みの母方血統に米国競馬系のルーツがある。道悪ダートでの上昇は未検証。",
      "ancestor_paths": ["DS", "DSS"],
      "evidence_ids": ["FACT-DS", "FACT-DSS"],
      "target_condition": {"surface": "dirt", "going": "muddy"},
      "coverage_status": "PARTIAL",
      "can_change_primary_conclusion": false,
      "has_validated_incremental_effect": false
    }
  ]
}
```

このJSONは**将来拡張のサンプル**であり、現行schemaで受理される完成仕様ではない。将来の`regional_roots`・`embedded_ancestry`の可用性は個別に`AVAILABLE`/`PARTIAL`/`UNKNOWN`/`NOT_IMPLEMENTED`/`AS_OF_UNVERIFIED`を持つ。注目血統の不在を証明できるのは、その対象の探索範囲を全て確認した場合のみ。

**設計時点では⑥⑦を既存の⑤`factors.positive`/`negative`へ追加せず、補足チャンネルに隔離する。** 将来の独立検証後に表現を昇格できるが、①〜④の主評価を上書きする採点は今回許可しない。

## 8. 段階導入・テスト

- **D1: taxonomyと仮説辞書（設計・sourceレビュー）**。未検証Gemini候補は`CANDIDATE`のまま。公式系統マスターとの突合、競走環境ラベルの定義、単一祖先からの過度な地域推定の防止。
- **D2: 祖先の位置検出**。canonical IDとS/Dパス、同一祖先の複数配置とクロス、部分グラフの`UNKNOWN`、父系/BMS経路の区別を検証。
- **D3: ⑥地域タイプと⑦祖先配置の条件別集計**。同一芝ダ・競馬場・距離帯、可能なら馬場状態・小回り/左回り、サンプルと信頼区間、時点条件で実測。実測なしは仮説のみ。
- **D4: ⑤へnon-scoring補足出力を接続**。全馬coverage、説明根拠ID、最大表示件数、重複抑制、主判断不変更、RaceNote未変更を回帰検証。
- **D5:時系列OOSと追加説明価値を検証**し、条件付きの言い回しを承認。追加説明価値が見つからなければ`FACT_ONLY`で残す。

必須テスト: 1) 祖先未解決は0%・不在にしない、2) 母父`DS`と遠祖を分離、3) 同じIDの2経路をクロスとする、4) 地域型タグ≠産地、5) 複数地域を保持、6) 条件`going`不明で道悪適性文を断定しない、7) ①〜④の結論・信頼度を⑥⑦が上書きしない、8) 時点漏洩を拒否、9) 未検証仮説を`VALIDATED`へ昇格させない、10) 同一源泉の重複を独立根拠と誤認しない。

## 9. 今回変更しないもの

⑥⑦の実行コード、正式taxonomy、仮説からの適性判断、⑤の実装済み出力JSON Schema、`brdb-review-v0.1`、BRDB CURRENT、RaceNote、PWA、Newspaper、GitHub Actionsの公開workflow。これらは後続開発で個別に受入検証する。

**本書の承認範囲は⑥⑦の設計方針のみ。**
