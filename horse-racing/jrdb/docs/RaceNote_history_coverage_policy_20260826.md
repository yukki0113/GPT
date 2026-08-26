# RaceNote history coverage policy - 2026-08-26

RaceNoteの履歴層はJRDB / JRAで取得できる国内履歴を正本範囲とし、海外戦を含むキャリア全体の完全収録を保証しない。

## 目的

`historical_profile.career.starts = 0` や `recent_runs = []` を、GPTが「その馬は未出走」と誤読しないよう、履歴の取得範囲を明示する。

## history_coverage

各馬に以下を付与する。

```json
{
  "scope": "jrdb_jra_history",
  "observed_history": "present",
  "observed_starts": 7,
  "overseas_history_coverage": "not_guaranteed",
  "reason": "jra_history_observed"
}
```

### observed_history

- `present`: Analysis Lite上に対象日以前のJRA履歴が1走以上ある。
- `none`: Analysis Lite上に対象日以前のJRA履歴がない。

### reason

- `jra_history_observed`: JRA履歴が1走以上確認できる。
- `no_prior_jra_history_observed`: 国内所属馬で対象日以前のJRA履歴が0走。新馬・初出走等を含む。
- `foreign_based_entry_no_jra_history`: 海外所属が明確で、対象日以前のJRA履歴が0走。
- `target_entry_not_found`: Analysis Liteに対象馬のtarget entryが見つからない。

## 海外所属馬

`basic.trainer_base` がJRA国内所属（美浦・栗東・地方）以外で、かつAnalysis Liteのcareer startsが0の場合、海外所属馬として明示する。

この場合、`historical_profile` の0件集計はキャリア0戦と誤読されやすいため `null` とし、`history_coverage.reason = foreign_based_entry_no_jra_history` を根拠とする。

## 国内所属馬の海外遠征

国内所属馬について、RaceNoteだけから海外戦が何走欠落しているかを推測しない。

`history_coverage.scope = jrdb_jra_history` と `overseas_history_coverage = not_guaranteed` を常に明示し、シンエンペラー等の海外遠征を挟む馬について `complete / partial` のような推測ラベルは付けない。

## 原則

- 取得できない海外実績を補完・推測しない。
- `0`（JRA履歴0走）と `null`（この履歴層ではキャリア集計として扱わない）を区別する。
- PACIの当日事前情報（IDM、適性、調教等）は履歴coverageとは独立して保持する。

## 実データ検証

2026-08-26に以下で再生成し、RaceNote Request経路が正常完走することを確認した。

### 2025-11-30 東京12R ジャパンカップ

- カランダガン（trainer_base=`仏国`）
  - `observed_history = none`
  - `observed_starts = 0`
  - `overseas_history_coverage = not_in_scope`
  - `reason = foreign_based_entry_no_jra_history`
  - `historical_profile = null`
  - PACI由来の当日事前情報は保持。
- シンエンペラー（trainer_base=`栗東`）
  - `observed_history = present`
  - `observed_starts = 7`
  - `overseas_history_coverage = not_guaranteed`
  - `reason = jra_history_observed`
  - 海外戦の欠落数やcomplete/partialは推測しない。
- 全18頭のreason分布
  - `jra_history_observed`: 17頭
  - `foreign_based_entry_no_jra_history`: 1頭

### 2026-05-09 京都11R 京都新聞杯

- 全16頭が `jra_history_observed`。
- 全16頭で `historical_profile` を保持。
- 海外所属誤判定・不要なnull化は0件。

以上から、海外所属馬の0件履歴と国内馬の観測済みJRA履歴を区別しつつ、海外遠征履歴の完全性を推測しない方針を採用候補とする。
