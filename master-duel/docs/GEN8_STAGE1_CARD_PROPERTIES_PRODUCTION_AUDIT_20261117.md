# MD Gen8 第1段階 正本属性移行監査（2026-11-17）

## 結果：正本昇格および独立読み戻し PASS

現行の非公開Drive正本 `GPT/MasterDuel/DB/MD_CURRENT_HEAD.json` を Gen7 → **Gen8** へ移行。カード自体の基本属性の欠落を是正する第1段階。元データのSHAを固定し、既存 Gen7 SQLite の変更不可なバックアップを保存した上で、追加テーブルを持つ候補を作成・Driveへ新規保存・独立読み戻し・正本HEAD切替・HEAD独立読み戻しを実施。

| 項目 | 結果 |
|---|---|
| generation | **8** |
| SQLite schema | **3**（旧schema 1,2と互換） |
| cards | **13,948**, 変更なし |
| monster subtype records | **12,636**, 変更なし |
| spell/trap property cards | **4,834** |
| spell: Normal / Quick-Play / Continuous / Field / Equip / Ritual | **1,056 / 555 / 500 / 328 / 280 / 82** |
| trap: Normal / Continuous / Counter | **1,303 / 556 / 174** |
| Link monsters / directional marker rows | **453 / 1,095** |
| link ratings | 453カードに記録（元JSONのマーカー本数から算出） |
| Pendulum scales | **385** |
| Japanese Pendulum effects | **369**、残り16はソースに当該項目なし（推定埋めせずNULL） |
| inventory | **184**、不変 |
| banlist_entries | **215**、不変 |
| original Gen7 tables | schema_migrations と card_attributes.link を除く既存全12テーブル行内容をSHA比較し一致 |
| integrity_check / foreign_key_check | **PASS / 0件** |
| Drive ZIP・SQLite・HEAD readback | **すべてSHA一致** |
| GitHub合成テスト | **PASS** |

## SHA/系譜

- 元 Gen7 SQLite: `d3ab2fa3e3c79e455a10dd9ff8aebb407a3bd045fac0d1f50711cc0443906ecb`
- 元 Gen7 HEAD: `248c25c554731492850a94b01911bc21f79d389801fca7175eb3c545c22097c7`
- Gen8 SQLite: `3b3aea170ce4adf44f369c3eeb079bb6de8cd75f71b717e2d38a6a568e53fa0a`
- Gen8 ZIP: `a12af074dbb2c04de733ed8df0fe9367115713c4fdee320af944a38bc8cf691a`
- Gen8 HEAD: `08329f9a9b2ecfb005b085338f593a8719f0b72d235ae3834752d92bef49d97b`
- Gen8 accepted regulation policy: `f36ac866c4b6b4d058a17e24bf33031b577d7d2f6af8524946b1f467271a5710`（規制215件の内容・施行日・承認状態は変更なし。SQLite pinのみGen8へ更新）
- raw MD JSON: `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b`
- raw cards JSON: `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7`

## 新たな格納先・実装

- `card_spell_trap_properties(card_id,property,source,verification)`
- `card_link_markers(card_id,arrow,source,verification)`
- `card_pendulum_details(card_id,scale,ja_pendulum_effect,source,verification)`
- 既存 `card_attributes.link` を、元MD JSONの各リンクマーカー数に基づき補完。
- `card_master_import/stage1_gen8_migration.py`：元データとGen7の厳密SHA・KONAMI ID照合、未対応値や不明な値で停止、全件カバレッジ、既存テーブル不変、ZIP生成前の整合性検査。
- `card_master_import/importer.py`：将来のv3カード取り込み時も上記属性を保持し、既存カードで不一致があれば停止。
- `sqlite_store/store.py`：旧v1/v2/v3と新テーブルの構造検証。
- `engine_m6/preflight.py`：schema v3対応。

## 安全性と未完了範囲

- 旧Gen7 HEAD・ZIPは不変で退避し、問題があれば検証後にHEADを手動で戻せる。Google Driveのatomic CASは存在せず、競合の無い単一ライター運用が前提。
- パック収録、テーマ所属、EX素材構造化、素材の同時確保・召喚成立の証明は**第1段階の対象外**。
- Gen7/Gen6のSHAに紐づいたM5-C・M6評価ポリシー・候補台帳はGen8ではそのまま使用できない。旧版は履歴として保持し、元の根拠と評価内容を保存したうえで、Gen8用に再発行する。
- **EX召喚の成立は、EXカード分類・リンクマーカー・カード本文の存在だけでは検証できない。** M6-5Bは未解析素材/召喚手段/同時条件が不足する場合 `REQUIRES_REVIEW` とし、`POSSIBLE_ON_PAPER` をゲーム内実証済みと扱わない。

## 参照

- [Gen7正本移行監査](GEN7_MONSTER_TYPES_PRODUCTION_MIGRATION_AUDIT_20261117.md)
- [デッキ構築標準手順](DECK_BUILD_STANDARD_WORKFLOW_20261110.md)
