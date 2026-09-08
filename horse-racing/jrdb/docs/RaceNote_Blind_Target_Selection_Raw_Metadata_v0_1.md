# RaceNote Blind Target Selection from JRDB Raw Metadata v0.1

## Purpose

Blind historical backtestの対象日・開催場・クラス・重賞を選ぶために、原則としてWeb検索を使わずJRDB Raw / RaceNote metadataを利用する。

## Authoritative source

対象日のレースメタデータはBACを第一候補とする。JRDB BAC固定長仕様には少なくとも次が含まれる。

- レースキー: 場コード / 年 / 回 / 日 / R
- 年月日: YYYYMMDD
- 発走時間
- 距離
- 芝ダ障害コード
- 右左 / 内外
- 種別
- 条件
- 記号
- 重量
- グレード
- レース名
- 頭数
- 開催区分

グレードコードはJRDB master definitionに従う。

- `1`: G1
- `2`: G2
- `3`: G3
- `4`: 重賞
- `5`: 特別
- `6`: L（リステッド）

条件コードもJRDB master definitionから1勝 / 2勝 / 3勝 / 新馬 / 未勝利 / OP等を解決できる。

## Selection rule

Blind backtestの候補日選定では:

1. JRDB BACまたはBAC由来のRaceNote `race` metadataを読む。
2. 日付・開催場・レース数・class/gradeを確認する。
3. G1等を含めたい場合もgrade code / RaceNote gradeから判定する。
4. 対象結果・HJC・SED target result・Web検索結果はprediction freeze前に参照しない。
5. 候補確認のためだけにJRA公式、競馬情報サイト、検索エンジンへ行かない。

RaceNote v1.0ではBAC由来メタデータが `race.date / venue / race_no / race_name / class / grade / surface / distance_m` 等として利用できるため、既にRaceNote artifactを取得済みならRawを再読込せずこのmetadataを使ってよい。

## Rationale

Rawファイルを保持する目的には、履歴再構成だけでなく、外部Webへ依存せず開催・条件・gradeを再現可能にすることも含まれる。Blind testではWeb検索により偶発的にtarget resultを露出させるリスクがあるため、内部Raw metadataを優先する。
