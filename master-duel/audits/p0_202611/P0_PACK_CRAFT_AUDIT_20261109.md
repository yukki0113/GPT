# P0追加監査 — MD入手パック・生成可否のデータソース評価（2026-11-09）

> **P0監査のみ**。実カード台帳・自動検索・デッキ構築・収集ジョブの実装には着手していない。監査元JSONの全文は公開Gitへ追加しない。

## 結論（先に読む）

- ユーザー提供の `master-duel-raw.json`（13,948件）は、**入手経路 `releases` 4,217/13,948件（30.234%）**、**生成可否の明示 `craftable` 17/13,948件（0.122%）**。いずれも**全件の入手経路・生成可能性を確定できる完全な項目ではない**。
- `releases` は主に `Legacy Pack` / `Master Pack` の大分類を示し、個別のシークレット／セレクションパック、販売期間、解除条件を網羅しない。
- **YGOJSON**には `masterDuel.craftable` と `sets.contents.cards` / `availability` を扱うスキーマが実在するが、監査できた配布メタデータは2025年時点であり、2026-11-09の現行パック情報としては採用不可。全件のMDセット網羅率は**未測定**。
- **Master Duel Meta**のカードページは複数の取得先を表示し、期限切れパックを区別する表示もある。実例の少量閲覧で、MD rawに記載のない入手経路が確認できた。ただし**公式ソースではなく、全件取得・再利用の利用条件と自動取得経路は未確認**。
- **P1の完成版は引き続きNO-GO**。特に「新規UR生成0」の厳密な判断には、**生成可否 UNKNOWN をfalse/trueに勝手に変換しないこと**が重要。既知の所持枚数・合法上限・生成可否を分ける。

## 1. 入力および計測定義

- 入力: ユーザー提供 `master-duel-raw.json`、13,948レコード。
- 入力サイズ: 83,388,036 bytes、SHA-256 `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b`。
- 保管先はGoogle Drive `source` フォルダ（ID `1fbPDT55sI-DCHadxoTJRx-C82dxzBMsh`）。File IDは更新時に変わるため、現行ファイルの取得は [Drive探索運用](../../docs/DRIVE_SOURCE_RESOLUTION.md) に従う。
- `releases` の分母: JSON全13,948行。キー存在だけではなく**文字列が非空**であること。
- `craftable` の分母: JSON全13,948行。キー存在を集計し、値 `No` とキー不在を区別。
- `releases` は**複数入手経路を1文字列に混在**させる例があるため、文字列全体を個別パックの正規化済みIDとはみなさない。

## 2. YAML Yugi MD専用JSON：全件実測

| 計測項目 | 分子/分母 | 割合 |
|---|---:|---:|
| MD候補行 | 13,948/13,948 | 100%（入力配布集合同士の母数） |
| `releases` 非空 | **4,217/13,948** | **30.234%** |
| `releases` 未記載 | **9,731/13,948** | **69.766%** |
| `releases` が `Legacy Pack` で始まる | **3,325/13,948** | **23.838%** |
| `releases` が `Master Pack` で始まる | **875/13,948** | **6.273%** |
| `releases` が上記以外から始まる | **17/13,948** | **0.122%** |
| `releases` のユニーク原文字列 | **67種類** | 正規化パック数ではない |
| `releases` に `;`（日付等の区切り） | **241/4,217** | 5.715% |
| `releases` に複数行 | **15/4,217** | 0.356% |
| `craftable` キーあり | **17/13,948** | **0.122%** |
| `craftable` 値 `No` | **17/17** | 100%（明示済み17件内） |
| `craftable` キーなし | **13,931/13,948** | **99.878%** |
| `craftable=Yes` 明示 | **0/13,948** | 0%（生成可能カードが0件という意味ではない） |

