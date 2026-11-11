> **2026-11-11 M5-C C1**：4テーマのsource-era試作知識をprivate Driveに保存・SHA読み戻し。記事のMAIN/EX合計が一致しない場合は推測で修復せず`REVIEW_REQUIRED`。全構築のゲーム内成立/MD合法性は未保証。[C1監査](../docs/M5C_C1_FOUR_THEMES_AUDIT_20261111.md)。

# M5 — テーマ・汎用札・出張パッケージの根拠付き候補グラフ

2026-11-10にM5の**初期パイロット（M5-A）**を実装。M4の日本語効果候補索引・M3の個人用SQLiteを読取専用で参照し、**正本DBとM4索引には一切書き込まず**、別の非公開SQLite索引を作る。

## データの区別

- `theme_relations`: `NAME_MATCH_CANDIDATE`（テーマの名称パターンとカード名が一致）と `QUOTED_TARGET_CANDIDATE`（M4の引用文中にテーマを名指し）を分離。**後者はテーマ所属やサーチ可能性の確証ではない**。M4テキストの位置、テキストSHA、版、原文句、分類ステータスを保持。テーマ名一致でもルール上の正式所属とは断定しない。
- `generic_roles`: 根拠URL付きの手札誘発・無効化・ドロー等の**人手候補**。テーマ所属やエンジン構成員と非排他的。出典の評価は`SECONDARY_SOURCE_CANDIDATE`として記録。所持枚数・現行禁止制限をこのテーブルから推測しない。
- `engines`/`engine_parts`/`choice_groups`/`engine_constraints`: 1枚の柔軟枠（SINGLETON）と複数枚のパッケージ（PACKAGE）の**候補バリアント**を別モデル化。MAIN/EXTRA、必須カード枚数、候補からの選択、始動・中継・終点、EX枠、条件、オプション経路の召喚制約を追跡。別エンジンでカードを共有できるが同時運用の保証はしない。

## 初期対象（実カードデータはprivate）

