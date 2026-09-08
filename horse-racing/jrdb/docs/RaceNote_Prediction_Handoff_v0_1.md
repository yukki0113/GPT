# RaceNote Prediction Handoff v0.1

## 1. Purpose

RaceNoteを中央競馬予想プロジェクトの「GPT向けJRDBデータアダプタ」として使い、ユーザーが

```text
9/12 中山11Rを予想して
```

のように1Rだけ気軽に依頼したとき、データ取得からGPTの予想までを一貫して実行するためのhandoff契約を定義する。

RaceNote自体へ予想ロジックを埋め込まない。

```text
JRDB / Analysis / Stats
  -> RaceNote v1.0 authoritative bundle
  -> Reader View v0.1
  -> GPT prediction layer
  -> user-facing prediction
```

この文書はGPT prediction layerの初期運用契約であり、学習済みスコアモデルや固定weightを定義するものではない。

## 2. Standard one-race flow

ユーザーが日付・開催場・Rを指定して予想を依頼した場合、GPTは原則として追加のartifact path入力をユーザーへ要求せず、次を実施する。

1. Google Driveアダプタで現行Analysis Lite / Stats Martをresolveする。
2. 標準 `[RACENOTE_REQUEST]` Issueを作成する。
3. GitHub Actions結果を確認し、`task_exit_code=0` / `collect_exit_code=0` のartifactを回収する。
4. `src/racenote_reader_zip.py` 相当のGPT-side処理でReader Viewを生成する。
5. `source_semantic_sha256` round-trip validationを通す。
6. Reader Viewを第一読込対象として予想する。
7. Reader Viewだけでは判断しづらい詳細がある場合のみ、対応するauthoritative `race_bundle_*.json` を参照する。
8. ユーザーへ予想と根拠を返す。

Drive取得はGPTアダプタの責務。RaceNoteへ新しいDrive bridgeを追加しない。

## 3. Prediction input contract

通常の1R予想で採用できる入力は次を満たすこと。

- RaceNote source schema: `1.0`
- Reader View version: `0.1`
- request targetとbundleの `date / venue / race_no` が一致
- Reader View round-trip semantic SHA validation: PASS
- historical requestの場合、`as_of_exclusive = target_date`
- target-date result / target-date以降の履歴が混入していない
- RaceNote warning / coverage / missing情報を無視しない

上記を満たさない場合、GPTは推測で埋めず、取得・validation側の問題として扱う。

## 4. Information reading order

v0.1では固定数式を導入せず、情報を次の順で整理してから比較する。

### 4.1 Race context

最初に `race` を読む。

主な対象:

- surface / distance
- turn / course_layout
- race_type / class / grade
- field_size
- race_conditions / weight_rule
- `race_trends`

レース条件を確認せず、馬単体の指数だけで順位を決めない。

### 4.2 Current-entry ability

各馬の今回エントリー時点の基礎情報を読む。

主な対象:

- `basic`
- `ability`
  - IDM
  - total_index
  - running_style
  - distance_fit
  - surface_fit
  - heavy_track_fit
  - JRDB class
- `jrdb_ratings`

単一indexを絶対評価とせず、今回条件・他馬との相対比較に使う。

### 4.3 Race shape / pace

`pace` から脚質構成と今回想定位置を比較する。

主な対象:

- start_index / late_break_rate
- forecast_pace
- front / pace / late / position indices and ranks
- forecast_positions
- pace symbol

「能力が高い」ことと「今回展開が向く」ことを分けて記述する。

### 4.4 Training / condition

`training` と `condition` を今回の上振れ・下振れ材料として読む。

主な対象:

- training_index / training_arrow
- main_workout
- workout clock indices
- one_week_ago
- condition_index / volume_grade
- improvement
- stable_evaluation
- rotation_interval
- rest_reason / horse_traits

調教単独で過去実績を覆すのではなく、能力評価に対するcurrent-state evidenceとして扱う。

### 4.5 Recent detailed history

`recent_runs` は最大5走の詳細履歴として読む。

主な対象:

- race condition
- finish / abnormal
- time / carried weight / jockey
- IDM and pace/performance indices
- corner positions
- first/last 3F
- body weight / condition
- special notes / equipment / leg information
- paddock / equipment / race comments

