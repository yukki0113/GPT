# JRDB Newspaper UI Layout v0.1

Status: DRAFT / MOBILE-FIRST UI CONTRACT

## 1. Purpose

JRDB PWA「自分用競馬新聞」のスマホ表示について、新聞らしい情報密度と横スクロール時の視認性を両立するためのUI契約を定義する。

本書はデータ生成Contractとは分離し、PWA表示側の列順・sticky policy・印群幅・過去走表示密度を扱う。

## 2. Core row order

1頭 = 1行を維持する。

論理列順は次を固定する。

```text
枠 -> 馬番 -> 馬名 -> 基本情報 -> 印群 -> 前走 -> 2走前 -> 3走前 -> ... -> Edge
```

意味上の上位契約は従来どおり:

```text
馬情報 -> 印群 -> 過去走 -> Edge
```

`枠 / 馬番 / 馬名 / 基本情報` はすべて馬情報に属する。

## 3. Sticky policy

### 3.1 Initial view

初期位置では次を自然に読む。

```text
枠 | 馬番 | 馬名 | 基本情報 | 印群 | ...
```

### 3.2 After horizontal scroll

横スクロール時に残すのは原則:

```text
馬番 | 馬名
```

のみとする。

- 枠はスクロールで消えてよい。
- 基本情報もスクロールで消える。
- 馬情報全体をstickyにしない。
- sticky領域は「いま何番の何という馬を見ているか」を識別できる最小限にする。

netkeiba新聞画面のように、横方向へ情報を追った際も馬番・馬名だけを左端へ残す挙動を参考にする。

## 4. Column width target

スマホ縦持ちのCSS viewportを概ね 375-430px と想定する。

初期PoC target:

| 列 | 幅目安 |
|---|---:|
| 枠 | 26-30px |
| 馬番 | 34-38px |
| 馬名 | 100-112px |
| 基本情報 | 118-135px |
| 印: 能力 | 34px |
| 印: 追切 | 30px |
| 印: JR印 | 32px |
| 印: Eval | 38px |
| 印: RN | 32px |
| 印: イルカ | 32px |
| 印: 指数 | 38px |
| 各過去走 | 145-155px |
| Edge | 160-180px |

sticky対象の馬番 + 馬名は合計およそ 134-150px を目標とする。

## 5. Mark group contract

### 5.1 Newspaper-style one-column-per-item

印群は1つの大きなセルへまとめず、競馬新聞の印欄のように **1項目 = 1細列** とする。

初期7列候補:

```text
能力 | 追切 | JR印 | Eval | RN | 🐬 | 指数
```

意味:

- 能力: JRDB能力 / IDM等の代表能力値
- 追切: JRDB調教指数・矢印・上昇度から新聞用に採用する短表示
- JR印: JRDB総合印等の代表印
- Eval: Eval指数
- RN: RaceNote prediction印
- 🐬: keibailuka掲載有無。掲載時は記号を押して短評を開く
- 指数: 将来の独自指数

未取得sourceは推測せず空欄とする。

### 5.2 Screen-fit requirement

印群は **馬番 + 馬名をsticky表示した状態で、7列すべてが同一スマホ画面内に収まることをUI目標** とする。

目安:

```text
sticky 馬番+馬名: 140px前後
印群7列: 236px前後
合計: 約376px
```

幅375px級端末ではborder/padding調整が必要なため、実装時は各印列のpaddingを極小化し、必要に応じて馬名幅を100px前後まで縮める。

「印群の途中までしか見えず、EvalとRaceNoteを同時比較できない」状態は避ける。

### 5.3 Header labels

ヘッダは狭い列に合わせ、次を許容する。

- 縦書き
- 2段改行
- 短縮表記

候補:

```text
能力
追切
JR
Eval
RN
🐬
指数
```

値は原則1行:

```text
86 | ↑ | ◎ | 78 | ○ | ○ | 70
```

数字は2-3桁、印は1文字を基本にする。

### 5.4 Mark-group navigation

印群全体を見やすくするため、横スクロールの「止まり位置」として印群開始位置を扱う。

実装候補:

- CSS `scroll-snap-type: x proximity`
- 印群先頭列に `scroll-snap-align: start`
- または小さい「印」ジャンプ操作

初期PoCでは過剰な自動snapを避け、まずsticky幅と列幅だけで1画面fitを確認する。

## 6. Basic-info column

馬名列には馬名だけを主表示する。

基本情報は隣の非sticky列へ分離する。

表示候補:

```text
セ7 58kg
横山琉人
父 エイシンフラッシュ
追込
```

詳細情報は馬名タップ等で別dialogへ回せる。

詳細候補:

- 調教師
- 母 / 母父
- 生産者
- 距離適性
- その他JRDB profile

## 7. Past-run columns

印群の右に過去走を置く。

```text
前走 | 2走前 | 3走前 | 4走前 | ...
```

初期表示は3走。

切替:

```text
3走 / 5走 / 8走
```

1-5走目 detailed は代表情報をセル内表示し、詳細dialogへ展開可能。
6-8走目 compact は `簡易` を明示する。

## 8. Edge column

Edgeは過去走群の末尾に配置する。

通常表示は `display_text` 中心。
複数Edge合致時は縦積みを許容する。
詳細押下でedge id / status / evidence等を確認できる余地を残す。

## 9. Row height target

新聞らしい一覧性を保つため、1頭の高さは過度に伸ばさない。

初期目標:

```text
100-125px / horse
```

ただし過去走セルの必要情報量を優先し、固定高にはしない。

馬名・基本情報側の余白で行高を増やさない。

## 10. Acceptance for next UI PoC

次のスマホ実機PoCでは少なくとも次を確認する。

1. 横スクロール後に馬番・馬名だけが残る。
2. 枠・基本情報は自然に左へ消える。
3. 印群7列が1画面内で同時に見える。
4. Eval / JR印 / RaceNote印を縦方向に比較しやすい。
5. 3走表示で前走列へ無理なく移動できる。
6. 16頭を縦スクロールしても馬の識別を失わない。
7. 1頭あたりの高さが新聞として許容範囲に収まる。

## 11. Deferred

- 枠色
- 印ごとの色分け
- フォントサイズ最終調整
- scroll snap強度
- landscape専用layout
- user-configurable visible mark columns

これらは基本layout確定後に調整する。
