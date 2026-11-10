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
