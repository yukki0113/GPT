# Boat racing project context

## Status
Active。競艇AI予想運用のための公式出走表・予想・販売選別・結果取得・検証を管理します。

## Source of truth

Python、README、予想仕様書はGit `main` を正本とする。
日次の取得CSV、予想CSV、予想根拠明細CSV、販売選別CSV、結果CSVはGit外のGoogle Driveを正本とする。

### Active prediction specs

2026-09-01以降の前向き試行では、以下を開始時に確認する。

1. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
2. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

`ForwardTrial_Ver0.1` では1を優先し、2を基礎・履歴仕様として参照する。

### Daily data

Google Drive `data`:
- Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`

Google Drive `analysis`:
- Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- バックテスト、結果参照前固定、検証集計、仕様改訂判断を保存

予想・販売選別の確定前は当該日の `results` を参照しない。

## Ledger source of truth

継続台帳の正本はネイティブGoogleスプレッドシート `競艇note販売運用台帳` です。

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- URL: `https://docs.google.com/spreadsheets/d/1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM/edit`
- タイムゾーン: `Asia/Tokyo`

Google Drive上の旧Excel版 `競艇note販売運用台帳.xlsx` と、GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` に残るファイルは移行前スナップショットであり、最新台帳として扱いません。正本へアクセスできない場合も旧Excelを最新と推定しません。
