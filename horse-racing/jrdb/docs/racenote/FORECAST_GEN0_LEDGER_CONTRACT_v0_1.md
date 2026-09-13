# RaceNote Forecast Gen0 Ledger Contract v0.1

Status: CURRENT
Last reviewed: 2026-09-13

## 1. Purpose

RaceNote Forecast Gen0の対象R固定、予想、Freeze、結果、振返り、generation改善を、ネイティブGoogle Sheets上で直接管理する。

この台帳は単なる成績表ではない。結果取得前に「どのレースを予想対象として固定したか」「GPTが何を重視し、各馬をどう比較したか」を保存し、結果取得後に別レコードとして検証する研究台帳である。

## 2. Authoritative ledger

- Spreadsheet title: `RaceNote Forecast Gen0 検証台帳`
- Spreadsheet ID: `1z9TJQJ61WEcrVSDxhAWP9D48plP1ixU0hCH-QGZrhnU`
- Parent folder ID: `1hWBtTRj4aHiFXAkln3qxjW_g7b1FUeoO`
- Google Sheets timezone: `Asia/Tokyo`

正本config:

`config/racenote_forecast_gen0_ledger_v0_1.json`

## 3. Access policy

ChatGPT運用ではGoogle Drive / Google Sheets connectorから台帳を直接読み取り・編集する。

RaceNote本体へGoogle API client、OAuth token、service account key、Drive secretを追加しない。

Gitはsampling / schema / validation / freeze / queue transition / row contractを持ち、Google Sheetsは継続運用データを持つ。

## 4. Tab model

### `README`

台帳利用者向けの短い入口。

### `設定`

current generation、forecast version、factor set version、sampling policy、freeze不変条件を保持する。

### `世代管理`

約50R単位のgenerationとsampling manifest identityを管理する。

主キー: `generation_id`

主要sampling列:

- manifest_id
- manifest_sha256
- sample_seed
- candidate_pool_sha256
- primary_count
- reserve_count

### `対象Rキュー`

**generation開始前に固定した問題集と進行状態。**

PRIMARY 50R + RESERVE 20Rをmanifest単位で保存する。

主要列:

- manifest_id / manifest_sha256
- generation_id
- sample_order
- sample_role (`PRIMARY / RESERVE`)
- queue_status
- race_date / venue / race_no / race_key
- surface / distance / class code / runner_count
- replacement_for / skip_reason
- forecast_id
- source_ready_status
- started_at / frozen_at / evaluated_at

このtabは進行管理であり、予想内容の正本ではない。

### `予想Freeze`

結果取得前のrace-level予想正本。1 race = 1 row。

主要identity:

- forecast_id
- generation_id
- race_key
- source_semantic_sha256
- prediction_hash

Freeze後に予想内容を上書きしない。

### `馬別評価`

結果取得前のrunner-level評価。1 forecast × 1 horse = 1 row。

長い内部chain-of-thoughtは保存せず、監査可能な短いreason / evidence / risk / relative comparisonを保存する。

### `ファクター使用`

GPTが予想時にファクターをどう扱ったかを構造化して保存する。

- importance: `HIGH / MEDIUM / LOW / NOT_USED`
- direction: `POSITIVE / NEGATIVE / MIXED / NEUTRAL`
- role: `PRIMARY / SUPPORT / RISK / DEEMPHASIZED`
- scope: `RACE / HORSE`

これらは点数ではなく、GPTの読み方を後から研究する観測メタデータである。

### `結果_馬別`

Freeze成功後にのみ追記するofficial result。結果を予想タブへ追記しない。

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

- post_relevance: `HELPFUL / NEUTRAL / MISLEADING / UNRESOLVED`
- over_under_eval: `OVER / UNDER / APPROPRIATE / NA`
- evidence_quality: `GOOD / MIXED / POOR / UNRESOLVED`

1Rの結果だけでファクターを廃止・強化しない。

### `Freeze監査`

hash整合、結果取得順、source runner coverage、factor usage identityを監査する。

最低条件:

- pre_race_guard_status = PASS
- result_visibility_status = HIDDEN
- prediction hash再計算一致
- source全出走馬とforecast horse setが完全一致
- factor usage identity `(factor_code, scope, horse_no)` が一意
- result取得後は `frozen_at < result_acquired_at`

### `条件別集計`

generation評価で再生成するderived集計。

### `ダッシュボード`

Freeze / evaluationに加え、PRIMARY件数、READY件数、RESERVE件数、技術SKIP件数を表示する。

### `変更履歴`

generation間の変更と基盤bug fixを記録する。

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

固定weightは持たない。GPTは各レースで重要度を変えてよい。

## 6. Sampling contract

現行sampling仕様は `FORECAST_GEN0_SAMPLE_QUEUE_v0_1.md` を正本とする。

Gen0-G000 default:

- source: JRDB Analysis Lite v1.3 `fact_entry_result_lite`
- PRIMARY: 50R
- RESERVE: 20R
- 障害 `track_type=3` 除外
- 芝/ダート各30%以上の軽い層化
- PRIMARY / RESERVEとも同一開催日3R上限
- result / final odds / payout列をselectionへ使用しない
- seed / candidate pool hash / manifest hashを固定
- 標準実行チャンク: 5R

