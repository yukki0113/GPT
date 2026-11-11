# M2-D 所持デッキ台帳 — Google Drive保存・横断検索マイルストーン（2026-11-11）

## 0. 位置付け
- 工程ID: **M2-D**（M2 Inventoryの隣接工程、Owned Deck Registry）。M1〜M8の番号を変更しない。M5-C再開より先に、所持デッキの音声入力受け入れを小規模で完成させる。
- ユーザー受入シナリオ: 音声登録室で「自分のイビルツイン・スプライト混合型」を登録し、別の構築室で「自分のイビルツインデッキを確認して」と依頼すると、private DriveからMAIN/EXが取得できる。
- 正本: 公開GitHub `master-duel/` はスキーマ・実装・架空テスト・仕様のみ。実デッキ・音声記録・私的索引は非公開Google Drive `GPT/MasterDuel/DB/`。ゲームのデッキリストとユーザーの所持台帳を混同しない。
- M2-Dの達成はM5-C/M6自動構築の完成を意味しない。

## 1. 現在地
- **D0 完了（2026-11-11）**: [owned_decks](../owned_decks/README.md)にprivate snapshot v1のローカル検証・保存・SHA読み戻し・名前検索・合成テストを実装。PR #2512をmainへマージ（commit `c449930b8523dc525c8f524f89a99a36bcfa21cf`）。回帰251テスト、1スキップ、失敗0。
- **D1 完了（2026-11-11）**: privateカタログのスキーマ/Validator・合成テスト、Drive空索引Generation 1のアップロード/別要求読戻し・SHA一致。空索引には実デッキなし。参照 [owned_decks](../owned_decks/README.md)。
- **D2 完了（2026-11-11）**: `owned_decks/publish.py`にprivate snapshotアップロード独立読み戻し検証・次世代候補生成・stale検出・更新後独立検証を実装。架空snapshot STAGED v1→CONFIRMED v2を別private検証フォルダで保存、catalog Generation1→2→3に更新、バックアップ・SHA独立確認成功。実個人用catalogは0件のまま。[D2運用手順](../owned_decks/README.md)。
- **D3 実装・Drive現物検証（2026-11-11）**：`owned_decks/lookup.py`および[他スレッド横断検索手順](OWNED_DECK_CROSS_THREAD_LOOKUP_WORKFLOW_20261111.md)を追加し、構築室・検索室の指示書へリンク。Driveの現行索引Generation2→実CONFIRMED snapshot v1のSHA/MAIN40/EX15検証。実際に異なるチャットUIでのエンドツーエンド起動はこの会話から操作できないため、D4で別会話受入試験として残す。
- **D4 受入完了（2026-11-11）**: ユーザー提供の別スレッド表示結果で、private Driveから登録済みデッキのCONFIRMED v1、MAIN40/EX15、catalog Generation2、snapshot SHA256照合PASS、読取専用を確認。実際の投入は音声ではなくユーザーの文字起こしMarkdownによるレシピ登録だったため、音声入出力の実端末試験は別途運用確認事項。個別の私的レシピ本文はGitHubに保存しない。
- 現行汎用所持台帳HEAD / SQLite / banlist / M4 / M5は本追加工程で勝手に更新しない。

## 2. マイルストーンとゲート

| ID | 状態 | 内容 | 最低受入条件 |
| --- | --- | --- | --- |
| D0 | DONE | private snapshot v1 validator、card_id照合、SHA命名・ローカル検索、合成試験 | GitHub main反映、CI回帰成功、private実カードがGitHubへ漏洩しない |
| D1 | DONE | privateデッキカタログ `MD_OWNED_DECK_CATALOG.json` のschema / validator / 初期作成 | 0件索引をDriveに実保存・独立取得・内容/SHA一致。同名複数variant、aliases、deck_id、版、ステージングと確定の区別を定義 |
| D2 | DONE | privateデッキJSONアップロードと索引更新の運用経路 | 架空デッキのSTAGED→本人確認→CONFIRMEDを模擬、保存結果ID取得、独立読み戻し、SHA一致、カタログ更新→再読込、バックアップ/旧版保持。失敗時に既存版・索引を壊さない |
| D3 | DONE | 構築室・検索室の自然言語名前検索ルーティング | 新規会話で「自分のイビルツイン」を指定→現行Drive索引取得→候補選択→最新CONFIRMED版取得→SHA・card_id・MAIN/EX照合。未登録・曖昧・STAGEDのみを区別し、会話メモリや旧File IDを正本扱いしない |
| D4 | DONE (テキスト登録と別会話読出し) | 受入・運用引継ぎ | 合成回帰＋Drive往復＋ユーザー提供の文字起こしレシピ登録→別スレッドで読出し成功。版、snapshot SHA、MAIN/EX枚数、索引世代を確認。実機音声入力試験は対象外として残す |

