# RaceNote Forecast Gen0 Sample / Queue Contract v0.1

Status: CURRENT
Last reviewed: 2026-09-13

## 1. Purpose

Gen0の約50Rは「一度にGPTへ予想させるbatch」ではなく、**改善判断を行う固定問題集**として先に選定する。

予想単位は常に1R。運用上は標準5R程度を1チャンクとして順番に消化してよいが、各Rのforecast / hash / Freezeは独立させる。

```text
JRDB Analysis Lite historical SQLite
  -> deterministic race sampler
  -> immutable 50R PRIMARY + 20R RESERVE manifest
  -> Google Sheets 対象Rキュー
  -> next READY race
  -> as-of-safe RaceNote
  -> GPT Forecast 1R
  -> guard / Freeze / ledger
```

## 2. Sampling source

標準sourceはJRDB Analysis Lite v1.3 SQLiteの `fact_entry_result_lite`。

使用可能なselection field:

- race_date
- venue_code
- race_no
- race_key
- track_type
- distance
- race_condition_code
- grade_code
- runner count (`COUNT(*)`)

selectionで使用禁止:

- finish
- abnormal result interpretation
- final_win_odds
- final_win_popularity
- win_payout / place_payout
- その他target race outcome

Analysis Lite自体は結果列を保持するが、sampler queryはそれらをSELECT / WHERE / ORDER BYへ使用しない。

## 3. Eligibility

初期Gen0では中央10場の平地のみ。

- `track_type=1`: 芝
- `track_type=2`: ダート
- `track_type=3`: 障害 -> 除外

JRDB BACの固定長定義に従う。

抽出時点ではRaceNote deliveryの実体存在まで結果由来の条件で選別しない。選出後、as-of-safe RaceNoteをresolveできない等の**技術的欠損**が判明した場合のみ予備枠へ置換する。

## 4. Initial sampling policy

`Gen0-G000` default:

- PRIMARY: 50R
- RESERVE: 20R
- same-date cap: 3R
- turf/dirt minimum share: each 30%
- seed: generationごとに固定しmanifestへ保存

芝/ダートを50:50へ強制しない。母集団比率を基本としつつ、片方が30%未満にならない程度の軽い層化だけ行う。

距離・class・開催場を均等割りしない。Gen0で細かく人工的な標本設計を入れすぎないためである。

PRIMARY 50RとRESERVE 20Rは別々に層化抽出し、PRIMARY本体の芝/ダート比率が予備枠の並びに左右されないようにする。

## 5. Reproducibility

samplerはcandidate poolをstable orderで読み、次を保存する。

- generation_id
- seed
- candidate_pool_sha256
- manifest_id
- manifest_sha256
- sampler version
- primary / reserve counts
- constraints
- selected race identities

同じcandidate pool + seed + sampler versionから同じmanifestを再生成できることを要求する。

## 6. PRIMARY and RESERVE

PRIMARY 50Rがgeneration評価対象。

RESERVE 20Rは最初から別に固定する。予備を使ってよいのは、例えば次のようなprediction以前の技術的理由だけ。

- historical RaceNoteをas-of-safeに生成できない
- source archive欠損
- race identity不整合
- Reader View validation failure
- source runner coverageを確立できない

次の理由では置換禁止。

- 予想が難しい
- 頭数が多い / 少ない
- 指数差が小さい
- 人気馬が強そう
- GPTが自信を持てない
- 予想後に結果が悪かった

置換時はPRIMARY rowを `SKIPPED_TECH` とし、未使用RESERVEのうち次を満たす最小sample_orderを `READY` へ昇格する。

1. failed PRIMARYと同じ `surface_code`（芝/ダート構成を維持）
2. 昇格後もeffective sampleの同一開催日3R上限を超えない

`replacement_for` と `skip_reason` を必ず記録する。

## 7. Google Sheets queue

継続台帳 `RaceNote Forecast Gen0 検証台帳` に `対象Rキュー` を置く。

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

`対象Rキュー` は進行管理であり、予想内容の正本ではない。予想正本は引き続き `予想Freeze / 馬別評価 / ファクター使用`。

## 8. Queue status

標準遷移:

```text
PRIMARY: READY
  -> SOURCE_READY
  -> IN_PROGRESS
  -> FROZEN
  -> RESULT_JOINED
  -> EVALUATED

RESERVE: RESERVE
  -> READY       (technical replacement only)
  -> SOURCE_READY
  -> ...
```

技術的欠損:

```text
READY / SOURCE_READY
  -> SKIPPED_TECH
```

結果や予想精度を理由に過去statusを戻さない。

## 9. Forecast execution chunk

標準チャンクは5R。

ユーザーが「Gen0-G000を5R進めて」と依頼した場合:

1. `設定 / 世代管理 / 対象Rキュー`をread
2. sample_order順に次のREADY 5Rを確定
3. 各Rについて個別にRaceNoteをresolve
4. **各Rを独立したforecast unitとして**GPTが全馬比較
5. guard -> hash -> Freeze -> Sheet write/readback
6. 次Rへ進む

チャンク内で前レースの**結果を取得しない**。また、前レースの予想内容を次レースの追加ルールへ変換しない。

結果処理は5RすべてFreeze後に行ってよい。

## 10. Generation learning boundary

途中で結果を取得・振返り記録してもよいが、Gen0-G000の50Rが終わるまでforecast framework / factor setを変更しない。

例外は研究成立を妨げる実装バグ、result leakage、source identity defectだけ。その場合もprediction logic changeではなくbug fixとして変更履歴へ残す。

50R完了後に初めてgeneration analysisを行い、次世代 `Gen0-G001` の変更を決める。

## 11. Implementation

- `src/build_racenote_gen0_sample_manifest.py`
- `src/racenote_forecast_gen0_queue.py`
- `tests/test_build_racenote_gen0_sample_manifest.py`
- `tests/test_racenote_forecast_gen0_queue.py`
- `config/racenote_forecast_gen0_ledger_v0_1.json`
- `FORECAST_GEN0_LEDGER_CONTRACT_v0_1.md`
- Google Sheets `対象Rキュー`
