# keirin

競輪Historicalデータ基盤・予想研究用領域。

## 現在地（2026-09-22）

目標は最低5年、可能なら10年程度のHistoricalを原本から再現可能な形で保持し、後段でCanonical Parquet/DuckDBへ変換して独自予想ロジックの検証に使うこと。外部へ公開・販売する対象は生データではなく独自ロジックの出力を想定する。

公開ページが技術的に取得可能であることと、有償予想に使うための自動・大量取得が許諾されていることは分けて扱う。2026-09-22時点の主要公開サイト調査では、商用目的または私的利用を超える複製・利用を制限する条件が確認されたため、正式Historical sourceは未確定。

## Phase 0

- approved source list（JSONL）を入力としたRaw取得
- policy_status=approved の明示ゲート
- 原本バイト列の不変保存
- SHA-256
- HTTP/取得結果/欠損を含むmanifest JSON
- provider固有discovery/parserはsource許諾確定後に追加

現時点では予想ロジック、Canonical parser、Parquet化、販売運用は未実装。

## Raw collector

実行例:

    cd keirin
    PYTHONPATH=. python -m keirin_historical.raw --source-list approved_sources.jsonl --output-dir /path/to/Drive/GPT/keirin/00_raw --manifest-path /path/to/Drive/GPT/keirin/20_audit/manifest.json --delay-seconds 1.0

source listは1行1JSON。policy_status が approved 以外のレコードはHTTPアクセスせず policy_blocked としてmanifestに残す。

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

1. Historical sourceの商用内部分析・自動取得条件を確認する。
2. 5〜10年のavailabilityを確認する。
3. provider-specific discoveryを追加する。
4. まず1か月を全件Raw取得し、expected/actual件数・HTTP失敗・欠損率をmanifest化する。
5. 1か月PASS後に年単位、最終的に5〜10年へ展開する。
