# ForwardTrial Ver0.2-alpha1 Active運用

Date: 2026-09-16  
Status: **Active for new result-unseen daily predictions**

## 1. 適用開始

今後の新規日次予想は `ForwardTrial_Ver0.2-alpha1` を使用する。

過去に `ForwardTrial_Ver0.1` でFreeze済みの予想・販売選別・結果・台帳実績は遡及変更しない。
`ForwardTrial_Ver0.2_alpha_Design_20260916.md` と `ForwardTrial_Ver0.2_alpha_Shadow運用_20260916.md` は研究・昇格前履歴として保存する。

## 2. 正本実装

- Active daily predictor: `boat-racing/src/forward_trial_v02_alpha_predict.py`
- v0.1基礎判定実装: `boat-racing/src/forward_trial_predict.py`
- alpha1研究層実装: `boat-racing/src/forward_trial_v02_alpha_shadow.py`
- 締切時刻parser: `boat-racing/src/forward_trial_deadline_gate.py`
- Active tests: `boat-racing/tests/test_forward_trial_v02_alpha_predict.py`

日次予想ではChat内に別ロジックを作らず、latest `main` のActive predictorをC. Pure Deterministic Executionで使用する。

## 3. 継承する規則

以下は `ForwardTrial_Ver0.1` と同じ。

- 公式出走表だけを予想入力とする情報遮断
- A/B/C判定
- 1着軸決定
- 2連単1点対象条件: 正式A・1号艇軸
- InnerPick: 2着本線/2着押さえのうち艇番が小さい方を1点化
- 結果参照状態はFreeze時 `未参照`

結果・着順・払戻・オッズ・展示・直前情報・当該日結果ファイルをFreeze前に参照しない。

## 4. OS-alpha1

相手総合スコアは以下の重みを使用する。

| 項目 | 重み |
|---|---:|
| 全国勝率 | 0.35 |
| 当地勝率 | 0.15 |
| 平均ST | 0.05 |
| モーター2連率 | 0.15 |
| 今節平均着順 | 0.15 |
| 級別 | 0.15 |

正規化・欠損処理はv0.1を継承する。
A/Bで軸艇を除いた相手5艇をalpha1 Score降順、同点は艇番昇順に並べ、1位=2着本線、2位=2着押さえ、3位=追加3着候補とする。

## 5. Q0 Pair-risk Gate

2連単1点対象のうち、以下をすべて満たすレースはQ0としてnote非掲載にする。

```text
2着候補分離度 < 0.08
AND 軸警戒 = なし
AND 比較支持項目数 != 4
```

Q0でも2連単1点対象・買い目・Score等は検証用に保持し、予想自体を削除しない。

## 6. 販売Score

各条件1点、最大4点。

1. `全国勝率差 >= 0.50`
2. `2着候補分離度 >= 0.08`
3. InnerPick相手が2〜4号艇
4. InnerPick相手 = 2着本線

販売順位は、Q0非該当かつ締切前の候補だけを次の順で並べる。

1. 販売Score降順
2. 2着候補分離度降順
3. 入力会場順
4. R昇順

## 7. 締切時刻掲載ゲート

有料・無料には、`販売選別確定日時 < 公式締切時刻` のレースだけを掲載する。

- 締切時刻到達済み・締切後は `非掲載`
- 予想判定、2連単1点対象、買い目、販売Scoreは検証用に保持
- 締切済み候補を除外した後の候補数で商品量を決める
- 締切時刻欠損・解析不能時は有料/無料へ推測掲載しない

## 8. 商品量

Q0非該当・締切前候補数により以下を適用する。

| 掲載可能数 | 有料 | 無料 | 扱い |
|---:|---:|---:|---|
| 0〜5 | 0 | 0 | 通常販売見送り |
| 6 | 4 | 2 | 掲載6R |
| 7 | 5 | 2 | 掲載7R |
| 8 | 5 | 3 | 掲載8R |
| 9 | 6 | 3 | 掲載9R |
| 10以上 | 7 | 3 | 掲載上限10R |

`CSVのみ` はv0.2-alpha1では使用しない。掲載外は `非掲載`、候補5R以下の日は `販売見送り` とする。

## 9. 標準成果物

通常ユーザー向け成果物は従来どおり3CSVとする。

1. `YYYYMMDD_事前予想_<会場...>_ForwardTrial_Ver0.2-alpha1.csv` — 24列互換
2. `YYYYMMDD_予想根拠明細_<会場...>_ForwardTrial_Ver0.2-alpha1.csv` — 26列互換、全R×6艇
3. `YYYYMMDD_2連単1点販売選別_<会場...>_ForwardTrial_Ver0.2-alpha1.csv` — 21列互換

24列/26列の相手関連項目・フラグはOS-alpha1で計算したPairを保存する。
販売選別CSVは既存21列互換を維持し、Q0・締切済み・日次掲載上限外の理由は `選別理由` へ記録する。

v0.2-alpha1では旧 `内部販売評価` のS/A/A-を販売判断に使用しないため、Active predictorでは互換列として空欄を保持する。

manifestは監査・再現性補助であり、通常のユーザー向け3成果物には数えない。

## 10. genuine forward境界

`ForwardTrial_Ver0.2-alpha1` のgenuine forwardは、このActive運用決定後、結果未参照の公式出走表からActive predictorでFreezeした日から開始する。

- 2026-09-01〜2026-09-15のv0.1 Control実績はv0.2へ遡及変換しない
- 2026-09-15 dry replay等の研究値はv0.2 genuine成績に算入しない
- 結果参照後の再ランキング・買い目変更・掲載区分変更は禁止

## 11. 日次実行

```bash
python boat-racing/src/forward_trial_v02_alpha_predict.py \
  --input <YYYYMMDD_公式出走表_....csv> \
  --output-dir <out> \
  --prediction-time '<YYYY-MM-DD HH:MM:SS+09:00>' \
  --source-commit <latest-main-sha>
```

実行前にlatest main、本書、Active predictorのversionを確認する。
