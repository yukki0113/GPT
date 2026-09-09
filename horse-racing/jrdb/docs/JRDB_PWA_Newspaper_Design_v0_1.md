# JRDB PWA 自分用競馬新聞 Design v0.1

Status: DRAFT / DESIGN ONLY / PWA implementation not started

## 1. Purpose

スマホ中心で閲覧する「自分用競馬新聞」を、既存JRDB / RaceNote / Eval / Edge / 将来の独自指数を統合する週末実戦用PWA画面として設計する。

この新聞は一般的な競馬新聞の基本情報と過去走を土台にし、その上へ自分専用の印・Edge・短評等を追加する。

主用途は2つ。

1. 週末にレースと各馬を一覧で比較する実戦画面
2. EdgeDBや独自指数が参照した条件・過去走が正しいかを人間が目視確認する検証画面

条件集計用Fact Liteは「調査室」、新聞は「週末実戦画面」と役割を分ける。

## 2. UI order contract

馬1頭を横1行とし、16頭立てならヘッダを除いて原則16行を縦スクロールする。

列の意味順は固定する。

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

概念表示:

```text
枠 | 馬番 | 馬情報 | 印群 | 前走 | 2走前 | 3走前 | ... | Edge
```

馬情報セル内部は複数行を許可する。

```text
馬名
性齢 / 斤量 / 騎手
父 / 脚質
```

スマホでは枠・馬番・馬名をsticky候補とし、残りを横スクロールする。馬情報全体を固定して横幅を圧迫しない。

## 3. Initial display density

### 3.1 Race header

初期候補:

- 開催日
- 開催場 / 開催回日
- R
- 発走時刻
- レース名
- 芝 / ダート / 障害
- 距離
- 右左 / 内外等のコース情報
- クラス / Grade
- 頭数
- 重量条件

### 3.2 Horse basic information

初期候補:

- 枠
- 馬番
- 馬名
- 性齢
- 斤量
- 騎手
- 父
- 脚質

詳細表示候補:

- 調教師
- 母 / 母父
- 生産者
- 馬体重系
- 距離適性
- JRDB class / 特記

### 3.3 Mark group

新聞の記者印欄に相当する狭い列群として扱う。

初期namespace候補:

- JRDB能力 / IDM
- JRDB総合印
- JRDB調教指数 / 調教矢印 / 上昇度
- Eval指数
- RaceNote予想印
- keibailuka掲載有無
- 将来の独自指数

keibailukaは掲載対象なら記号を表示し、押下時に短評をpopover / dialogで表示できるContractとする。

未取得sourceは推測せず `null` とし、PWAでは空白表示する。

### 3.4 Past runs

データ側は最大8走を初期候補とする。

- detailed recent: 最大5走
- compact older: 最大3走

初期画面は3走だけ表示する。

PWA操作候補:

```text
3走 -> 5走 -> 8走
```

表示切替は既に端末へ取得したJSONの表示範囲を変えるだけとし、通常は追加ネットワーク取得を要求しない。

1走セルの表示候補:

- 日付 / 場 / R
- レース名またはクラス
- 芝ダ / 距離 / 馬場
- 着順 / 頭数
- 人気
- 騎手 / 斤量
- コーナー通過順
- タイム / 上がり3F
- IDM等の代表指数
- 馬体重 / 増減

情報密度はUI PoCで調整する。すべてを同一視覚強度で表示しない。

## 4. Race-level note area

出走馬tableの下にレース単位の短評欄を置く。

候補:

- RaceNoteレース短評
- RaceNote展開コメント
- JRDB予想ペース
- JRDBペース / 展開関連指数
- その他、文章化しなくても有用なレース単位値

JRDBに自然文短評が存在しない場合、無理に生成せず `ラベル: 値` のstructured itemで表示する。

## 5. Source separation

新聞は中央統合表示層であり、各sourceの正本責務を奪わない。

```text
JRDB PACI / history  -> newspaper JRDB base
Eval                  -> eval namespace
RaceNote prediction   -> racenote_prediction namespace
keibailuka             -> keibailuka namespace
JRDB Edge Registry     -> edge_matches
Independent index      -> my_index namespace
```

