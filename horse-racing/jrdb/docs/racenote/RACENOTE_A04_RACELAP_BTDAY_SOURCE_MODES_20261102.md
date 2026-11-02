# A04 — BTDAY RaceLap baseline／approved-current の入力契約分離

更新日: 2026-11-02  
対象: `racenote_v055_r6_btday_turn1_shared.yml`／`racenote_v056_btday_turn1_shared.yml` と共通RaceLap入力検証のみ。

## 背景

A03により元Actions artifact (`12101869150`) の期限付き依存は解消済み。
ただし共有BTDAYが過去のRaceLap `racelap-forward-canonical-20261017-01` とParquet SHAを
直接固定していたため、研究再現のbaselineと新しい受入済みCURRENTの選択ができなかった。

2026-11-02時点でGoogle Driveの `RaceLap_CURRENT.zip` (`1RdmS-8q0NsA8opCvNioaqVotk2wiEZz-`) と
受入済みimmutable `RaceLap_CURRENT_20261017.zip` (`1q7pmoTRsg27d--xi5HhtTaJXAI_TdzUi`) は
双方サイズ1,663,722 bytes、SHA-256 `a4b076e69e9d26c464b49fd8301640b07e89fbd28925a88229869a465a51ae96` で完全一致した。
これは**観測時点での一致**であって、将来の最新版追従を保証するものではない。

## 2つのモード

| mode | 目的 | 正本ポインタ | 選択 |
|---|---|---|---|
| `baseline` | BTDAY過去入力を厳密再現 | `config/racenote_btday_racelap_baseline_v1.json` | 既定（旧selectionも互換） |
| `approved_current` | 今回の実行開始時に**Gitで受入済みの最新昇格ポインタ**を解決 | `config/racenote_btday_racelap_approved_current_v1.json` | selection明示時のみ |

- 両ポインタは別ファイル。基準世代を更新しない。
- CURRENTポインタは、**最新DriveファイルをAPIで自動列挙する仕組みではない**。
  「承認済みの最新版」を参照する仕組みである。承認以降にDrive CURRENTが更新されていても自動追従しない。
- 初期のapproved-currentは2026-10-17受入済みimmutableを指すため、初期段階ではbaselineと出力データが等しい。
  差は**後続の承認・promotion時にbaselineを据え置き、approved-currentのみを変更できる**点。
- 新しい成功run／更新可能な `RaceLap_CURRENT.zip` を、そのまま暗黙採用しない。

## BTDAY実行入口

従来の `horse-racing/jrdb/backtests/BTDAY-xxxx/selection.json` にキーを省略した場合は
`baseline` とする。新しい受入済みCURRENTを明示的に使う場合だけ、selectionに:

```json
"race_lap_mode": "approved_current"
```

を追加する。`workflow_call.inputs.race_lap_mode` は任意。指定されたときは、
selectionの `race_lap_mode` と完全一致しなければ停止する。
`push` 起動も同じselectionを読むため、過去の選択条件を予期せず変更しない。

両workflowは `src/racenote_btday_racelap_source.py` を共通して呼ぶ。

```bash
PYTHONPATH=horse-racing/jrdb/src python horse-racing/jrdb/src/racenote_btday_racelap_source.py \
  --mode baseline \
  --output-root /tmp/racelap \
  --selection-id BTDAY-9001 \
  --target-date 2025-10-12
```

上の日時・IDは例。取得はリポジトリ既定の
`tools/gpt_io/public_drive/fetch.py` とGitにレビュー済みのSHA固定manifestを使う。
認証付きDrive API、サービスアカウント、共有権限変更、恒久的なGitHub Actions artifact依存は禁止。

## 取得・受入ゲートとrun receipt

1. 選択したモードに対応するbinding JSONの `status` と選択方針を検査。
2. `config/public_drive/` のレビュー済み輸送manifestで、immutable file ID、サイズ、アーカイブSHAを確認。
3. 公開された固定ファイルのみ、共通 `fetch.py` で取得しSHA／サイズを照合。
4. ZIP CRCとメンバー重複を検査し、`current/manifest.json`、`race_lap.parquet`、`audit.json` の世代・SHA・期間・レース件数・validation PASSを照合。
5. 必要なParquet・audit・manifestと `race_lap.input_receipt.json` を保存。
6. workflowは `source_audit/race_lap_input_receipt.json` をBTDAYのimmutable T1へ保存する。
   receiptには `mode`、`approval_id`、`binding_sha256`、`transport_manifest_sha256`、
   `drive_file_id`、`archive_sha256`、`generation_id`、`period_to`、
   `race_count`、`parquet_sha256` を固定する。
7. SHA・世代・period・status等に不一致があればfail-closed。別runや最新候補へ自動fallbackしない。

## CURRENT昇格（手動レビュー前提）

1. GPTの接続済みGoogle Driveコネクタでcanonical RaceLap folderを直接確認し、
   `RaceLap_CURRENT.zip` のID・サイズ・更新日時・世代・validationを実物で照合。
2. 今回受入するCURRENTの実物を**不変ファイル**として既存保存先へ保管する
   （既存同一バイトのimmutableがある場合は再作成不要）。保存先の権限を変更しない。
3. size・SHA・generation ID・period_to・race_count・parquet SHA・検証結果を記録し、
   新しい公開read-only輸送manifest `v2` 以降をGit PRで作成する。旧A03 manifestは上書きしない。
4. `racenote_btday_racelap_approved_current_v1.json` の `approval_id` と
   `transport_manifest`／`artifact_id`／世代・SHAなどを**同じPR**でレビューし切り替える。
5. `baseline`のJSONは変更しない。CIで差分を確認後にmergeする。
6. 以後の`approved_current`モードのBTDAYだけが新ポインタを取得する。
   既存の実行済みBTDAYにはその実行時のreceiptと入力世代が残る。

**重要:** CURRENTの更新を承認なしで自動昇格しない。Gitのポインタも、
実行中の同一commitで参照が固定される。日時だけではなくmanifestとSHAで整合性を確認する。

## 対象外

- 通常FORWARDのRaceLap CURRENT resolver/SED増分更新（既存ルートを維持）。
- Analysis/RRDB最新性（A05）とRRDB CURRENT ID切替（A06）。
- Drive権限変更、共有`tools/gpt_io/`変更、PWA/Pages公開、新規研究条件の自動昇格。
- この変更で全BTDAYを再実行することはしない。重い実データT1は別途対象日ごとの承認が必要。
