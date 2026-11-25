# M1-U MD新規実装カード・マスター差分更新 詳細設計 v1.1
2026-11-25 / ユーザー方針反映・再設計（U1部分実装済み、U2〜U5未実装）

## 目的・品質方針（v1.1 正式）
MyDBは公式カードDBの複製ではなく、GPTがテーマ・レアリティ・カードの動き・相性を把握して実用的なデッキを構築する知識基盤。新規UR生成0を支えるMD実装、MDレア、所持、規制、カード同一性を重視し、効果は構築判断に必要な意味精度を求める。一字一句のMD/OCG一致、全カードの裁定証明、全収録枠の網羅を登録ゲートにしない。
同一OCG/MDカードは、反証がない限りOCGの基本属性・日本語効果を通常の情報源として採用する。これは運用上の仮定であり公式の完全一致保証ではない。OCG由来であることだけで検索・M6採用を制限しない。具体的な効果差・エラッタ・裁定差が構築に影響する場合のみ対象を確認する。全件一致監査は必須にしない。
更新単位は新パック自体ではなくMD新規実装イベント。セレクション、シークレット、ストラクチャー、配布等を含む。パックは発見の入口およびM7補助。初回は2026-11-24のザ・レルム・オブ・トリニティおよび同日別経路の実装候補。別経路を同パック所属とみなさない。

## MyDB収録範囲・品質
| 項目 | 収録・更新方針 |
|---|---|
| 新規MDカード | 確認済み実装・一意ID・名称・必要基本属性・効果内容を追加。レア不明はNULL |
| 既存カード再録 | マスター変更なし。レア・効果・属性の実質変更が確認された場合のみ更新 |
| イラスト違い | 同じ論理カードIDに集約。別カード・別所持行を作らない |
| OCGのみ | MD実装根拠がなければ本番MDカタログに追加しない |
| MD先行・海外先行 | MD固有情報で解決。既存ID方式・日本語本文が確定しない場合はprivate候補として保留 |
| テーマ・動き | M4/M5の既存分類・名称/効果関連索引を更新。GPTの候補発見を優先し、全テーマの手動展開解説は必須にしない |
| MDレア・生成 | MD根拠のみ。OCGレアを転用しない。UNKNOWNは費用確定に使わない |
| 所持・禁止制限 | 共通台帳とM3運用を維持。新カード所持未登録はUNKNOWN |
| パック全収録・販売終了 | M7補助、任意の独立更新。未取得でもカード追加可能 |


## 既存実装との関係
card_master_import/importer.py, text_import.py, monster_types_migration.py, stage1_gen8_migration.py, stage2_gen9_migration.py の形式を利用する。旧移行の固定SHA・固定件数は再利用しない。schema v4を維持。inventory_m2/README.md の単一ライター・ZIP/HEADバックアップ・独立読み戻しに従う。M3は既存承認済み規制JSONを維持。
M6 discovery.py は card_texts をcard_id/languageだけでJOINするため複数ja版は検索重複を招く。現行ja版を1件だけ保持し、改訂前の全文・版・SHAは非公開履歴と旧DBに保持。既存複数版があれば対象カードのみ明示選択し、推測で消さない。

## モジュール
card_master_import/incremental/{discovery,resolver,normalize,diff,apply,reconcile}.py およびtests。Web/Drive取得はChat/Work、Pythonは取得済み入力の決定的処理。外部サイト全体の巡回はしない。

## U1 新規MD実装探索・取得元
起動はユーザーの更新指示。取得優先順位は (1) 既存MD全件JSONの新しい版が利用可能なら差分、(2) MD新規実装一覧・レアリティが確認できる継続利用可能な構造化ソース、(3) 公式告知＋Game8/MD攻略情報・速報等の限定取得。各ソースの利用条件に従う。既存JSON更新を待たず、確認できたカードを先行処理。MD側の最低限の探索項目はカード名（英語可）・実装根拠・日付・MDレア（不明可）。出典URL・観測日時を記録。パック名・種別・終了日・全収録一覧は得られる範囲で別記。
新規実装のcoverageとパック収録のcoverageを独立管理（FULL/PARTIAL/UNKNOWN）。パック85枠等は異版を含む可能性があり新規カード数ではない。既存DBにないだけではMD初実装と断定しない。日付はJST。
U1-S（取得元再監査）はU1の残作業：既存JSON配布元、MD構造化データ候補について取得可能性・更新遅延・新規一覧・MDレア充足率・利用条件をP0資産から再評価。パック全件一覧の取得率は補助指標。未確立でも確定カードのU2以降を止めない。全件取得の主張には実測根拠を要する。
既存 discovery.py と md-pack-discovery-v1 は互換入力として維持し、同日別経路候補を実装イベントの独立入力へ展開するアダプタを設計・実装する。未取得の収録枠やMD実装を推測で埋めない。

## U2 解決・正規化
KONAMI ID、正式日本語名、正規化名、英語名・属性種別による補助照合の順。曖昧IDは保留。OCG公式DB・YAML Yugi個別/OCG JSON等の利用可能なOCG情報を標準経路として日本語名・属性・効果文を取得し、MD実装とMDレアはMD資料で確認。OCG原文を採用する場合は項目別出典に OCG_SHARED を記録し、MD本文確認済みとは称さない。具体的な意味差が疑われる場合だけ対象を保留しMD原文を優先。表記差・改行差のみでは保留しない。海外先行でID/日本語文が取れない場合は仮IDを本番に作らない。ユーザー確認は最終手段。取得不能情報は推測しない。
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
マスターの追加・実質更新がともに0件なら本番HEADを更新しない。パック索引のみ更新可能。

## U5 後日照合
新しいMD JSON入手時、先行登録ID・効果・属性・MDレア・実装状況を比較。一致は出典追記、矛盾は対象項目を確認して差分更新、未解決は再試行。元JSONは版・SHA別に保持。MD JSON不掲載のみで既存カードを削除しない。全件再調査・全件再登録は不要。

## テスト・受入
合成: MAIN/融合/S/X/リンク/P/魔法罠追加、?攻守、未知レア、ID曖昧、部分成功、再録no-op、効果改訂・素材アンカー一致、既知値保護、重複再実行、base SHA競合、rollback、所持・規制・デッキ全行保持、HEAD読戻し不一致。
実データ: 今回のパックで取得できる一覧を照合し、既知の新規カードを実際に登録、既存検索で取得、新旧件数・未解決・SHA・Drive読み戻しを確認。全カード実演、OCG/MD全文一致、全M5出張更新、全パック網羅は受入条件にしない。新規実装coverageとパックcoverageを別々に報告し、部分成功を全件完了としない。加えてOCG_SHAREDの通常検索、同日別経路の追加、既存再録・異版のno-op、OCGのみの除外を合成テストする。テーマ名・効果の動き・MDレアで候補を取得できることを実用受入とする。
報告は追加/更新/再録/未解決件数、世代、正本保存成否を短く。公開GitHubには仕様・コード・合成テスト・集計のみ。実カード全文・所持・DBは非公開Drive。
