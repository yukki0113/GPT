# RaceNote Forecast Gen0 Ledger Contract v0.1

Status: CURRENT
Last reviewed: 2026-09-13

## 1. Purpose

RaceNote Forecast Gen0の予想・Freeze・結果・振返り・generation改善を、ネイティブGoogle Sheets上で直接管理する。

この台帳は「当たり外れの成績表」だけではない。結果取得前にGPTが何を重視し、各馬をどう比較し、どの不確実性を残して予想したかを固定し、結果取得後に別レコードとして検証するための研究台帳である。

## 2. Authoritative ledger

- Spreadsheet title: `RaceNote Forecast Gen0 検証台帳`
- Spreadsheet ID: `1z9TJQJ61WEcrVSDxhAWP9D48plP1ixU0hCH-QGZrhnU`
- Parent folder ID: `1hWBtTRj4aHiFXAkln3qxjW_g7b1FUeoO`
- Google Sheets timezone: `Asia/Tokyo`

このSpreadsheet IDは日次artifact IDではなく、継続研究台帳のstable identityとしてGit configへ保持する。

正本config:

`config/racenote_forecast_gen0_ledger_v0_1.json`

## 3. Access policy

ChatGPT運用ではGoogle Drive / Google Sheets connectorから台帳を直接読み取り・編集する。

RaceNote本体へGoogle API client、OAuth token、service account key、Drive secretを追加しない。

標準操作:

- current generation / factor set確認: `設定`, `世代管理` を直接read
- duplicate確認: `forecast_id`, `race_key + generation_id` をSheet内で検索
- pre-result write: Google Sheets batch update
- post-result write: Google Sheets batch update
- generation analysis: Sheetsの対象行を直接readして集計・GPT分析

Gitはschema / validation / freeze / row contractを持ち、Google Sheetsは継続運用データを持つ。

## 4. Tab model

### `README`

台帳利用者向けの短い入口。

### `設定`

current generation、forecast version、factor set version、初期factor定義、freeze不変条件を保持する。

### `世代管理`

約50R単位のgenerationを管理する。

主キー: `generation_id`

初期generation:

`Gen0-G000`

### `予想Freeze`

**結果取得前のrace-level予想正本。**

1 race = 1 row。

主要identity:

- `forecast_id`
- `generation_id`
- `race_key`
- `source_semantic_sha256`
- `prediction_hash`

この行はFreeze後に予想内容を上書きしない。

### `馬別評価`

結果取得前のrunner-level評価。

1 forecast × 1 horse = 1 row。

長い内部chain-of-thoughtは保存しない。保存するのは監査可能な短いreason summary / evidence summary / risk / relative comparisonである。

### `ファクター使用`

GPTが予想時にファクターをどう扱ったかを構造化して保存する。

- `importance`: `HIGH / MEDIUM / LOW / NOT_USED`
- `direction`: `POSITIVE / NEGATIVE / MIXED / NEUTRAL`
- `role`: `PRIMARY / SUPPORT / RISK / DEEMPHASIZED`
- `scope`: `RACE / HORSE`

これらは点数ではない。GPTがそのレースでどの材料を重く・軽く読んだかを後から研究する観測メタデータである。

### `結果_馬別`

Freeze成功後にのみ追記するofficial result。

1 race × 1 horse = 1 row。

結果を`予想Freeze`や`馬別評価`へ追記しない。

### `振返り`

race-level post-race evaluation。

客観指標:

- ◎着順
- ◎勝利
- 勝馬の事前印
- 上位3着内に何頭印を付けていたか

GPT review:

- race reading
- ability
- suitability
- pace / position
- training / condition
- recent form
- history
- uncertainty handling

### `ファクター検証`

`ファクター使用`の事前記録と結果後の評価を結びつける。

- `post_relevance`: `HELPFUL / NEUTRAL / MISLEADING / UNRESOLVED`
- `over_under_eval`: `OVER / UNDER / APPROPRIATE / NA`
- `evidence_quality`: `GOOD / MIXED / POOR / UNRESOLVED`

「F03が外れたからF03を廃止」のような1R追従には使わない。generation単位で繰り返し傾向を見る。

### `Freeze監査`

hash整合と結果取得順を監査する。

最低条件:

- `pre_race_guard_status = PASS`
- `result_visibility_status = HIDDEN`
- prediction hash再計算一致
- `frozen_at < result_acquired_at`

### `条件別集計`

