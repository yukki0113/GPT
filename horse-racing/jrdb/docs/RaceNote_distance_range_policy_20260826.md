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

## 実データ再検証

### 2026-05-09 京都11R 京都新聞杯 2200m

対象レンジ: `1800–2400`

馬自身の履歴:

- exact 2200m: starts中央値 0、0走 13/16頭
- range 1800–2400m: starts中央値 3、0走 0/16頭

種牡馬の京都芝条件5年窓:

- exact 2200m: starts中央値 4.5、20走未満 11/16頭、0走 6/16頭
- range 1800–2400m: starts中央値 58、20走未満 6/16頭、0走 0/16頭

騎手の京都芝条件5年窓:

- exact 2200m: starts中央値 20.5、20走未満 7/16頭、0走 2/16頭
- range 1800–2400m: starts中央値 143、20走未満 2/16頭、0走 1/16頭

完全一致距離が疎な3歳2200m戦では距離レンジが明確に補助情報として機能した。

### 2026-01-05 京都11R 万葉S 3000m

対象レンジ: `2500+`

馬自身の履歴:

- exact 3000m: starts中央値 1、0走 3/9頭
- range 2500+: starts中央値 5、0走 0/9頭

種牡馬の京都芝条件5年窓:

- exact 3000m: starts中央値 3、20走未満 9/9頭、0走 3/9頭
- range 2500+: starts中央値 6、20走未満 9/9頭、0走 3/9頭

騎手の京都芝条件5年窓:

- exact 3000m: starts中央値 1、20走未満 9/9頭、0走 3/9頭
- range 2500+: starts中央値 1、20走未満 9/9頭、0走 3/9頭

長距離ではレンジ化しても母数不足が残る。これは距離レンジ仕様の失敗ではなく、京都芝2500m以上という条件自体の希少性を正しく反映している。

## 判定

- exact-distanceは保持する。
- distance rangeは置換ではなく補助情報として併記する。
- 3歳・非定番距離では特に有効。
- 長距離ではrangeを加えても小サンプルが残るため、別論点としてsample sizeの明示方法を検討する。
