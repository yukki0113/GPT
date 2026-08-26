# RaceNote history run layers policy - 2026-08-27

RaceNoteの `recent_runs` / `older_runs` は、キャリア全体の完全な直近N走を保証する配列ではなく、取得元と情報密度の異なる2つの履歴レイヤーとして扱う。

## 方針

フィールド名は互換性のため維持する。

- `recent_runs`
  - source: PACI
  - role: `detailed_recent_history`
  - 最大5件
  - target KYIから参照でき、ZED/ZKBで詳細化できた過去走を保持する。
  - 「キャリア上の直近5戦を必ず完全収録する」という意味ではない。
- `older_runs`
  - source: JRDB Analysis Lite
  - role: `compact_older_history`
  - 通常RaceNoteでは最大3件（8走案）。
  - `recent_runs` に含まれる最古日より厳密に前のJRA履歴を取得する。
  - `recent_runs` が5件未満でも不足分を推測補完する用途には使わない。

## 重複回避

`older_runs` は `recent_runs` の最古日より前だけを対象とするため、2レイヤー間の日付重複を避ける。

`recent_runs` が空の場合は対象日より前のAnalysis Lite履歴を最大件数まで取得する。

## 海外戦・欠落

国内所属馬が海外遠征を挟む場合など、RaceNoteだけから途中の欠落走数を推測しない。

したがって両レイヤーとも `career_completeness = not_guaranteed` とし、`history_coverage.scope = jrdb_jra_history` / `overseas_history_coverage` と併せて解釈する。

海外所属馬でJRA履歴がない場合も、`recent_runs=[]` を「未出走」とは解釈しない。

## run_layers metadata

各馬の `history_coverage.run_layers` に、配列の意味と観測件数を明示する。

```json
{
  "run_layers": {
    "recent_runs": {
      "source": "PACI",
      "role": "detailed_recent_history",
      "observed_count": 5,
      "max_count": 5,
      "career_completeness": "not_guaranteed"
    },
    "older_runs": {
      "source": "JRDB Analysis Lite",
      "role": "compact_older_history",
      "observed_count": 3,
      "max_count": 3,
      "selection": "strictly_older_than_oldest_recent_run",
      "career_completeness": "not_guaranteed"
    }
  }
}
```

## 正式採用候補

通常RaceNoteでは以下を採用候補とする。

```text
recent_runs  PACI詳細 最大5
older_runs   Analysis簡略 最大3
合計         最大8（ただし固定8件ではない）
```

履歴件数を10走へ増やすより、各レイヤーの意味・coverage・距離統計・sample sizeを明確にすることを優先する。