1. デモンスミス：主要初動・補助・EXパーツからなる参考経路。最低スロットMAIN5/EX3。**候補構成のUR最低5枚であり、低レアコアとは判定できない**。この5枚を新規生成するという意味ではなく、所持数照合はM6で行う。根拠：[Game8 デモンスミス出張](https://game8.jp/yugioh-masterduel/664818)。
2. スピードロイド：ベイゴマックス＋タケトンボーグの参考経路（最低MAIN2/EX0、UR0）。任意のチューナー経路に伴う属性制約は`OPTIONAL_LINE`扱いで、全経路へ無条件に適用しない。根拠：[Game8 ベイゴマックス出張](https://game8.jp/yugioh-masterduel/654519)。
3. 壊獣：代替の壊獣から最低1枚を選ぶ単体除去候補（MAIN1/EX0、UR0）。セット採用前提の複数枚エンジンとは分ける。根拠：[Game8 壊獣カード](https://game8.jp/yugioh-masterduel/433515)。

汎用札の少数候補には[Game8 汎用カード](https://game8.jp/yugioh-masterduel/423814)を採用。ゲーム内禁止・制限の最新状態と採用可否を公式確定した資料ではない。**M3の2026-11-05禁止制限候補と照合すると、汎用役割登録の一部に禁止0枚のカードが含まれる**ため、M5内の汎用評価を「採用可能」と読み替えず、M6のM3日付付き評価で除外する。

## API

```python
from engine_m5 import (build_private_m5_index, search_theme, search_generic_roles,
                       list_engine_variants, preview_engine,
                       assess_engine_variant, inspect_engine_combination)

# 全入力はprivate、SHA-256をピン留めして読込。M3本番HEADは変更しない。
result = build_private_m5_index(
    private_source_sqlite, private_m4_index, private_pilot_seed_json, private_m5_index,
    expected_source_sha256=SOURCE_DB_SHA256,
    expected_m4_sha256=M4_INDEX_SHA256,
    expected_seed_sha256=SEED_SHA256)

# 名前からの関係と日本語効果文中での引用を分けて検索。
relations = search_theme(private_m5_index, 'SPEEDROID', limit=100)
roles = search_generic_roles(private_m5_index, role='HAND_TRAP')
variants = list_engine_variants(private_m5_index)
preview = preview_engine(private_m5_index, 'SPEEDROID_BAYGO_REFERENCE_LINE')

# この結果は「パッケージ仕様の不足」のみ。遊べる/合法/無料とは断定しない。
status = assess_engine_variant(private_m5_index,
    'SPEEDROID_BAYGO_REFERENCE_LINE',
    [{'card_id':'konami:12047','section':'MAIN','quantity':1},
     {'card_id':'konami:12052','section':'MAIN','quantity':1}])
pair = inspect_engine_combination(
    private_m5_index, ['SPEEDROID_BAYGO_REFERENCE_LINE','KAIJU_SINGLE_REMOVAL'])
```

- `assess_engine_variant` は明示されたバリアントの最低枚数・代替グループ・上限・セクション/EX15枠を検査し、`COMPLETE_SPEC_VARIANT`/`INCOMPLETE_SPEC`/`OVER_SPEC_MAX`を返す。**完成デッキの合法性やコンボ成立を証明しない**。
- `inspect_engine_combination` は共有カードを原則 **max(各セット必要枚数)** で概算し、多重使用の可能性を必ず注意表示する。EX上限の明確な超過を区別し、各制約があれば`REVIEW_REQUIRED`とする。代替グループの選択によって変わる必要枠は、最低限の**候補下界**として表示する。
- `search_theme` / `list_engine_variants` のソースSHA指定引数で古いindexを排除する。すべてのクエリは列挙型とパラメータ化SQLを利用。データソースを読み込んだという理由だけで高い確度に昇格させない。

## 運用・今後の完了条件

- 3テーマと汎用候補の**種データ**は個別のprivate JSON、派生索引もprivate ZIPに保存。public GitHubはコード、架空fixture、集計、根拠となる公開URLのみ。カード効果原文・所持情報・全カード個票はpublic commitに載せない。
- ソースのSQLite SHAとM4派生索引SHA、シードSHAを毎回照合する。変更時は新バージョンを生成して独立読み戻しを行う。本番DB HEAD、所持、禁止制限、M4索引は非変更。
- **M5-Aの範囲**：3テーマ・3パッケージの候補と汎用候補の関係グラフおよびEX/制約チェックを実運用の試験素材として提供。全テーマの正式な所属判定、全ギミックの展開成立、人手による正誤ラベル、間接的な属性・種族／レベル対象の精密マッチングは未完了。
- **M6の前提**：各推薦候補は、M3の日時付き禁止制限、所持数、レアリティ、生成CP、EX構築を**別途再評価**する。生成可否UNKNOWNはユーザー決定どおり暫定GO、禁止・制限確定違反や新規UR0条件の明確な違反は除外する。M4/M5の候補分類だけで「低レアテーマとして完成」を宣言しない。

監査：[M5_AUDIT_20261110.md](M5_AUDIT_20261110.md)

## M5-B — 横断属性・種族サポート／名称グループ候補（2026-11-10）

3テーマの手動パイロットのみではM6の「広い候補から低レアデッキ発掘」の目的に不十分なため、`engine_m5/support.py` を追加した。private DB 13,948枚とM4索引をSHA固定で読み取り、**属性・種族の条件が効果動作と同一文にあるもの**を別private SQLite索引へ取り出す。 `CONDITION`/`REFERENCED` はサポートできる証拠とみなさない。

```python
from engine_m5 import (build_private_support_index, search_property_support,
                       search_name_groups, search_name_group_support)
index_meta = build_private_support_index(source_sqlite,m4_sqlite,private_output_sqlite,
    expected_source_sha256=SOURCE_SHA,expected_m4_sha256=M4_SHA)
# 風属性のサーチ・特殊召喚を記述するカードの候補
wind = search_property_support(private_output_sqlite,attribute='WIND',
                               action='SPECIAL_SUMMON',limit=50)
# 対象カードの属性または種族に対応する候補。両方指定する場合はALL。
combination = search_property_support(private_output_sqlite,
    target_card_id='konami:1001',match_mode='ALL',limit=50)
# 私有効果文の引用名称から自動抽出した「候補グループ」であり正式テーマではない。
groups = search_name_groups(private_output_sqlite,query='架空戦団')
if groups['results']:
    links = search_name_group_support(private_output_sqlite,
                                      groups['results'][0]['group_key'])
```

実データからは名称グループ候補580、属性・種族条件付き支援候補2,288を収録。引用文には制約やコスト・相手の効果も含まれうるため、**候補は本当のサポート・合法なデッキ採用とは異なる**。M4の原文を検証し、M3の禁止制限・所持・生成CPを後段で再評価。名称グループにはカード単体名指定も含む。[実データ監査](M5B_SUPPORT_AUDIT_20261110.md)。

## M5-C C0 — 構築知識スキーマ/出典管理の検証器（2026-11-11）

設計：[M5-C基本設計](../docs/M5C_THEME_BUILD_AND_COMBO_KNOWLEDGE_DESIGN_20261110.md)。

- `engine_m5/source_registry.py`: `validate_sources` でURL・媒体・掲載/更新/確認時刻・MD/OCG/TCG区別・出典の親子関係・収集状態・許諾状態・検証用SHAを検査。取得不可・日時不明は明示的な`null`/`UNKNOWN`を保持。参照欠損・循環・重複を拒否。
- `engine_m5/knowledge_schema.py`: `validate_knowledge` でv1の12エンティティ（sources, theme_profiles, claims, recipe_refs, recipe_cards, combo_routes/nodes/edges, resource_states, package_candidates, assessments, refresh_queue）を検査。型・ID参照・重複・展開グラフの循環、未解決カードと解決済みカードの区別、検証ステータスの不正昇格を検知。
- `GAME_TESTED`の登録は実ゲーム証跡の明示が必要。記事・人物の記述をそのままゲーム内検証済みにしない。外部の記事本文は**実行可能な指示として解釈しない**単なる構造化入力。外部ページの安全性や不適切な命令文の自動検出を保証するものではない。
- 本工程は**データモデルの検証のみ**であり、実記事の取得、意味抽出、実カードID照合、実コンボ再現、MD規制合否、Driveへのknowledge保存は含まない。C1以降で別途実装する。
- public GitHubはコード・合成fixture・監査件数だけ。実際のデッキレシピや私的DB個票は非公開Drive正本を維持し、既存HEAD/所持台帳/MD所持デッキ索引を更新しない。

使用例（架空データをプライベート実行環境で読み込む）:

```python
from engine_m5.knowledge_schema import validate_knowledge
result = validate_knowledge(private_knowledge_json)
# result はスキーマ版・件数のみ（検証した中身を公開しない）
```
