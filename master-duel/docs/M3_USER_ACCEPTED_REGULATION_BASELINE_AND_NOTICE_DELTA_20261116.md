# MD禁止制限 運用基準版とゲーム内差分更新（2026-11-16 正本）

## 決定・適用範囲

2026-11-16のユーザー合意により、現在の本番Gen6 SQLiteにあるMD_STANDARDの禁止制限候補215件を**通常構築に利用するユーザー承認済み基準版**として採用する。情報元の全件ゲーム内照合は行わない。既存の`UNVERIFIED_SOURCE`という「取得元のゲーム内検証状態」はそのまま保存するが、これを理由として日常のデッキ構築をBLOCKしない。

- 原版：`md-standard-2026-11-05-candidate-2651601cb3bf`
- 発効日（原データ）：2026-11-05
- ユーザー運用承認日：2026-11-16
- 出典Gen6 SQLite SHA-256：`0ac8a2b91a3f05dd87dd4f06d09456f096cf9aef7820c546a2a3c2d0f77133b7`
- 内容：禁止114件（0）、制限77件（1）、準制限24件（2）。その他は**3枚**として扱う疎テーブル。
- **非公開正本**：Drive `GPT/MasterDuel/DB/MD_REGULATION_ACCEPTED_BASELINE_GEN6_20261116.json`。公開GitHubには個票215件・所持情報を保存しない。
- policy schema：`md-regulation-accepted-baseline-v1`。元のSQLite snapshotを改変・出典確認済みと偽装しない。

## 以降の運用：最新ゲーム内お知らせを差分だけ転記

最新のゲーム内告知で変更が発表されたら、次の値を伝えるだけでよい。

- 施行日、必要ならお知らせの発表日。
- 変更したカードの日本語名と、**新しい規制区分**（禁止0／制限1／準制限2／無制限3）。
- 旧区分の記載があれば併記し、既存テーブルの値と照合。旧区分が不明ならデータから旧値を確認して更新イベントに明記する。

差分イベント `REGULATION_REVISION` は `GAME_IN_APP_NOTICE` を根拠とし、施行日以前の構築には適用しない。同じカードの元値（`before`）が一致しない場合、変更を**中止**して確認する。更新しなかったカードの規制値は保持。イベントID・発表日・適用日・0〜3の前後値・根拠を保存し、過去の日時で旧規制を再現可能にする。

ゲーム内を見て基準版に誤りを発見した場合は `DATA_CORRECTION` / `GAME_IN_APP_OBSERVATION` として、正式改訂イベントと区別して1カード単位で訂正する。

通常運用時にJSON・Game8・Web・公式全リストを毎回再取得する必要はない。明確な矛盾、取得破損、カードID不一致、指定された告知の内容が不明である場合だけ局所確認する。

## M6-8への接続

1. 現行private HEAD/SQLiteを通常どおり取得し、読み戻し・バイトSHAを照合する。
2. この基準版JSON（更新イベントを含む）をprivate Driveから取得する。
3. `validate_regulation_policy` に現在の `master_sha256`、構築基準日 `as_of`、候補カードIDを渡す。
4. 基準版中にないIDは上限3とする。禁止0、制限1、準制限2に対する上限超過は**BLOCK**。
5. M6-1所持preflight、M6-7再構築、M6-4費用・採否監査まで、同一policyを渡す。単に`UNVERIFIED_SOURCE`のために候補を阻害しない。
6. データ規制受入状態と、ゲーム内全件での検証済み状態を区別する。前者`USER_APPROVED_OPERATIONAL_BASELINE`、後者は未確認ならfalse。ユーザー承認版を「全カードゲーム内検証済」と説明しない。
7. M6-8のテーマ成立、カード効果、EX素材、所持枚数、UR生成上限、評価入力事前固定など**他のゲートは従来どおり**。

## DB世代に関する注意

初期規制正本のSQLite SHAは**出典の履歴**であり、新規所持登録によってGEN7等に変化しても禁止制限表の再取得を要求しない。実行対象となる新しいSQLiteは別途SHA固定し、基準版にある規制対象カードIDが最新カードマスター内に存在することをチェックする。原版Gen6のDBを使用する場合は、原版スナップショットID・215件・適用日との照合を追加実施する。