RaceNote v1.0 authoritative bundleはRaceNoteの正本のままとする。
Eval / blog / prediction結果をRaceNote bundleへ書き戻さない。

## 6. Newspaper Race Bundle

配布単位は原則 **1レース1JSON** とする。

Draft schema:

`schema/jrdb_pwa_newspaper_race_schema_v0_1.json`

主構造:

```text
metadata
race
race_notes
horses[]
  key
  basic
  jrdb
  addons
    eval
    racenote_prediction
    keibailuka
    my_index
  history[]
  edge_matches[]
```

外部source欠損時もkey / JRDB base / historyを維持し、addonだけnullにする。

## 7. Daily Manifest

1日分を1巨大JSONに固定せず、日付manifest + race JSON群とする。

Draft schema:

`schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json`

概念配置:

```text
YYYYMMDD/
  manifest.json
  01_01.json
  01_02.json
  ...
  09_12.json
```

manifestは少なくとも次を持つ。

- date
- manifest revision
- generated_at
- source readiness
- race list
- 各race JSON path / revision / SHA-256 / size
- expected / ready race counts

これにより1Rだけaddonが更新された場合も対象race JSONだけを更新可能にする。

## 8. Identity / merge keys

外部consumerの基本join key:

```text
date + venue_code + race_no + horse_no
```

JRDB内部では以下も保持する。

```text
race_key
race_horse_key
horse_id
```

馬名文字列による推測joinを標準経路にしない。

## 9. Hybrid generation / merge

理想の日次Work操作は1種類の依頼で何度でも安全に再実行できる形とする。

ユーザー例:

```text
09/12の競馬新聞用データを生成してください。
```

### First run

PACIが存在すればJRDB baseを生成する。

```text
PACI
 -> Common Reader
 -> race / runner current info
 -> as-of-safe history
 -> newspaper JRDB base
 -> available addonsを探索
 -> merge
 -> Drive canonical
```

外部sourceが未取得でも失敗扱いにしない。

例:

```text
JRDB                  READY
Eval                  PENDING
RaceNote prediction   PENDING
keibailuka             PENDING
Edge                   READY
MyIndex                PENDING
```

### Later rerun

同じ日付に対して再度実行すると、利用可能になったsourceだけをmergeする。

```text
JRDB base revision 1
 + Eval
 + RaceNote prediction
 -> revision 2

revision 2
 + keibailuka
 -> revision 3
```

mergeはidempotentとし、同じsource versionを再適用しても意味上の重複を作らない。

## 10. Namespace ownership rule

source間の上書き事故を防ぐ。

- JRDB builderは `race`, `basic`, `jrdb`, `history` を所有
- Eval mergerは `addons.eval` だけを所有
- RaceNote prediction mergerは `addons.racenote_prediction` とrace-level RaceNote noteだけを所有
- keibailuka mergerは `addons.keibailuka` だけを所有
- independent index mergerは `addons.my_index` だけを所有
- Edge matcherは `edge_matches` だけを所有

他namespaceの値をmerge時に削除・再解釈しない。

## 11. Edge display contract

JRDB Edge Registryの既存情報を新聞表示へ投影する。

候補:

- edge_id
- display_text
- polarity
- status
- strength_score
- confidence_band
- registry_version

新聞の通常表示は `display_text` を中心にする。

詳細押下時にedge id / polarity / status / 簡易根拠を確認できる余地を残す。

初期UIではACTIVEを主表示候補とし、PROVISIONAL等を表示する場合は状態を視覚的に区別する。最終policyはEdge Registry側の運用確定後に決める。

## 12. History source policy

既存RaceNoteのvalidated production policyを再利用候補とする。

```text
recent_runs: PACI detailed max 5
older_runs: Analysis Lite compact max 3
```

ただしNewspaper bundleはRaceNote bundleそのものを正本にせず、共通Reader / shared enrichment engine等を再利用するconsumerとして設計する。

同じ固定長offsetや独立した過去走解決ロジックを新モジュールへ複製しない。

Historical PoCでは必ず `history_date < target_date` を守る。

## 13. Target-race leakage boundary

