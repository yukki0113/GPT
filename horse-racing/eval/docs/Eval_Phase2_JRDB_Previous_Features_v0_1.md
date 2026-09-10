# Eval Phase2 JRDB Previous-run Features v0.1

## 1. 目的

Eval Phase2研究で、今走の距離・芝ダ条件変化等を説明するため、KYIが明示する前走1競走成績キーを利用して前走条件をexact-linkで取得する。

対象実装:

```text
horse-racing/eval/src/build_phase2_jrdb_previous_features.py
```

## 2. 入力とas-of

現在レース:

```text
PACI BAC + KYI
```

前走:

```text
PACI ZED
```

ZEDはSEDと同一フォーマットだが、現在レースより前の既走結果としてPACIに収録された履歴情報である。現在レースのSEDは読まない。

```text
source_availability_class = PRE_RACE_HISTORY
```

## 3. 結合

KYI:

```text
previous[0].result_key
```

とZED:

```text
result_key
```

を完全一致で結ぶ。

馬名、日付近似、直近走推測等によるfallbackは行わない。

ステータス:

```text
RESOLVED
NO_PREVIOUS
LINK_NOT_RESOLVED
```

ZEDで解決した前走日が現在開催日以上の場合はas-of違反としてエラーにする。

## 4. 保持項目

現在条件:

```text
current_distance_m
current_surface_code
current_surface_label
current_race_class_code
```

前走条件:

```text
previous_race_date
previous_race_key
previous_distance_m
previous_surface_code
previous_surface_label
previous_track_condition_code
previous_track_condition_label
previous_race_class_code
```

派生:

```text
distance_change_m = 今走距離 - 前走距離
surface_transition = 前走芝ダ -> 今走芝ダ
surface_changed = 0/1
```

距離短縮は負、距離延長は正とする。

例:

```text
前走1800m -> 今走1600m = -200
前走ダート -> 今走芝 = ダート->芝
```

## 5. 馬場状態

`previous_track_condition_*` は前走ZEDの確定実馬場状態なので、前走履歴特徴量として利用可能。

一方、今走の確定実馬場状態は対象レース後SED由来であり、Forwardの事前特徴量には使用しない。過去Discoveryで実馬場との交互作用を見る場合は、結果時点データであることを明示して別レイヤーで扱う。

## 6. クラス変更

v0.1では以下だけを保持する。

```text
current_race_class_code
previous_race_class_code
```

これらを単純な文字列順・数値順で「昇級/降級」へ変換しない。

JRDB KYI固定長には別途 `降級フラグ` が存在するが、2026-09-11時点のCommon `jrdb_raw.Parser.kyi()` は当該フィールドを公開していない。

したがってEval側で固定長位置539を直接読まず、必要ならJRDB共通Parser側へフィールド追加を依頼する。

昇級判定についても、競走条件・条件グループ・格上挑戦等の意味規則を固定した後に別派生特徴量として実装する。

## 7. Discoveryでの初期用途

購入条件には直結させず、まず以下を調べる。

```text
Eval順位/差
× 市場人気/オッズ
× 距離増減
× 芝ダ変更
× 前走馬場
```

主眼は、Eval高評価馬が市場から相対的に嫌われる理由を、条件変更が説明するかどうかの確認である。

同一標本で見つけた有利な距離幅や芝ダ遷移を、そのままForward条件へ追加しない。
