# ForwardTrial 0917以降 Control / Shadow 並行運用

Date: 2026-09-16
Status: **Current daily prediction operation from 2026-09-17**

## 1. 基本方針

2026-09-17以降の新規・結果未参照日では、選定した対象会場の全Rについて、**同一のFreeze済みBOAT RACE公式出走表CSV**から次の2系統を結果参照前に並行生成する。

- Control: `ForwardTrial_Ver0.1`
- Shadow: `ForwardTrial_Ver0.2-alpha1`

ControlとShadowは別version・別資産としてFreezeし、相互に上書きしない。
過去にFreeze済みのControl資産・結果・台帳実績も遡及変更しない。

## 2. Control

Controlは従来どおり `ForwardTrial_Ver0.1`。

Canonical implementation:

- `boat-racing/src/forward_trial_predict.py`
- `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
- `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

結果参照前に標準3CSVをFreezeする。

1. 事前予想CSV
2. 予想根拠明細CSV
3. 2連単1点販売選別CSV

ControlのA/B/C、軸、相手、InnerPick、販売Score、掲載区分はControl仕様に従う。

## 3. Shadow

Shadow version:

`ForwardTrial_Ver0.2-alpha1`

Canonical implementation:

- `boat-racing/src/forward_trial_v02_alpha_shadow.py`
- `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Shadow運用_20260916.md`
- `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Design_20260916.md`

### 3.1 据え置き

- 1着軸 / A-B-C判定: Ver0.1据え置き
- InnerPick: 2着本線 / 2着押さえのうち艇番が小さい方を選択
- 2連単1点対象条件: 正式A・1号艇軸

### 3.2 OpponentScore OS-alpha1

| 項目 | 重み |
|---|---:|
| 全国勝率 | 0.35 |
| 当地勝率 | 0.15 |
| 平均ST | 0.05 |
| モーター2連率 | 0.15 |
| 今節平均着順 | 0.15 |
| 級別 | 0.15 |

正規化・欠損処理はControl実装を継承する。

### 3.3 Q0 Pair-risk Gate

以下をすべて満たす2連単1点対象はQ0としてnote非掲載。

```text
2着候補分離度 < 0.08
AND 軸警戒 = なし
AND 比較支持項目数 != 4
```

Q0でも対象判定・買い目・scoreは検証用に保持する。

### 3.4 Shadow販売Score

各1点、最大4点。

1. 1号艇全国勝率 - 最強非1号艇全国勝率 >= 0.50
2. 2着候補分離度 >= 0.08
3. InnerPick相手が2〜4号艇
4. InnerPick相手 = 2着本線

順位は販売Score降順、同点は2着候補分離度降順、その後は入力会場順、R昇順。

### 3.5 商品量

Q0通過候補から日次商品を構成する。

| Q0通過候補数 | 有料 | 無料 | 合計掲載 |
|---:|---:|---:|---:|
| 0〜5 | 0 | 0 | 通常販売見送り |
| 6 | 4 | 2 | 6 |
| 7 | 5 | 2 | 7 |
| 8 | 5 | 3 | 8 |
| 9 | 6 | 3 | 9 |
| 10以上 | 7 | 3 | 10 |

`CSVのみ` はShadowでは使用しない。掲載外は `非掲載`。

## 4. 情報遮断

Control / Shadowとも、Freeze完了前に以下を参照しない。

- 結果 / 着順
- 払戻
- オッズ
- 展示 / 直前情報
- 当該日結果ファイル
- 結果を示唆する外部情報

両系統とも同じ公式出走表CSVを入力にし、入力file ID / SHAを監査可能にする。

## 5. Freeze順序

1. 対象6場を確定
2. 公式出走表CSVをFreeze
3. Control 3CSVを生成・Freeze
4. 同一公式出走表からShadow資産を生成・Freeze
5. Control / Shadowそれぞれのversion、確定日時、source commit、input SHAを記録
6. 締切真正性を各レースで監査
7. その後にのみ結果参照へ進む

ControlとShadowは別ファイル名・別versionを持ち、片方の生成物をもう片方へコピー・上書きしない。

## 6. 締切真正性

各レースについて、Control prediction freeze / Control sales freeze / Shadow freezeを公式締切時刻と比較する。

締切時刻到達済み・締切後にFreezeされた系統は、そのレースを `CONTAMINATED` としてgenuine forward集計から除外する。

有料 / 無料掲載についても締切済みレースを載せない。

## 7. 0917開始境界

2026-09-17の選定6場72Rを最初のgenuine parallel Control / Shadow対象とする。

0916以前のv0.2-alpha1 dry replay / research / Active昇格用実装試行は、0917以降のShadow genuine forward成績へ算入しない。

## 8. 先行Active化の扱い

`ForwardTrial_Ver0.2-alpha1_Active運用_20260916.md` および `forward_trial_v02_alpha_predict.py` は、2026-09-16中に作成された昇格検討履歴として保持するが、**0917以降の日次標準経路には使用しない**。

現行標準はControl `forward_trial_predict.py` + Shadow `forward_trial_v02_alpha_shadow.py` の並行Freezeである。
