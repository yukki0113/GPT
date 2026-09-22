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
- `10_canonical`: 将来のCanonical Parquet
- `20_audit`: source list / manifest / validation
- `30_analysis`: 将来の研究出力

GitHub Actions側にGoogle Drive認証経路が無いため、Drive転送は取得成功条件に含めない。
Raw取得が成功しDrive転送だけ未実施/失敗の場合でも、全ロールバックはしない。
GitHub artifactを30日保持し、後続でDriveへ手動または別経路転送可能とする。

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

## 2016 verification

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

## 10-year backfill

2016はIssue #1186の取得済み成果を再利用し、2017〜2025を新規取得する。

Workflow:
`.github/workflows/keirin_historical_10y_backfill_issue.yml`

方式:
- year matrix 2017..2025
- `max-parallel: 1`
- 各年12か月を逐次
- 開催間隔3秒
- 月間切替10秒
- fail-fast false
- 年ごとRaw + audit artifact
- 30日保持
- 最後に2016既存実績と統合して10年summaryを生成
- Drive uploadは成功条件から分離

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

1. 2016〜2025 backfill完了を確認する。
2. GitHub artifactsをDrive `00_raw` / `20_audit` へ転送する。
3. Raw HTMLからpre / postを物理分離するCanonical parserを実装する。
4. Canonical Parquet / DuckDBへ移行する。
5. ライン/並び情報のcoverageを別途監査する。
6. 独自予想印・指数等の有料販売は commercial_output_pending のまま、販売開始前に追加確認する。
