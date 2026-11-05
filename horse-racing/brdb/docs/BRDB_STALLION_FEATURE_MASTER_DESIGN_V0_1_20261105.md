# BRDB 6工程・①種牡馬血統特徴マスタ設計 v0.1

Date: 2026-11-05  
Status: **DESIGN / RESEARCH CANDIDATE — NOT APPLIED TO CURRENT**

## 1. 目的と決定済み優先度

ユーザー方針: **父および母父を必須の分析起点**とし、母母ラインはデータが取れれば付記する非必須拡張。
総合血統レビューの優先度は **①父産駒 ≒ ②母父 ≒ ③父系×母父系 ＞ ④兄姉・近親 ≫ ⑥地域ルーツ・⑦内包血統**。⑥⑦は`supplemental_insights`専用で主判断を加点・上書きしない。

採用する実装順:
1. 種牡馬・血統特徴マスタの定義と運用境界 (**本書とSQL候補**)
2. 12候補の個別祖先情報と`S/D`経路を出典付きで登録
3. PACI/JRDB→BRDBの父・母父を起点に血統特徴を展開・凍結
4. 母母ラインの解決（可能な範囲のみ、欠損ならUNKNOWN）
5. D3: 条件別実績検証
6. D4: ⑤の補足レビュー接続

## 2. データ分離

`schema/brdb_stallion_feature_master_candidate_v0_1.sql` は本番DDLではなく、研究用の**独立提案SQL**。実際のBRDBの`lineage_code_master`を参照する前提で、以下を保持:

| テーブル | 目的 |
|---|---|
| `stallion_subject_candidate` | 種牡馬・祖先の**個体同定**。内部`subject_key`と公式JRDB`horse_id`は別。外部出典と状態を保存 |
| `stallion_official_line_candidate` | JRDBの**公式系統コード**へのリンク。公式コードを再分類・再採番しない |
| `stallion_ancestor_path_candidate` | 個体→祖先の1経路1行。S=父/D=母、深度1..5、確認済みの固有祖先だけ |
| `stallion_regional_root_candidate` | 日本/米国/欧州/南半球の競馬的ルーツ候補。出生国ではない。複数タグを許容 |
| `stallion_feature_snapshot_candidate` | 世代・coverage・as-of・`prediction_safe=false`を保持 |

**内部subject_keyは交差参照用のキー**であって、JRDBの血統登録番号ではない。発行ルールと独立出典の一意性検査を確定するまで、古い有名種牡馬のIDを推測登録しない。
同じ名前の複数馬や、異名同馬は明示的な監査済みalias・複数独立ガードで確認する。表記一致だけで統合しない。

公式系統コードは父・母父に付いたJRDB正本`sire_line_code` / `broodmare_sire_line_code` を優先。**系統コードは祖先個体IDでも出生国でもない**。Storm Bird系(1108)はStorm Cat本人という意味ではなく、Halo系(1206)はSunday Silence本人という意味ではない。

## 3. 出走馬への展開契約

既存`pedigree_fact`またはPACIの`horse_id`の出走馬情報（正本のプロファイル日付付き）から:

- **父起点**: `sire_name` + `sire_birth_year` + `sire_line_code`等を独立ガードに使い、正式な個体リンクを検証する。解決した種牡馬マスタの内包経路`p`には `S+p` を接頭する。
- **母父起点**: `broodmare_sire_name` + `broodmare_sire_birth_year` + `broodmare_sire_line_code`等を独立ガードに使う。解決した種牡馬マスタの内包経路`p`には `DS+p` を接頭する。
- **母母起点**: `parent_relation.role=dam`の確認済み母個体から `DD` をたどる。母母本人が未解決なら、その先はUNKNOWN。母父の展開結果で母母経路を補完したことにしない。
- **重複経路**: 同一の承認済み祖先個体IDが複数の完全経路に現れた場合だけ観測クロスとする。異なるsource IDは監査済みcrosswalkなしに同一視しない。
- **未解決**: マスタ個体が未同定、祖先パス未確認、ソースに欠損がある場合は`UNKNOWN`。欠損を「存在しない」「血量0」「不適性」にしない。
- **深さ制限**: 展開後の`S+p`/`DS+p`長さが5を超えたものは削除ではなく「評価範囲外」としてcoverageへ記録。二重の祖先情報をクロス・独立根拠として重複計上しない。

**重要な構造的制約**: 種牡馬のマスタに確認された`DS`（その種牡馬の母父）がある場合、父起点では`SDS`、母父起点では`DSDS`。父の血統経路と母父の血統経路は同じ経路にはならない。母母側は`DD`に続く独立経路であり、母父の情報からは復元できない。

## 4. 「DBを引くためにDBを引く」への対処

```text
JRDB事実・公式系統マスター　　外部出典により確認済みの種牡馬・祖先マスタ
               \                /
                \              /
                BRDB研究用feature generation
                    │  source SHA + taxonomy version固定
                    ├─ 父特徴（S...）
                    ├─ 母父特徴（DS...）
                    └─ 母母特徴（DD...）optional/UNKNOWN
                    ↓
         ①〜④の別根拠 + ⑥⑦の補足候補
                    ↓
               ⑤統合レビュー
                    ↓
          RaceNote / PWA（完成JSONのみ）
```

マスタの検索・結合は**世代生成時**に行う。RaceNote/PWAのAPIリクエストごとに複数の内部DBを巡回しない。`generation_id`/`schema_version`/`taxonomy_version`/`as_of`とSHAを固定して同条件リプレイ可能にする。

## 5. source/検証・研究用ゲート

- JRDB正本コードは`lineage_code_master.parquet`の同一世代で整合を確認。誤記/複数コード観測は別監査。公式コードを国ルーツへ即時変換しない。
- 祖先個体`horse_id`未収録の場合、外部の確認済みIDは`identity_source_record_key`に置き、内部キーと区別。外部ID=JRDB IDとして流用しない。
- 公式固有IDがない場合は`PENDING`か`EXTERNAL_VERIFIED`のガード済み状態を保持し、**未承認名義だけの祖先経路登録を禁止**。
- ancestor pathの独立出典、対象馬との関係、各エッジと出典版を保存。1件の血統表で全世代の観測事実として使う場合でも、その表の有効日と検証範囲を残す。
- 歴史的レース前に情報が存在した保証は**単純なプロフィール日付だけでは成立しない**。元資料のeffective date/source観測時点と時系列再演を検証するまで`AS_OF_UNVERIFIED`, `prediction_safe=false`。
- 種牡馬マスタから来た⑥⑦の属性は、**仮説ではなく事実・分類の裏付けを持つこと**と、**その属性に対応する条件適性が証明済みであること**を別々に扱う。血統ルーツだけで「道悪得意」などと断定しない。
- 最初の受入は父・母父の母集団coverageを必須指標として計測。母母ラインの欠損を全馬レビューの失敗条件としない。

## 6. 次段階の受入条件

**②**: 12候補のID・出典が確定した場合のみ実際の祖先経路を登録し、未同定候補は残件として管理。父／母父のマスタcoverageを最優先で報告。**③**: 既存`parent_relation`と重複解決しないよう出所とidentity guardを一致させ、S/DSの接頭経路・時点・衝突をテスト。**④**: 母母側を任意で追加、未解決はUNKNOWN。**⑤⑥**: 条件別のout-of-sample検証と⑤のsupplemental contract整合後のみ外部利用を検討。

従来の`brdb-review-v0.1`、BRDB CURRENT、RaceNote、PWA、Newspaper、本番workflowは本工程で変更しない。