**重大な解釈制限**:
- `releases` 未記載 = 入手不可能、としてはいけない。
- `Legacy Pack` 記載 = **現在の入手可能な全経路**がLegacy Packのみ、としてはいけない。
- `craftable` 未記載 = 生成可能、としてはいけない。逆に生成不可能としてもいけない。**UNKNOWN** とする。
- `releases` に期日があっても現在購入できるかを示す `available_at` / `start` / `end` / `unlock_requirement` 等の構造化項目はこの入力では計測できない。
- サンプル: `Speedroid Terrortop`, `Fiendsmith Engraver`, `Gameciel, the Sea Turtle Kaiju` はMD JSONで `releases` が未記載。**テーマカードや出張パーツの入手先がこのファイルだけでは判別できない**。

## 3. YGOJSON：スキーマ・データ供給・更新時点の監査

- Repo: https://github.com/iconmaster5326/YGOJSON
- スキーマ（カード）: https://github.com/iconmaster5326/YGOJSON/blob/main/schema/v1/card.json
- スキーマ（セット）: https://github.com/iconmaster5326/YGOJSON/blob/main/schema/v1/set.json
- 一括配布: https://github.com/iconmaster5326/YGOJSON/releases/download/v1/aggregate.zip

GitHub上で**実際に読み取った構造**:
- カード定義 `masterDuel` に `rarity` と真偽値 `craftable` が必須。
- セット定義 `contents` にカード一覧、仮想セットの `availability`（`startDate`/`endDate`）がある。これは期間限定パックのモデリングに適した構造。
- `v1/individual` の `sets.json`（UUID一覧）を読み取り **3,306件**。これは**MDパック数ではなく、紙のカード商品を含む全セット数**。
- `v1/individual` の `cards.json`（UUID一覧）は **14,616件**。これもMD収録枚数とは異なる。
- `v1/aggregate` の `meta.json`: `increment=1559`; `lastYamlyugiRead=2025-05-13T01:53:50.828316`; `lastYugipediaRead=2025-10-25T01:45:37.418418`; `lastYGOProDeckRead=2025-10-25T01:45:35.506172`。**2026-11-09の最新情報を反映したことは証明できない**。
- 初期UUID8件の個別セットを取得し、名称・カードリスト構造をサンプル検査したが、いずれもMDパックでなく**MD期間制御のデータ値は未検証**。

**取得の限界**: `aggregate.zip` はGitHub Releaseに配布が存在する（確認時約35.6MB）。監査環境からのZIPダウンロードは失敗したため**内部のMDセット数・全カードのcraftable値・販売期間の取得率は未測定**。READMEは `v1/aggregate/cards.json` と `sets.json` のraw直接取得が「BROKEN and OUT OF DATE」と明記している。**raw巨大集約を無条件に最新正本にしない。** 参考の個別リスト等は更新時刻の独立確認を欠く。

### craftable導出ロジックの注意

YGOJSONのコード（`src/ygojson/importers/yugipedia.py`、2026-11-09閲覧）には、MD記事に対し `master_duel_craftable=True` を初期値とし、Yugipediaの「cards that cannot be crafted」カテゴリに含まれる場合にfalseに変更する処理がある。この方式では**カテゴリ未収載や取得不調がtrueに見える可能性**があるため、ゲーム内または独立ソースでの**生成不可例外検証**が必要。

GitHubのMIT LICENSEはプロジェクトのソフトウェアコードに関係する。カード文面や外部データ、第三者サイトの機械取得/転載許諾を一律に保証するものではない。

## 4. Master Duel Meta：少量の公開ページ実見

- https://www.masterduelmeta.com/cards/Speedroid%20Terrortop
- https://www.masterduelmeta.com/cards/Ash%20Blossom%20%26%20Joyous%20Spring
- ページは `How to Obtain` として複数のパック・入手手段を掲載し、**赤表示のパックは期限切れ**との凡例を持つ。