PRIMARY / RESERVEはgeneration予想開始前に一括固定する。

## 7. Queue state contract

標準遷移:

```text
READY
 -> SOURCE_READY
 -> IN_PROGRESS
 -> FROZEN
 -> RESULT_JOINED
 -> EVALUATED
```

RESERVEは通常 `RESERVE` のまま。prediction開始前の技術欠損時だけ `READY` へ昇格できる。

技術欠損:

```text
READY / SOURCE_READY -> SKIPPED_TECH
RESERVE -> READY
```

予備昇格はfailed PRIMARYと同じsurface_codeを選び、昇格後も同一開催日3R上限を維持する。

予想難易度、自信度、人気構成、結果を理由とした差替は禁止。

queue transitionのdeterministic helper:

`src/racenote_forecast_gen0_queue.py`

## 8. Evaluation modes

### `BLINDED_HISTORICAL`

過去JRDBデータからtarget resultとtarget date以降の情報を遮断した再現予想。Gen0初期50Rは原則このmode。

### `TRUE_FORWARD`

実開催前に予想・Freezeし、開催後に結果を取得する真正forward。

## 9. Generation initialization transaction

1. `設定 / 世代管理`をread
2. historical Analysis Lite SQLiteをresolve
3. `build_racenote_gen0_sample_manifest.py`でcandidate poolを構築
4. 障害を除外し、結果列非参照を確認
5. seed付きでPRIMARY50R + RESERVE20Rを固定
6. manifest_id / manifest_sha256 / candidate_pool_sha256を生成
7. `世代管理`へmanifest identityをwrite
8. `対象Rキュー`へ70Rを同一batchでwrite
9. readbackで70R、PRIMARY50、RESERVE20、manifest hashを確認
10. ここまで完了してから最初の予想チャンクへ進む

## 10. Forecast chunk transaction

標準5R。

1. `対象Rキュー`からsample_order順に次のREADY最大5Rを取得
2. 各Rについて個別にas-of-safe RaceNoteをresolve
3. source validation成功なら `SOURCE_READY`
4. 1Rだけをcurrent forecast unitとしてGPTが全馬比較
5. structured payload validation
6. pre-race guard / result hidden確認
7. prediction hash生成 / Freeze
8. source runner coverage / factor identity guard
9. `予想Freeze + 馬別評価 + ファクター使用 + Freeze監査`を同一batchでwrite
10. readback後にqueue rowを `FROZEN` へ進める
11. 次Rへ進む

チャンク中は前Rの結果を取得しない。前Rの予想内容から新ルールを作らない。

技術欠損時は `SKIPPED_TECH` とし、contractに従うRESERVEを昇格する。

## 11. Post-result transaction

5R等のチャンクがすべてFreezeした後、結果処理を行ってよい。

1. frozen forecastをread
2. prediction_hash再監査
3. official result取得
4. `result_acquired_at > frozen_at`検証
5. 全出走馬identity突合
6. `結果_馬別`へwrite
7. GPT事後review
8. `振返り + ファクター検証 + Freeze監査更新`をwrite
9. queue rowを `RESULT_JOINED -> EVALUATED` へ進める
10. readback

事後reviewで予想正本を書き換えない。

## 12. Generation cycle

```text
Gen0-G000
 -> fixed 50R problem set
 -> 1R forecasts, normally 5R chunks
 -> 50R freeze/evaluation
 -> generation analysis
 -> change proposal/history
 -> Gen0-G001
```

50R終了までforecast framework / factor setを変更しない。

result leakage、schema破損、source identity defect等の研究成立を妨げるbugは途中修正可。ただしprediction logic changeとは分けて変更履歴へ残す。

## 13. Generation analysis

最低限:

- ◎成績 / 印内捕捉
- confidence別
- 芝ダ / 距離 / class別
- primary factor別
- HELPFUL / MISLEADING
- OVER / UNDER
- failure category
- data coverage不足
- contradictory evidence処理
- 単一indexの言い換えになっていないか

旧deterministic policyへ戻すためではなく、GPT Forecast Gen0の読み方を改善するために使う。

## 14. Implementation references

- `src/build_racenote_gen0_sample_manifest.py`
  - result-blind race candidate query
  - deterministic seed sampling
  - PRIMARY / RESERVE manifest
  - queue row projection
- `src/racenote_forecast_gen0_queue.py`
  - READY chunk selection
  - state transition validation
  - technical reserve replacement
- `schema/racenote_forecast_gen0_schema_v0_1.json`
- `src/racenote_forecast_gen0.py`
- `src/racenote_forecast_gen0_guard.py`
- `src/racenote_forecast_gen0_evaluation.py`
- `tests/test_build_racenote_gen0_sample_manifest.py`
- `tests/test_racenote_forecast_gen0_queue.py`
- `tests/test_racenote_forecast_gen0.py`
- `tests/test_racenote_forecast_gen0_guard.py`
- `tests/test_racenote_forecast_gen0_evaluation.py`
- `config/racenote_forecast_gen0_ledger_v0_1.json`
- `FORECAST_GEN0_SAMPLE_QUEUE_v0_1.md`
