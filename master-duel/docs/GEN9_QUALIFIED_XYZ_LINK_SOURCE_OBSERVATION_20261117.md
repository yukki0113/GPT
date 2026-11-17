# Gen9限定EX素材の構文観測：初回実装・実データ回帰（2026-11-17）

## 入力・正本

- GitHub main開始時 SHA: `f532ac40f7a3afeaa94c529dd2728fbb485da057`。当該監査はGen9 private HEADを読み取り専用で評価した。
- 現行SQLite SHA256: `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`。
- HEAD/ZIP/SQLiteの前回独立検証、およびスキーマv4・SQLite整合性を維持。原文・カード個票・所持をGitHubに公開しない。
- 正本DBやHEADの書き換えを実施していない。既存M6-5B `POSSIBLE_ON_PAPER` 判定は一切緩和しない。

## 実装

- `engine_m6/qualified_material_grammar.py`：NFKC正規化後の限定されたXYZ/LINK素材ヘッダーを構文観測。単純な属性・種族・テーマ表記等をソース由来の**不透明な限定語**として保持する。限定語の意味・カード適合性を推論しない。
- `audit_source_pinned_qualified_headers`：期待SQLite SHAと原文・ヘッダーSHAを検証し、既存 `UNPARSED` のXYZ/LINKについて読み取り専用集計する。
- `engine_m6/tests/test_qualified_material_grammar.py`：架空名のみで、基本限定素材・トークン除外・複雑な同異条件・代替表記・認証フラグfalseをテスト。
- `qualification_verified`、`summon_route_verified`、`simultaneous_materials_verified` はこの観測結果では常にfalse。既存M6-5Bの構造化召喚審査を迂回しない。

## 読み取り専用・実データ初回観測

| 種別 | Gen9のUNPARSED | ソースの限定文型を追加認識 | 未認識 |
|---|---:|---:|---:|
| XYZ | 221 | 131 | 90 |
| LINK | 385 | 205 | 180 |
| 合計 | **606** | **336** | **270** |

この数値は現行Gen9の素材ヘッダーに対し、実装と同一の狭い正規表現を用いたローカル検証結果であり、**DBのgrammar列の更新件数ではない**。
「構文の候補を抽出した」だけであり、ゲーム内素材適合、特殊召喚条件、必要同時確保、規制適合性は引き続き未検証。
限定語を汎用素材扱いしない。未認識270件は原文審査を維持。

## 未完のゲート

1. CIの新テスト・既存回帰の結果を確認し、失敗時は原因を修正する。
2. 追加336件を正式M6の素材条件審査へ渡すには、限定語の意味・対象候補・召喚制約の検証契約と合成反例を追加する。その時点までは `REQUIRES_REVIEW` のみ。
3. 将来Gen10等でDB正本更新する場合は、新世代ZIPとSHA、旧テーブル・所持184・規制215の保全、独立読み戻し、単一ライター、旧HEADバックアップを必須とする。
