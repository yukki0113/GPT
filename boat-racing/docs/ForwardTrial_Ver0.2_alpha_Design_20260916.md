# ForwardTrial Ver0.2-α 研究設計メモ

Date: 2026-09-16  
Status: **Research / retrospective diagnostic only**  
Control remains: `ForwardTrial_Ver0.1`

---

## 1. Purpose

`ForwardTrial_Ver0.1` の 2026-09-01〜2026-09-15 genuine 2連単1点対象 166R を用いて、以下を分離して再評価した。

1. 最終1点化（2着本線/押さえのうち内側艇を選ぶ規則）
2. Pair候補2艇を作る `OpponentScore`
3. 販売Gate
4. 日次商品量と有料/無料の配分

本メモの数値は retrospective 開発分析であり、forward 成績として扱わない。Ver0.2へ昇格させる場合は結果参照前に仕様・実装・Freeze asset を確定すること。

---

## 2. InnerPickは変更しない

166Rの反実仮想比較では、現行の「2着本線/押さえのうち艇番が小さい方を1点選択」が最も良かった。

- 現行 InnerPick: 51的中、ROI 約90.4%
- 常に2着本線: 39的中、ROI 約83.2%
- 常に2着押さえ: 29的中、ROI 約64.8%

したがって、Ver0.2-αでは最終1点化規則を変更対象にしない。

---

## 3. 現行 OpponentScore

`ForwardTrial_Ver0.1` の相手総合スコアは以下。

| 項目 | 現行重み |
|---|---:|
| 全国勝率 | 0.35 |
| 当地勝率 | 0.20 |
| 平均ST | 0.15 |
| モーター2連率 | 0.10 |
| 今節平均着順 | 0.15 |
| 級別 | 0.05 |

各項目はレース6艇内で0〜1 min-max正規化し、ST・今節平均着順は小さいほど良い方向へ反転する。欠損は0.0、全艇同値は0.5。A/Bで軸艇を除いた相手5艇をScore降順に並べ、1位=2着本線、2位=2着押さえ、3位=追加3着候補とする。

canonical implementation: `boat-racing/src/forward_trial_predict.py`

---

## 4. Freeze成果物とcanonical式の履歴差分

genuine 166Rについて、公式出走表 / Freeze済み予想根拠明細の値から current canonical `OpponentScore` を再計算したところ、160Rは保存済み `2着本線/2着押さえ` と一致したが、以下6Rは一致しなかった。

| 日付 | 会場R | Freeze本線/押さえ | canonical式 再計算上位 |
|---|---|---|---|
| 2026-09-02 | 大村8R | 2 / 6 | 2 / 5 / 6 |
| 2026-09-03 | 若松9R | 2 / 4 | 4 / 2 / 3 |
| 2026-09-05 | 宮島12R | 4 / 6 | 4 / 3 / 6 |
| 2026-09-05 | 戸田7R | 4 / 6 | 4 / 3 / 6 |
| 2026-09-06 | 平和島7R | 6 / 2 | 4 / 2 / 6 |
| 2026-09-08 | 児島5R | 6 / 3 | 6 / 5 / 3 |

9/9以降の対象では同種の不一致は確認されなかった。

この6RはControl実績を書き換えない。既存Freezeを正本として残し、Ver0.2研究では以下の2系統を区別する。

- historical Control fact: 保存済み本線/押さえ
- formula-replay research: canonical式から再計算した相手順位

仕様・実装・Freeze成果物の整合監査を今後の日次non-regression guardへ追加する候補とする。

---

## 5. OpponentScore重み探索

0.05刻み・合計1.00の重みを全探索した。ただし、ST=0や当地=0など極端な retrospective 最適解は過学習候補として採用しない。

primary評価は、上記6Rを除く canonical式整合160Rのうち、実1着=1号艇・非返還の111Rにおける「実2着がPair上位2艇に入るか」とした。

現行式:
- Pair cover = 62 / 111

変更幅を抑えた有力候補:

### Candidate OS-α1

| 項目 | 現行 | α1 |
|---|---:|---:|
| 全国勝率 | 0.35 | 0.35 |
| 当地勝率 | 0.20 | 0.15 |
| 平均ST | 0.15 | 0.05 |
| モーター2連率 | 0.10 | 0.15 |
| 今節平均着順 | 0.15 | 0.15 |
| 級別 | 0.05 | 0.15 |

変更:
- 当地 -0.05
- ST -0.10
- モーター +0.05
- 級別 +0.10
- 全国・今節は据え置き

