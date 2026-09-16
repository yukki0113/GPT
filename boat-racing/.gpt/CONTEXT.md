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

2026-09-16の運用決定以降、新規の結果未参照日では `ForwardTrial_Ver0.2-alpha1` をActive prediction ruleとする。

開始時に以下を確認する。

1. `boat-racing/docs/ForwardTrial_Ver0.2-alpha1_Active運用_20260916.md`
2. `boat-racing/src/forward_trial_v02_alpha_predict.py`
3. `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Shadow運用_20260916.md`
4. `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Design_20260916.md`
5. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
6. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

Active実装はv0.1のA/B/C判定・1着軸・InnerPickを継承し、OpponentScore以降をOS-alpha1、Q0 Pair-risk Gate、4項目販売Score、日次商品量ルールへ変更する。日次標準成果物は事前予想・予想根拠・販売選別の3CSVとし、結果参照前に同一freezeで確定する。

過去に `ForwardTrial_Ver0.1` でFreeze済みの予想・販売選別・結果・台帳実績は遡及変更しない。研究用Shadow/dry replayをv0.2 genuine forward成績へ算入しない。

README / HANDOFF / WORKFLOWに旧v0.1をActiveとする記述が残っている場合は、本節と `ForwardTrial_Ver0.2-alpha1_Active運用_20260916.md` を現行Active prediction ruleとして優先し、履歴文書のv0.1記述は過去Controlの説明として扱う。

### Deadline publication gate

`ForwardTrial_Ver0.2-alpha1` の日次販売選別では、公式出走表の `締切時刻` と `販売選別確定日時` を結果参照前に比較する。

- `販売選別確定日時 < 公式締切時刻` のQ0非該当2連単1点対象だけを有料・無料の掲載順位へ参加させる。
- 締切時刻に到達済み・締切後の対象は有料・無料に掲載せず `非掲載` として検証用に保持する。
- Q0該当も `非掲載` とする。
- Q0非該当かつ締切前候補数が5R以下なら通常販売見送り。
- 6R以上はv0.2-alpha1の商品量表に従い、有料4〜7R・無料2〜3R、掲載上限10Rとする。
- `CSVのみ` はv0.2-alpha1では使用しない。
- 予想判定、2連単1点対象、買い目、販売Score、freeze時刻は結果参照後に変更しない。

詳細は `docs/ForwardTrial_Ver0.2-alpha1_Active運用_20260916.md` を正本とする。

### Commander / venue selection

会場選別は購入レースの決定ではなく、当日どの会場の全RをForwardTrialへ通すかを決める探索母集団設計とする。

- 全R構造、2連単適格、販売選別を別層で評価する
- 新規・未検証会場も探索枠として扱う
- 開催日目やSG/G1を機械的な除外条件にしない
- 会場特性マスタはタイブレーク・補助情報に限定する
- 公式締切時刻は会場選別に使わず、freeze真正性監査と販売掲載ゲートに使用する
- 台帳が未完了の日は最新の真正完了世代までを根拠にし、未検証日を手計算で補完しない

詳細は `docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を正本とする。

### Daily data

Google Drive `data`:
- Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`

Google Drive `analysis`:
- Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- バックテスト、結果参照前固定、検証集計、仕様改訂判断を保存

### Monthly long-term storage

日次CSVは当月だけの作業正本。閉鎖月の長期保存正本はfamily × month × schema hash単位のZSTD level 3 Parquetとmanifestである。schemaは厳密に分離し、元CSVの全値をstringのまま保持、必須`source_csv`で追跡する。Drive upload・再取得・Lossless/key検証・manifest uploadの全PASS前にCSV/ZIPを削除しない。DuckDBは分析エンジンであり正本ではない。実行・修正版generation・cleanup gateは`docs/Parquet月締め運用.md`を正本とする。

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