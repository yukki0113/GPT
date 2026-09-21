# keirin

競輪Historicalデータ基盤・予想研究用領域。

## 現在地（2026-09-22）

目標は最低5年、可能なら10年程度のHistoricalを原本から再現可能な形で保持し、後段でCanonical Parquet/DuckDBへ変換して独自予想ロジックの検証に使うこと。外部へ公開・販売する対象は生データではなく独自ロジックの出力を想定する。

KEIRIN.JPへの確認結果を受け、Historical取得・非公開保存・個人予想研究は `personal_research_approved` として扱う。Raw / 正規化しただけのデータの配布・販売は禁止。独自予想印・指数等の有料販売は `commercial_output_pending` として別確認事項に残す。

機械取得は明確な禁止ではないが、サービス提供に支障があるアクセスは制限対象となり得るため、低頻度・再取得抑止・fail-closeを標準とする。

## Phase 0 raw acquisition

- source list（JSONL）を入力としたRaw取得
- `policy_status=approved` または `personal_research_approved` の明示ゲート
- GET / POST双方に対応
- 原本バイト列の不変保存
- SHA-256
- HTTP/取得結果/欠損を含むmanifest JSON
- 429 / 403 / 5xx増加やアクセス制限兆候があれば停止
- provider固有discoveryとしてKEIRIN.JP月間開催日程 -> `/pc/racelist` POSTを実装

現時点では予想ロジック、Canonical parser、Parquet化、販売運用は未実装。

## KEIRIN.JP monthly collector

月間開催日程を1回GETし、各開催セルに埋め込まれた公式 `encp` を利用して、開催ごとに `/pc/racelist` を1回POSTする。R単位の大量アクセスは行わない。

実行例:

    cd keirin
    PYTHONPATH=. python -m keirin_historical.keirin_jp_month \
      --year 2016 \
      --month 1 \
      --output-dir /path/to/Drive/GPT/keirin/00_raw \
      --audit-dir /path/to/Drive/GPT/keirin/20_audit \
      --delay-seconds 3.0

`--delay-seconds` は2秒未満を拒否し、標準は3秒。

## 2016-01 one-month PoC

GitHub Issue #1185 / Actionsで実データPoCを実施。

- 月間日程GET: HTTP 200
- discovered events: 60
- successful events: 60
- failed events: 0
- coverage: 100%
- request interval: 3.0 seconds
- event raw total: 2,698,910 bytes
- schedule raw: 123,354 bytes
- schedule SHA-256: `7a6a18947bab7ea0fb3117bc802b3201a9b0e914e976c8d2e3cb7ae6b37c0358`
- workflow result: success
- Issue #1185: Close / completed

このPoCにより、「月間日程1回 + 開催ごと1回」の低頻度経路で2016年Historicalを100%回収できることを確認した。

## Raw collector

汎用source listを直接取得する場合:

    cd keirin
    PYTHONPATH=. python -m keirin_historical.raw \
      --source-list approved_sources.jsonl \
      --output-dir /path/to/Drive/GPT/keirin/00_raw \
      --manifest-path /path/to/Drive/GPT/keirin/20_audit/manifest.json \
      --delay-seconds 3.0

未承認のpolicy_statusはHTTPアクセス前に `policy_blocked` とする。

## Storage contract

- Drive /GPT/keirin/00_raw: source bytes (immutable)
- Drive /GPT/keirin/10_canonical: future canonical Parquet
- Drive /GPT/keirin/20_audit: source lists / acquisition manifests / validation
- Drive /GPT/keirin/30_analysis: future research outputs
- Gitには大容量Raw/CSV/Parquetをcommitしない

## Validation

    cd keirin
    PYTHONPATH=. python -m unittest discover -s tests -v
    python -m py_compile keirin_historical/*.py

## Next gate

1. 2016年1年分へ拡張し、月別coverage・HTTP異常・開催数の季節差を監査する。
2. 2016年通年PASS後、複数年へ拡張する。
3. 5〜10年Raw回収前に保存先・年次圧縮/Parquet化方針を確定する。
4. Raw HTMLからpre / postを物理分離するCanonical parserを実装する。
5. ライン/並び情報がKEIRIN.JP Historical内で十分取得できるかを別途coverage監査する。
6. 独自予想印・指数等の有料販売は commercial_output_pending のまま、販売開始前に追加確認する。
