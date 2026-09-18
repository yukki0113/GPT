# JRDB PWA Fact Lite Parquet / DuckDB 移行報告 — 2026-09-18

## 結論

条件別集計 PWA の SQLite / sql.js から Parquet / DuckDB-Wasm への**本体切替は完了**した。通常配布・通常実行で Fact Lite SQLite を使用しない。

正式な読込経路は以下とする。

`Fact Lite Parquet generation → current.json → generation manifest → Pages配布 → OPFS generation cache → DuckDB-Wasm`

Drive は immutable generation の長期保存正本、GitHub Pages はブラウザ配布経路である。

## 確認済み事項

- current generation: `fact-lite-v0_3-20260913`
- 6 relation / `fact_stats_entry` 516,061行の SQLite / Parquet 同値性監査: PASS
- Pages は Fact Lite の Parquet、DuckDB-Wasm、Arrow依存を同一originで配布
- Parquet manifest・asset SHA-256・size・schema・行数を検証後にのみ OPFS の current generation を切替
- 通常検索、複数の集計軸・条件検索、OPFSからの復元を確認済み
- 初期読込後、機内モードでの検索を確認済み
- Fact Lite は SQLite runtime fallback を持たない。障害時のrollbackは旧SQLiteへフォールバックせず、Pages / current generation 単位で行う

初回読込は Parquet asset の取得・検証と DuckDB-Wasm初期化を伴うため、旧SQLite方式より5〜10秒程度長くなることがある。これは性能改善の対象として残すが、現時点で集計操作の実用性は確認済みである。

## 次回更新の受入手順

開催後の通常更新は次の順序で行う。

1. 更新済みAnalysisから Fact Lite Parquet の新しい immutable generation を生成する。
2. schema・identity・WIN5・SHA-256・size・同値性監査を通過した generation のみ current として発行する。
3. GitHub Pagesへ `current.json`、manifest、manifest記載のParquet assetを配布する。
4. 端末で「最新版を確認」を実行し、新generationの検出・取得・検証・OPFS切替を確認する。
5. 切替後に通常検索、オフライン検索、前generationが不完全な場合にcurrentを維持することを確認する。

したがって、明日・明後日の開催後に行う **Fact Lite Parquet更新 → PWA配布 → 更新検出・検索・オフライン確認** は、残るgeneration更新受入として正しい手順である。

## 未了の受入

- 新generationへの実更新を用いた端末切替確認
- iPhoneを含む複数端末での更新・オフライン復帰確認
- 初回同期時間の計測と最適化方針の検討

これらは移行後の運用受入であり、SQLiteからParquet/DuckDBへの本体切替を戻す理由ではない。
