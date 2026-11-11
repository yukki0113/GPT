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
