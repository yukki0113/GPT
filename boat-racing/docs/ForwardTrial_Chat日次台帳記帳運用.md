# ForwardTrial Chat日次台帳記帳運用

Updated: 2026-09-16

## 目的

通常のChat / Workスレッドから、日次の4 CSV正本を既存のGoogleスプレッドシートへ安全に記帳する。
利用者が対象日を指定したとき、Drive資産の特定、FT2・既存販売台帳の更新、9派生集計の
同世代監査、完了確認までを**一つの論理作業**として扱う。途中返信を通常運用にしない。

この文書はスレッド移行時の運用正本である。日別の「現在どこまで進んだか」は本書に書かず、
Drive・Google Sheetsを読み直して判断する。

## 正本と固定事項

| 種別 | 正本 | 使い方 |
| --- | --- | --- |
| コード・テスト・文書 | GitHub `main` | 実行前に最新内容を確認 |
| 日次入力 | Google Drive `data` folder `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1` | racecard / prediction / sales / result の4資産 |
| 継続台帳 | Google Sheets `競艇note販売運用台帳` (`1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`) | 旧Excelは使わない |
| 完了記録 | `FT2_取込管理` と `FT2_集計監査` のread-back | 同一世代・件数を照合 |

結果取込では、事前予想、A/B/C、1着軸、2着本線/押さえ、2連単1点買い目、販売Score、
販売順位、有料/無料/CSV区分、prediction/sales freeze、結果値を変更しない。既存frozen列と
再取込候補が異なる場合は `DOMAIN_VALIDATION_FAILED` とし、上書きしない。

## 実行経路

Workでは、Driveの種別別フォルダから4原本を取得し、GitHub `main` の決定論moduleで
書込計画を生成したうえで、接続済みGoogle Sheetsへ直接書込み・read-backする経路を標準とする。
書込み中は `集計再生成中` とし、全監査成功後だけ `完了` とする。CSVの手計算やセル単位の
場当たり的転記を完了扱いにしてはならない。

Googleサービスアカウント、`GPT_GDRIVE_SERVICE_ACCOUNT_JSON`、およびGitHub ActionsからのGoogle Drive / Sheetsアクセスは断念・廃止した。台帳記帳にIssue / Actionsを用いない。旧 `run_forward_trial_chat_import.py` および旧台帳import workflowを前提にしない。

| Component | Role |
| --- | --- |
| `forward_trial_analysis_import.py` | CSV preflight、正規化、freeze/grade監査、集計値生成 |
| `forward_trial_chat_ledger.py` | stable-key upsert、FT2全再集計、既存販売台帳mirrorの純粋な書込計画 |
| 接続済みGoogle Drive / Sheets | 認証済みI/O、write、read-back。決定ロジックは持たせない |

## Workの開始契約

対象日ごとにDriveの種別別フォルダから4原本のfile IDを固定する。候補が複数ある場合は推測せず停止する。Workが決定論moduleの書込計画を生成し、接続済みGoogle Sheetsへ直接反映する。

## 1回の処理で完了と認める条件

1. Driveの4資産が対象日・会場集合・キー・freezeで整合し、可能な範囲でSHA256を記録した。
2. `FT2_全R明細` をstable keyでupsertし、frozen列の差異・重複がない。
3. `FT2_開催メタ` と `FT2_Freeze監査` を更新した。公式gradeが未解決なら `未分類 + 要確認` とし、完了にしない。
4. Atomic Aggregate Setの9タブ（日別、会場別、会場日目別、グレード別、判定構造別、販売選別検証、Score検証、Freeze監査、ダッシュボード）を、全明細から同一処理で再生成した。
5. `FT2_集計監査` の9行で `aggregate_generation_id`、raw/genuine/contaminated/exacta件数、max対象日、検証状態が一致した。
6. `daily_append` では、直前完了世代と比べて source raw/genuine/exacta件数、対象日集合、既存日のgenuine件数が縮退していない。新規日追加時は当日取込値を加えた期待累計値とも一致した。
7. `missing_dates` と `regressed_dates` が空で、Non-Regression Guardが `OK` である。
8. 修復が必要なときだけ `repair_rebuild` を使い、理由・前後件数・変更stable key・処理者/時刻を監査へ記録した。結果確認後のfreeze内容を書換える用途には使わない。
9. 販売記事台帳・販売掲載明細・既存販売派生集計をmirrorし、掲載は有料+無料のみでCSVのみを混ぜていない。
10. Sheets read-backで行数、FT2_ID重複0、9タブ世代、数式エラー0を確認した。
11. 上記すべての後にだけ `FT2_取込管理.取込状態` を `完了` にする。

本体writeの間は `集計再生成中` を使用する。ひとつでも失敗した場合は完了を付けず、
`集計不整合`、`要確認`、または`エラー`を使う。再実行はstable-key upsertと全再生成で
idempotentでなければならず、件数・投資・回収を加算しない。

## スレッド移行時の再開手順

1. GitHub `main` の README、`.gpt/CONTEXT.md`、`.gpt/HANDOFF.md`、`.gpt/WORKFLOW.md`、本書を読む。
2. 対象日のDrive 4資産とfile IDを取得する。旧Issue本文・run ID・artifactを復元する必要はない。
3. `FT2_取込管理`、`FT2_集計監査`、`FT2_全R明細`を読む。明細の存在や日別集計の最新日だけで完了判定しない。
4. 必要な書込計画をGit正本moduleから再構成し、接続済みGoogle Sheetsへ反映する。
5. `FT2_取込管理`、`FT2_集計監査`、`FT2_全R明細`をread-backし、同一generation・件数・重複0を確認する。
6. 原本不整合は修正まで停止し、Work直結経路で完了条件を満たしたときだけ最終報告する。

## 最終報告の最低内容

- 対象日、4 Drive file IDと可能な範囲のSHA256
- `aggregate_generation_id` とAtomic Aggregate Set 9タブの監査結果
- Raw / Genuine / CONTAMINATED / duplicate、2連単の件数・的中・投資・回収
- 有料・無料・CSVのみ・掲載の件数とROI
- 既存販売台帳mirror、grade状態、`#REF!` / `#VALUE!` / `#DIV/0!` が0であること

失敗時は完了と表現せず、failure_class、実際の停止箇所、再開に必要な正本上の条件だけを報告する。
