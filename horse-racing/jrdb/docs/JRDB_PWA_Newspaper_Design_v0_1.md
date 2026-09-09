# JRDB PWA 自分用競馬新聞 Design v0.1

Status: DRAFT / DESIGN ONLY / PWA implementation not started

## 1. Purpose

スマホ中心で閲覧する「自分用競馬新聞」を、既存JRDB / Eval / Edge / RaceNote prediction / keibailuka / 将来の独自指数を統合する週末実戦用PWA画面として設計する。

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

データ側は最大8走を初期候補とする。ただしこれは**Newspaper自身の表示要件**であり、RaceNoteの実装契約を継承するものではない。

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

- RaceNote prediction由来のレース短評 / 展開コメント（addonが存在する場合のみ）
- JRDB予想ペース
- JRDBペース / 展開関連指数
- その他、文章化しなくても有用なレース単位値

JRDBに自然文短評が存在しない場合、無理に生成せず `ラベル: 値` のstructured itemで表示する。

## 5. Hard architecture boundary

### 5.1 Newspaper is not a RaceNote derivative

NewspaperのJRDB Base/historyはRaceNoteの内部実装から生成しない。

次の依存は禁止する。

```text
RaceNote v1.0 bundle -> Newspaper Base/history
src/racenote_jrdb.py -> Newspaper Base
src/racenote_history_engine.py -> Newspaper history
その他 src/racenote_* の内部ロジック -> Newspaper JRDB Base/history
```

採用する依存方向は次とする。

```text
JRDB Raw / PACI
  -> neutral JRDB layer
     - src/jrdb_raw.py
     - src/jrdb_raw_history.py
     - Canonical / Analysis等のconsumer-neutral access
     - 必要に応じて新設するneutral history/helper module
        -> RaceNote adapter
        -> Newspaper adapter
```

### 5.2 Promotion rule for reusable logic

RaceNote内にNewspaperでも必要なロジックが存在する場合、Newspaperから直接importして使わない。

1. その処理が本質的にJRDB汎用責務かを判定する。
2. 汎用なら `jrdb_*` neutral moduleへ抽出する。
3. RaceNote側をそのneutral module利用へリファクタする。
4. RaceNote回帰テストでsemantic behavior不変を確認する。
5. Newspaperも同じneutral moduleを利用する。

RaceNote固有のschema projection、GPT-facing enrichment、Reader View、prediction handoff等はNewspaper Base/historyへ持ち込まない。

### 5.3 RaceNote prediction is an external addon

RaceNote predictionの**成果物**である印・短評・展開見立ては、Evalやkeibailukaと同じ外部sourceとして `addons.racenote_prediction` にmergeできる。

これはRaceNote内部実装への依存とは別責務であり、JRDB Base/history生成の前提にしない。

## 6. Source separation

新聞は中央統合表示層であり、各sourceの正本責務を奪わない。

```text
JRDB PACI / neutral history -> newspaper JRDB base
Eval                         -> eval namespace
RaceNote prediction output   -> racenote_prediction namespace
keibailuka                    -> keibailuka namespace
JRDB Edge Registry            -> edge_matches
Independent index             -> my_index namespace
```

RaceNote v1.0 authoritative bundleはRaceNoteの正本のままとする。
Eval / blog / prediction結果をRaceNote bundleへ書き戻さない。

## 7. Newspaper Race Bundle

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

## 8. Daily Manifest

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

## 9. Identity / merge keys

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

## 10. Hybrid generation / merge

理想の日次Work操作は1種類の依頼で何度でも安全に再実行できる形とする。

ユーザー例:

```text
09/12の競馬新聞用データを生成してください。
```

### First run

PACIが存在すればJRDB baseを生成する。

