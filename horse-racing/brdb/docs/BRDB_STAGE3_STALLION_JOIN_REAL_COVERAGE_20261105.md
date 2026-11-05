# BRDB 工程③ — 父・母父のマスタ結合および実データcoverage監査

Date: 2026-11-05
Status: **RESEARCH ADAPTER COMMITTED + REAL-DATA SQL AGGREGATE MEASURED / NO VERIFIED JRDB→JBIS ID CROSSWALK / NOT PRODUCTION**

## 1. 工程③の実装

- `src/brdb_stage3_feature_adapter.py`：PACI/BRDBの同一`horse_id`に対して、既存`pedigree_fact`の父・母父名、生年、JRDB公式系統コードを3条件照合。
- `tests/test_brdb_stage3_feature_adapter.py`：父と母父の経路プレフィックス、照合ガード、マスタ未登録、名前一致と個体ID一致の区別、未承認公開拒否等の10合成ケースを作成。
- 返却`lanes.sire` / `lanes.broodmare_sire`は**2つの独立した入口**。父の元経路`p`は`S+p`、母父の元経路`p`は`DS+p`とする。
- 種牡馬12件が`name+birth_year+lineage_code`と一致しても、結果は`GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY`、`person_identity_verified=false`。**JBIS IDをJRDB horse_idへ流用せず、マスタに保存した祖先経路も表示名付きの記述的観測に限定**。
- 不一致なら`GUARD_CONFLICT`（名前があるが生年/コードが異なる）、未登録なら`NOT_IN_SEED`。判定不能や候補不足は`UNKNOWN`相当であり、不適性ではない。
- `verified_ancestor_paths=[]`, `supplemental_insights=[]`, `regional_roots=[]`, `aptitude_claims=[]` を維持。重複した血統名から**クロス確定や血統適性を生成しない**。歴史的`as-of=UNVERIFIED`、`prediction_safe=false`。
- 母母`DD`経路は`NOT_ATTEMPTED_IN_STAGE3`で工程④へ引き継ぎ。父・母父のレビューを母母不足で中断しない。

## 2. 実データ調査（DuckDB 1.1.3、Parquet読取のみ）

Source: BRDB research generation `5279af0bd8226cde`、`generation/pedigree_fact.parquet`、SHA256 `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`、132,652血統収録馬。対象コホートは**birth_dateの出生年**で抽出（出走日・出走馬数ではない）。

12候補について、`sire_name + sire_birth_year + sire_line_code` または `broodmare_sire_name + broodmare_sire_birth_year + broodmare_sire_line_code` の正規完全一致を分母コホートごとに集計。`person-ID verified`は承認済みJRDB⇔JBIS crosswalkが**0件**のため全て0件。`proxy`の解決件数とは別。

| 母集団 | 馬数 | 父 proxy候補（率） | 母父 proxy候補（率） | verified individual join |
|---|---:|---:|---:|---:|
| 全収録 | 132,652 | 2,579（1.944%） | 13,533（10.202%） | 0 |
| 2015〜2024年生 | 45,428 | 0（0.000%） | 1,765（3.885%） | 0 |
| 2022〜2024年生 | 12,018 | 0（0.000%） | 98（0.815%） | 0 |

- 全収録の`Sadler's Wells`母父ラベルは**名前一致849件に対し3条件一致848件**。コード例外1件を誤結合せず`GUARD_CONFLICT`に分類。
- 2022〜2024年生12,018頭の母父proxy 98頭の内訳：Storm Cat 33 / Sunday Silence 29 / Kingmambo 13 / Forty Niner 9 / Sadler's Wells 7 / A.P. Indy 7。その他候補0。
- 2015〜2024年生45,428頭の母父proxy 1,765頭は、SS 873、Storm Cat 199、Forty Niner 178、Kingmambo 161、Tony Bin 123、Sadler's Wells 104、A.P. Indy 69、Deputy Minister 29、Northern Taste 15、Danzig 14。計1,765。
- 同一コホートにおける`父0%`は、**古い12祖先が現代馬の直接種牡馬ではないため**であり、父系の内部にそれらの血が存在しないという意味ではない。
- 2026-11-01東京5Rの8頭はこの特定の研究用`pedigree_fact`世代にhorse_id未収録であり、**実レースE2Eの父/母父coverageを算定できない**。PACIデータに問題があるという意味ではない。

## 3. 解釈とマスタ拡充方針

**この12候補だけの直接照合では、父・母父マスタとしてカバー率不足。**

従って工程③の本来の価値は、**現役種牡馬自身をマスタへ追加し、父の血統構成（S/S...）を展開するための入口を整備**することにある。拡充優先順位は出走馬の父・母父としての登場頻度、同定の容易さ、資料/経路coverage。父優先、次に母父。古い12候補の直接親名例を現在の父へ無条件に継承しない。

候補個体照合の安全条件:
1. JRDB側の`sire_name`と生年・系統、JBIS側外部ID・生年・親情報などの独立事実を監査し、正式の`identity_crosswalk`を別資料として承認。
2. 個体ID未確定なら`GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY`で止める。形だけ`verified`フラグを立てない。
3. 観測経路`S/DS`は研究用の`SOURCE_PARENT_NAME_ONLY`として保持。父/母父への一致が仮対応なら、外部で確定しているSunday Silence→Haloの父系も**対象出走馬への正式パスには昇格させない**。
4. 多年比較・条件別実績を⑦へ使う際は歴史的as-of検証・母数・重複/依存の抑制を別工程で行う。①〜③の評価を上書きしない。

## 4. 検証状態

- ローカル実行したもの：**研究用Parquetの実SQL集計とSHA256照合**。計測結果は`stage3_real_coverage.json`（ローカル監査JSON）に保持。
- GitHubへ登録したもの：研究用adapter・10ケースの回帰テスト・本監査資料。GitHub上のソース読み戻しで確認する。
- 未実施：**コミット済みPythonテストの実行、adapterによる12候補の実レースE2E、JRDB↔JBIS個体crosswalkの承認、BRDB本番組込み**。実データ集計の実行はアダプター全体のE2E PASSを意味しない。

## 5. 工程④へ

工程④で母母側を任意補完する前に、次の整備が有効：
- 現役の父・母父の高頻度種牡馬を追加し、出走馬の入口coverageを大きくする。
- 現在の研究世代の収録対象とPACI現行出走馬の世代の接続可否を監査する。
- JRDB↔外部個体を結ぶ**承認済みの同定・alias・出典表**を追加する。
- 母母側は`DD`本人を確実に同定したときだけ展開し、未確認を欠損として残す。

Production boundary: **BRDB CURRENT、旧Blood Review v0.1、⑤schema、RaceNote、PWA、新聞、本番workflowは変更しない。**
