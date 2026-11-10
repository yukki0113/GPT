# M5-C 基本設計：テーマ構築・展開知識の収集・蓄積

- 設計版: v0.1 / 2026-11-10
- 状態: **設計確定候補（実装前）**
- 対象: 個人用 Yu-Gi-Oh! Master Duel デッキ推薦プロジェクト
- 前提: [基本設計](BASIC_DESIGN.md)、[残工程](INITIAL_GOAL_REMAINING_ROADMAP_20261110.md)、[M5-A](../engine_m5/README.md)、[M5-B監査](../engine_m5/M5B_SUPPORT_AUDIT_20261110.md)
- 本書は追加のM5-C工程を定義する。カードDBの本番HEAD更新、サイト自動収集、M6実装、ゲーム内操作を今回実施したという記録ではない。

## 1. 目的・責務と非目的

### 目的

1. M5-Bで得た広い**名称グループ／属性・種族サポート候補**から、実用性・低レア構築可能性を持つテーマを選び、必要時に外部記事を調査する。
2. テーマごとに「構築の考え方・必須/任意部品・初動/展開分岐・到達盤面・苦手な妨害・制約・代替可能性」を**カードID・根拠・記事版付き**で構造化する。
3. 調査済みの結果を再利用し、更新時は差分を検知して再検証する。未知を失敗ではなく未確認状態として保存する。
4. M6へ**検証可能な構築素材**を提供し、M6で所持・レア・禁止制限・CPを再評価させる。

### 境界

- M5-C: 知識の抽出、構築例の復元、コアと出張の区別、展開**仮説**、ソース証拠と再調査。
- M6: 40–60 MAIN / 0–15 EXのデッキ**候補生成**、所有数・2026-11-05など適用日付きMD規制・レアリティ・CP・新規UR0、合法性の保守的判定、推薦/不採用理由。
- 対戦シミュレータや実ゲームの完全再現、勝率保証、全テーマの一括調査は非目的。
- 学習とはLLM重みの再学習ではなく、**検索・照合可能な非公開の構造化知識を蓄積すること**。

## 2. 既存資産と制約

- private本番SQLite: カード13,948、日本語カード本文13,948。正本はDrive `GPT/MasterDuel/DB/`、HEAD世代3。既存SQLite、所持5種/9枚、M3規制215候補は変更しない。
- M4: 効果候補75,913行。ACTION / CONDITION / REFERENCED / RESTRICTION / METADATAと原文オフセット・SHAを持つ。正確な裁定の証明にはならない。
- M5-A: 3テーマ・3パッケージの候補グラフ。M5-B: 名称グループ580候補、属性・種族の効果文共起2,288候補。**580個の公式テーマや580件の成立デッキではない**。
- KONAMI IDがカード識別子。日本語名やテーマ表記「ＳＲ」をMDレアリティSRと混同しない。
- private所持UNKNOWNを0枚扱いしない。生成可否UNKNOWNは候補生成暫定GO、明示NOは新規不足のときブロック。MD規制候補の未検証状態は保存し、OCG/TCG規制を流用しない。

## 3. 外部データの収集方針

### ソースと優先順位

| 種類 | 例 | 主な用途 | 注意 |
|---|---|---|---|
| ゲーム公式 | マスターデュエルゲーム内・KONAMIのMD告知 | MD施行日・公式の規制・仕様 | 全テーマの構築記事を提供するとは限らない |
| MD攻略記事 | Game8、AppMedia、Master Duel Meta等 | デッキ構成、回し方、展開例、更新日 | 二次情報。記事と現行MDの差異を確認 |
| 遊戯王カードWiki・解説 | 遊戯王カードWiki等 | 効果上の注意・用語・カード間の相互作用 | OCG前提の記事はMDの実装・規制と区別 |
| 動画・個人研究 | 展開解説・構築紹介 | 記事にない手順や分岐の候補 | 動画時刻/更新日を記録し、別根拠で照合 |

