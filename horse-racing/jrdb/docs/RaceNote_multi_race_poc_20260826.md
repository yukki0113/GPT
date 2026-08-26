# RaceNote 5-race information/coverage PoC — 2026-08-26

## Purpose

RaceNoteの初期拡張案（PACI詳細 + Analysis Lite履歴/profile + Stats Mart傾向）が、性質の異なるレースでも同じ契約で扱えるかを確認する。

対象:

- 2026-07-05 小倉11R 北九州記念 — 芝1200m / ハンデG3
- 2026-05-09 京都11R 京都新聞杯 — 3歳芝2200m G2
- 2026-03-29 中山11R マーチS — ダート1800m / ハンデG3
- 2026-01-05 京都11R 万葉S — 芝3000m / OP / 9頭
- 2025-11-30 東京12R ジャパンC — 芝2400m G1 / 海外馬あり

注: 当初指定の2025-11-30東京11RはウェルカムSで、ジャパンCは東京12RだったためPoC対象を12Rへ補正した。

## Execution route

2026年4レース:

```text
[RACENOTE_REQUEST]
 -> GitHub Actions
 -> historical date detected
 -> daily PACI
 -> racenote_jrdb.py
 -> Analysis Lite enrichment (race_date < target_date)
 -> Stats Mart prior years + Analysis target-year YTD
 -> RaceNote ZIP
```

2025ジャパンC:

```text
[RACENOTE_REQUEST]
 -> GitHub Actions
 -> annual Raw BAC/KYI/CHA/CYB
 -> KYI prev1-5に必要なSED/SKBのみ取得/抽出
 -> PACI-equivalent reconstruction
 -> racenote_jrdb.py
 -> Analysis/Mart as-of enrichment
 -> RaceNote ZIP
```

5レースともtask/collect exit code 0。全bundleで `as_of_exclusive = target_date`、確認したrecent/older runにtarget-date以降の行は0件。

## Results

| Race | Horses | Bundle bytes | recent_runs | older_runs | same_distance=0 | sire starts<20 | jockey starts<20 |
|---|---:|---:|---|---|---:|---:|---:|
| 北九州記念 | 13 | 267,444 | 全13頭=5 | 12頭=3, 1頭=2 | 1/13 | 4/13 | 2/13 |
| 京都新聞杯 | 16 | 262,283 | 2〜5走 | 11頭=0, 最大3 | 13/16 | 11/16 | 7/16 |
| マーチS | 16 | 331,891 | 全16頭=5 | 全16頭=3 | 0/16 | 1/16 | 2/16 |
| 万葉S | 9 | 191,164 | 全9頭=5 | 全9頭=3 | 3/9 | 9/9 | 9/9 |
| ジャパンC | 18 | 320,103 | 0〜5走 | 0〜3走 | 2/18 | 6/18 | 8/18 |

Approximate enrichment overhead versus the same JSON with `older_runs` / `historical_profile` / `stats` / `race_trends` removed:

- 北九州記念: +17.2%
- 京都新聞杯: +14.1%
- マーチS: +17.0%
- 万葉S: +17.4%
- ジャパンC: +19.2%

The 8-run cap therefore remains a reasonable initial payload size across these cases.

## Important observations

### 1. Young horses naturally remain sparse

京都新聞杯ではcareer中央値4.5走、16頭中11頭で`older_runs=0`。PACI recent_runsだけでほぼ全キャリアを覆う馬が多く、Analysisが無理に履歴を水増ししないことを確認した。

一方、exact `same_distance` (2200m) は16頭中13頭が0走。3歳戦では完全一致距離だけを単独の適性材料として扱うと情報が疎になりやすい。

### 2. Standard dirt conditions produce strong sample sizes

マーチSではsame_distance=0が0/16、種牡馬stats<20が1/16、騎手stats<20が2/16。中山ダ1800mのような施行数の多い条件では現在のexact-distance Stats Mart粒度が十分機能する。

### 3. Long-distance exact stats are extremely sparse

万葉S（京都芝3000m）ではsame_distance中央値1走。種牡馬・騎手statsは全9頭でstarts<20、各3頭はstarts=0。frame trend自体も枠ごと11〜17 starts程度。

率をstartsなしで扱ってはいけない、という現在の契約は必須。将来はexact distanceに加えてdistance band / fallback aggregateを検討する価値が高い。

### 4. Foreign-horse coverage remains honestly missing

ジャパンCのカランダガンはJRDB国内Analysis履歴を持たず:

- `recent_runs = 0`
- `older_runs = 0`
- `historical_profile.career.starts = 0`
- sire stats starts = 0
- jockey stats starts = 1

一方、PACI target-race情報としてIDM/total_index/適性/調教等の事前項目は存在する。海外履歴を推測補完せず欠損のまま表現できている。

海外遠征を含む国内馬でもPACI detailed recent_runsが国内履歴より短くなるケースがあり得るため、`recent_runs`件数を「career全履歴」と解釈しない。

### 5. 8-run cap remains natural

- 古馬一般: recent5 + older3 が多い
- 3歳: 既存キャリア分だけ1〜8走
- 海外馬: 0走も許容

固定8件を埋めるのではなく、`min(available_history, 8)`として自然に欠損を保つ現在方針を維持する。

## Design questions surfaced by this PoC

実装変更を即決せず、予想仕様設計前に次を検討する。

1. `same_distance` 完全一致だけでなく距離帯集計を追加するか。
2. sire/jockey/frameのexact course-distance statsが低母数のとき、距離帯・会場surface・surface全体等へfallbackするか。
3. statsの低母数を`starts`だけでGPTに判断させるか、machine-readable `sample_size` / `reliability` を付けるか。
4. 海外馬・海外遠征歴について、JRDBで提供される範囲をそのまま欠損として受け入れるか、別ソース層を将来追加するか。

現時点では予想ロジックをconverter/routerへ入れず、RaceNoteは中立な観測データとprovenance/sample sizeを渡す方針を維持する。
