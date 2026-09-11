# JRDB 2026 Raw — Google Drive operational reference

## Purpose

2026年のJRDB RawをChat / Work / Actionsから扱う際の、既存外部資産の優先順位を固定する。

この文書は **Driveに既に保存済みのRawを再利用することを標準** とし、JRDB upstreamからの再取得を欠損補完へ限定するための運用referenceである。

## Standard 2026 Raw set

2026年の標準Rawセットは次の3系統。

- `PACI`
- `SED`
- `HJC`

既存資産がGoogle Driveにある場合、まずDriveを正本搬送元としてresolveする。

## Drive roots

### PACI

Google Drive folder:

`https://drive.google.com/drive/folders/12lmU6_NZF24ixrB7MMMzzvcBNzbhQTr0`

日次命名:

`PACIyymmdd.zip`

PACI ZIPには少なくとも次の固定長Rawが同梱される。

- BAC
- KYI
- UKC
- CHA
- CYB

ほかにもPACI同梱familyがあるため、PACI内に存在するfamilyを個別にJRDB upstreamから取り直さない。

### SED

Google Drive folder:

`https://drive.google.com/drive/folders/1ywucQ_84OgnSzJG6_HXa_M8KWWkVOTa4`

日次命名:

`SEDyymmdd.zip`

2026開催日分のSEDはこのDrive資産を先にresolveする。

### HJC

2026標準Rawセットの一部。Drive上の日次HJCを使用する。

HJCの個別File IDをGitへ固定しない。Google Driveアダプタで日付・命名規則からresolveする。

## Mandatory acquisition order

2026 Rawを必要とする処理は、必ず次の順序で確認する。

1. GitHub `horse-racing/jrdb/.gpt/CONTEXT.md` / `WORKFLOW.md` / 本referenceを確認する。
2. Google Driveアダプタで既存 `PACIyymmdd.zip` / `SEDyymmdd.zip` / `HJCyymmdd.zip` をresolveする。
3. 対象日・ZIP妥当性・必要familyの存在を検証する。
4. **Driveに欠損または破損がある対象だけ** JRDB upstream取得を使用する。
5. upstream取得した補完Rawは、既存運用に従ってDriveへ保存して再利用可能にする。

禁止事項:

- Drive inventoryを確認せず、年初から対象日まで全日付・全familyをupstreamへ総当たりする。
- PACI同梱family（BAC/KYI/UKC/CHA/CYB等）を、PACIが存在するのに個別取得し直す。
- 既存Drive Rawとupstream再取得Rawを由来不明のまま混在させる。

## File ID policy

- 個々の日次ZIPのDrive File IDは変動し得るため、Gitの恒久契約にしない。
- 上記folder rootと命名規則を探索referenceとして使い、実ファイルはGoogle Driveアダプタで都度resolveする。
- E2Eや監査で使った個別File ID / URLはEvidenceとして記録してよいが、通常運用の必須入力にはしない。

## Training Edge / research usage

Training Edgeを含む2026 YTD研究でも同じ優先順位を使う。

- 事前・調教系入力: 既存PACIを使用
- 開催後成績: 既存SEDを使用
- 払戻が必要な研究: 既存HJCを使用

研究用に新しい取得経路を作る前に、必ず既存Drive Rawで必要入力を満たせないか確認する。
