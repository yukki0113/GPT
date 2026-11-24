# R3 新馬戦4R — 固定入力復元・受入実行器 (2026-11-24)

**PREPARATION PASS / REAL DUAL-SOURCE NEWCOMER E2E PENDING / R4 NOT AUTHORIZED.**

上位正本: [R3共通契約](RACENOTE_R3_INDEPENDENT_EVIDENCE_CONTRACT_20261124.md)、[JPDB×BRDB方針](racenote/RACENOTE_JPDB_BRDB_INDEPENDENT_EVIDENCE_POLICY_20261120.md)、[BRDB新ロードマップ](../../brdb/docs/BRDB_THREAD_HANDOFF_20261124.md)。
基準main: 151ccbf2c2a40f1d3f0ffa0c3e6e2f4ff21b4efe。既存契約・集計・予想を変更しない。

## 実測復元監査

非公開Library /JPDB/R1, /JPDB/R2, /JPDB/R3 の3 ZIPをmaterialize、CRC検証。Git上のR3受入集計JSONと比較しR1 profile 2、R2 context 2、R3旧manifest 2、R3 detail 2、preview 6の計14ファイルSHA一致。R1/R2/R3/previewのrace/horse_no/horse_id/予定騎手/取消フラグ全76頭一致。旧manifest内のPACI実バイトは今回materializeしておらず、新規R3再生成や歴史Parquet再集計は未実施。

| 対象日 | race_key_raw | 登録頭数 | 今回の状態 |
|---|---|---:|---|
| 2026-06-13 | 05263305 | 7 | PENDING_BRDB_ACCEPTED_INPUT |
| 2026-06-13 | 09263306 | 13 | PENDING_BRDB_ACCEPTED_INPUT |
| 2026-11-15 | 05265404 | 12 | PENDING_BRDB_ACCEPTED_INPUT |
| 2026-11-15 | 05265405 | 10 | PENDING_BRDB_ACCEPTED_INPUT |

新馬対象4R42頭、両DB追加受入0R。BRDB /M7/ の既存受入は05265412の通常戦のみ。別レース流用禁止。BRDB側の非公開B1/B2・B3研究receiptは確認済み（RESEARCH_ONLY / PASS_RESEARCH_ONLY）だが、対象4Rの受入済み全頭B5/M7出力とは異なる。B4/B5の未確認成果を存在しないと断定せず、受入済み候補とreceiptを入手して照合する。JPDBからBRDB側の専用母集団/研究契約を勝手に決定しない。

## 追加実装

- src/racenote_r3_newcomer_replay.py: 独立pin済み旧R3 detail群からA1のみ計画。1日につき1 BRDBレース入力を取る既存R3 CLIの制約を保ち、対象ごとに別manifest/出力dirで実行。旧PACI・R1/R2・両receiptのSHA固定、BRDB5 asset全件必須、対象日/レース/全馬照合。既存builder/独立auditを2回呼び、detail/preview/auditのSHA一致を要求。未入力の対象はPENDING。R4自動承認なし。
- tests/test_racenote_r3_newcomer_replay.py: 8/8 PASS (ローカルPython 3.13.5)。subprocessは合成fixture/mocked runnerであり実データ結合の認証ではない。
- 実データ旧detail2件によるplan CLI PASS、4R42頭。summary SHA256 15734858b3a183d742bf6b625aaee686d65a530ca0cd9ad37dc01e489da9ae9e。
- source SHA256 de586861507b0ebd463ab6de3d9682ab41e49f3f96cc1c6f4055fd81e7c43f3a、test SHA256 ffb1384d15f5b14383e76131afd1be2c566f2a1483b7ebfb3c2b4a31437204cb。

CLI: `python horse-racing/jrdb/src/racenote_r3_newcomer_replay.py --previous-detail <private-detail> <Git-receipt-SHA> --previous-detail <private-detail2> <Git-receipt-SHA2> --output-dir <new-private-dir>`。両DB入力の受入後、対象ごとに `--job <race-key> <private-v1-manifest> <independently-pinned-manifest-SHA>` を追加。実行時は共通wheel-first方針による承認済みvenvを `--python`、jsonschema監査環境を `--audit-python` で指定。配置パスのみ変更した新manifestは元asset/receipt SHAを独立照合して作成。planのみは標準ライブラリで完結するため依存導入不要。既存正本R3 code/schemaの再利用を維持。

## 次ゲート

1. BRDB B4/B5の新馬専用研究契約と全馬出力受入をBRDB側と照合。同一PACI 4RについてM7互換の一般条件Evidenceを受入できる場合も、新馬専用実績とは区別。
2. 4R別のM7受入v0.3・④詳細・①②原出力・各receiptを取得し、同じPACI/JPDB源を再materializeして本CLIで実際に再演。全42頭/2回の独立監査がPASSするまでR3残工程PENDING。
3. この実行器のPASS_M7_COMPOSITION_ONLYは既存M7一般条件の結合受入のみ。BRDB新馬専用契約は別途受入・必要ならバージョン付きR3追加契約を設計し、既存v0.1を変質させない。
4. R4 Shadowは上位方針に従う別ゲート。R5/R6/Confidence Z/Freeze/CURRENT/RaceNote/PWAは変更なし。ライセンス付き個別データは非公開保持。Actions未起動。