新聞baseは開催前情報で生成する。

対象レースについて以下を混入させない。

- target finish
- final target popularity / odds
- payout
- final target track condition
- target result indices

過去走については対象日より前の確定結果を表示可能。

## 14. Drive canonical and PWA delivery

保存正本候補:

```text
Google Drive
  JRDB/newspaper/YYYYMMDD/
    manifest.json
    race JSONs
```

PWAがDriveを直接読むことは初期案としない。

既存Fact Liteの安全な配布思想を再利用し、概念的には:

```text
Drive canonical
 -> Issue / Actions publish
 -> GitHub Release or Pages data artifact
 -> GitHub Pages
 -> PWA
 -> OPFS
```

とする。

Gitはcode / schema / docsの正本であり、日次生成JSON自体はGit管理しない。

## 15. PWA offline behavior

新聞JSONはSQLite化を必須としない。

初期候補:

- manifestはonline時network-first
- race JSONはSHA-256 / revision比較
- 初回当日新聞open時、その日全raceを端末へprefetch可能
- OPFSへ `newspaper/YYYYMMDD/` 単位で保存
- 以後はlocal first
- online時だけmanifestを見て変更raceを差分取得
- update失敗時は既存local版を維持

日次JSONサイズは実データPoCで測定し、圧縮やSQLite化は必要性が出てから判断する。

## 16. Performance strategy

16頭×最大8走程度は、Fact Lite SQLite全量集計より小さい表示問題と見込むが、実機で測る。

初期対策:

- 1レースだけDOMへ描画
- 過去走は3走のみvisible
- 4走目以降は同じJSONから展開
- 重い詳細popoverは押下時生成
- race切替時に前race DOMを破棄
- day manifestのみ常時保持
- optional addon欠損を埋めるための追加network callを描画中に発生させない

## 17. Proposed module boundaries

実装時の候補。名前は実装開始時に確定する。

```text
src/newspaper_build.py
src/newspaper_merge.py
src/newspaper_publish.py
schema/jrdb_pwa_newspaper_race_schema_v0_1.json
schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json
pwa/newspaper.html
pwa/newspaper.js
```

Work専用スレッドはこのmodule contractを読み、ユーザーが日付だけ指定できる運用を目標とする。

## 18. Validation contract

日次生成で最低限確認する。

### Base

- PACI target date一致
- BAC race identity一意
- KYI `(race_key, horse_no)` 一意
- `BAC declared_field_size == horses count` を監査
- horse_id / race_horse_keyを可能な限り保持
- unknownは推測補完しない

### History

- 全history date < target date
- sequence重複なし
- recent / older重複なし
- coverageを虚偽に完全履歴と表現しない

### Merge

- source namespace以外を変更しない
- join key unmatchedを監査
- duplicate addon keyはエラー
-同一source version再mergeでsemantic result不変

### Distribution

- schema validation PASS
- file size / SHA-256一致
- manifestのrace countと配布race file数一致
- publish失敗時に既存current day setを壊さない

## 19. First PoC proposal

画面実装へ入る前に、既存データが揃っている16頭立ての1Rでnewspaper JSONを生成する。

第一候補:

```text
2026-08-16 札幌11R 札幌記念 16頭
```

理由:

- RaceNote history enrichment PoC実績あり
- 16頭でスマホ新聞の典型的な行数を確認できる
- 芝2000m重賞で過去走・統計が十分ある
- 既存RaceNote 8-run bundleサイズ実測がある

PoCで確認する。

1. 1 race JSON bytes
2. 1 horse rowの表示密度
3. 3走 / 5走 / 8走切替
4. sticky列の必要幅
5. iPhone横スクロール
6. Edge/addon null slot表示
7. OPFS保存 / 再読込

## 20. Deferred decisions

以下は初期設計で固定しない。

- target race live/final oddsの別日中更新
- 当日最終馬体重の別source取込
- 勝負服画像
- 10走以上の履歴
- Edge PROVISIONALの通常表示policy
- 独自指数の計算方式
- Newspaper Bundle全日のgzip等の圧縮方式
- 競馬場での自動更新頻度

これらはv0.1の1R PoCを確認してから判断する。