`recent_runs`件数をcareer全履歴と解釈しない。`history_coverage.run_layers` を必ず併読する。

### 4.6 Longer history / suitability

`historical_profile` と `older_runs` を使う。

- career
- same_surface
- same_distance
- distance_ranges
- same_venue
- compact older_runs

small sampleの100%を強い根拠として扱わない。`starts` と `sample_size_band` をセットで読む。

### 4.7 Context statistics

`stats` / `race_trends` は補助的な条件傾向として読む。

- sire
- jockey
- frame trends
- exact condition
- target-relevant distance ranges

母数を無視して率だけで評価しない。

### 4.8 Market information

RaceNote内の `market` はJRDBが事前データとして保持するbase odds/rankであり、RaceNote inputとして利用可とする。

ただし:

- live oddsとはみなさない
- 最終人気・最終オッズとはみなさない
- popularityだけで予想順位を決めない
- live odds取得を別途行う場合は、RaceNote predictionとは入力sourceを明示的に分ける

## 5. Comparison discipline

各馬を独立に長文評価してから順位を付けるのではなく、最後に必ず横比較する。

最低限、次の軸を比較する。

1. 基礎能力
2. 今回条件適性
3. 展開適合
4. 調教・状態
5. 近走内容
6. 履歴・条件実績
7. 騎手・種牡馬・枠等の補助統計
8. 不確実性 / coverage

v0.1では軸ごとの固定weightを定義しない。weightを固定する場合は別途backtest/forward testを行い、prediction model versionとして管理する。

## 6. Missing / uncertainty policy

- `null` を平均値や無難な値へ補完しない。
- overseas/JRDB scope外履歴を推測しない。
- `sample_size_band=small` は小母数として明示する。
- `history_coverage.observed_history=none/unknown` を能力不足と同義にしない。
- 調教コメントや特記がないことをnegative signalと決めつけない。
- contradictory evidenceがある場合、どちらかを隠さずriskとして残す。

## 7. Result leakage policy

Historical race predictionでも、予想が確定する前に次を参照しない。

- target race finish
- target race final odds / final popularity
- target race payout
- target date以降のhorse history
- web記事や検索結果に含まれるtarget race result

RaceNote v1.0のas-of contractをそのままprediction layerでも守る。

Post-race evaluationを行う場合は:

```text
prediction freeze
 -> prediction record/hash
 -> result acquisition
 -> evaluation
```

の順序を守る。

## 8. Default user-facing prediction format

ユーザーが特別な形式を指定しない1R予想では、初期標準を次とする。

```text
◎ 馬番 馬名
○ 馬番 馬名
▲ 馬番 馬名
△ 馬番 馬名
（必要なら△追加）

展開:
短いレース全体の見立て

本命理由:
◎の主要な根拠とrisk

相手:
○▲△の差を簡潔に説明

自信度: A / B / C
```

- 印は相対順位の表現であり、確率を装わない。
- `A/B/C` はGPTのevidence confidenceであり、的中確率ではない。
- 買い目はユーザーが求めた場合、または今後別のbetting policyを正式化した場合に追加する。
- 根拠はRaceNoteの具体的な観測値・履歴・展開から説明し、存在しない情報を生成しない。

## 9. Separation from other prediction-support subsystems

中央競馬予想プロジェクトにはEvalやkeibailuka等の別consumer/sourceが存在するが、RaceNote単独の標準1R prediction contractへ暗黙に混ぜない。

追加sourceを併用する場合は:

- RaceNote由来
- Eval由来
- blog由来
- その他外部source

を区別して扱う。

将来、複数sourceを統合する中央prediction layerを作る場合も、RaceNoteはJRDB data adapterの責務を維持する。

## 10. v0.1 acceptance state

Reader Viewまでのreal-data E2Eは `docs/RaceNote_Reader_View_E2E_20260908.md` でPASS済み。

次の開発段階は、このhandoffを使った**blinded historical prediction PoC**である。

PoCでは結果を伏せた状態で複数レースを予想freezeし、その後結果を取得して、

- 読み落とし
- evidenceの過大/過小評価
- confidence calibration
- 印の安定性
- Reader Viewで不足する情報

を検証する。

この検証前に固定weightや自動買い目生成をproduction化しない。
