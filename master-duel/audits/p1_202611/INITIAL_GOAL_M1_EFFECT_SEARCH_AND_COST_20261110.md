# 初期ユースケースへの進捗：M1カード・効果検索とレシピ費用判定（2026-11-10）

## 受入判定

**M1の初期語句検索と、将来M6向けのレシピ費用/UR制約判定を実装・受入PASS。元のデッキ自動提案、意味理解、現行禁止制限、パック解放ナビは未完了。** 関連する残工程M1〜M8は [ロードマップ](../../docs/INITIAL_GOAL_REMAINING_ROADMAP_20261110.md) を正本とする。

## 正本と実装

- 元の設計：`master-duel/docs/BASIC_DESIGN.md`。既定 `LOW_RARITY_CORE` は中核UR0、新規UR生成0、所持URは単体汎用/出張として利用可。全UR禁止の `STRICT_NO_UR` は別。
- `master-duel/deck_assistant/search.py`：schema v1 SQLiteを `mode=ro` / `query_only=ON` で開き、名称NFKC/ケース/空白正規化、種類・レア・属性の厳密絞込、全文原文AND語句検索と出典/バージョン表示。同名別IDはAMBIGUOUS、未収録はUNRESOLVED。**これは字句検索であり、効果の意味・発動条件の解析は未実装。**
- `master-duel/deck_assistant/cost.py`：与えられたレシピ限定。MAIN/EX枚数、`STRICT_NO_UR`、`LOW_RARITY_CORE`、`OWNED_UR_ONLY`、`UR_BUDGET`、`CP_BUDGET`。個人の所持UNKNOWNを0枚と混同しない。banlist未確定、craftable UNKNOWN、CP単価未確認ならPASSではなくINDETERMINATE。デッキの自動生成やゲーム内の現行合法性保証はしない。
- `tools/run_full_regression.py` に新規7件を追加。公開Gitには**コード・架空fixture・集計だけ**を保存し、実JSON/効果本文/所持情報を含まない。

## 全回帰：100/100 PASS

Python標準`unittest`、GitHub正本モジュールをローカル取得し、実Drive本番ZIPを読み取り入力として使用：

| suite | tests | skipped |
|---|---:|---:|
| p1_a0 | 47 | 0 |
| sqlite_store | 13 | 0 |
| zip_store | 9 | 0 |
| voice_staging | 12 | 0 |
| card_master_import | 12 | 0 |
| deck_assistant | 7 | 0 |
| **計** | **100** | **0** |

- 実カード本番ZIP：`MD_PROD_SNAPSHOT_001_FULL_JA_EFFECTS_20261110.sqlite.zip`、SHA-256 `9239a9d8a7888490975e3a01688ed8ee64d8d5d23d2bf0cfd9ef4796be6d2762`。
- 実カード読み取りスモーク：`灰流うらら` の名称/URフィルタPASS、`ドロー`の字句検索（Nで6例取得）PASS、`デッキから`＋`手札に加える`のAND検索（Rで6例取得）PASS。`カオス・ソルジャー` の2候補AMBIGUOUS、`増殖するＧ`は正規化で一意、未収録名称はUNRESOLVED。
- 出力は参照結果のみ。本番ZIPの変更・所持枚数の登録・HEAD切替はいずれもなし。

## M2 所持確認の優先候補（私的資料）

本番DBに存在する18件について日本語表示名の正規化とKONAMI ID一意性、MDレアリティ値を確認し、**所有者専用DriveのDBフォルダへ新規JSON**として保存。`MD_INVENTORY_PRIORITY_CANDIDATES_PRIVATE_20261110.json`、SHA-256 `8c4a770bde101aa9835c4afc55789811f53b02f4941cd40531ee1d6a4fa7102b`。情報は**所持を質問する候補**であり、現行環境の採用推奨や規制合法性を保証しない。全18件の`owned_count=null`、`known_state=UNKNOWN`。加えてデモンスミス/スピードロイド/壊獣は出張パッケージ構成が**未整理**であることだけを記録。利用者からの枚数申告なしには本番所持テーブルへ一切書き込まない。公開Gitに個人用Drive file IDと私的リストの全件は保存しない。

## 技術残件

1. M2：汎用優先候補の枚数申告→P3プレビュー→確定書き込み→Driveバックアップ/独立読み戻し/HEAD切替。所持未登録URのゼロCP保証は禁止。
2. M3：MD禁止・制限snapshot、施行日・フォーマット・未掲載UNKNOWNの正式運用。2026-11-05配布ベクター215件は候補値であり現行公式判定ではない。
3. M4/M5：効果ファセットと関連条件検索、テーマ・出張パッケージの必要/任意部品、EX枠/ロック、適合性検証。原文検索だけでシナジーを確定しない。
4. M6：複数テーマ・レシピ生成、低レア条件と所持・規制・エンジンを結合した候補比較。`LOW_RARITY_CORE`の中核範囲はルールで説明可能にする。
5. M7：生成CP・パック収録/販売/解放条件の時点付きデータと逆引き。「収録候補」を「現在入手可能」とはしない。
6. M8：自然言語UC-01〜07を通したAI問い合わせ、回帰・差分更新と非公開本番の単一ライター運用。

判定はM1初期機能GO、最初のデッキ構築提案全体の完成は**未達**。依頼内容をM1完成と取り違えない。
