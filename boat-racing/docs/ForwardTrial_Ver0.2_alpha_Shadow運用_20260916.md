# ForwardTrial Ver0.2-alpha1 Shadow運用

Date: 2026-09-16  
Status: **Implementation-ready / not yet genuine forward**

Controlは引き続き `ForwardTrial_Ver0.1`。本ShadowはControlを上書きしない。

## 1. 対象実装

- Control: `boat-racing/src/forward_trial_predict.py`
- Shadow: `boat-racing/src/forward_trial_v02_alpha_shadow.py`
- Tests: `boat-racing/tests/test_forward_trial_v02_alpha_shadow.py`
- CI: `.github/workflows/boatrace_v02_alpha_tests.yml`
- Research basis: `boat-racing/docs/ForwardTrial_Ver0.2_alpha_Design_20260916.md`

Shadow version:

```text
ForwardTrial_Ver0.2-alpha1
```

## 2. 固定変更点

Controlから変更するのはOpponentScore以降のみ。

### OpponentScore OS-alpha1

| 項目 | 重み |
|---|---:|
| 全国勝率 | 0.35 |
| 当地勝率 | 0.15 |
| 平均ST | 0.05 |
| モーター2連率 | 0.15 |
| 今節平均着順 | 0.15 |
| 級別 | 0.15 |

A/B/C判定、1着軸決定、InnerPick（本線/押さえの内側艇）はControlと同じ実装を使う。

### Q0 Pair-risk Gate

```text
2着候補分離度 < 0.08
AND 軸警戒 = なし
AND 比較支持項目数 != 4
```

Q0は内部記録するがnote非掲載。

### Shadow販売Score

各1点、最大4点。

1. 全国勝率差 >= 0.50
2. 2着候補分離度 >= 0.08
3. InnerPick相手が2〜4号艇
4. InnerPick相手 = 2着本線

同点は分離度降順、その後は入力会場順→R順で決定論的に並べる。

### 商品量

| Q0通過候補数 | 有料 | 無料 | 扱い |
|---:|---:|---:|---|
| 0〜5 | 0 | 0 | 通常販売見送り |
| 6 | 4 | 2 | 掲載6R |
| 7 | 5 | 2 | 掲載7R |
| 8 | 5 | 3 | 掲載8R |
| 9 | 6 | 3 | 掲載9R |
| 10以上 | 7 | 3 | 掲載上限10R |

`CSVのみ` はShadowでは使用しない。掲載外は `非掲載`。

## 3. 情報遮断

Shadow生成はControlと同じfreeze済み公式出走表だけを入力にする。

Shadow確定前に以下を参照しない。

- 結果・着順
- 払戻
- オッズ
- 展示/直前情報
- 当該日結果ファイル
- 結果を示唆する外部情報

`forward_trial_v02_alpha_shadow.py` はControlの `validate_input` を再利用し、結果・払戻・オッズ等を含む入力をfail closedする。

## 4. 日次Freeze手順

真正forwardとして数える最初の日から、結果参照前に以下を実行・保存する。

1. 会場選別を確定
2. 公式出走表CSVをFreeze
3. Control `ForwardTrial_Ver0.1` の3CSVを通常どおりFreeze
4. 同じ公式出走表をShadow generatorへ入力
5. Shadow CSVを別version・別ファイルとしてFreeze
6. Control / Shadowの確定日時とsource file IDを監査記録
7. その後にのみ結果取得へ進む

実行例:

```bash
python boat-racing/src/forward_trial_v02_alpha_shadow.py \
  --input <公式出走表.csv> \
  --output <YYYYMMDD_Shadow販売選別_ForwardTrial_Ver0.2-alpha1.csv> \
  --shadow-time '<YYYY-MM-DD HH:MM:SS+09:00>'
```

## 5. Shadow CSV

最低限以下を固定する。

- 日付 / 会場 / R
- ShadowVer / ControlVer
- 正式判定 / 1着軸
- α1の2着本線 / 2着押さえ / 追加3着候補
- α1分離度
- 2連単1点対象 / 2連単1点
- 軸警戒 / 比較支持項目数 / 全国勝率差
- Q0_PairRisk
- Shadow販売スコア / Shadow順位
- 掲載区分（有料/無料/非掲載/販売見送り/対象外）
- Shadow確定日時
- 結果参照状態=未参照

## 6. Genuine判定

Shadow自体も締切監査対象とする。

各レースについて、Control prediction freeze / Control sales freeze / Shadow freezeのうち最も遅い時刻が公式締切より前であること。

締切後ならそのレースのShadow評価も `CONTAMINATED` とし、genuine forward集計から除外する。

過去日へ遡ってShadow genuineを付与しない。

## 7. 結果後の比較

ControlとShadowを別々に集計する。最低限:

1. 対象R数
2. 1号艇頭成功率
3. Pair cover率
4. InnerPick成功率
5. 1点的中率 / ROI
6. Q0 / 非Q0
7. 有料 / 無料 / 非掲載
8. 日次掲載本数
9. grade / venue / 開催日目
10. Controlから相手Pairが変わったRの勝敗

Shadowで相手Pairが変わっていないレースと変わったレースを分離し、OpponentScore変更そのものの寄与を測る。

## 8. Promotion禁止事項

- retrospective 9/1〜9/15をShadow forward成績へ算入しない
- 1〜数日のROIだけでVer0.2へ昇格しない
- Control実績をVer0.2ルールで遡及置換しない
- 商品本数を合わせるためQ0を有料/無料へ昇格しない
- 5R以下の日に通常価格商品を自動生成しない

## 9. 実装監査状況

2026-09-16時点:

- Shadow module main反映済み
- Control既存test + Shadow test = 12 tests PASS
- CI run `35044389100` success
- 2026-09-15公式出走表のdry replay:
  - 2連単対象13R
  - Q0 3R
  - Q0通過10R
  - 有料7R / 無料3R
- 2026-09-15 三国1Rは実運用Controlでは締切後freezeでCONTAMINATED。上記dry replayはロジック再現でありgenuine Shadow成績ではない。

## 10. 次回開始条件

次回の結果未参照日について、会場選別・公式出走表Freeze後に本ShadowをControlと同時にFreezeした時点を `ForwardTrial_Ver0.2-alpha1` genuine forward開始点とする。

開始前にmain HEAD、CI成功、Shadow version、重み、Q0式、商品量表が本書と一致することを確認する。
