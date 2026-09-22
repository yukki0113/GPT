# keirin

競輪Historicalデータ基盤・予想研究用領域。

## 現在地（2026-09-22）

目標は2016〜2025の10年Historicalを原本から再現可能な形で保持し、後段でCanonical Parquet/DuckDBへ変換して独自予想ロジックの検証に使うこと。外部へ公開・販売する対象は生データではなく独自ロジックの出力を想定する。

KEIRIN.JPへの確認結果を受け、Historical取得・非公開保存・個人予想研究は `personal_research_approved` として扱う。Raw / 正規化しただけのデータの配布・販売は禁止。独自予想印・指数等の有料販売は `commercial_output_pending` として別確認事項に残す。

機械取得は明確な禁止ではないが、サービス提供に支障があるアクセスは制限対象となり得るため、低頻度・再取得抑止・fail-closeを標準とする。

## Drive 正本

ユーザー指定の競輪専用フォルダ:
- root: `1Ai2sOLnjKskNb2I7KVPI1zYvnybd5UBq`
- `00_raw`: Raw原本
  - `backfill_archives`: `1dNVxRqowGH8uYuYHnjpnEOAL3I0oOVmx`
- `10_canonical`: 将来のCanonical Parquet
- `20_audit`: source list / manifest / validation
  - `backfill_summaries`: `1xyvr0g1T9rTFgirEmx8vlw50ERfH3hQk`
- `30_analysis`: 将来の研究出力

取得成功とDrive転送成否は分離する。Raw取得が成功しDrive転送だけ失敗した場合でも全ロールバックしない。

2026-09-22、GitHub artifact -> ChatGPT connector handoff -> Google Driveの経路で10年資産のDrive移送を完了。
- `00_raw/backfill_archives`: 2016〜2025の年別ZIP 10本
- `20_audit/backfill_summaries`: 2017〜2025年次summary ZIP 9本 + 10年summary ZIP 1本
- 年別Raw ZIPのDrive上サイズをGitHub artifact metadataと突合済み
- GitHub artifactの保持期限はバックアップ/再取得用であり、Driveを長期正本とする

## Phase 0 raw acquisition

- source list（JSONL）を入力としたRaw取得
- `policy_status=approved` または `personal_research_approved` の明示ゲート
- GET / POST双方に対応
- 原本バイト列の不変保存
- SHA-256
- HTTP/取得結果/欠損を含むmanifest JSON
- 429 / 403 / 5xx増加やアクセス制限兆候があれば停止
- provider固有discoveryとしてKEIRIN.JP月間開催日程 -> `/pc/racelist` POSTを実装

## KEIRIN.JP monthly collector

月間開催日程を1回GETし、各開催セルに埋め込まれた公式 `encp` を利用して、開催ごとに `/pc/racelist` を1回POSTする。R単位の大量アクセスは行わない。

標準アクセス間隔は3秒。月切替時は10秒。

## Verification / 10-year backfill

2016-01 one-month PoC:
- discovered 60
- successful 60
- failed 0
- coverage 100%

2016 full-year audit:
- discovered 755
- successful 755
- failed 0
- overall coverage 100%
- failed months none

Cross-year structure audit:
- targets: 2017/2020/2023/2025 × Jan/Jul = 8
- all schedule HTTP 200
- all racelist POST HTTP 200
- all major structure match = true

2016〜2025 full backfill:
- Issue #1189: Close / completed
- years: 10
- discovered events: 8,464
- successful events: 8,464
- failed events: 0
- overall coverage: 100%
- failed years: none

Workflow:
`.github/workflows/keirin_historical_10y_backfill_issue.yml`

方式:
- 2016はIssue #1186の取得済み成果を再利用
- 2017〜2025を新規取得
- `max-parallel: 1`
- 各年12か月を逐次
- 開催間隔3秒
- 月間切替10秒
- fail-fast false
- 年ごとRaw + audit artifact
- 最後に2016既存実績と統合して10年summaryを生成
- Drive uploadは取得成功条件から分離

## Raw collector

汎用source listを直接取得する場合:

    cd keirin
    PYTHONPATH=. python -m keirin_historical.raw \
      --source-list approved_sources.jsonl \
      --output-dir /path/to/Drive/GPT/keirin/00_raw \
      --manifest-path /path/to/Drive/GPT/keirin/20_audit/manifest.json \
      --delay-seconds 3.0

未承認のpolicy_statusはHTTPアクセス前に `policy_blocked` とする。

## Validation

    cd keirin
    PYTHONPATH=. python -m unittest discover -s tests -v
    python -m py_compile keirin_historical/*.py

## Next gate

1. Raw HTMLからpre / postを物理分離するCanonical parserを実装する。
2. Canonical Parquet / DuckDBへ移行する。
3. ライン/並び情報のcoverageを別途監査する。
4. Canonical生成後にRaw->Canonical件数・キー・欠損・結果リーク監査を行う。
5. 独自予想印・指数等の有料販売は commercial_output_pending のまま、販売開始前に追加確認する。