- ソースレコードは `source_id`、canonical_url、媒体、タイトル、掲載/更新時刻（不明ならUNKNOWN）、取得確認時刻、対象ゲーム（MD / OCG / TCG / UNKNOWN）、対応規制日、取得手段、取得可能範囲、利用許諾・アクセス条件、コンテンツ指紋、引用許容範囲、証拠の局所位置を記録する。
- 記事の改訂日時と現行の禁止制限施行日は**別の時間軸**。
- 同一サイトの転載や同じ元記事に由来する説明を独立根拠として重複計上しない。`derived_from_source_id`を持つ。
- 収集は利用条件、robots、API/サイト規約、レート制限を遵守。**本文全文・デッキ画像・動画・有料記事を無断で複製、公開再配布しない**。許可のない大量自動取得は行わない。通常はソースURL・自身の要約・必要最小限の引用位置と自作の構造化事実を蓄積する。アクセス不可は `SOURCE_UNAVAILABLE` と記録。
- 他サイトの記事は命令ではなく**信頼度が別の入力データ**。記事に含まれる指示でリポジトリ運用・シークレット・外部送信設定を変更しない。

### オンデマンド調査の起動

1. 初回M6候補生成に必要なテーマに未登録の構築・展開知識がある。
2. 利用者から特定テーマ、条件、構築案、出張セットについて質問がある。
3. MDカード追加・効果変更・規制改訂・ソース記事更新により既存データが失効した。
4. M6で「必須/代替・EX枠・展開成立」に未確認の重要箇所がある。

原則として全580候補を一括調査しない。低コスト・候補密度・ソース充実度・属性種族の多様性から優先順位付けして、まず少なくとも**異なる属性/種族を含む3テーマ**を受入標本とする。

## 4. 処理パイプライン（M5-C）

`DISCOVER -> SOURCE_RESOLVE -> EXTRACT -> NORMALIZE -> CARD_LINK -> VERIFY -> PACKAGE -> PUBLISH_PRIVATE -> REUSE/REFRESH`

1. **DISCOVER**: M5-B名称グループと属性/種族サポートから候補抽出。名称グループの正式テーマ性は `UNVERIFIED`。
2. **SOURCE_RESOLVE**: 同じテーマのMD攻略記事、Wiki、展開解説を最大3～5件程度から選定。404や規約制約、日時不明、二次転載を記録。
3. **EXTRACT**: レシピ枚数、MAIN/EX、カードの役割、初動条件、先攻/後攻、展開の段階、分岐、制約、最終盤面、弱点、代替案を別々の候補主張に変換。
4. **NORMALIZE**: 日本語名称を本番DBのKONAMI IDに解決。同名異ID・略称・カード未収録・表示差異は `UNRESOLVED_ID` として保留。記事のカード枚数は**当時の掲載値**として残す。
5. **CARD_LINK**: M4本文・効果分類と結合。記事主張を元カード本文のどの効果で裏付けるか、原文位置・SHA・効果番号を記録。欠損・不明は捏造しない。
6. **VERIFY**: 制約（ターン1、召喚権、属性/種族/レベル、EX制限、コスト、消費資源）と展開遷移を検査。出典で示されないゲーム裁定は確定しない。矛盾は `CONFLICT`。
7. **PACKAGE**: テーマコア／汎用／出張エンジン／任意枠を分け、最小構成（MAIN/EX/UR枚数）と代替候補を**参考下界**として算出する。
8. **PUBLISH_PRIVATE**: 新規のバージョン付きJSON+SQLite sidecarを非公開Driveへ保存。ZIP・manifest SHAを独立再取得検査。元HEADの変更なし。
9. **REUSE/REFRESH**: 同じ規制/カード効果版では既存の知識を優先。依存カードや記事だけ差分更新、失効・根拠切れの主張を非推奨にする。過去の版と監査履歴は削除しない。

## 5. 非公開データモデル（提案schema v1）

公開GitHubへ実記事全文・個人所持・カード個票は入れない。下記の型・合成テスト・集計のみを公開する。

