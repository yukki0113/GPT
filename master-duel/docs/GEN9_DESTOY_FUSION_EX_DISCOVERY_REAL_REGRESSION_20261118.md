# デストーイ融合EX検索漏れ：Gen9正式M6-5A実データ回帰監査（2026-11-18）

## 結論・スコープ

**以前のM6-8再構築で欠落した融合EXカード3種類は、Gen9の正式M6-5A検索エントリ `engine_m6.discovery.search_cards` によりすべて検出できた。検索不具合の再発なし。**

本監査は**検索・EX区分の回帰確認のみ**で、デストーイの正式 `recompose_portfolio` 実行、デッキ40/15枚の生成、融合素材の同時確保、ゲーム内の合法性確認は対象外。追加パーサー・追加判定器を作らず、既存実装を実行した。

## 使用した正本・実行バイナリ

- GitHub監査時点のmain：`a134c208483d7ca600a0e475bca580e6ebfb434f`。
- **正式ランタイムZIP**：GitHub Actions `Master Duel M6-8 runtime bundle` run [44206488066](https://github.com/yukki0113/GPT/actions/runs/44206488066)（SUCCESS）、artifact id `14383408885`、ランタイム元commit `fba802ed62dfb236673509607e513d971a637edc`。mainとの差分は直近の監査文書更新で、検索本体 `discovery.py` はランタイム版とGitHub mainで内容一致。
- ランタイム二重ZIPを展開して、`GIT_COMMIT_SHA.txt` に記録されたコミットと `FILE_SHA256SUMS.txt` の全90項目を検査：**PASS**。正式Python `engine_m6.discovery.search_cards` をランタイムルートから直接 import して実行した。独自の検索器は作成していない。
- Drive現行 `MD_CURRENT_HEAD.json` SHA-256 `e592b34198c290f59580976b6b861de893e6708596eb9df57b3b6e594643a66a`（Gen9 / schema v4）。
- Drive ZIP SHA-256 `0fa5fc724f8ab7671404f9297fb240095127840725d1bfd45a7431357467432f`、ZIP内 `master_duel.sqlite` のバイトSHA-256および読取専用実行SQLite SHA-256 `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`。いずれもHEADと一致。
- SQLite `integrity_check=ok`、`foreign_key_check` 違反0件。検証により正本DB・Drive HEAD・ユーザー所持・禁止制限は変更していない。

## 正式M6-5Aの検査内容と結果

各カードは `cards` の名称・ID一致、`card_monster_types` に明示的な `FUSION` 行あり、`card_attributes` は `kind=MONSTER`、`level` が非NULL、`rank`/`link` はNULL。次の**実行上の結果**を得た。

| 対象 | card_id | レベル | `search_cards(section='EXTRA', exact_card_ids=[3 IDs])` |
|---|---|---:|---|
| デストーイ・チェーン・シープ | `konami:11717` | 5 | HIT |
| デストーイ・デアデビル | `konami:12885` | 8 | HIT |
| 沼地のドロゴン | `konami:13454` | 4 | HIT |

正式検索結果の `schema` は `md-m6-5a-catalog-discovery-v1`、`section_candidate=EXTRA`、`compatibility=UNVERIFIED_CANDIDATE`。

追加の全検索ケース：

1. `section='EXTRA', exact_card_ids=[3 IDs]` → **3/3 HIT**、`truncated=false`。
2. `section='EXTRA', theme_terms=['デストーイ']` → **11種類**、チェーン・シープとデアデビルを含む。これは名称一致であり、公式テーマ所属11件確定ではない。
3. `section='EXTRA', theme_terms=['沼地のドロゴン']` → **1/1 HIT**。
4. `section='MAIN', exact_card_ids=[3 IDs]` → **0件**（EXモンスターのMAIN混入なし）。

`card_monster_types` の `FUSION` はGen7以降の正式分類カラムを参照する実装。レベルを持つ融合EXがランク・リンク検索に依存せず検出できることを実際に確認した。収録・素材・ゲーム内裁定についてカード種別の `verification=UNVERIFIED_SOURCE` を超えて断定しない。

## テスト環境上の補足

- ランタイムZIPのマニフェスト全90項目のバイトSHA検査はPASS。
- ZIPで `python -m unittest discover -s engine_m6/tests -p 'test_*.py' -q` を単独実行すると、343件を実行したうえで、`card_master_import.stage2_gen9_migration` を参照する1件が `ModuleNotFoundError` になる。これはランタイムZIPに当該開発用モジュールが含まれないためで、今回のM6-5A検索が失敗したものではない。ローカルの全テストPASSとは報告しない。
- 一方、GitHub CIのランタイム配布runはSUCCESS、同系統のリポジトリ回帰（コミット `a134c2084`、[run 44206679320](https://github.com/yukki0113/GPT/actions/runs/44206679320)）はSUCCESS。ランタイム単体実行とCIの検証範囲を混同しない。
- 検索不具合再発に関する合成回帰は既存 `engine_m6/tests/test_m6_5a.py::M65A.test_gen7_canonical_types_recover_fusion_without_keywords` が既に含む。今回は新しい検索ロジック・テストをむやみに増やさない。

## デッキ構築スレッドへの引き渡し

**DB側の「3種類を正式融合EX検索で取得できるか」の第一段階はPASS。** 次は構築スレッド側で、最新HEADの独立確認と所持全件Preflight、Gen6の55候補・元ポリシー不変保存、Gen9用M5-C/M6-5A/M6-5Bの再発行、`engine_m6.runtime_recompose` 正式入力束と事前固定のv2採点ポリシーを揃えて `recompose_portfolio` を実行する。

**検索PASSは「再構築PASS」ではない。** 素材証拠不足を理由とした `REQUIRES_REVIEW` は、正しい保留として維持する。今回の第一段階だけを受入完了し、テーマ台帳整備・トークン監査・Gen10移行は開始しない。