generation評価で再生成する集計用tab。正本明細は上記raw tabsであり、このtabはderived outputとする。

### `ダッシュボード`

運用進捗の簡易表示。的中率だけをモデル採否基準にしない。

### `変更履歴`

generation間で何を変えたかを記録する。

「前の方が成績が良かったので旧方式へ戻した」はcurrent方針として採用しない。変更理由はGen0自身のreading auditから説明できること。

## 5. Initial factor set

`FSET-Gen0.1` は10ファクター。

| code | factor |
| --- | --- |
| F01 | 基礎能力 |
| F02 | 条件適性 |
| F03 | 展開・位置取り |
| F04 | 調教・状態 |
| F05 | 近走内容 |
| F06 | 長期履歴・条件実績 |
| F07 | 騎手・厩舎 |
| F08 | 血統 |
| F09 | 枠・条件統計 |
| F10 | 事前市場情報 |

固定weightは持たない。

GPTは各レースで重要度を変えてよい。事前市場情報はRaceNoteに含まれる開催前base odds / rankのみを指し、target race final odds / final popularityではない。

factor setを変更する場合は同じgenerationを上書きせず、versionと変更履歴を更新する。

## 6. Evaluation modes

### `BLINDED_HISTORICAL`

過去JRDBデータからtarget resultとtarget date以降の情報を遮断した再現予想。

Gen0初期50Rは原則このmodeから開始する。

### `TRUE_FORWARD`

実開催前に予想・Freezeし、開催後に結果を取得する真正forward。

両modeを同じ列で混ぜず、`evaluation_mode`を必ず記録する。

## 7. Pre-result transaction

1Rについて次の順序を固定する。

1. `設定` / `世代管理` をread
2. as-of-safe RaceNoteを取得
3. source identity / semantic SHAを検証
4. GPTが予想
5. structured forecast payloadを作る
6. `src/racenote_forecast_gen0.py`相当のvalidationを通す
7. `pre_race_guard_status=PASS` / `result_visibility_status=HIDDEN`を確認
8. prediction hashを生成
9. Freeze
10. duplicateがないことを確認
11. `予想Freeze + 馬別評価 + ファクター使用 + Freeze監査`を同一batchでwrite
12. readbackで`forecast_id / prediction_hash / row count`を確認
13. **ここまで成功するまで結果を取得しない**

Google Sheets batchUpdateは同一transactionにまとめ、途中tabだけ更新した状態を作らない。

## 8. Post-result transaction

1. frozen forecastを台帳からread
2. `prediction_hash`を再監査
3. official resultを取得
4. `result_acquired_at > frozen_at`を検証
5. 全出走馬identityを突合
6. `結果_馬別`へwrite
7. GPTが事後reviewを行う
8. `振返り + ファクター検証 + Freeze監査更新`を同一batchでwrite
9. readback

事後reviewによって`予想Freeze / 馬別評価 / ファクター使用`を書き換えない。

## 9. Generation cycle

初期targetは約50R。

```text
Gen0-G000
  -> 50R blinded forecast/freeze
  -> 50R result join/evaluation
  -> generation analysis
  -> change proposal
  -> change history
  -> Gen0-G001
```

1R単位でframeworkを修正しない。

50R到達前でも、result leakage、schema破損、入力欠落など研究成立を妨げる実装バグは修正してよい。その場合はprediction logic変更とbug fixを変更履歴で区別する。

## 10. Generation analysis

最低限、次を見る。

- ◎成績 / 印内捕捉
- confidence別
- 芝ダ / 距離 / class等の条件別
- primary factor別
- `HELPFUL / MISLEADING`
- `OVER / UNDER`
- failure category
- data coverage不足
- contradictory evidence処理
- 予想が単一indexの言い換えになっていないか

成績が良い旧deterministic policyへ戻すための比較ではなく、GPT Forecast Gen0の読み方を改善するために使う。

## 11. Implementation references

- `src/racenote_forecast_gen0.py`
  - pre-result validation
  - result leakage guard
  - prediction hash
  - Freeze
  - pre-result ledger row projection
- `src/racenote_forecast_gen0_evaluation.py`
  - freeze-before-result audit
  - result identity validation
  - objective outcome calculation
  - post-race review row projection
- `tests/test_racenote_forecast_gen0.py`
- `tests/test_racenote_forecast_gen0_evaluation.py`
- `config/racenote_forecast_gen0_ledger_v0_1.json`
