> **2026-11-11 D3 read-only lookup**：`owned_decks/lookup.py` の `select_deck` / `verify_and_render` と[横断検索ワークフロー](../docs/OWNED_DECK_CROSS_THREAD_LOOKUP_WORKFLOW_20261111.md)を参照。Drive接続は読み出し側会話で行い、現行フォルダ列挙→catalog現行確認→名前選択→CONFIRMED snapshot取得→SHA・枚数検証。所有数/規制は別途preflight。接続不可や未登録は fail-closed。実所持レシピをGitに出さない。

# 所持デッキ音声登録 — private snapshot v1

公開GitHubには**コード・架空テストだけ**置く。実レシピ・発話・カード個票はGoogle Drive `GPT/MasterDuel/DB/` のprivate保存とする。既存本番HEAD (所持DB) は変更しない。

## データ形式

1デッキの1版 = JSON 1件。例はすべて架空カード。

```json
{
  "schema": "md-owned-deck-v1",
  "deck_id": "synthetic-evil-twin",
  "name": "架空イビルツイン",
  "aliases": ["イビルツイン"],
  "version": 1,
  "supersedes": null,
  "state": "STAGED",
  "entries": [
    {"section":"MAIN", "spoken_name":"架空A", "card_id":"synthetic:a", "quantity":40},
    {"section":"EXTRA", "spoken_name":"架空B", "card_id":"synthetic:b", "quantity":1}
  ]
}
```

- `deck_id` は同じデッキの更新で不変。混合型の区別は名前・aliases・任意variantで維持し、別デッキなら別deck_id。
- `version` は1から単調増加。2以降は直前版のsnapshot SHA256を`supersedes`に保持。古い版を削除しない。
- `STAGED` は中断・枚数不足・ID不明・EX超過でも保存できる。`CONFIRMED` は全カードID解決済み、MAIN40–60/EX15以下のみ。**CONFIRMED はゲーム合法性・所持照合の証明ではない**。
- `spoken_name`は原発話に対応。重複発話は音声スレッド側で原文・行番号・合算根拠をprivateチェックポイントに保持し、確定行では区画とcard_idで一意に集約する。
- 所持台帳への自動加算・更新は厳禁。デッキレシピには未所持カードがあってもよい。
- MD禁止制限・制約・所持枚数やレアリティは、構築時に最新HEADとM3/M4/M5を改めて照合する。

## ローカル検証と私的スナップショット

`master-duel/`から:

```sh
python -m unittest discover -s owned_decks/tests -v
python -m owned_decks validate --input /private/deck.json --db /private/master_duel.sqlite
python -m owned_decks save --input /private/deck.json --db /private/master_duel.sqlite --private-dir /private/decks
python -m owned_decks find --private-dir /private/decks --name イビルツイン
python -m owned_decks show --private-dir /private/decks --sha256 <64文字の実SHA>
```

`/private/decks`は事前に非公開ディレクトリとして作成。保存はSHA命名の不変JSON（0600）で、同一内容の再登録は冪等。これは**ローカルの検証・保存・検索コード**でありGoogle Drive自動接続ではない。Driveへの保存は認証済みChatGPT/Workコネクタから別途実行し、再取得とSHA一致で確認する。GitHub ActionsにDrive資格情報を渡さない。

## 音声スレッドの操作手順

1. ユーザーが「自分のイビルツインデッキを登録」と宣言したら、`deck_id`・variantを確定し、MAIN/EXを10件程度ずつ読み上げる。
2. 未解決カードと区画を確認し、途中終了なら`STAGED` JSONをprivate Driveへ保存・再取得。チェックポイント未成功を「保存済み」と扱わない。
3. 「読み上げ終了」は入力終了のみ。MAIN/EX枚数・カードID照合を見せ、ユーザーの**保存承認**を得てCONFIRMED JSONをprivate Driveに不変の新規ファイルとして保存する。
4. デッキ名、`deck_id`、version、SHA、private DriveファイルID、状態をまとめたprivate索引（例 `MD_OWNED_DECK_CATALOG.json`）へ追記。索引も別ファイルでバックアップし、単一ライターで更新後再取得する。前版は保持。
5. 検索室・構築室で「自分のイビルツインデッキ」と指定されたら、毎回private索引を取得し、名前・aliasesから候補を挙げ、選んだdeck_idの最新CONFIRMED版を取得。JSONのSHAとカードIDを照合してMAIN/EXを返す。見つからなければ未登録と明示する。STAGEDのみの場合は未完成と明記する。
6. 別デッキとの同名・複数variantがあれば候補一覧で区別する。索引をGitHubや会話メモリの固定IDだけで代用しない。

**現状**: v1ローカル検証・検索器を追加。ユーザーの実所持デッキはまだ未登録。private Drive catalog自動同期および本番SQLiteの`decks`/`deck_cards`書込器は未実装。実運用ではDriveコネクタ経由の保存・索引更新を要する。

## M2-D1：private catalog（2026-11-11）

保存済みデッキの発見には、個々のsnapshot ZIP/JSON名ではなく、非公開Driveの `MD_OWNED_DECK_CATALOG.json` を入口として使用する。

