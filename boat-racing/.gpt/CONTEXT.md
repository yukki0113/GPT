# Boat racing project context

## Status
Active。競艇AI予想運用のための公式出走表・予想・販売選別・結果取得・検証・台帳分析を管理します。

## Thread continuity

会話量上限やスレッド移動時の再開入口は `boat-racing/.gpt/HANDOFF.md` とする。
新しいChat / Workスレッドでは、過去会話だけを前提にせず、latest `main` を確認したうえで **repository root `.gpt/GITHUB_OPERATION_POLICY.md` → repository root `.gpt/README.md` → `boat-racing/README.md` → 本CONTEXT → `HANDOFF.md` → `WORKFLOW.md` → 対象 `docs/` / `src/`** を確認する。

司令室・会場選別・仕様研究を引き継ぐ場合は、さらに `boat-racing/docs/ForwardTrial_司令室運用・会場選別・Shadow検証.md` を読む。

結果取得、台帳記帳、ForwardTrial分析は担当工程を分離する。公式結果取得スレッドは結果CSV・取得ログの生成と監査までを担当し、ネイティブGoogleスプレッドシートへの台帳記帳は別工程とする。

日次の変動状態（最新記帳日、累計成績、直近日の採用会場）は本CONTEXTへ固定しない。Google Drive / Google Sheetsの正本から都度再取得する。

## Source of truth

Python、README、予想仕様書、運用文書はGit `main` を正本とする。
日次の取得CSV、予想CSV、予想根拠明細CSV、販売選別CSV、結果CSVはGit外のGoogle Driveを正本とする。

### Active prediction specs

2026-09-17以降の新規・結果未参照日では、**Control / Shadow並行運用**を現行標準とする。

- Control: `ForwardTrial_Ver0.1`
- Shadow: `ForwardTrial_Ver0.2-alpha1`

開始時に以下を確認する。

1. `boat-racing/docs/ForwardTrial_0917以降_Control_Shadow並行運用_20260916.md`
2. `boat-racing/src/forward_trial_predict.py`
3. `boat-racing/src/forward_trial_v02_alpha_shadow.py`
4. `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Shadow運用_20260916.md`
5. `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Design_20260916.md`
6. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
7. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

Controlは従来どおりVer0.1を正式運用として維持する。Shadowは同一のFreeze済み公式出走表から結果参照前に別version・別資産として生成し、Controlを上書きしない。

ShadowはVer0.1の1着軸/A-B-C判定とInnerPickを据え置き、OpponentScoreのみOS-alpha1（全国0.35 / 当地0.15 / ST0.05 / モーター0.15 / 今節0.15 / 級別0.15）へ変更する。Q0は `2着候補分離度<0.08 AND 軸警戒なし AND 比較支持項目数!=4` としnote非掲載。販売Scoreは全国勝率差>=0.50、分離度>=0.08、InnerPick相手2〜4号艇、本線一致の4項目各+1。CSVのみは使用せず、掲載外は非掲載とする。

Shadowの商品量はQ0通過候補数に応じ、6Rなら有料4/無料2、7Rなら5/2、8Rなら5/3、9Rなら6/3、10R以上なら7/3。5R以下は通常販売見送り。合計掲載は6〜10R。

2026-09-16中に作成された `ForwardTrial_Ver0.2-alpha1_Active運用_20260916.md` と `forward_trial_v02_alpha_predict.py` は昇格検討履歴として保持するが、0917以降の日次標準経路には使用しない。

過去にFreeze済みのControl資産・結果・台帳実績は遡及変更しない。0916以前のv0.2-alpha1 research / dry replay / Active昇格試行を0917以降のShadow genuine forward成績へ算入しない。

### Deadline / genuine gate

Control / Shadowとも、公式出走表の `締切時刻` と各系統のfreeze時刻を結果参照前に比較する。

- 締切時刻より前にFreezeされたものだけをgenuine forwardとして扱う。
- 締切時刻到達済み・締切後にFreezeされた系統はそのレースを `CONTAMINATED` としてgenuine集計から除外する。
- 有料・無料掲載にも締切済みレースを含めない。
- Control / Shadowの予想判定・買い目・Score・freeze時刻は結果参照後に変更しない。

詳細は `docs/ForwardTrial_0917以降_Control_Shadow並行運用_20260916.md` を正本とする。

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