# CONTEXT — 欲しがるな、勝ち取れ

## Purpose

3人それぞれの異なる競馬観・分析方法を維持したまま、ChatGPTを共通の整理・研究支援レイヤとして使い、予想・回顧・検証を共同で育てる。

## Members

### けんしょー
- データ予想派
- Project host
- インフラ / データ管理 / GitHub / Google Drive / 実装エンジニア担当
- 他メンバーの既存運用をなるべく変えずに接続可能な形へ整備する

### りょーた
- 馬体・回顧派
- AIによる動画解析を利用
- 位置取り、不利等を抽出
- レース情報と突合して次走注目馬を選定
- 現在はExcel中心で管理・運用

### おーじ
- 回顧派
- JRA-VAN個人データへ長年の回顧メモを蓄積
- 既存資産のProjectへの取り込み方式は未確定
- 形式変更や移行を先に要求しない

## Chat structure

初期の共有ChatGPT Projectは次の4系統とする。

- けんしょーの部屋
- りょーたの部屋
- おーじの部屋
- 管理室

各個人部屋は本人が作成し、本人とGPTの研究・壁打ちに使う。

管理室は主にけんしょーが利用し、全体運用、GitHub / Drive、データ連携、adapter設計、各部屋の成果統合を扱う。

1つのチャットへ複数メンバーがリアルタイム共同参加しているものとして扱わない。

## Repository / storage

GitHub repositoryは `yukki0113/GPT` のみを使用する。

本ProjectのGit root:

```text
shared-projects/hoshigaruna-katsitore/
```

共有データ・Excel・大容量成果物等はProject用Google Driveを利用する。

既存のけんしょー個人Project資産を利用する場合も、既存側の正本を本Projectへ移管したと解釈しない。必要に応じてinterface / adapterで接続する。

## Current phase

初期立ち上げ段階。

優先順位:
1. 3人がストレスなく自分の方法で研究できること
2. 成果をメンバー別に識別して統合できること
3. 必要になった箇所からadapter / schemaを追加すること
4. 早期に過剰な共通フォーマットを固定しないこと
