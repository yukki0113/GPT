# RaceNote 運用文書バックアップ・切り戻し台帳（2026-10-30）

基点：更新前 `main` commit `4f60b7a32b1b6ba1473bd2b716bab6ca91369899`。
全11ファイルについて Git blob SHA が更新前 `main` とバックアップで完全一致した。

| 元ファイル | バックアップ（このディレクトリ内） | 元Git blob SHA |
|---|---|---|
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_BATCH_CONTROLLER_v0_1.md` | `RACENOTE_V055_BATCH_CONTROLLER_v0_1.md` | `ec7c64eaee79d0e83b4a9661fbafa5430febb042` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_FAST_FORWARD_OPERATION_v0_1.md` | `RACENOTE_V055_FAST_FORWARD_OPERATION_v0_1.md` | `591f00a68572037b22e8085bfaf6b2589fbb7f04` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_PREDICTION_FIRST_ONE_TURN_CONTRACT_20261028.md` | `RACENOTE_V055_PREDICTION_FIRST_ONE_TURN_CONTRACT_20261028.md` | `a281354a657da7d5de414d30f710ab2f465580b7` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_R6_SHARED_T1_v0_1.md` | `RACENOTE_V055_R6_SHARED_T1_v0_1.md` | `c76800797cf7fca8c10d069221b4320ae6bfbe98` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_R6_T1_ORCHESTRATOR_OPERATION_20261029.md` | `RACENOTE_V055_R6_T1_ORCHESTRATOR_OPERATION_20261029.md` | `8323cad33f0850ed6c36bb30e93fc7c8efa71e9b` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_R6_T2_SUBMISSION_HANDOFF_v0_1.md` | `RACENOTE_V055_R6_T2_SUBMISSION_HANDOFF_v0_1.md` | `4fd1cd5e0c8c32dba9685fa82f6c335f63655710` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_SINGLE_DAY_RUNBOOK_v0_1.md` | `RACENOTE_V055_SINGLE_DAY_RUNBOOK_v0_1.md` | `a21b5eb2353c8061118e1d8f2a2cf9b640eea9ed` |
| `horse-racing/jrdb/docs/racenote/RACENOTE_V055_TWO_PHASE_TURN2_OPERATION_v0_1.md` | `RACENOTE_V055_TWO_PHASE_TURN2_OPERATION_v0_1.md` | `6731a939e3e9d5a319fd63065d5d1891af8d240f` |
| `horse-racing/jrdb/docs/racenote/README.md` | `README.md` | `e00f6f267eb9334aee41ac8a37af6852e48f5537` |
| `horse-racing/jrdb/.gpt/HANDOFF.md` | `gpt__HANDOFF.md` | `93aa3fcc2280d97fd7f10804c5f0bb19214407a6` |
| `horse-racing/jrdb/.gpt/WORKFLOW.md` | `gpt__WORKFLOW.md` | `2f2a05556d3152ada2cf07af32d9ed2809f76e05` |

## 切り戻し手順

1. `main` で対象操作世代・未完了T1/T2を確認。実行中なら新規の先行T1起動を止める。
2. 新規ブランチを `main` から作り、この台帳に記載した該当バックアップ本文を元のパスに戻す。機械実装、BTDAY選定台帳、保存済み予想、Freeze成果物は変更しない。
3. `RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md` の参照状態を明確化（必要なら旧手順への参照を変更）。差分をレビューし、ドキュメント変更のみのPRで戻す。
4. Git blob SHAで戻した内容とバックアップの完全一致を確認し、マージ後 `main` を再確認。

**注意**：このバックアップは運用文書の全文コピーであり、データ・予想・Workflowコードのバックアップではない。旧契約r4/r5の記述を復元してもr6のFreeze済み予想を書き換える理由にならない。
