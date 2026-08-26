# RaceNote distance range policy decision - 2026-08-26

RaceNoteのAnalysis Lite / Stats Mart enrichmentで、完全一致距離だけでは若駒・長距離などで母数が疎になることが5レースPoCから確認された。

初期仕様として完全一致距離を維持しつつ、以下の重複距離レンジを補助情報として追加する。

```text
1000–1400
1400–1800
1800–2400
2500+
```

## 境界方針

- 1400mは1000–1400と1400–1800の両方に所属する。
- 1800mは1400–1800と1800–2400の両方に所属する。
- 2400mは1800–2400のみに所属する。
- 長距離レンジは2500mからとする。
- JSON上の正本は「短距離」「マイル」等のカテゴリ名ではなく `min_m` / `max_m` とする。
- `2500+` は `min_m=2500`, `max_m=null` で表現する。

## 適用対象

- horse `historical_profile.distance_ranges`
- `horses[].stats.sire.distance_ranges`
- `horses[].stats.jockey.distance_ranges`
- `race.race_trends.frame[*].distance_ranges`

完全一致統計 (`same_distance` および既存sire/jockey/frame summary) は削除・置換しない。

## as-of

距離レンジ集計も既存のas-of安全性をそのまま適用する。

- 対象年より前: Stats Mart
- 対象年: Analysis Liteの `race_date < target_date`
- target race当日およびそれ以降の結果は利用しない。
