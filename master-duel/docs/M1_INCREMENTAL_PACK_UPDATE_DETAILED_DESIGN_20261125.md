# M1-U 新パック・カードマスター差分更新 詳細設計 v1.0
2026-11-25 / 設計（未実装）

## 目的
新パック実装時にユーザーの全カード撮影や全件MD JSON更新を要求せず、公開情報を許諾範囲で取得し、現行MyDBへ差分反映する。初回受入は11/24実装ザ・レルム・オブ・トリニティ。既存M6の追加ゲートや全召喚証明は対象外。

## 既存実装との関係
card_master_import/importer.py, text_import.py, monster_types_migration.py, stage1_gen8_migration.py, stage2_gen9_migration.py の形式を利用する。旧移行の固定SHA・固定件数は再利用しない。schema v4を維持。inventory_m2/README.md の単一ライター・ZIP/HEADバックアップ・独立読み戻しに従う。M3は既存承認済み規制JSONを維持。
M6 discovery.py は card_texts をcard_id/languageだけでJOINするため複数ja版は検索重複を招く。現行ja版を1件だけ保持し、改訂前の全文・版・SHAは非公開履歴と旧DBに保持。既存複数版があれば対象カードのみ明示選択し、推測で消さない。

## モジュール
card_master_import/incremental/{discovery,resolver,normalize,diff,apply,reconcile}.py およびtests。Web/Drive取得はChat/Work、Pythonは取得済み入力の決定的処理。外部サイト全体の巡回はしない。

## U1 収録一覧
起動: ユーザーの新パック更新指示。パック名、種別、実装日、終了日(任意)、カード名、MDレアリティ(不明可)、出典URL、観測時刻を収集。公式MD告知を実装根拠に、Game8/MD攻略情報を一覧・MDレアの補助に用いる。全件MD JSONが新しければ優先、未更新でも進める。収録一覧の取得範囲（全件/部分/不明）を記録。再録と初実装は既存DB有無だけで断定せず、実装資料と照合。未登録はDB追加候補であって初実装と同義ではない。日付はJST。

## U2 解決・正規化
KONAMI ID、正式日本語名、正規化名、英語名・属性種別による補助照合の順。曖昧IDは保留。OCG公式DB・YAML Yugi個別/OCG JSONから日本語名・属性・原文を補完、MD側の実装とレアはMD資料で確認。OCGとMDの効果差が疑われる場合は対象のみ保留しMD原文優先。海外先行でID/日本語文が取れない場合は仮IDを本番に作らない。ユーザー確認は最終手段。取得不能情報は推測しない。
非公開入力 schema md-card-incremental-update-v1: batch_id,effective_on,base_generation,base_sqlite_sha256,pack metadata,cards[],unresolved[]。各カード card_id,name_ja,kind,attribute,race,level,rank,link,atk,def,rarity,craftable,ja_text,monster_types,spell_trap_property,link_markers,pendulum_scale,ja_pendulum_effect,sources（項目別URL/取得日/検証段階）。出典のない値は確定扱いしない。
cards/card_attributes/md_catalog/card_texts/card_monster_types/card_spell_trap_properties/card_link_markers/card_pendulum_details/card_extra_material_requirements の既存形式へ変換。?攻守=NULL、非該当=NULL、craftable=UNKNOWN、所持は行なし=UNKNOWN。EX素材は既存extract_material_requirementを用い原文SHAを保持、UNPARSED許容。通常・効果以外も既存列挙値準拠。日本語原文・ID・MD実装・必要基本属性が不足なら対象のみ保留。レア不明はNULLで登録可能、費用・レア指定M6候補は保留。

## U3 差分・適用
INSERT/UPDATE_TEXT/UPDATE_RARITY/UPDATE_ATTRIBUTES/REPRINT/NO_CHANGE/PENDING。再録だけならマスター変更なし。旧値・新値・根拠をprivate差分に保持。不明値で既知値を上書きしない。変更なしの再実行はno-op。候補DBは最新HEADのSQLite複製、事前確定した差分をBEGIN IMMEDIATEで適用し失敗時rollback。非対象カード行およびinventory/inventory_batches/inventory_history/decks/deck_cards/banlist_snapshots/banlist_entriesの全行ハッシュを保持。規制変更はM3別イベント。入力候補のbase SHAが変化したら差分再計算。旧版効果をprivate履歴へ退避し、現行テキストと素材アンカーを同時更新。旧版保持の確認後に昇格。

## パック索引（M7補助）
別private SQLiteまたはJSON。packs: pack_id,name_ja,pack_type,available_from,available_until,source_url,observed_at。pack_cards: pack_id,card_id,pool_role(PICKUP/COMMON/UNKNOWN),effective_from,effective_until,source_url。複合キーpack_id/card_id/effective_from。既存全パックの調査は不要。収録終了とカードMD実装を混同しない。未解決カードは一覧候補に保持し正式ID確定後に結合。パック索引の不完全さでカード追加を止めない。

## U4 索引・保存
M4効果分類、M5名称/効果関連索引は変更カードを対象に更新、既存処理が全件再生成のみ対応ならローカル再生成可。M5出張・汎用評価は必要時追加のみ。SHA依存の派生索引は旧SHAを黙って書き換えない。内容再照合または再生成し、未更新索引は旧版と明記し現行カードマスター検索へフォールバック。M6実行用入力は新SHAで生成。古いレシピ・結果は履歴保存。M6スコアや審査ゲートの変更なし。
最新HEAD、元ZIP、元SQLiteのSHA検証。候補SQLite integrity_check/FK、件数、非対象行ハッシュ、カード種別・属性・効果文一意性・素材原文SHA、所持不変を検証。新規カードの正式M6-5A検索（MAIN/EX・レア）を確認。レアNULLは名称/効果検索確認。旧カード数は固定値にしない。
非公開Driveへ更新バッチ・未解決・監査・旧HEAD/ZIPバックアップ・新ZIPを保存。候補を独立取得しSHA確認。最新HEAD再取得後に単一ライターでHEAD更新（atomic CASなし）。Drive更新には2026-11-24 M3追補で実証したステージング→fetch→正式file_uri参照を使用。生成ファイルのコネクタ受渡しが失敗したら成功としない。HEAD再取得と参照ZIP再取得までが完了条件。世代は現行+1、schemaはv4のまま。障害時は旧HEAD保全、曖昧な書き込みは現行状態を再観測し復旧判断。
カード追加が0件の場合は本番HEADを更新しない。パック索引のみ更新可能。

## U5 後日照合
新しいMD JSON入手時、先行登録ID・効果・属性・MDレア・実装状況を比較。一致は出典追記、矛盾は対象項目を確認して差分更新、未解決は再試行。元JSONは版・SHA別に保持。MD JSON不掲載のみで既存カードを削除しない。全件再調査・全件再登録は不要。

## テスト・受入
合成: MAIN/融合/S/X/リンク/P/魔法罠追加、?攻守、未知レア、ID曖昧、部分成功、再録no-op、効果改訂・素材アンカー一致、既知値保護、重複再実行、base SHA競合、rollback、所持・規制・デッキ全行保持、HEAD読戻し不一致。
実データ: 今回のパックで取得できる一覧を照合し、既知の新規カードを実際に登録、既存検索で取得、新旧件数・未解決・SHA・Drive読み戻しを確認。全カード実演、全M5出張更新、全パック網羅は受入条件にしない。収録一覧が部分なら明示し全件完了としない。
報告は追加/更新/再録/未解決件数、世代、正本保存成否を短く。公開GitHubには仕様・コード・合成テスト・集計のみ。実カード全文・所持・DBは非公開Drive。
