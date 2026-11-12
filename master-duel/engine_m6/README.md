> **2026-11-12 M6-5C（所持汎用を使ったMAIN/EX再構成）初版**：`recompose.py`はM6-5AのSHA一致DB候補と役割注釈・M6-5B素材レビューを入力に、テーマCOREを先に置き、所持済み汎用札でMAIN40+へ仕上げ、EXを15枠内で再編し、純/出張/混合を別案で生成。所持UR上限、STRICT_NO_UR、必要出張パーツ、素材未証明のEX、自動補完禁止を検査。private現在Gen5では《灰流うらら》3/《無限泡影》3/《トロイメア・フェニックス》1を独立read-only確認。**本段階は構造ヒューリスティックであり、実データでの全工程自動構築・カード効果成立や最新規制はM6-6/7で確認する**。[M6-5C監査](../docs/M6_5C_OWNED_STAPLE_RECOMPOSITION_AUDIT_20261112.md)。

> **2026-11-12 M6-5B初版**：`effect_review.py`はcurrent SQLite raw SHAと日本語効果本文SHAをピンして素材/必要MAIN・EX/出張依存を根拠付き確認。`material_screen.py`はレベル4×2/異名2体LINK等を候補の盤面証拠と照合するが、ゲーム上の召喚成立とロック無矛盾は断定しない。private独立監査では軍貫UR0 EX7の補強候補として所持済みの非教師SR汎用LINKを確認（カード別所持はprivateのみ）。M6-5CでMAIN/EX自動再組立と所持汎用最終調整が必要。[M6-5B監査](../docs/M6_5B_EFFECT_MATERIAL_ENGINE_AUDIT_20261112.md)。

> **M6-5A追加：教師外カードを実際に候補へ組み直す機能**：`engine_m6/rebuild.py`で、SHAピンの`discovery.py`検索結果（教師外のテーマ低レア・汎用・所持出張）から出典付き`ASSEMBLED`候補を組み立てる。所持汎用は所持数超過を拒否、MAIN/EX構造と出典を再検証する。実装済みは明示候補選択に対する構造処理であり、効果・ロック・展開の自動的な相性判断と最適化はM6-5B/Cの範囲。[M6-5A監査](../docs/M6_5A_RECONSTRUCTION_AUDIT_20261112.md)。

> **2026-11-12 M6-5A 構築ロジック再設計（探索基盤・思考ゲート初版）**：ユーザーが目指す「低レアテーマ再構築＋所持済み汎用・出張で実戦仕様に締める」を優先するよう工程を改訂。`discovery.py`でSHA確認済みprivateカード正本の名前/属性/種族/レベル/ランク/リンク/所持済み絞込み、`reasoning.py`で9段階の探索証跡ゲートと純/出張/混合の比較・MAIN/EX再検討を要求する。EX7を単に完成とは判定せず、根拠付き探索結果がなければBLOCKED。**現時点では探索器と検査器の初版であり、自動的な効果判定・新規テーマ混合・MAIN/EX再構築はM6-5B/Cに残る**。[基本設計](../docs/M6_5A_DECK_RECONSTRUCTION_DESIGN_20261112.md)。

> **2026-11-11 M6-5完了**：`report.py`に所持台帳全件（135行）採否の根拠付き比較とEX未使用枠の監査を追加。`proposal_store.py`でSHAピン/外部期待SHA検証付きの不変ZIP+manifestをprivate保存（独立読戻し一致）。軍貫UR0版はEX7（空き8）で、元記事との差8枚はUR7/SR1。SR《希望皇ホープ・ダブル》もMAIN《ダブル・アップ・チャンス》と他のホープXyzが現案にはないため補強保留。所持4枚を認めるM6-4回帰修正も反映。**完成推薦・実データの全工程統合はM6-6**。[M6-5監査](../docs/M6_5_COMPARISON_PRIVATE_PROPOSAL_AUDIT_20261111.md)。

> **2026-11-11 M6-4受入**：`evaluate.py`で原本SHAを照合したread-only SQLiteの構造候補評価を実装。M2所持UNKNOWNの必要枚数上下限、4通貨別CP、三つのUR0ゲート、M3の未検証禁止制限候補と正式規制の分離、EX未使用枠を返す。private軍貫2案の**独立ソース監査**を保存し、UR0案はUR追加0、ただしEX7/15・SR以下と中核/現行規制/CP残高は未確定。新コードのprivate一気通貫テストはM6-6。[M6-4監査](../docs/M6_4_COST_REGULATION_EVALUATION_AUDIT_20261111.md)。次はM6-5比較・EX補強調査・不採用理由監査。

> **2026-11-11 M6-3受入**：`assemble.py`でM5-CレシピとUR0低コスト仮案をMAIN40〜60/EX0〜15の根拠付き構造候補へ変換。記事40宣言/可視39を拒否し、明示編集は別`ASSEMBLED`版と理由で記録。探索上限、同一候補重複、除外/要求カード、未検証出張の自動採用禁止を合成回帰。private C5を別プログラムで独立監査：軍貫MAIN40/EX15とUR0仮案MAIN40/EX7の2件構造PASS、イビルツイン39/40はBLOCKED。現行MD規制/所有/CP/必須コアはM6-4以降。[監査](../docs/M6_3_ASSEMBLY_AUDIT_20261111.md)。