| エンティティ | 主キーと主なフィールド | 関係/用途 |
|---|---|---|
| `sources` | source_id, URL, platform, published_at, updated_at, checked_at, game_scope, banlist_on, content_hash, access_state, license_state, derived_from | 参照元の識別・追跡 |
| `theme_profiles` | profile_id, theme_key, display_name, archetype_status, archetype_aliases, playstyle, source_version, verification | テーマ基礎情報。正式所属を確定としない |
| `claims` | claim_id, profile_id, claim_type, normalized_fact_json, source_id, source_locator, confidence, verification, reviewed_at | 採用理由・制約・弱点・代替可能性の個別主張 |
| `recipe_refs` | recipe_id, profile_id, source_id, article_revision, main_count, extra_count, game_scope, banlist_on | 掲載レシピの時点付き引用記録 |
| `recipe_cards` | recipe_id, card_id, section, quantity, role, essentiality, resolve_status | 原文と違う現行デッキではない |
| `combo_routes` | route_id, profile_id, source_id, route_version, start_condition_id, end_state_id, verification | 分岐するルート群 |
| `combo_nodes` | node_id, route_id, sequence, action_type, actor_card_id, effect_ref, before_state_ref, after_state_ref, evidence_id | 1手順ごとのカードID／効果番号／状態差分 |
| `combo_edges` | route_id, from_node, to_node, branch_predicate, branch_kind, probability_status | 選択/ランダム/相手応答など分岐 |
| `resource_states` | state_id, locations_json, normal_summon_used, resources_json, locks_json, turn_phase, assumptions_json | 手札・場・墓地・除外・EX等と各制約 |
| `package_candidates` | package_id, profile_id, core_or_optional, min_main, min_extra, ur_copies, alternate_group, prerequisite_ids, verification | M5-Aエンジン互換の構成部品 |
| `assessments` | assessment_id, object_type, object_id, checked_at, md_regulation_snapshot, catalog_sha, outcome, reasons, evidence_ids | 判定履歴と再検証 |
| `refresh_queue` | item_id, source_id, affected_profile_ids, cause, priority, last_checked_at, status | 更新時の依存関係と差分処理 |

共通要件：UUIDまたは決定的キー、UTC/JSTオフセット付き日時、KONAMIカードID、版・SHA・出典URI、原文参照位置、欠損の明示、append-only変更履歴。JSONにはバリデータを設け、入力型・ID参照整合・循環・重複・未解決の監査を行う。

### 事実・解釈・評価の厳密な分離

- `SOURCE_OBSERVED`: 記事がそのように書いている（ゲーム成立確定ではない）
- `CARD_TEXT_CORROBORATED`: 対応カード原文の記述と整合（裁定確定ではない）
- `EXPERT_REVIEWED`: 展開・制約を人/専門レビューで確認した
- `GAME_TESTED`: 実ゲームで該当ルートを再現した証跡がある場合のみ
- `CONFLICT`: 他のカード原文/規制/記事と矛盾
- `UNKNOWN`, `SOURCE_UNAVAILABLE`, `STALE`: 確認不能・古い情報

ルートの運用ステータスは `HYPOTHESIS` / `TEXT_CHECKED` / `REVIEWED` / `GAME_TESTED` / `BLOCKED`。二次サイトの記事を読んだだけで `GAME_TESTED` に昇格しない。

## 6. 展開モデルと例外

1. **開始条件**: 必要手札（カードID・枚数）、先後/フェイズ、墓地など初期資源、召喚権、必要なEX、前提の相手盤面。
2. **1ステップ**: どのカードのどの効果（番号不明ならUNKNOWN）を、どの発動条件・コストで使い、手札/場/墓地/除外/デッキ/EXの何を移したか。
3. **分岐**: `PLAYER_CHOICE`、`RANDOM_OUTCOME`、`OPPONENT_RESPONSE`、`CONDITIONAL` を区別。運・相手の意思が含まれるルートを一本道の保証としない。
4. **制約伝播**: ターン1、同名制限、EX召喚制限、属性・種族、特殊召喚の前後条件、残り召喚権、EX枠、支払済コストを状態に付加。任意の展開経路でのみ発生するロックは他経路へ無条件適用しない。
5. **到達点**: 終了時のフィールド・墓地・手札/継続リソース・妨害の候補数・保護効果・次ターンリソース。妨害の数は効果を発動できる前提条件とともに記録。
6. **不成立と不明**: 固定素材不足、明示的規制超過、EX枠超過、確定ロック違反は `BLOCKED`。効果番号、分岐、裁定不足は `REVIEW_REQUIRED`。**未知=不成立ではない**。
7. **UR代替**: URを削った後に初動・展開終点・必要素材・妨害数・制約がどう変わるかを差分として保存する。弱体化しても成立しうる低コストルートを別バリアントとして保持。無根拠の置換は確定案にしない。

