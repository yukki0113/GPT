# 欲しがるな、勝ち取れ

競馬仲間3人とChatGPTで共同して中央競馬の予想・研究を行う共有ProjectのGit正本です。

## Project root

```text
shared-projects/hoshigaruna-katsitore/
```

共有Projectに固有のsource / schema / adapter / config / docsは、原則としてこのroot以下で管理します。

既存の `horse-racing/`、`boat-racing/`、`local-horse-racing/` 等は別Projectの正本であり、本Projectの通常作業で直接変更しません。

## Members

- **けんしょー** — データ予想派。インフラ、データ管理、GitHub / Drive連携、実装エンジニア担当。
- **りょーた** — 馬体・回顧派。AI動画解析から位置取り・不利等を抽出し、レース情報と突合して次走注目馬を選定。Excelで管理・運用中。
- **おーじ** — 回顧派。JRA-VANの個人データに長年の回顧メモを蓄積。Projectへの資産化方法は検討中。

詳細は `docs/MEMBER_ROLES.md` を参照します。

## GitHub connection

本Projectで利用するGitHub Connectorは **`yukki0113/GPT` の接続のみ** とします。

複数GitHubアカウントを同時接続した構成は使用しません。

Repository:

```text
https://github.com/yukki0113/GPT
```

## Google Drive

共有Project用のデータ・Excel・大容量資産・分析成果物は、従来どおり共有Drive側で管理します。

共有Drive root:

```text
https://drive.google.com/drive/folders/1E2rYfbAS-hX2kBXNZuis__-oJFksocRF
```

GitHubとDriveの役割分担、および外部管理データの境界は `.gpt/DATA_BOUNDARY.md` を参照します。

## Basic policy

- 3人の分析方法そのものを無理に統一しない。
- 人間がシステムに合わせるのではなく、可能な範囲でadapterが各人の既存運用を吸収する。
- 共通化するのは、必要に応じて最終出力や機械連携interface。
- 各人の分析・主張・成果物は誰に由来するかを保持する。
- 一致だけでなく意見の相違も情報として残す。
- 共有Projectと既存個人Projectの資産境界を明確に保つ。

## Initial structure

```text
shared-projects/hoshigaruna-katsitore/
├─ README.md
├─ .gpt/
│  ├─ CONTEXT.md
│  ├─ WORKFLOW.md
│  └─ DATA_BOUNDARY.md
└─ docs/
   ├─ MEMBER_ROLES.md
   ├─ INTEGRATION_POLICY.md
   └─ PROJECT_INSTRUCTIONS.md
```

`adapters/`、`schemas/`、`src/`、`tests/`、`config/` 等は、実際に必要になった時点で追加します。空の将来ディレクトリを先に固定しません。

## GPT / Work start order

1. repository共通 `.gpt/GITHUB_OPERATION_POLICY.md`
2. repository共通 `.gpt/README.md`
3. 本 `README.md`
4. `.gpt/CONTEXT.md`
5. `.gpt/WORKFLOW.md`
6. 必要に応じて `.gpt/DATA_BOUNDARY.md`
7. 対象source / docs / schema / adapter

共有ChatGPT ProjectのInstructions正本案は `docs/PROJECT_INSTRUCTIONS.md` です。