α1結果:
- canonical式整合111R: Pair cover 67 / 111（現行62）
- 全166R formula-replay: head success対象116R中 Pair cover 72R
- 前半（〜9/8）: 32→33
- 後半（9/9〜）: 30→34
- 日別Pair coverは整合サンプル上で現行より悪化する日なし

より大きく重みを変える候補ではさらにPair coverが増えるが、retrospective最適化色が強いため第一候補にはしない。

---

## 6. Ver0.2-α Pair-risk Gate

現行分析から得られた危険群:

```text
2着候補分離度 < 0.08
AND 軸警戒 = なし
AND 比較支持項目数 != 4
```

旧OpponentScoreで31R。α1で分離度を再計算すると30Rとなり、旧31Rとの共通は25R。

α1再計算時:
- Q0: 30R
- 非返還30R
- head success 21R
- Pair cover 7R
- 1点的中 6R
- 参考ROI 約52.0%

Q0以外:
- 136R（非返還132R）
- head success 95R
- Pair cover 65R
- 1点的中 47R
- 参考ROI 約106.8%

したがってQ0は、OpponentScore変更後も一定の分離能力を維持した。

注意: 返還レースの反実仮想買い目について、候補艇が返還対象かはFT2結果明細だけでは完全に確定できないため、上記ROI比較は非返還レース中心の参考値とする。

---

## 7. Ver0.2-α 販売Score候補

単純加点を4項目へ縮小する。

| 条件 | 加点 |
|---|---:|
| 1号艇全国勝率 - 最強非1号艇全国勝率 >= 0.50 | +1 |
| 新OpponentScoreでの2着候補分離度 >= 0.08 | +1 |
| InnerPick相手が2〜4号艇 | +1 |
| InnerPick相手 = 2着本線 | +1 |

削除候補:
- 軸警戒なし +2
- 比較支持5 +2 / 4 +1
- 分離度0.15以上 +2

絶対Score閾値で有料/無料を固定せず、日次順位用途とする。

α1でのScore別参考値:
- Score4: 17R, ROI 約122.9%
- Score3: 64R, ROI 約98.3%
- Score2: 63R, ROI 約80.2%
- Score1: 21R, ROI 約122.4%
- Score0: 1R

Score1の跳ねが残るため、「Score>=3なら有料」のような固定閾値は採用しない。

---

## 8. 商品量ルール候補

Q0を先に非掲載化し、残候補を新販売Score降順、同点は分離度降順、その後は固定決定論的順序で並べる。

日次掲載上限10R。

| 掲載可能数 | 有料 | 無料 |
|---:|---:|---:|
| 6 | 4 | 2 |
| 7 | 5 | 2 |
| 8 | 5 | 3 |
| 9 | 6 | 3 |
| 10以上 | 7 | 3 |

5R以下は通常販売見送り候補。

α1 + Q0での過去14日再演:
- 全日で掲載6〜10Rに収まる
- 9/9のみ6R
- その他は7〜10R

再演集計（非返還中心の参考値）:
- 掲載: 126R / 参考ROI 約107.4%
- 有料: 86R / 約107.1%
- 無料: 40R / 約107.9%
- 非掲載: 40R / 約64.0%

これは retrospective product replay であり、販売実績として扱わない。

---

## 9. Ver0.2-α 第一候補

現時点の第一候補は以下。

1. 1着軸/A-B-C判定: Controlから変更しない
2. InnerPick: 本線/押さえの内側艇を選択、変更しない
3. OpponentScore: OS-α1へ変更候補
4. Q0 Pair-risk Gate: `分離度<0.08 AND 軸警戒なし AND 支持数!=4`
5. 販売Score: 4項目へ簡略化
6. CSV-only区分: 廃止候補。掲載外は非掲載として保持
7. 日次掲載: 6〜10Rを通常商品レンジ、上限10R
8. Controlは変更せず、次回未実施日からShadow/Ver0.2 trialとしてFreezeして検証する

---

## 10. Promotion前の必須条件

Ver0.2へ昇格する前に以下を満たすこと。

- 仕様書と実装を同一commitで固定
- frozen公式出走表から本線/押さえが100%再生成一致するnon-regression testを追加
- OpponentScore / 分離度 / Q0 / SalesScoreを結果参照前にFreeze
- Control `ForwardTrial_Ver0.1` を上書きしない
- retrospective 166Rは開発データと明記
- forward期間で、Pair cover / InnerPick / 掲載量 / paid/free / ROI / grade / venue / day を別々に監査
- 少数日の好成績だけで昇格しない

---

## 11. Current decision

**Control変更なし。**

Ver0.2-α研究では `OS-α1 + Q0 + 4項目SalesScore + 日次6〜10R商品量` を第一候補として、次の genuinely forward なFreezeへ進める。
