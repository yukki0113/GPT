# RaceNote 過去時点/as-of監査 — 2025-08-24 新潟2歳S

対象: 2025-08-24 新潟11R 新潟2歳ステークス（G3、芝1600m、10頭）

## 目的

札幌記念PoCで定めた「過去レース再現時は対象日以降の情報を混ぜない」という約束を、履歴の薄い2歳重賞で再確認する。

## Raw原本監査

Google Drive `/GPT/JRDB/00_raw/` の2025年次ZIPを使用。

- BAC_2025.zip
- KYI_2025.zip
- CHA_2025.zip
- CYB_2025.zip
- SED_2025.zip
- SKB_2025.zip

`KYI250824.txt` の新潟11R 10頭を確認した結果、前走1〜5競走成績キーは合計18件。

- SED一致: 18 / 18
- SKB一致: 18 / 18
- Analysis Liteで `race_date < 2025-08-24` とした各馬履歴のresult key列と、KYIの前走キー列は10頭すべて順序まで完全一致

各馬の事前出走歴は1〜4走で、全頭5走以内に収まる。
したがって現行RaceNoteのPACI `recent_runs` 最大5走で全キャリアを覆えるケースであり、Analysis由来 `older_runs` は0件が正常。

## 各馬の事前履歴数

| 馬番 | 馬名 | 8/24以前の出走数 |
|---:|---|---:|
| 1 | メーゼ | 1 |
| 2 | リネンタイリン | 2 |
| 3 | タイセイボーグ | 2 |
| 4 | フェスティバルヒル | 1 |
| 5 | ヒルデグリム | 1 |
| 6 | フォトンゲイザー | 4 |
| 7 | サノノグレーター | 2 |
| 8 | サンアントワーヌ | 1 |
| 9 | リアライズシリウス | 1 |
| 10 | タイセイフレッサ | 3 |

全10頭で `prev_result_key_1` / `prev_race_key_1` も存在。

## Analysis historical_profile

対象日は必ず `race_date < 2025-08-24` として集計する。

初期PoCで採用する集約:

- career
- same_surface
- same_distance
- same_venue

2歳戦では1〜4走しかないため、率は高低だけで評価せず `starts` を必須で併記する。

## Stats Mart as-ofルール

5暦年窓は `2021-2025YTD`。

- 2021〜2024: Stats Mart年次行を合算
- 2025: Analysis Liteを `race_date < 2025-08-24` で都度集計
- 馬場状態: 事前未確定のため all_conditions

完成済み2025 Martをそのまま使わない。

### 漏洩確認

2021〜2025完成Martをそのまま使用した値とas-of値を比較したところ:

- 10頭 × sire/jockey = 20統計すべてで値が変化
- 枠1〜8も8枠すべてで値が変化

したがって、過去レースPoCで対象年の完成Martを直接使うことは未来情報混入となることを実データで再確認した。

例: 新潟芝1600m・5年窓の1枠

- as-of 2025-08-23: 195戦 10勝 top3=36、勝率5.1%、複勝圏率18.5%
- 完成2025 Mart: 206戦 11勝 top3=38、勝率5.3%、複勝圏率18.4%

## 結論

新潟2歳Sは札幌記念とは対照的な検証ケースとしてPASS。

1. PACIの最大5走で全馬の当時の全履歴を覆える。
2. Analysis `older_runs` は無理に追加せず0件が正しい。
3. Analysis `historical_profile` は1〜4走という小標本をそのまま `starts` 付きで表現する。
4. sire/jockey/frame傾向は個体履歴が薄い2歳戦で補助情報になりうるが、必ず母数を併記する。
5. 過去時点再現では、対象年のStats Mart完成値を使わず、対象年だけAnalysisから対象日前までを再集計するas-of方式を必須とする。

この結果により、RaceNote履歴拡張の初期方針は以下で整合する。

- PACI recent_runs: 最大5走・詳細
- Analysis older_runs: PACIの5走を超える履歴だけ、最大3走
- Analysis historical_profile: career / same_surface / same_distance / same_venue
- Stats: 5年窓、sire / jockey / frame、startsを必須、all_conditions
