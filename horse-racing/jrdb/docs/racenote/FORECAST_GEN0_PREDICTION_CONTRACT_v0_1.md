# RaceNote Forecast Gen0 Prediction Contract v0.1

Status: CURRENT
Last reviewed: 2026-09-13

## 1. Purpose

この文書は、RaceNote Forecast Gen0においてGPTが1Rをどう予想するかの**予想者契約**を定義する。

目的は固定数式を再実装することではない。

RaceNoteに含まれる開催前情報を材料として、GPT自身がレースごとに重要なファクターを判断し、全馬を相対比較して予想する。

## 2. Prediction principle

```text
RaceNote evidence
  -> race-specific interpretation
  -> horse-to-horse comparison
  -> prediction
```

次のような固定ルールを置かない。

- F01を常に30%、F03を常に20%とする固定weight
- 単一index最大馬を自動的に◎へする規則
- 旧v1.1-PのTop5 / Good差 / Edge polarity gate
- 人気順をそのまま印順へする規則

GPTはレースによって重視する材料を変えてよい。

## 3. Allowed factor set

初期factor set `FSET-Gen0.1`:

1. `F01 基礎能力`
2. `F02 条件適性`
3. `F03 展開・位置取り`
4. `F04 調教・状態`
5. `F05 近走内容`
6. `F06 長期履歴・条件実績`
7. `F07 騎手・厩舎`
8. `F08 血統`
9. `F09 枠・条件統計`
10. `F10 事前市場情報`

factor setは「全部を同じ強さで使え」という意味ではない。

そのレースでは有効性が低いと判断したfactorを軽視・不使用としてよい。

## 4. Reading sequence

予想時は以下を順に確認するが、これは採点順ではない。

### 4.1 Race context

最初にレース条件を把握する。

- 芝 / ダート
- 距離
- コース形態
- class / grade
- 頭数
- 斤量条件
- 馬場関連情報
- race trends

### 4.2 Field structure

全馬の脚質・能力分布・想定位置を見て、そのレース固有の構造を作る。

例:

- 明確な逃げ候補が1頭だけ
- 先行馬が多く差し向きの可能性
- 上位能力馬同士に位置取り差がある
- 能力差が大きく展開逆転を期待しにくい

### 4.3 All-runner reading

全出走馬を読む。

最初からTop5だけに絞らない。

各馬について少なくとも:

- 強み
- リスク
- 今回条件で効きそうな根拠
- conflicting evidence
- 情報不足

を確認する。

### 4.4 Relative comparison

各馬を独立採点しただけで終わらず、近い評価の馬を直接比較する。

特に:

- どちらが今回の勝ち筋を持つか
- どちらの弱点が今回表面化しやすいか
- 能力差を展開・状態・適性が覆せる程度か

を考える。

### 4.5 Vulnerability check

有力馬について「負けるなら何が原因か」を考える。

穴馬については「何が起きれば能力差を超えられるか」を考える。

根拠のない逆張りはしない。

### 4.6 Final prediction

最後に相対順位と印を決める。

最低限:

- ◎ 1頭
- ○ 最大1頭
- ▲ 最大1頭
- △ 任意
- 全馬のGPT順位
- confidence A/B/C

を記録する。

confidenceは的中確率ではなく、入力coverageと根拠の整合性に対する予想時点の確信度である。

## 5. Factor usage recording

予想結果とは別に、何を重視したかを記録する。

### importance

- `HIGH`
- `MEDIUM`
- `LOW`
- `NOT_USED`

### role

- `PRIMARY`: 結論へ強く影響
- `SUPPORT`: 結論を補強
- `RISK`: 評価を下げる / 不確実性を増す
- `DEEMPHASIZED`: 材料はあるが今回重く見ない

### direction

- `POSITIVE`
- `NEGATIVE`
- `MIXED`
- `NEUTRAL`

これらを点数へ変換しない。

研究用の観測ラベルである。

## 6. Evidence discipline

具体的な根拠はRaceNote内のevidenceへ紐づける。

存在しない事実を補完しない。

以下を守る。

- nullを平均値へ勝手に補完しない
- 小母数100%を絶対視しない
- 海外履歴等のscope外情報を推測しない
- commentがないことをnegative signalとしない
- conflicting evidenceを隠さない
- JRDB derived indexとそのcomponentを二重投票させない

## 7. Market information

`F10`はRaceNoteに開催前情報として含まれるJRDB base odds / rank等のみを対象とする。

- final oddsではない
- final popularityではない
- live oddsを暗黙取得しない

市場評価は使ってもよいが、「人気だから強い」「穴だから買う」だけで印を決めない。

## 8. EdgeDB

Gen0 core factor setにEdgeDBを自動決定ruleとして含めない。

別途Edge evidenceを併用する実験を行う場合はsourceを明示し、旧v1.1-Pのpolarity gateを復活させない。

## 9. Output content

保存対象は**結論を監査するための短いreason summary / evidence summary**である。

private chain-of-thoughtや逐語的な内部推論過程を台帳へ保存する必要はない。

保存する内容:

- race shape summary
- important condition factors
- 馬ごとのstrength / risk
- evidence conflict
- relative comparison
- factor usage labels
- ◎理由
- uncertainty summary

## 10. Pre-result self-audit

Freeze前に次を確認する。

- 全馬を見たか
- 単一indexの順位を書き写していないか
- レース構造を考えたか
- 能力と展開を別要素として扱ったか
- 調教だけで能力評価を覆していないか
- 人気だけで決めていないか
- 小母数を過大評価していないか
- contradictory evidenceを残したか
- ◎の負け筋を確認したか
- target result / final odds / target date以降の情報を見ていないか

修正した場合、Freezeするのは修正後の最終予想だけとする。

## 11. Forbidden information

予想Freeze前に参照禁止:

- target race finish
- target race final odds
- target race final popularity
- target race payout
- target date以降のhorse history
- target resultを含む記事・検索結果

過去予想ではweb検索で対象レースを調べない。

## 12. Evaluation

結果取得後は予想そのものを書き換えず、別recordで検証する。

特に:

- 何を読み違えたか
- 何を過大評価したか
- 何を過小評価したか
- どのfactorが有効だったか
- evidence自体が弱かったのか、GPTの解釈が悪かったのか

を区別する。

改善は原則generation約50R単位で行う。

## 13. Initial generation

- generation: `Gen0-G000`
- forecast version: `RaceNote-Forecast-Gen0.1`
- factor set: `FSET-Gen0.1`
- initial mode: `BLINDED_HISTORICAL`
- target: 50R

Gen0-G000の第一目的は、高い成績を宣言することではなく、GPT予想・Freeze・結果検証・factor learningの一連のサイクルを成立させることである。