- `owned_decks/catalog.py`：catalog v1検証、SHA算出、デッキ名/aliases/IDによる候補検索、最新CONFIRMEDポインタ抽出、取得したsnapshotとのID・版・SHA照合。
- `schema=md-owned-deck-catalog-v1` / `generation` / UTC `updated_at` / `decks[]`。各デッキに `deck_id`（重複不可）、`name`、`aliases`、`variant`、`versions[]`。各版は連続番号、`STAGED|CONFIRMED`、snapshot SHA256、小文字、Drive file ID、直前版SHAを`supersedes`に保持。
- 複数バリアントが同じ愛称に一致したら `AMBIGUOUS` を返し、勝手にひとつへ確定しない。登録なしは `NOT_FOUND`、STAGEDのみなら `STAGED_ONLY`。確認済みの旧版があり最新がSTAGEDの場合は、最後のCONFIRMED版を候補にする。
- **D1で作成した0件索引**：非公開Drive `GPT/MasterDuel/DB/MD_OWNED_DECK_CATALOG.json`、Generation 1。初期SHA256 `dc1b899a157918093c28aeb87b877904eb529e447bdec14ca49df260b7623734`。ID/ハッシュは初期作成時の監査証跡であり、**後続処理は毎回フォルダで現行索引を再発見**する。索引が複数存在した場合、更新順で勝手に選ばず競合として保留。
- D1は**空カタログの初期化・検証のみ**。snapshot upload→catalog安全更新→読戻しのD2、本会話外からの経路検証D3、実デッキ登録D4は未実施。

ローカル例（GitHubには架空データのみ）：

```sh
python -m owned_decks.catalog init --timestamp 2026-11-11T00:00:00Z --output /private/MD_OWNED_DECK_CATALOG.json
python -m owned_decks.catalog validate --input /private/MD_OWNED_DECK_CATALOG.json
python -m owned_decks.catalog resolve --input /private/MD_OWNED_DECK_CATALOG.json --name イビルツイン
```

Driveへの認証付き保存・取得はChatGPT/WorkのGoogle Drive接続を使用し、GitHub Actionsや公開Issueでprivateデータを取り扱わない。

## M2-D2：Drive公開経路（2026-11-11）

`owned_decks/publish.py` は**Drive接続を内包しない確定的な安全ゲート**。`verify_uploaded_snapshot` → `prepare_catalog_update` → `verify_base_before_activation` → **認証済みDrive接続で既存catalog更新** → `verify_activated_catalog` の順に使用する。個人データにGitHub Actionsや公開Issueを使わない。

### 保存手順（PRODUCTION / 合成テスト双方で遵守）

1. Google Drive `GPT/MasterDuel/DB/` の対象カタログを**フォルダ列挙で1件だけ確認**し、現在のカタログを別要求でダウンロードしてSHA/スキーマ検証する。複数候補は競合として停止。実カードの場合は`MD_CURRENT_HEAD.json`が指す最新カードマスターSQLiteをSHA検証済みの読取専用で使用する。
2. 音声整形したsnapshotを`check_snapshot`で検証。本人に内容とMAIN/EX集計を提示し、**保存承認**を得る。STAGEDは途中保存、CONFIRMEDは承認済み・カードID照合済みとし、最新MD禁止制限の検証済みという意味ではない。
3. `<snapshot-sha256>.json`をprivate Driveへ**新規アップロード**（同じ名前を上書きしない）。別API要求で実ファイルをダウンロードし、`verify_uploaded_snapshot`で期待バイト列・SHA・カードマスターID照合が一致することを確認。ダウンロード不一致時はカタログを更新しない。
4. 取得した実DriveファイルIDを使い、`prepare_catalog_update`で候補Generation+1を生成。既存`deck_id`なら直前snapshot SHAを`supersedes`に保持し、版番号を連続させる。新しいvariantは別`deck_id`で登録。同じデッキの名称や別名変更は無断上書きせず別の明示移行とする。
5. 更新前のcatalogファイルをprivate Drive上で**別名バックアップ**。そのバックアップを独立取得・SHA照合し、内容一致を確認する。更新直前に現行catalogを**再取得**し、`verify_base_before_activation`で初回の内容と一致することを確認。単一ライター維持。
6. 認証済みDrive接続でcatalogの**既存ファイルIDへ候補JSONバイトを置換**。`files.update`はatomic CASを提供しないため読取・書込間の同時更新を完全防止できない。通信失敗や対象競合では成功とみなさず、既存バックアップを保持する。
7. 別要求で現行catalogを独立取得し`verify_activated_catalog`。候補と一致し、各snapshot参照が正しいことを確認した時点だけ`COMMITTED`。不一致は`FAILED/HOLD`で停止し、バックアップと新規アップロード済み未参照snapshotを保全。無断自動再試行・上書き・削除をしない。

### D2 private Drive合成往復実績

- **隔離フォルダ**：`GPT/MasterDuel/DB/MD_D2_SYNTHETIC_TEST_20261111/`。本番索引 `MD_OWNED_DECK_CATALOG.json` と `MD_CURRENT_HEAD.json` は不変。実レシピではなく架空カードIDのみ。
- synthetic snapshot v1 `STAGED`：SHA `fc4b2da0ff1f0760b29c7d687771f0d09c57c648dcc43c94ebf2aef6171d236f`。v2 `CONFIRMED`：SHA `204427e503d70370a7818c2043f202f9c5c908de4bd32c50c9110aa447fa2b15`。後者はMAIN40/EX1（全て架空カード）。両者をprivate Driveに新規保存・別要求で独立取得し、期待JSONバイト列・SHA一致。
- synthetic catalog Generation 1→2（v1 STAGED）→3（v2 CONFIRMED）、独立読戻しSHA `727baecffa11fee36544d3822a1a058d45a71a549fe4bb429f180a60b680fa18`。
- Generation 1/2のバックアップも別名Driveファイルに保持・独立取得して各SHAを照合。旧snapshot未変更、索引は同一Drive IDのまま版追加。これは合成データ実地往復試験であり、**実デッキ1件目の登録完了やD3横断検索の完了を意味しない**。
