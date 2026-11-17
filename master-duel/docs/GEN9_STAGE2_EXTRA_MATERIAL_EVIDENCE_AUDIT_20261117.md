# Gen9 第2段階：EX素材の出典付き構造化とM6-5B審査（2026-11-17）

## 本番状態

**非公開Driveの正本 `MD_CURRENT_HEAD.json` を Gen9 / SQLite schema v4 へ昇格済み。** 第1段階の魔法・罠、リンク、ペンデュラム属性は維持。第2段階ではEXモンスターの素材指定先頭行・効果発動記述より前の召喚制約・元の日本語効果文SHAを、すべてのEXカードでソース付き保存する。

| 種別 | 対象 | 基本形を機械分類 | 保留/特殊素材 |
|---|---:|---:|---:|
| FUSION | 564 | 473 | 91 |
| SYNCHRO | 524 | 259 | 265 |
| XYZ | 588 | 367 | 221 |
| LINK | 453 | 68 | 385 |
| **合計** | **2,129** | **1,167** | **962** |

`card_extra_material_requirements` の保存項目：`card_id`、`summon_method`、`material_header`（日本語原文）、`material_header_sha256`、`pre_effect_restrictions`（召喚条件に関わる原文の効果番号前段落）、`source_text_sha256`、`grammar`、`min_materials`、`level_required`、`qualifier`、`material_labels_json`、`material_verification`、`simultaneous_materials_verified`、`summon_route_verified`、`source`。

`material_labels_json` は解釈を確定した対象カードID群ではなく、**日本語原文に記載された素材ラベル**。カード名・テーマ・種族・属性・選択可能範囲・代替召喚手段の適合性は元の制約を追加で解釈・確認する。

**全2,129件の `summon_route_verified` と `simultaneous_materials_verified` は0（未検証）として保存。** 日本語原文の抽出成功・文型分類は「ゲーム内成立」の証明ではない。

## 正本の整合性

- Gen8 raw SQLite SHA: `3b3aea170ce4adf44f369c3eeb079bb6de8cd75f71b717e2d38a6a568e53fa0a`
- Gen9 raw SQLite SHA: `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`
- Gen9 ZIP SHA: `0fa5fc724f8ab7671404f9297fb240095127840725d1bfd45a7431357467432f`
- Gen9 HEAD SHA: `e592b34198c290f59580976b6b861de893e6708596eb9df57b3b6e594643a66a`
- 原Gen8の16テーブルは**スキーマ履歴へのversion 4の追加を除いて全行・全値一致**。
- 所持カード184種類・MD禁止制限215件を維持。既存日本語効果本文やカードIDは変更なし。
- `PRAGMA integrity_check=ok`、`PRAGMA foreign_key_check` 0件。
- 新ZIPをDriveへ新規保存し、独立読み戻しでZIP/SQLiteのSHAを照合。Gen8 HEADは原文一致のバックアップとして保存。正本HEADは更新後に独立再取得・SHA一致。
- Gen9承認済みMD規制は、215件・適用日・承認状態は不変で `master_sqlite_sha256` のみGen9に更新した別ファイル。旧Gen8版は上書きしない。

## 実装

- `card_master_import/stage2_gen9_migration.py`：GEN8_SHA外部固定、source SQLiteから全EXを列挙し、新しい素材アンカーテーブルへ出典・文型・召喚前段落を追加。元のSQLiteをコピーして既存表を更新せず、検査に通らなければ候補作成失敗。
- `sqlite_store/store.py`：v4テーブルとインデックスの実在・スキーマ世代確認を追加。
- `engine_m6/preflight.py`：v4正本を許可。
- `engine_m6/structured_materials.py`：Gen9の実DB/SHA・カード原文SHAに結合し、**個別カードID付き素材根拠・同時確保根拠・召喚方法根拠・制約確認**の4つを要求。XYZではレベル、Synchroではチューナーと合計レベル、Linkではリンク値寄与・素材数・効果モンスター指定、Fusionでは原文ラベルを机上で照合する。複雑な文型や条件未確認は保留。
- `engine_m6/integration.py`：Gen9の新テーブルがある場合は旧M6-5Bの本文推測式判定を使わず、structured素材審査へ切り替える。Gen8以前は履歴再現用の旧処理を維持。
- `card_master_import/importer.py`：Gen9以降、出典付きEX素材情報の無い新規EXカードをサイレントに取り込まない（fail closed）。
- 合成テスト：新規`test_gen9_structured_materials.py`。実カード情報・非公開所持個票を公開GitHub CIへ流さない。

## 判定・未完了の境界

`POSSIBLE_ON_PAPER` は、明示された仮想ボード・根拠・制約確認の主張がソースの数値条件に矛盾しないという意味のみ。**ゲームで同時に素材を揃えられた、効果が通る、正規召喚が成功する、ルートが再現可能、といった保証ではない。** 元DB自体に「検証済み召喚」フラグを真として登録しない。候補テーマの実際のコンボルートは別途資料・ゲーム内挙動と突き合わせる。

文型未解析962件は構築から削除するのではなく、`REQUIRES_REVIEW` として候補価値を残し、人手の根拠付き精査が必要。原文の先頭だけでは読み切れない特別な代替召喚・召喚ロックは、必ず保存済み原文全体も参照する。

**Gen8以前のM5C/評価ポリシー/入力束は旧SQLite SHAピンに基づくため、Gen9へ無言で再利用しない**。新Gen9用の正本参照で再作成し、評価値変更・根拠不足を差分監査する。

現行正本の変更は単一ライター方式で行った。Google Driveには原子的CASが無く競合書き込みを絶対に防止する保証はない。

## 関連
- [Gen8 第1段階監査](GEN8_STAGE1_CARD_PROPERTIES_PRODUCTION_AUDIT_20261117.md)
- [M6-8 包括仕様](M6_8_COMPREHENSIVE_EVIDENCE_BUILD_SPEC_20261116.md)
