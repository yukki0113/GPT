# Integration Policy

## Principle

このProjectは3人を同じ予想方法へ揃えるためのものではない。

```text
異なる入力・思考
      ↓
必要な箇所だけadapter / structure化
      ↓
由来を保持した統合
      ↓
3人で検討
```

を基本とする。

## Do not normalize humans first

技術的に扱いづらいという理由だけで、各メンバーの使い慣れた方法を変更しない。

優先順位:

1. 現行運用をそのまま読めるか
2. adapterで吸収できるか
3. 中間形式へ変換できるか
4. それでも不可能な場合のみ、本人と相談して入力側を変更する

## Canonicalization

共通schemaは目的ではなく手段。

初期段階では、
- 各人の推奨
- 根拠
- 対象レース / 馬
- confidenceや評価（本人が使用している場合）
など、実運用で繰り返し必要になる要素を観察する。

その後、必要十分なschemaを定義する。

## Existing personal assets

既存個人Projectの資産を本Projectで利用する場合、
- 元資産の正本所在は維持
- 不要なコピーを避ける
- shared側はinterface / adapterを所有
を基本とする。

これにより、既存資産の改修をshared側へ二重反映する状態を避ける。

## Attribution

統合結果では、可能な限り
- member source
- tool / data source
- GPT整理
を区別する。

GPTが整理・補完した仮説を、本人の確定意見として扱わない。
