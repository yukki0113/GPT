# M6-0 受入監査 — 入出力データ契約（2026-11-11）

## 完了判定

**M6-0 PASS（合成検査と公開API契約に限る）**。M6-1〜M6-7の所持DB read-only統合、レシピ生成、禁止制限・CP評価、独立チャット受入は対象外。

## 成果物

- `engine_m6/schema.py`：BuildRequest/SourcePins/PreflightAudit/DeckCandidate/DeckEvaluationのv1契約。厳格な必須項目、列挙状態と数量、card ID形式、SHA形式を検査。
- `engine_m6/inputs.py`：明示指示を優先するモード正規化、予測したHEAD世代との一致、未検証M5 Bundleの保守的扱い。
- `engine_m6/tests/test_m6_0.py`：**35件の合成試験**。デッキ内UR0・必須中核UR0・新規生成UR0は別のフィールドに分離し、まだ正答値の推定はしない。
- `tools/run_full_regression.py`：新しいM6スイートを追加。

### 明示的にテストした不成立例

1. `LOW_RARITY_CORE`を誤って`STRICT_NO_UR`にすること、明示厳格指示の上書き。
2. 異なるHEAD/SQLite/所持/規制世代と不足SHAを成功判定すること。未観測の世代はPARTIAL、異世代はBLOCKED。
3. 登録済み所持の一部だけ判定して全件確認済みと主張すること、登録枚数不明を0へ変換すること、複数の同一card ID、根拠不足の採用。
4. MAIN40枚未満、区画と枚数矛盾、同一カード採用数の集約後3枚超過、必須中核カードの欠落を完成候補と主張すること。
5. M5-C `STALE`/矛盾や原文/規制未検証なのに`VERIFIED_RECOMMENDATION`を設定すること。
6. CP-SRとCP-URの通貨を混ぜた予算判定。

## セキュリティ・次工程

GitHubには架空fixture・コード・合成テスト・集計のみ。本番DB/所持/デッキ登録/知識Sidecarは読出しも書込みも行わない。実SHAの独立検証・最新版探索・IDとゲームの意味的検証は次工程以降。

## CI

[Actions run 42964555821](https://github.com/yukki0113/GPT/actions/runs/42964555821) にて **M6 35件 PASS、全体408件、1スキップ、失敗0**を確認。スキップはCIに未配置のprivate実ZIPに依存する既存試験であり、M6-0契約試験にはスキップなし。最終ドキュメントコミットのCIも別途確認する。