> **2026-11-11 M6-2候補プール受入**：`candidate_pool.py`でM5-C掲載カード/UR0代替候補/C2展開経路をSHA参照付きで収集、`dependency.py`で出張依存・競合・共有カード・代替・EX下界・任意ロックを検査。`m5_inputs.py`でM5-A/Bのprivate旧索引をread-only・SHA付き受入。両索引は古いGen3由来なので`STALE_SOURCE_GENERATION`、現行Gen5の確定サポートではない。C5 5テーマのprivate集計を別監査し、未確認中核はUNKNOWNに維持。**完成レシピ・規制/所有/CP判定は未着手**。[M6-2監査](../docs/M6_2_CANDIDATE_POOL_AUDIT_20261111.md)。次はM6-3。

# M6 — 制約付きデッキ候補生成

## M6-0（2026-11-11）入出力契約・Fail-closed基盤

[M6基本設計](../docs/M6_DECK_GENERATION_BASIC_DESIGN_20261111.md) に基づく **契約検証のみ**。現時点で自動候補生成、Driveへのアクセス、所持全件SQL取得、規制判定、カード生成/CP額算定、ユーザーのデッキ上書きは行わない。

- `schema.py`：`validate_request`、`validate_source_pins`、`validate_inventory_audit`、`validate_candidate`、`validate_evaluation` を提供。厳格な必須フィールド、SHA形式、世代整合、所有UNKNOWNとKNOWN_ZERO、登録済み全件の意思決定、MAIN/EX・各カード3枚・中核カード・採用理由・評価状態を検査。
- `inputs.py`：`request_from_interpretation`は構造化したユーザー意図を受け、既定`LOW_RARITY_CORE`と明示`STRICT_NO_UR`を区別。自由文を誤読したときにモードを自動決めるNLPではない。`pin_envelope`は観測した正本世代の一致を検査するがSHAの**文字列形式検証 ≠ 生バイトの真正性証明**。`risk_summary`はM5-Cの未検証・STALE/CONFLICTを保持し、無断で推薦資格を付与しない。
- `tests/test_m6_0.py`：架空のカードID、出典、デッキのみを使用する合成テスト。正本SHAの欠落・異世代・未観測、全件所持漏れ、UNKNOWN→0、必要中核の脱落、MAIN40/EX15超過、重複、未確認の`VERIFIED_RECOMMENDATION`拒否などを含む。
- `tools/run_full_regression.py`へ`engine_m6`を追加し、既存M1〜M5/M2-Dの回帰と同一CIで検査。

### 利用例（架空の構造化意図）

```python
from engine_m6.inputs import request_from_interpretation
request = request_from_interpretation(
    request_id="synthetic-001", as_of="2026-11-11T10:00:00+09:00",
    theme_query="架空テーマ")
assert request["mode"] == "LOW_RARITY_CORE"
```

### 判定の意味

- `PINS_PRESENT_NOT_BYTES_VERIFIED` は必要SHA/世代の**契約上の存在確認**であり、Driveから独立に実バイトを取得した証明ではない。
- `CONTRACT_VALIDATED_NOT_FACT_VERIFIED` は評価オブジェクトの整合確認であり、カード効果・所持・現行合法性の独立実証ではない。
- 本工程では`VERIFIED_RECOMMENDATION`を一律拒否。M6-1以降で証明能力のあるアダプタを導入する。
- 既存M2本番HEAD、所持デッキcatalog、M5-C private sidecarは**すべて未変更**。public GitHubにprivate個票を置かない。

次工程：**M6-1**。private Drive最新HEADと実ZIPの外部SHA照合、read-only SQLiteによる全件所持preflight、M3/CP/M5-Cの実読出し、同一世代ゲートを接続する。

## M6-1（2026-11-11）：read-only private preflight

`preflight.py`に**SHAピン付きHEAD二度読み→ZIP/SQLite→登録済み所持全件→M3・CP→M5-C sidecar**のオフライン検証器を追加。GitHubには架空SQLiteでの19合成テストのみ。private Driveの実DBではカード13,948・所持登録135（KNOWN_POSITIVE66/KNOWN_ZERO69）とM3候補215を別途読取監査し、C5 sidecar/CP/HEAD SHA一致。実カード個票をpublicへ公開しない。

- 現時点のテーマ固有採否は135件とも`REVIEW_REQUIRED`。**全件列挙PASSと採否判定PASSは異なる**。所持0と未登録UNKNOWNも区別。
- M3の候補禁止0をゲーム内確定としない。候補禁止0の所持カード採用をfail-closedにする。CPは外部SHAピン付き`USER_CONFIRMED`。
- M5-Cは`engine_m5.private_bundle.open_sidecar`を再利用。M4/M5-A/Bは別途raw SHAが必要なのでpin状態はPARTIAL。Drive転送・最新HEAD発見は呼出側が実施する。
- [M6-1監査書](../docs/M6_1_READONLY_PREFLIGHT_AUDIT_20261111.md)。次は**M6-2（候補プール・テーマ中核・出張）**。
