# 既存JSON→SQLite 基本カードマスター投入設計（2026-11-10）

## 結論と実装境界

**新規サイト巡回ではなくDrive既存JSON 2本のクロスウォークとSQLite投入が中心。** P0ではMD 13,948件、日本語名補完 13,948件、KONAMI ID一意 13,948件を既に確認済み。最初は**基本メタデータのみ**を検証用SQLiteに生成し、実データに関するP1-A1 NO-GOを解除したと誤認しない。本番 HEAD を更新せず、実際のフルテキストの継続DB化は利用条件と別ゲートを確認後に決定する。

汎用カードや出張エンジンの優先リストは**この投入の前提ではない**。全カードIDと名前が引ける状態を先に作る。現行P3音声ステージングは未解決名を保持できるため、前後工程は独立。

## 入力（現行Drive正本を再探索）

Drive `GPT/MasterDuel/source/` に既存：
- `master-duel-raw.json`（MD候補13,948行、83,388,036バイト、監査SHA `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b`）
- `cards.json`（OCG/TCG候補14,416行、110,258,836バイト、監査SHA `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7`）
- `current.vector.json` は2026-11-05版の制限候補215件で、**基本マスター投入には使わない**。

投入前にDriveのフォルダ一覧→最新のファイルID/サイズ→ダウンロード→SHA-256を再照合。監査SHAと違えば**別入力版として中断・差分監査**。上記数字は2026-11-09の過去監査値であり現行ダウンロードでの再検証を意味しない。詳細：`docs/DRIVE_SOURCE_RESOLUTION.md` と `audits/p0_202611/P0_JA_CROSSWALK_20261109.md`。

## A. JOIN／識別契約

1. JSONルートは両方とも配列。MDの `en_name` と `cards.name.en` をまず完全一致 JOIN（監査済み13,931件）。1対多を許容する。
2. 完全一致しない13件はNFKC/casefoldと句読点・空白処理で候補抽出し、属性・種別照合を条件にする。正規化一致だけで確定しない。
3. 例外4件は監査手順に従い明示解決：`Black Luster Soldier` の通常/儀式別カードは別KONAMI ID、`Dark Magician` と `Polymerization` の複数パスコード・イラストは**同じKONAMI IDを持つ候補だけ**ゲーム上1カードに集約。未知の多重候補は要手動判定。
4. MD rawの `yugipedia_page_id` とcards側の記事IDは互換キーではない。パスコードや日本語名も主キーにしない。
5. canonical `card_id` は**KONAMI ID由来の不変キー**（例 `konami:12345`）。`konami_id` 自体にユニーク制約を維持。カードID文字列の規則は一度固定し将来変えない。カード名重複を許す。別イラストの画像ID一覧を今の `cards` に無理に詰めない。

## B. マッピング（基本メタデータ限定）

| 入力 | 既存SQLiteテーブル/列 | ルール |
|---|---|---|
| cards.`konami_id` | `cards.konami_id` / `cards.card_id` | 正の整数必須。欠損・重複・多対多は本番化を拒否 |
| cards.`name.ja` | `cards.name` | `<ruby>` を解析し本文を表示名として残し、`rt` 読み仮名で重複させない。読み仮名は将来のalias用に別管理 |
| MD.`card_type`, `types` | `card_attributes.kind` | MONSTER / SPELL / TRAP等へ明示マップ。未知タイプは推測せず監査 |
| MD.`attribute`, 種族・level/rank/ATK/DEF | `card_attributes` 同名相当列 | 存在する項目のみ。非適用と欠損を0と混同しない。LINK値は `link_arrows` の型確認と変換テストまでNULL |
| MD.`rarity` | `md_catalog.rarity` | N/R/SR/URのみ。出典を `rarity_source='MD:yaml-yugi:<snapshot>'` として保存 |
| 明示的な MD.`craftable=No` | `md_catalog.craftable='NO'` | 17件のみ。その他は全て UNKNOWN。欠損をYESにしない |
| 各入力の参照識別子 | `source`, `acquired_at`, `verification` | スナップショットID/SHA参照と取込日。**未検証はUNVERIFIED_SOURCE**、画面照合済みサンプルと一律にGAME_VERIFIED扱いしない |

