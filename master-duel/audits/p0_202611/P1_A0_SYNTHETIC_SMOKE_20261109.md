# P1-A0 合成契約試作・初回検証（2026-11-09）

## Scope
- **限定P1-A0**: 架空カードのID、MDレアリティの出典、UNKNOWN、禁止制限日付、所有確認ガードのみ。
- 実データ取込、カード本文永続保存、全文検索、パック取得、自動ログイン、デッキ生成は**未実施**。
- P0-Cのゲーム内公式確認30件は**0/30**であり、P1-A1完成版NO-GOは継続。

## GitHubコード正本
- `master-duel/p1_a0/catalog_contract.py` Git Blob SHA: `45baa5c08c92cdca3f74ca79b141e122d658af7a`
- `master-duel/p1_a0/tests/test_catalog_contract.py` Git Blob SHA: `abbca06e215e7aa3cc4180268b0ce3bba16635c1`
- `master-duel/p1_a0/README.md` に実行方法を記載。
- 既存の `tools/data-storage/README.md` を確認済み。今回はDuckDB/Parquet処理を実装しないため標準Pythonのみを採用、共通基盤の再実装なし。

## 実行検証

この実行環境からGitHub raw URLへ直接アクセスするとDNSが失敗したため、ツール経由でGitHubへ登録したソース/テストと同じ内容を**ローカルに復元**。両ファイルの `git hash-object` が上述のGitHub Blob SHAと**完全一致**した状態でテストを実行。

```text
cd /mnt/data/md_p1_a0_check
python -m unittest discover -s tests -v
Ran 11 tests in 0.000s
OK
```

実測: **11 / 11 PASS**。対象:
1. 同名でも別のcanonical IDを許容
2. canonical IDの重複を検出
3. Konami ID重複を検出
4. 複数passwordを1カードとして保持
5. OCG印刷レアリティのMD混入を拒否
6. 生成可否とパックのUNKNOWNを維持
7. 非公式・未検証制限を公式合法性に昇格しない
8. ゲーム内検証済み規制のみ明示capを返す
9. 所持不明のURを「新規UR生成0確定」にしない
10. GAME_VERIFIEDのみのフィルタが機能
11. SHA入力未確認のスナップショットを拒否

## 監査上の限界
- これは**合成fixtureテスト**であり、MD実カード13,948件への適用試験ではない。
- `Game_VERIFIED` はデータ型として存在するが、公式ゲーム内30件から検証済みの行を投入したことはない。
- `confirmed_new_ur_zero` はUR所有枚数の必要条件チェックであり、完成デッキ構築・CP算出・合法性の保証ではない。
- `legality_as_of` は発効日以降の単一規制スナップショットのcapを返す最小契約。複数スナップショットの最新適用選択、別ルール形式、正式なbanlist全件確認は未実装。
- `Dataset` はsource_shaの形とID重複を検証するだけで、与えたshaがファイルの実バイトに一致するかは**実データ取得時の別工程**で検証する。
- カード本文権利・自動取得許諾を解決したわけではない。