```text
PACI
 -> Common Reader / neutral JRDB modules
 -> race / runner current info
 -> Newspaper-owned as-of-safe history projection
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

## 11. Namespace ownership rule

source間の上書き事故を防ぐ。

- JRDB builderは `race`, `basic`, `jrdb`, `history` を所有
- Eval mergerは `addons.eval` だけを所有
- RaceNote prediction mergerは `addons.racenote_prediction` とrace-level RaceNote noteだけを所有
- keibailuka mergerは `addons.keibailuka` だけを所有
- independent index mergerは `addons.my_index` だけを所有
- Edge matcherは `edge_matches` だけを所有

他namespaceの値をmerge時に削除・再解釈しない。

## 12. Edge display contract

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

## 13. Newspaper history policy

履歴はNewspaper自身のconsumer contractとして設計する。

初期要件:

```text
bundle max history: 8
initial visible: 3
all history dates: < target_date
```

取得は次のneutral情報だけを土台にする。

- KYIが明示するprevious result/race links
- `src/jrdb_raw.py`
- `src/jrdb_raw_history.py`
- 必要に応じてCanonical / Analysisのneutral historical access
- 今後抽出するconsumer-neutral history helper

最大8走の具体的なsource構成はneutral dependency inventory後に決める。

既存RaceNoteで「PACI detailed 5 + Analysis compact 3」が実用的だったという知見は**設計参考値**として利用してよいが、Newspaperの実装contractやimport dependencyにはしない。

同じ固定長offsetを新モジュールへ複製しない。履歴解決に必要な汎用機能が不足する場合はneutral層へ追加する。

Historical PoCでは必ず `history_date < target_date` を守る。

## 14. Target-race leakage boundary

新聞baseは開催前情報で生成する。

対象レースについて以下を混入させない。

- target finish
- final target popularity / odds
- payout
- final target track condition
- target result indices

過去走については対象日より前の確定結果を表示可能。

## 15. Drive canonical and PWA delivery

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

## 16. PWA offline behavior

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

## 17. Performance strategy

16頭×最大8走程度は、Fact Lite SQLite全量集計より小さい表示問題と見込むが、実機で測る。

初期対策:

- 1レースだけDOMへ描画
- 過去走は3走のみvisible
- 4走目以降は同じJSONから展開
- 重い詳細popoverは押下時生成
- race切替時に前race DOMを破棄
- day manifestのみ常時保持
- optional addon欠損を埋めるための追加network callを描画中に発生させない

## 18. Proposed module boundaries

実装時の候補。名前は実装開始時に確定する。

```text
# neutral JRDB layer（不足時のみ新設）
src/jrdb_history_common.py  # name tentative

# Newspaper consumer
src/newspaper_build.py
src/newspaper_history.py
src/newspaper_merge.py
src/newspaper_publish.py
schema/jrdb_pwa_newspaper_race_schema_v0_1.json
schema/jrdb_pwa_newspaper_manifest_schema_v0_1.json
pwa/newspaper.html
pwa/newspaper.js
```

`src/newspaper_*` から `src/racenote_*` をimportしないことをarchitecture test / review項目にする。

Work専用スレッドはこのmodule contractを読み、ユーザーが日付だけ指定できる運用を目標とする。

## 19. Validation contract

日次生成で最低限確認する。

### Architecture

- Newspaper Base/history import graphに `racenote_*` が存在しない
- 共通化した汎用処理は `jrdb_*` neutral moduleに置かれている
- RaceNoteから汎用処理を抽出した場合、RaceNote回帰がPASSしている

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
- history source重複なし
- coverageを虚偽に完全履歴と表現しない

### Merge

- source namespace以外を変更しない
- join key unmatchedを監査
- duplicate addon keyはエラー
- 同一source version再mergeでsemantic result不変

### Distribution

- schema validation PASS
- file size / SHA-256一致
- manifestのrace countと配布race file数一致
- publish失敗時に既存current day setを壊さない

## 20. First PoC proposal

画面実装へ入る前に、まず**neutral dependency inventory**を作成する。

確認対象:

1. BAC/KYI/CHA/CYB/UKCの新聞Baseに必要なfieldがCommon Readerで揃うか
2. previous 1-5の履歴解決がneutral moduleだけで可能か
3. 6-8走目を補う場合に必要なneutral historical accessは何か
4. RaceNote内にしかないが本質的に汎用な処理があるか
5. ある場合、どの単位でneutral層へ格上げするか

その後、既存データが揃っている16頭立ての1RでNewspaper JSONを生成する。

第一候補:

```text
2026-08-16 札幌11R 札幌記念 16頭
```

このレースを選ぶ理由はRaceNoteを入力に使うためではなく、過去にデータ量や16頭表示の参考測定があり、比較しやすいため。

PoCで確認する。

1. 1 race JSON bytes
2. 1 horse rowの表示密度
3. 3走 / 5走 / 8走切替
4. sticky列の必要幅
5. iPhone横スクロール
6. Edge/addon null slot表示
7. OPFS保存 / 再読込
8. RaceNote非依存のimport graph

## 21. Deferred decisions

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