第1段階では **`card_texts`, `banlist_*`, パック・現行販売・出張分類、所持`inventory`には書き込まない**。効果本文 `MD.ja_text` は日本語文字列13,948件が存在するが、MD公式全文一致と保存・利用条件の確認は未完了。旧 `cards.text.ja` との差分も大きいため、無検証混合禁止。禁止制限ベクトルにないカードを無制限3枚とみなさない。

既存schema v1で表現できない読み仮名・表記揺れ・クロスウォーク例外・取込manifestは**公開Gitにコード／空スキーマだけ**追加し、実データ版のprivate manifestを別ファイル保存。初回投入のために schema v1 を大規模変更しない。

## C. 一括ETL手順

1. Driveの入力2件のSHA固定、データとライセンス状況を監査。
2. `json.load` で2配列解析。中間のID照合はメモリ上で行い、`konami_id`／MDレアリティ／日本語名の重複・例外・不一致をレポート。
3. **dry-run** で件数・JOIN方式別件数・エラー・入力ハッシュ・非空率・推定ZIPサイズを表示。個別のカード本文や全件名は公開ログに出力しない。
4. 独立した空の検証用SQLiteスナップショット（schema v1）を生成。**BEGIN IMMEDIATEを伴う一括トランザクション**で `cards` → `card_attributes` → `md_catalog` の順に投入する。既存 `inventory` は一切変更しない。
5. 投入後、card件数、`konami_id`一意性、日本語名非空、MDレアリティ4種・元の内訳一致、外部キー、SQLite integrity、代表例外の照合、P3 `resolve_name` の曖昧状態、検索を検証。
6. `zip_store` のSQLite backup API／再ZIP・再展開・SHA照合を適用。Driveの **別名の不変な検証用ZIP** とprivate manifestに保存→独立再取得・SHA一致確認。
7. **本番 `MD_CURRENT_HEAD.json` を切り替えない**。データの採用・権利とP1-A1ゲートを別判断し、承認後のみ単一ライターがHEAD切替。古いベースラインを保持し、CASがないので同時書込禁止。

## D. 完了基準／保留判断

固定SHAの入力版について：
- 13,948枚のMD候補が1レコード1論理カードとして出力できる（入力版が変更されていれば新規監査値を優先）。
- 13,948件のMD rarityと日本語名、KONAMI ID、基本種別が取得可能。JOIN未解決/同一KONAMI IDの矛盾/不正型=0。新しい不一致が出たら**サイレント補正しない**。
- メタデータの `verification=UNVERIFIED_SOURCE` を維持し、MD公式検証を宣言しない。
- 所持枚数の UNKNOWN を維持し、P3ステージング・検索での動作確認。
- private Drive ZIPのSHAとintegrity一致。実カードDBは **P1-A1 NO-GO中は本番に昇格しない**。
- 転記・転載権限とカード全文の利用条件は**別ゲート**。第2段階の効果文、禁止制限、パック情報は後続に分離。汎用／エンジン優先所持登録リストも別工程。

## E. 次の実装PR

Codex Cloudに `master-duel/card_master_import/` 等のETLモジュール、例外固定fixture、CSV/JSON dry-run監査出力、合成テスト、Drive I/Oを分離したprivate ZIP出力を実装させる。全件テストは入手可能なDrive JSONでの**ローカル合否と監査数値のみ**報告し、原JSON・日本語効果本文・個人データは公開PRに含めない。既存P1/P2/P3テストに回帰。Work/ChatGPTがDriveの権限・実保存・読み戻しを検証する。

**工程はシンプルに保ちつつ、名前／記事IDの誤結合と実カードデータの利用条件だけは省略しない。**
