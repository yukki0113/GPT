# M2-D3 所持デッキの他スレッド横断検索 — 共通読出し正本（2026-11-11）

## 目的・トリガー

構築室・カード検索室・新規チャットにおいて、ユーザーが「**自分の**イビルツイン」「**持っている**デッキ」「**登録済み**のスプライト型」等と述べた場合、公開レシピや会話メモリから推測する前に、**Google Drive上の非公開所持デッキ索引**を検索する。ユーザーが単に「イビルツインの構築例」と一般検索を求めた場合は所有デッキと混同しない。

**前提**: その会話で認証済みGoogle Drive接続が利用可能なこと。チャットを新しく開くだけで自動的にDBが永続マウントされるわけではない。接続不可の会話では検索済みと偽らず、Drive接続を利用できる実行環境でやり直す。

## 正本探索（毎回行う）

1. GitHub `yukki0113/GPT` の最新mainの本書、`owned_decks/README.md`、`owned_decks/catalog.py` と `owned_decks/lookup.py` を参照する。
2. 認証済みGoogle Driveで `GPT/MasterDuel/DB/` を**フォルダ列挙**。フォルダの既知起点はID `1QdnvkJ7dNR4Z-HIMuOZenDPm0aStYzfQ`。その直下にある厳密名 `MD_OWNED_DECK_CATALOG.json` が**1件のみ**であることを検証する。0件・複数件なら停止。前回の会話に残るファイルIDを最新だと推定しない。
3. 現行catalogを独立ダウンロードし、JSON形式・generation・スキーマ・全ポインタ・内容SHAを `owned_decks.catalog.validate` で検証。canonical形式の生バイトと一致すること。
4. ユーザーのデッキ名・通称を `owned_decks.lookup.select_deck(catalog_raw, query)` に渡す。
   - `NOT_FOUND`: 未登録。一般のデッキレシピで穴埋めしない。
   - `AMBIGUOUS`: 候補デッキ名/variantを表示して選択を求める。勝手に決定しない。
   - `STAGED_ONLY`: 入力途中のみ。確定レシピとして提示しない。
   - `READY`: **最新CONFIRMED版**のsnapshotの `drive_file_id`, `version`, `snapshot_sha256` を取得。明示的な旧版指定があればその版を返す。
5. 索引が指すDrive snapshotを**実IDで独立取得**し、`owned_decks.lookup.verify_and_render(catalog_raw, selection, snapshot_raw, db_path=None)`で照合する。任意フィールドやファイル名だけで中身を信用しない。snapとcatalogのSHA、deck_id、version、state、supersedes、MAIN/EX枚数および各カード最大3枚を検証。
6. **カード名は登録時に読み上げた `spoken_name` で表示**。正式名の確認が必要なら、別途最新 `MD_CURRENT_HEAD.json` が指すカードマスターをSHA検証して読み取り専用でカードIDから解決する。DB未取得のときは登録時の `spoken_name` を「正式名称再照合済み」と表示しない。
7. 出力：デッキ名/variant、version、CONFIRMED、MAIN枚数、EX枚数、カード名と採用数、`catalog_generation`、`catalog_sha256`、`snapshot_sha256`、取得時点、未検証事項（所持/MD禁止制限/レア/最新マスター）。デッキレシピのコピーを公開GitHubやIssueへ書かない。

## 構築室との責務分離

登録済みデッキは**ユーザー申告の構築レシピ**であり、汎用カードの実所持数を示すものではない。採用カードの生成費・規制・効果・所持判定を求められたら、別途M6の最新HEAD全件preflightで確認する。参照だけならM3/M4/M5の全再ロードを必須にしない。

## 継続・障害対応

- 同一会話での続きは取得済み情報を文脈として使えても、最新版の問い合わせではcatalogを再取得する。
- 他スレッドでは前の会話のメモリ・固定DriveファイルIDは信頼せず、本書とDriveフォルダから再発見する。
- Google Driveが接続されていない/取得不能、SHA不一致、重複catalog、catalogリンク欠損、snapshot改竄なら **BLOCKED** と明記し、架空のデッキを答えない。
- 本書は**新しい会話への動作方針**であり、ChatGPTが任意の新規スレッドに自動で初期指示を注入する機能ではない。既存の検索室・構築室にはこの仕様を組み込み、次回そのスレッドが最新GitHub仕様を参照する際に適用する。

## スモークケース

1. 登録済み・別名「イビルツイン」を指定 → 正式名称「イビルツイン・スプライト」、最新版v1、MAIN40/EX15、snapshot SHA照合PASS。
2. 未登録名 → `NOT_FOUND`。
3. 2種類以上の同名別variant → `AMBIGUOUS`。
4. STAGEDのみ → `STAGED_ONLY`。
5. 旧CONFIRMEDに新STAGEDが追加された場合は、旧CONFIRMEDを返す。
6. snapshot改竄/不一致とcatalog再取得差異はfail-closed。

## 証拠の残し方

公開Gitに実デッキ名・個別カード一覧・個人デッキの具体的参照先を恒久記載しない。個別検索時の結果は会話内またはprivate監査に留める。合成fixture・件数・SHA・CI結果のみ公開可能。
