# Boat racing project context

## Status
Active。競艇AI予想運用のための公式出走表・予想・販売選別・結果取得・検証・台帳分析を管理します。

## Thread continuity

会話量上限やスレッド移動時の再開入口は `boat-racing/.gpt/HANDOFF.md` とする。
新しいChat / Workスレッドでは、過去会話だけを前提にせず、latest `main` の `README.md` → 本CONTEXT → `HANDOFF.md` → `WORKFLOW.md` → 対象 `docs/` / `src/` を確認する。

司令室・会場選別・仕様研究を引き継ぐ場合は、さらに `boat-racing/docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を読む。

結果取得、台帳記帳、ForwardTrial分析は担当工程を分離する。公式結果取得スレッドは結果CSV・取得ログの生成と監査までを担当し、ネイティブGoogleスプレッドシートへの台帳記帳は別工程とする。

日次の変動状態（最新記帳日、累計成績、直近日の採用会場）は本CONTEXTへ固定しない。Google Drive / Google Sheetsの正本から都度再取得する。

## Source of truth

Python、README、予想仕様書、運用文書はGit `main` を正本とする。
日次の取得CSV、予想CSV、予想根拠明細CSV、販売選別CSV、結果CSVはGit外のGoogle Driveを正本とする。

### Active prediction specs

2026-09-01以降の前向き試行では、以下を開始時に確認する。

1. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
2. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

`ForwardTrial_Ver0.1` では1を優先し、2を基礎・履歴仕様として参照する。

ControlのA/B/C、相手、2連単1点、販売Score、順位、掲載区分は結果参照後に変更しない。仕様改訂候補はControlへ直接混ぜず、結果前freezeした別version / Shadowとして管理する。

### Commander / venue selection

会場選別は購入レースの決定ではなく、当日どの会場の全RをForwardTrialへ通すかを決める探索母集団設計とする。

- 全R構造、2連単適格、販売選別を別層で評価する
- 新規・未検証会場も探索枠として扱う
- 開催日目やSG/G1を機械的な除外条件にしない
- 会場特性マスタはタイブレーク・補助情報に限定する
- 公式締切時刻は会場選別に使わず、freeze真正性監査にだけ使う
- 台帳が未完了の日は最新の真正完了世代までを根拠にし、未検証日を手計算で補完しない

詳細は `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を正本とする。

### Daily data

Google Drive `data`:
- Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`

Google Drive `analysis`:
- Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- バックテスト、結果参照前固定、検証集計、仕様改訂判断を保存

予想・販売選別の確定前は当該日の `results` を参照しない。
結果取得時に当該スレッドへ事前予想CSVがない場合は、対象日が明示されているならGoogle Drive `data/predictions` のfreeze済み正本を検索する。対象日・会場集合・仕様版で一意に確定できない場合は推測しない。結果参照後の予想再生成は禁止する。

## Ledger source of truth

継続台帳の正本はネイティブGoogleスプレッドシート `競艇note販売運用台帳` です。

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- URL: `https://docs.google.com/spreadsheets/d/1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM/edit`
- タイムゾーン: `Asia/Tokyo`

日次台帳記帳はWork / 接続済みGoogle Drive・Sheetsを使う直接経路を標準とする。Googleサービスアカウントおよび台帳記帳用Issue / Actions経路は廃止済みであり、起動しない。

決定論ロジックは `src/forward_trial_analysis_import.py` と `src/forward_trial_chat_ledger.py` を使用し、Drive 4原本を固定して書込計画を作成後、接続済みGoogle Sheetsへ反映・read-backする。Atomic Aggregate Setと `FT2_集計監査` の世代・母数が一致して初めて `FT2_取込管理=完了` とする。

Google Drive上の旧Excel版 `競艇note販売運用台帳.xlsx` と、GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` に残るファイルは移行前スナップショットであり、最新台帳として扱いません。正本へアクセスできない場合も旧Excelを最新と推定しません。