**Speedroid Terrortop（サイト表示、2026-11-09参照）**:
`Stalwart Force`, `Master Pack`, `Outlaws from the Inferno`, `Detonate to the Top Speed`, `Warp-Speed Toys` の5つの入手先名が表示された。MD rawの同カードは `releases` 未記載。この差により、MD rawの入手経路非空率30%を全入手可能率と誤解してはいけないことを確認した。

**Ash Blossom & Joyous Spring（サイト表示、2026-11-09参照）**:
`Master Pack`, `One-Time Bundle Deal`, `Birth of a Challenger`, `Challengers Collection`, `Power Up Selection` 等の取得先を掲載。MD rawは `Master Pack` のみ記載。

**留意**: テキスト抽出には「赤パック」のどれが赤かを正確に復元できないため、上記掲載済み入手先について**現在購入可能**と断定しない。別イラスト・配布限定・一度きり購入・期間限定を別モデルにする。サイトの実利用条件と大量収集の許可は未確認のため、**少量の公開閲覧に限定**し、API無断巡回・構造解析は行わない。

## 5. 候補の採用判断

| 用途 | 現時点の有力候補 | 証拠水準 |
|---|---|---|
| MDカードの大分類入手経路 | YAML Yugi `releases` | **実測可**。網羅性不足 |
| 複数パックの紐付け | Master Duel Meta、YGOJSON `sets` | **ページ上実見 / スキーマ確認**。全件未取得 |
| 期間限定の開始・終了日 | YGOJSON `availability` | **スキーマ上可能**。実値未測定・鮮度不足 |
| カード生成可否 | YGOJSON `masterDuel.craftable` | **スキーマ/算出ロジック確認**。全件鮮度/正確性未検証 |
| 現在の販売・解除状態 | MDゲーム内の「入手方法」・ショップ表示 | **ゲーム内での検証が必要**。この監査では未実見 |
| 正規のカードID | 既存 `cards.json` の `konami_id` を基準とするクロスウォーク候補 | P0別監査でMD候補全件結合済。YGOJSON側UUID/複数passcodeとの対応は別検査 |

## 6. P0→P1の判定と次に必要な実測

**P0の「既存MD raw内のパック・生成可否フィールド充足率実測」は完了**。パックと生成可否の**実用レベルの全件取得は未達**。従来のP1完成版 **NO-GO維持**。

優先順位:
1. YGOJSONの**実データ**（`aggregate.zip`。ただし2025年頃の古いスナップショットである可能性が高い）を取得できる環境で `sets` / `cards.masterDuel` を計測し、MDのみの入手・生成可否率、YAML母集団との差、更新日を算出。古い場合は**現行正本としては使わず**構造検証の材料に留める。
2. MD公式ゲーム内の「入手方法」「生成不可」を少なくとも30件で層化照合。特にLegacy、Master、シークレット、期限切れセレクション、ストラクチャー、配布限定、別イラスト、出張エンジン例。
3. ソース利用条件を確認し、Master Duel Metaを**少量の検証参照**として使えるか、継続機械取得が許容されるかを区別。全件機械取得が未承認の間は巡回しない。
4. 最低限のスキーマで `pack_id`/種類/`availability_periods`/`status=UNKNOWN`/`acquisition_route`/`craftable=UNKNOWN|YES|NO`/`source_checked_at` を別々に扱える設計案を確定。**P1本実装は別途GO判定後**。
5. 新規UR生成0の予算では、「所持済みか」「規制上使えるか」「生成可能か」を別々に判定し、未確認生成可否をtrueにして誤予算を出さない。

### 再現性
標準Pythonで `json.load(open("master-duel-raw.json"))` により配列を解析し、全行で `releases` 非空、`craftable` キー存在・値、`releases` 接頭辞、文字列の改行・区切り、`en_name` サンプルを集計。入力hashでスナップショットを同定。Git側は本書と `P0_PACK_CRAFT_METRICS.json` に集計数と観測条件のみ保存する。