## 3. データモデル（最小契約）

### private catalog (v1)
- `schema = md-owned-deck-catalog-v1`
- `generation` と `updated_at` と `decks[]`。
- 各デッキに `deck_id`（不変）、`name`、`aliases[]`、`variant`（任意）、`versions[]`。
- 各版に `version`、`state`（STAGED/CONFIRMED）、`snapshot_sha256`、`drive_file_id`、`supersedes`。
- 検索時は現行索引からデッキを解決し、`CONFIRMED`の最大版を採用。複数同名/variantは曖昧扱いで候補提示。`STAGED`のみなら未完成と表記。
- カタログ自身をprivate Driveでバックアップし、書込直前に再取得。単一ライター、競合時は中止。Driveにはatomic CASがないため完全な競合防止と断定しない。
- 実レシピと個人情報を公開GitHub/Actions/Issueへ送らない。

### snapshot (既存v1)
- `schema = md-owned-deck-v1`、`deck_id`、`name`、`aliases`、`version`、`supersedes`、`state`、`entries`。
- 行は`section=MAIN|EXTRA`、`spoken_name`、確定された`card_id`、`quantity`。
- 不完全/不明名/枚数異常はSTAGEDに保持できるが、CONFIRMEDへ昇格させない。音声入力時の原文・訂正経緯はprivateステージング側で管理する。

## 4. 不変条件と受入ケース
1. デッキA/Bで共用の《架空カード》3枚をそれぞれ登録しても、汎用所持枚数は変わらない。
2. 0件catalog・未登録デッキの問い合わせ・同名複数variant・STAGEDのみ・見つからないcard_idでfail-closed。
3. MAIN 39/61、EX16、単一カード4枚、区画不明、未解決カードは入力を失わず、CONFIRMED登録を拒否。
4. 旧版v1を保持してv2を追加し、通常検索は最新CONFIRMED、明示指定で旧版を取得できる。
5. snapshot/catelogの改竄、SHA不一致、Driveファイル欠損、途中保存失敗を「成功」と報告しない。
6. 本番所持DB HEAD（Generation等）、汎用所持枚数、M3/M4/M5を変更しない。
7. 音声会話中に接続ツールが使えない場合はテキスト化後に保存。会話ログだけを永続保存と呼ばない。
8. レシピ登録のCONFIRMEDは音声照合済みを意味し、現行MD規制/所持枚数/ゲーム内展開の検証済みを意味しない。

## 5. 作業順と境界
1. D1: schema・validator・架空データテスト→private 0件catalog作成・再取得。
2. D2: **完了**。架空snapshotでprivate Drive往復・版更新/失敗ガード・バックアップを検証。実所持DBは不変。
3. D3: 読み出しコード・構築室/検索室の共通運用仕様を反映。別スレッドでの実読出しはD4の利用者提供証跡で確認済み。
4. D4: ユーザーのMarkdown文字起こしレシピ登録と別会話からの独立参照を確認済み。音声入力UIの実端末利用試験は未実施であり、音声入力機能の完成保証とは分離する。
5. D4の上記受入完了をもって、次工程はM5-C C0以降へ戻る。必要なM6の登録済みデッキ取得連携は本工程で最低限用意するが、レシピ自動生成は対象外。

## 6. 参照
- [所持デッキsnapshot v1](../owned_decks/README.md)
- [音声所持・デッキ登録スレッド](VOICE_INVENTORY_AND_DECK_REGISTRATION_THREAD_WORKFLOW_20261110.md)
- [デッキ構築標準手順](DECK_BUILD_STANDARD_WORKFLOW_20261110.md)
- [カード・ギミック検索室仕様](CARD_AND_ENGINE_SEARCH_THREAD_WORKFLOW_20261110.md)
- [.gpt/GITHUB_OPERATION_POLICY](../../../.gpt/GITHUB_OPERATION_POLICY.md)
