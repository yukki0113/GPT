# RaceNote Request Router v0.1

RaceNote生成を「過去データ取得」「当日取得」「未来取得」に分けず、1つのリクエスト契約で扱うための入口です。

## Design goal

ユーザー/GPTからは次だけを指定します。

- `date` — 対象日
- `venue` — 任意。未指定なら全開催
- `race` — 任意。指定時は `venue` 必須

例:

```text
明日8/27のRaceNoteを作成してください。
2025/08/24のデータを取得してください。
2025/08/24 新潟11RのRaceNoteを取得してください。
```

RaceNote Request Routerが日付と対象範囲を正規化し、データ取得方法を内部で選択します。

## Temporal routing

日付判定と対象範囲判定を分離します。

```text
target_date < today  -> past
target_date = today  -> current
target_date > today  -> future
```

対象範囲は独立して以下です。

```text
venueなし             -> all
venueあり / raceなし  -> venue
venueあり / raceあり  -> race
```

### current / future

```text
JRDB PACI
 -> racenote_jrdb.py
 -> Analysis Lite enrichment
 -> Stats Mart enrichment
 -> selected bundles
 -> ZIP
```

### past

JRDBの配布形態に合わせ、base backendを年境界で分けます。

2026年以降の過去日は、その日付のPACIを直接取得します。PACIは事前情報パックなので、Analysis/Mart enrichment側で `as_of_exclusive = target_date` を固定すれば対象日結果や未来結果は混入しません。

```text
2026+ historical date
 -> JRDB daily PACI
 -> racenote_jrdb.py
 -> Analysis Lite (race_date < target_date)
 -> Stats Mart as-of aggregation
 -> selected bundles
 -> ZIP
```

2025年以前は現段階の安全なfallbackとして年次Rawを使います。

```text
<=2025 historical date
 -> annual Raw
 -> target-date BAC/KYI/CHA/CYBだけ抽出
 -> KYI prev1-5が明示するSED/SKBだけ抽出
 -> PACI-equivalent ZIPを再構成
 -> racenote_jrdb.py
 -> Analysis Lite (race_date < target_date)
 -> Stats Mart as-of aggregation
 -> selected bundles
 -> ZIP
```

Raw fallbackは正当性確認とArchive未整備期間の互換経路です。日常の過去RaceNote量産で恒久的にRawを毎回走査することを意図していません。

将来はbase backendだけを次へ差し替えます。

```text
past -> RaceNote Archive
```

リクエスト契約、GPT Issue経路、Analysis/Mart enrichmentは変更しません。

## Future leakage contract

過去レースでは `as_of_exclusive = target_date` を固定します。

- Analysis個体履歴: `race_date < target_date`
- target year Stats: Analysisを `race_date < target_date` で集計
- prior years Stats: Stats Mart年次行を利用
- 対象レース結果、対象日以降の結果は参照しない
- Historical RawではKYIが明示するprev1-5 result keyのみをSED/SKBへJOINする

完成済み当年Martをそのまま過去日へ適用しません。

## CLI

### Plan only

```bash
python src/racenote_request.py \
  --date 20250824 \
  --venue 新潟 \
  --race 11 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --plan-only
```

### Past race

```bash
python src/racenote_request.py \
  --date 20250824 \
  --venue 新潟 \
  --race 11 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --output ./output
```

2025年以前で必要な年次Rawは `fetch_jrdb_history.py` を通じて取得します。前走5走が前年へ跨る場合も、KYI result keyから必要年だけ追加取得します。2026年以降の過去日はPACIを取得します。

### Future / current all races

```bash
python src/racenote_request.py \
  --date 20260827 \
  --analysis ./jrdb_analysis.sqlite \
  --mart ./jrdb_stats_mart.sqlite \
  --output ./output
```

## Output

```text
RaceNote_YYYYMMDD.zip
RaceNote_YYYYMMDD_新潟.zip
RaceNote_YYYYMMDD_新潟_11R.zip
```

ZIP内:

- selected `race_bundle_*.json`
- `request_manifest.json`

RaceNote JSONは現行の「PACI詳細 + Analysis履歴 + Stats傾向」を使用します。履歴は詳細recent_runs最大5走 + Analysis older_runs最大3走の8走上限を初期方針とします。

## GPT / GitHub Actions route

Issue prefix:

```text
[RACENOTE_REQUEST] <request_id>
```

Issue bodyはraw JSON:

```json
{
  "date": "20250824",
  "venue": "新潟",
  "race": 11,
  "analysis_url": "<current Analysis Lite Drive URL>",
  "mart_url": "<matching Stats Mart Drive URL>"
}
```

`venue` / `race` は省略可能です。

GPTはIssue作成前にGoogle Driveから現行Analysis/Martを解決します。Drive file IDは再生成で変わり得るためGitへ固定しません。

Workflow:

```text
GPT
 -> Driveでcurrent Analysis/Martを解決
 -> [RACENOTE_REQUEST] Issue
 -> GitHub Actions
 -> DB download
 -> racenote_request.py
 -> artifact ZIP
 -> machine-readable Issue comment
 -> Issue close
 -> GPTがartifactを回収
```

## External data / secrets

GitHubへ大容量SQLite、Raw ZIP、認証情報をcommitしません。

Actionsでは以下のRepository Secretsを利用します。

- `JRDB_USER`
- `JRDB_PASSWORD`

秘密値はRepository Settingsの `Secrets and variables -> Actions` でのみ管理します。値そのものを次へ記載・保存しません。

- Git管理ファイル
- Issue本文 / Issueコメント
- workflow input
- artifact
- ChatGPTへの依頼文
- ログ

Workflowは実行時だけ `${{ secrets.JRDB_USER }}` / `${{ secrets.JRDB_PASSWORD }}` を環境変数へ渡します。Actionsログではsecret値が `***` にマスクされることを確認します。

2026-08-26の接続試験では、Repository Secretsが両方Workflowへ供給され、JRDB PACI取得処理まで到達することを確認済みです。未提供日のPACIに対してJRDBから404が返り、認証失敗時の401/403とは区別されています。秘密値そのものはログへ出力されていません。

Analysis/MartはIssue requestで渡されたDrive URLから一時取得し、artifactには含めません。

## Current limitation / next backend

v0.1では、2026年以降の過去日はdaily PACI、2025年以前の過去base bundleはannual Raw fallbackを使用します。

過去RaceNoteを大量生成する運用へ入る前に、同じrequest contractのまま `RaceNote Archive` backendを追加します。Archiveはtarget-dateの事前情報を高速に取り出すための派生層であり、Raw/Coreは監査・再生成用のまま残します。

5レース横断PoCの結果は `docs/RaceNote_multi_race_poc_20260826.md` を参照してください。