### 具体的検証対象の例（今回調査、保存設計のみ）

[Game8のスピードロイドデッキ記事](https://game8.jp/yugioh-masterduel/447534)（2026-11-09更新）には、ベイゴマックス初動からGOMガンを介し、タケトンボーグ/ダブルヨーヨーのどちらが手札かで分岐する例が掲載されている。GOMガンは公開解説中にEXモンスター除外や召喚制約の条件が記述されている。

M5-Cではこれを**記事観測**として `START` → `SUMMON` → `SEARCH` → `LINK_SUMMON` → `RANDOM_OUTCOME` → 複数の `BRANCH` で表す。記事内手順の丸写しは避け、個々の採用カードID・発生条件・証拠位置を個別解決する。現時点ではこの展開をM5-Cの正式な `GAME_TESTED` データとして登録しない。

## 7. M6接続コントラクト

M6入力は `ThemeKnowledgeBundle` とし、最低限次を返す：

- `profile_id`、`knowledge_version`、`source_ids`、`as_of`、`catalog_sha`、`regulation_date`、`verification`
- `core_packages` / `optional_packages` / `generic_candidates`：MAIN/EX枠、KONAMI ID、必要コピー、代替選択、制約
- `combo_routes`：初動・分岐・到達点・検証状態と未確認事項
- `low_cost_variants`：UR除外後の成立条件と損失
- `unresolved_claims` / `conflicts` / `stale_dependencies`

M6はこのBundleだけで合法性・生成コストを確定せず、M2所持、M3の施行日付き規制、CPポリシーと例外台帳、現在のカード本文を必ず再評価する。

既定 `LOW_RARITY_CORE`：テーマ中核の必須UR0、新規生成UR0、所有済みURの採用可、MAIN40～60・EX0～15。 `STRICT_NO_UR` は所有済みも含めUR0。自動で完成レシピを作れない場合も、理由・不足情報・候補を返す。生成可否UNKNOWNは暫定GOという利用者決定を維持する。

## 8. 更新・再調査・コスト制御

- キャッシュキー: profile + original source revision/hash + referenced-card-text SHA + banlist effective_on + extractor_version。取得日時だけで内容が変化したとはみなさない。
- 再調査トリガー: (A) MD規制の変更カードがレシピに含まれる、(B) カード効果改訂、(C) 記事更新、(D) 新規カード、(E) 利用者から不一致報告、(F) 現行Bundleが不足。
- 規制だけが更新された場合は**M3評価をやり直し**、記事本文を必ずしも再取得しない。カード効果改訂は依存ルートのみ `STALE`。
- 自動調査の優先度: 低レアテーマ中核比率/UR必要枚数見込み/記事の質/初動・展開情報充実度/異なる属性・種族。調査上限件数・ページ数・取得時間・失敗リトライ回数を設定し、永久巡回を避ける。
- 更新差分に異なる主張が生じたら新版を作成し旧版を保持。バイナリ索引はmanifest+ZIP SHAで独立読み戻し。編集は単一ライター、衝突時はHEAD世代・期待SHAを再照合し上書きしない。

## 9. 受入基準・テストと段階導入

| 段階 | 受入 |
|---|---|
| C0: スキーマ・ソース仕様 | 収集規約・用途・出典・欠損のバリデーション。合成テストで未知・重複・参照欠損・悪意のある記事指示を拒否。 |
| C1: 構築知識試作 | 少なくとも3テーマ（異なる属性/種族）、各2ソース候補を比較し、1テーマ以上で完全MAIN/EXの掲載構成を取得・カードIDへ解決。欠損や規制不一致は明示。 |
| C2: 展開・分岐 | 最低3種のルート（一本道・ランダム分岐・任意制約）を型付きグラフで保存し、根拠・状態差分・制約伝播を合成テストと実例で確認。全展開は`GAME_TESTED`でなくてもよい。 |
| C3: 低コスト代替 | 1テーマ以上で元構築と新規UR0候補バリアントを並べ、必須/任意・EX枠・失った展開/残る展開の差分を説明。成立未確認なら`REVIEW_REQUIRED`。 |
| C4: 再利用・失効 | 同一記事版の再調査をスキップし、規制差分/カード本文差分で影響するルートだけ`STALE`にする。 |
| C5: 非公開統合 | SHAピンを伴う生成、private Drive ZIP+manifest保存、独立読み戻し、ソースHEAD不変、公開Gitは架空fixture+集計のみ、CI全緑。 |

品質KPI：ID解決率、抽出された主張の根拠URL付与率、分岐回収率、コスト/制約矛盾件数、独立ソース整合率、UNKNOWN残数、再取得削減率。これらを計測せず「理解率100%」等と呼ばない。

### 推奨作業順序

1. C0: 公開GitHubに `engine_m5/knowledge_schema.py`、`source_registry.py` のスキーマ・バリデータと合成テストを実装。
2. C1: 非公開Driveに3テーマの調査記録とカードID解決結果を保存。Game8スピードロイドを分岐のテストケースに使用。
3. C2: `combo_graph.py`で前提/操作/分岐/結果を型付けし、原文と矛盾を検査。
4. C3: M5-A/Bのカード集合と組み合わせてUR低減バリアント作成。
5. C4/C5: 再調査の依存関係・キャッシュ・差分・監査・CIを完成させ、M6へBundle APIを提供。

## 10. 参照先と監査境界

- [Game8 マスターデュエル デッキレシピ一覧](https://game8.jp/yugioh-masterduel/423801)
- [Game8 スピードロイド：レシピ・回し方・分岐](https://game8.jp/yugioh-masterduel/447534)（2026-11-09更新、2026-11-10確認）
- [AppMedia デッキレシピ一覧](https://appmedia.jp/master_duel/27414477)
- 遊戯王カードWikiはカード効果の参考として候補だが、OCG前提とMD施行規制を区別し、個別ページごとにアクセス条件と掲載日を確認する。

本書は現行GitHub READMEのM5-A/B実装を置き換えず、**未実装のM5-C仕様**として追加する。データの私的格納やCI成功を今回の設計書の成立条件にはしない。

## 11. 初期受入テーマ・利用者要求に基づく評価シナリオ（2026-11-10追補）

この4テーマは「4つとも新規UR0で成立するべき」という期待値ではなく、**別々の受入判定を意図した教師ケース**である。出典記事が記載する採用枚数・過去の規制を現行MDの正本とは扱わず、同じカードIDと規制施行日で再照合する。

| ケース | 初期対象 | 主な検証目標 | 成功条件 |
|---|---|---|---|
| MIGRATION | イビルツイン：スプライト混合 → デモンスミス混合 | 既存レシピからの入替、維持札、追加MAIN/EX、必要生成CP、初動/妨害/ロックの差分 | **現在のスプライト型40～60/EX構築が入力された場合**、共通・削除・追加をカードIDごとに算出し、所持/不明を分け、双方の展開・変更理由を根拠付きで説明。未入力なら「具体的移行CP」はUNKNOWN。 |
| DISCOVERY_LOW_COST | 海晶乙女（マリンセス） | 水属性/サイバース族の間接サポートとテーマ展開・EX枠・水属性縛りを検証 | 所持に依存しないSR以下中心の候補構成と展開候補を抽出し、汎用URとテーマ必須URを区別。記事でのNR構築は当時の形式・規制を保つ。 |
| DISCOVERY_LOW_COST | 軍貫 | テーマにURを必要としない戦術・ランク4出張の可否・低予算 | テーマ所属/中核と汎用ランク4、出張エンジンを分離。SR/R/N中心でMAIN/EXに最低限の筋道を立て、汎用URは所持・代替・省略で扱う。 |
| NEGATIVE_CONTROL | ブラック・マジシャン | 表記とカード名指定サポートの識別、必須URの不成立判定 | 必須カード《ブラック・マジシャン》のMDレアリティURを認識し、同カードを必須とする構築について**テーマ中核必須UR0**がFAILであると根拠付き判定。新規生成UR0とは独立評価。 |

### ブラック・マジシャンに関する不変条件

- M5-Bの名称グループは正式テーマ名ではない。文字列 `ブラック・マジシャン` を名前に含まない関連カードでも、カード名指定・魔法使い族/闇属性・《ブラック・マジシャン》扱いの効果条件など、原文から**名称指定・支援・対象**を別関係として検出する。
- `REQUIRES_CARD(card_id)`、`TREATED_AS_NAME(card_id, name)`、`SUPPORTS_NAMED_TARGET(card_id, name)` を混同しない。「ブラック・マジシャンを扱う」という記述から、そのカードが低コストで代用可能とは推論しない。
- `LOW_RARITY_CORE` の **必須テーマ中核UR0** は、所持済みであっても必須URがあるならFAIL。別の `NEW_UR_CRAFT_ZERO` は実所持で必要数が足りればPASSになり得る。`STRICT_NO_UR` はUR採用そのものを拒否。これらを一つの「UR0」フラグに畳まない。
- 単なる関連カードだけで構築し、《ブラック・マジシャン》を含まない案を「ブラック・マジシャン構築の低レア代替」とは自動認定しない。中核カードを除いた派生案は `CORE_REMOVED_VARIANT` と明示し、独立に戦術成立を調べる。
- 初回外部確認：Game8《ブラック・マジシャン》MDレアリティUR [カードページ](https://game8.jp/yugioh-masterduel/432516)（2026-11-10取得）。最終判定は実カードDBのレアリティと突き合わせる。

### イビルツインの移行費用と相性

- 利用者の現行スプライト混合型の**実レシピと所持枚数は未取得**。参考記事のリストを「ユーザーの現在構築」として代入してはいけない。
- 過去/現行のリストは`deck_variant`・`regulation_effective_on`・`user_owned_status`を区別。必要な追加生成UR/SRは `max(0, 必要枚数 - 確認済み所持枚数)` で計算し、所持UNKNOWNは費用不確定とする。
- 展開経路はスプライト型、破械/デモンスミス型、三者混合型を別バリアントとして保存。カテゴリ上で併記されているだけで主軸が移行したとは断定しない。
- MD向け公開参考：[2026年のスプライト型解説](https://note.com/takeo_spright/n/ne4a5e7752a7a)、[デモンスミス破械型の展開](https://note.com/srmy_tcg/n/n6553a924e3dd) 、[ニューロン投稿・MD登録](https://www.db.yugioh-card.com/yugiohdb/member_deck.action?cgid=97f9350fb367f02ef4d69b645be697c5&dno=10&request_locale=ja)。後者は利用者投稿であり公式が内容を保証した構築とは扱わない。

### 低レア発掘の正例

- [海晶乙女NR構築の掲載例](https://appmedia.jp/master_duel/75397048) と通常レシピを区別。NR限定構築の記事を読むことと、現行MDでそのまま合法/実戦的であることは別。
- [軍貫のテーマ内UR0という公開考察](https://note.com/scrapironstatue/n/ncd0a3d61e8b8) を候補根拠として採用し、[2026-11-09更新のGame8軍貫デッキ](https://game8.jp/yugioh-masterduel/446958) と突き合わせる。汎用URの採用はテーマ内必須URの数に混ぜない。
- C1/C3の受入は**少なくとも4テーマ**に変更し、正例2テーマ・移行例1テーマ・意図的不成立例1テーマを含む。単に候補を4件表示するのではなく、検証意図ごとの合否と未確認事項を保存する。

