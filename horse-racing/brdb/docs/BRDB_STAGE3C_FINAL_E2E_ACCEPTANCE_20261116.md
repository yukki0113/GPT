# BRDB ③-C 正本実Parquet E2E最終受入監査

実行日：2026-11-16（JST）  
対象PR：[ #2432 ](https://github.com/yukki0113/GPT/pull/2432)  
対象研究世代：`5279af0bd8226cde`

**判定：PASS — 研究用③-C初期親子グラフのmain取り込みを許容**。本番公開・予想利用は許可しない。

## 使用した正本ソース

GitHub Actions正規fallbackでPR HEAD `e99245d0ce9edbe5e0f400bdc46e34f1de48da53` をcheckoutし、以下のトラッキング済み7ファイルをハッシュ付きZIPにエクスポート。

- `src/brdb_stage3b_identity_crosswalk.py`
- `src/brdb_stage3c_direct_parent_graph.py`
- `src/run_brdb_stage3c_direct_parent_graph.py`
- `src/verify_brdb_stage3c_direct_parent_graph.py`
- `src/run_brdb_stage3c_final_e2e.py`
- `taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json`
- `taxonomy/stage3b_priority4_bridge_candidate_v0_4.json`

[Actions run #43825782921](https://github.com/yukki0113/GPT/actions/runs/43825782921) のartifact `data-storage-fallback-43825782921`（artifact ID `14205874131`）をダウンロード・展開し、`stage3c_export_manifest.json`に記録された**7ファイル全件のSHA256実バイト照合をPASS**。

研究用Parquetと元50頭JSONはChatGPTローカル環境の固定ファイルを使用し、これらの原本・秘匿データをGitHub Actions成果物に含めなかった。

| 入力 | SHA256 |
|---|---|
| JRDB `pedigree_fact.parquet` | `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536` |
| JRDB `parent_relation.parquet` | `c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85` |
| ③-B `stage3b_top50_master_research.json` | `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0` |
| v0.1個体crosswalk | `d9680857e1f8dcb6669b3ff57c57a4ba95de763b5fda9ff19221ab8b4e4e645e` |
| v0.4 source bridge | `ce8e3bada8a692ec5cfa34ef48eed2f23eff9e9cfc3b8e9444ee9310660f3843` |

## 正本E2Eの実行

正本`src/run_brdb_stage3c_final_e2e.py`を、上記の7ファイルと固定Parquet・50頭JSONで実行。内部で**正本`run_brdb_stage3c_direct_parent_graph.py`を2回実行**し、`verify_brdb_stage3c_direct_parent_graph.py`で独立した46辺/59ノード/13祖先候補の受入ゲートをPASSした。

実行環境：Python 3.13.5、DuckDB 1.1.3（固定版wheel）。正本コード全てはGitHub artifactから展開し、移植実装ではなくrepoの実ソースを直接実行した。

| 正本検証項目 | 実測 | 判定 |
|---|---:|---|
| 起点JRDB馬 | 37 | PASS |
| 直接親子JRDB辺 | 42 | PASS |
| 直接親子JBIS辺 | 4 | PASS |
| **型付き直接親子辺合計** | **46** | **PASS** |
| 個体キー別ノード | **59** | **PASS** |
| 2根以上から到達する共有祖先候補 | **13** | **PASS** |
| source間person IDを勝手に同一化 | 0 | PASS |
| 未確認の名前だけのparent edge | 0 | PASS |
| 非8桁の子ID入力 | 6行除外（`NO_CANDIDATE`4、`INSUFFICIENT_KEY`2） | PASS |
| 同一入力から2回生成 | バイト単位で完全一致 | PASS |

生成グラフSHA256：`4c3a9315ae2e5742f17a0e8a5a7969e49d4843f13fbdda16971c5fb91ceb1ccd`。

## Python回帰テスト

同じexport run（ソースcommit `e99245d0ce9edbe5e0f400bdc46e34f1de48da53`）の`stage3bc-regressions`でStage3B/Stage3Cの**73件を実行、0 failures / 0 errors、PASS**。実際のstderrで`Ran 73 tests ... OK`を確認。

追加された`test_brdb_stage3c_parquet_input_guard.py`では、実Parquetで発見した追加の`broodmare_sire`役割と非8桁の子IDの除外、解決済み非8桁IDがあった場合の停止を検証している。

## 取り込み可否と保留事項

**③-C第1バッチ（研究用の出典付き直接親子ネットワーク）についてマージ可**。

- `prediction_safe=false`
- `AS_OF_UNVERIFIED`
- `supports_production_cross_detection=false`
- JRDB 8桁とJBIS 10桁を別ID名前空間で保持する
- クロス候補は実際の近交・適性・予想加点を意味しない
- 母母ラインや古い海外祖先への個体接続は後続の研究課題
- BRDB CURRENT、Blood Review⑤、RaceNote、PWAの本番処理は対象外

旧監査の`[正本E2E未完了]`という状態は本監査によって解消した。主出典の人の同一性や出走当日の情報可用性まで新たに認証したものではない。