**同じDriveファイルを更新するときは差分追加後の内容・SHAを独立保存し、世代と読み戻しを確認する。** Concurrent writerで競合した場合、latest内容を再読込して衝突する差分を再評価する。新たな改訂を既存履歴の無言の変更で処理しない。

## 過去のブロックと切り替え

旧`md-m6-7-regulation-gate-v1` は全候補の明示的制限値・GAME_VERIFIED/REVIEWED_MD_SOURCE・最大31日経過による見直しを要求していたため、候補215件が`UNVERIFIED_SOURCE`のGen6で構築を停止させた。旧ゲートは履歴互換のみに残し、承認済み基準版スキーマでは「全候補を毎回認証」と「31日で自動失効」を廃止。M6-1とM6-4での`UNVERIFIED_SOURCE`扱いもこの運用基準版の指定時のみ切替える。

## 非目標

- 禁止制限の全215カードを手作業で検証し直すこと。
- 外部JSONやGame8を自動で再クロールすること。
- ゲーム内告知を自動で取得したと偽ること。
- 実際のプレイで勝てるかやカード効果解釈の完全保証。


## 2026-11-24追補：Drive規制正本の更新ファイル参照（再発防止）

### 原因と対応

2026-12-04施行差分の書込み時、`files__manage_library` でLibraryへ保存したJSONの `file_id` を、Google Drive `update_file(file_uri=...)` にそのまま渡して `INVALID_ARGUMENT` となった。**LibraryのファイルIDはDriveの更新用ファイル参照ではない**。JSON構築・規制値の不一致ではなく、ファイルサービス間の受渡し方法の誤りだった。

修正後は、まず更新候補をDriveの同じ非公開DBフォルダへ**別名ステージングアップロード**する。そのステージングをDriveコネクタの `fetch(download_raw_file=true, include_base64=false)` で再取得し、返却された `file_uri.file_id`（この環境では `sediment://file_...`）を**元ファイルIDのまま** `update_file` に渡す。実際のコンテンツの根拠は、作成したJSONのバイト列とステージング再取得のSHA一致で確認する。

### 実行手順（一般化）

1. 現行正本を独立取得し、変更前の該当カード・履歴・件数を照合する。日付指定の追加イベントとして作成し、既存 `baseline_entries` は変更しない。
2. 元のDrive正本を別名バックアップし、更新候補を**実際にコネクタが受け付ける添付ファイル参照**から `upload_file` で別ファイルに保存する。Library `file_id` をコネクタ参照として直接流用しない。受け付ける添付が用意できないときは正本更新を試行せず、その不足を報告する。
3. ステージングを **Driveから別要求で再取得**して候補ファイルとのバイトSHAを照合する。成功後、下記の形式で既存の正本ファイルを更新する。更新先の `canonical_file_id` は実際に取得したIDを使い、生成しない。

```javascript
const staged = await tools.mcp__Google_Drive__fetch({
  url: verified_staging_url,
  download_raw_file: true,
  include_base64: false,
});
const ref = staged.result.file_uri?.file_id;
if (typeof ref !== "string" || !ref.startsWith("sediment://")) {
  throw new Error("Drive connector staging reference unavailable");
}
await tools.mcp__Google_Drive__update_file({
  fileId: canonical_file_id,
  file_uri: ref,
  mime_type: "application/json",
});
```

4. **元の正本URL**を再取得し、バイトSHA一致、履歴保持、イベント件数、前後値、施行日前後の規制計算を検証して完了とする。ステージング成功だけを「正本更新済み」とは呼ばない。
5. 更新元の適用日・根拠の区別と単一ライター運用は既存の規則に従う。基準値変更・新旧イベントの直接破壊・Gen10 SQLiteや所持台帳の不要な変更は行わない。

実績：2026-12-04施行6件のJSON差分を既存規制正本へ反映し、Driveから独立再取得した候補と正本のSHA-256一致を確認。これは**Driveのファイル受渡し失敗の修正**であって、禁止制限の全件追加検証を要求する仕組みではない。
