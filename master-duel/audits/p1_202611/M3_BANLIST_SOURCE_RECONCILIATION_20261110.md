# M3：2026-11-05 マスターデュエル禁止制限の出典・差分・全件監査

監査日：2026-11-10 JST。対象：MD_STANDARD、2026-11-05施行、非公開Google Drive本番HEAD世代3。

## 結果・判定

- **215件**：禁止114／制限77／準制限24。非公開Drive `source/current.vector.json` はYAML Yugiの2026-11-05版 `data/master-duel/2026-11-05.vector.json` と**3395 bytesの完全一致（各215件・差異0）**。公開ファイルGit blob `6cb1fb1461df5de6a2762dbee6aacc19a417a2d4`、作成更新Git履歴 `45c3fe15553e246fe6ce85f041dd4bf99fe494eb`（2026-10-27 UTC）。元SHA256 `2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781`。
- **YAML YugiはKONAMIの一次データではない**。YAML YugiはYugipediaなどのファンデータを集約する。これを掲載する [yugiohcardlist.com](https://yugiohcardlist.com/banlist/master-duel/2026-11-05) は自ら「Data via YAML Yugi」と記すため、同サイトとの一致は**独立した確認1件として数えない**。
- **本番SQLite格納データの全件照合**：215/215のKONAMI IDおよび規制上限値がsource vectorと一致、欠損0・異値0・重複0。SHAが本番HEADと一致し、SQLite integrity=ok、外部キー違反0、規制verification=`UNVERIFIED_SOURCE`。
- **改訂差分**：YAML Yugiの2026-10-06版（209件／禁止111・制限72・準制限26）と2026-11-05版を集合差分比較し**変更9件のみ**。公式Xの改訂予定日（2026-10-26告知→11-05施行）と公式告知引用／独立解説（Master Duel Meta、Game8、AppMedia）の列挙した9件が一致した。**この照合は9件の変更分のみを対象とし、歴史的に継承した206件を公式ゲーム内で照合したことにはならない**。
- Master Duel VNの2026-11-05版は215件・禁止114・制限77・準制限24を掲載し、**集計数が一致**。ただし、同サイトのデータ系譜・全215行の独立ID照合は立証しておらず、全件公式照合の証拠として数えない。
- **最終判定：`SOURCE_ORIGIN_IDENTIFIED / INTERNAL_215_MATCH / REVISION_9_CROSSCHECK / GAME_OFFICIAL_215_PENDING`**。現DBの`UNVERIFIED_SOURCE`は変更・昇格しない。

## 2026-11-05 施行、旧版との差分9件

| KONAMI ID | カード | 10/06→11/05 | 確認 |
|---|---|---|---|
| 5594 | マジック・キャンセラー | 無制限相当→禁止(0) | 新規禁止、外部告知と一致 |
| 6027 | 神殿を守る者 | 無制限相当→禁止(0) | 新規禁止、外部告知と一致 |
| 14708 | ＧＯ－ＤＤＤ神零王ゼロゴッド・レイジ | 無制限相当→禁止(0) | 新規禁止、外部告知と一致 |
| 21789 | 星辰響手プリクル | 無制限相当→禁止(0) | 新規禁止、外部告知と一致 |
| 4966 | 早すぎた埋葬 | 禁止(0)→制限(1) | 緩和、外部告知と一致 |
| 21953 | キラーチューン・ミクス | 準制限(2)→制限(1) | 規制強化、外部告知と一致 |
| 21955 | キラーチューン・レコ | 準制限(2)→制限(1) | 規制強化、外部告知と一致 |
| 22117 | 耀聖の波詩ディーナ | 無制限相当→制限(1) | 新規制限、外部告知と一致 |
| 22119 | 燿ける聖詩の獄神精 | 無制限相当→制限(1) | 新規制限、外部告知と一致 |

旧版ベクトルで未掲載のカードの値を「3」と断定せず、変更表の「無制限相当」は旧ベクトルで未掲載かつ公式改訂告知の「無制限→」表示と対応することを意味する。一般の未掲載カードは引き続き `UNLISTED_UNKNOWN` とする。

**参考公開ソース**：
- [YAML Yugi 改訂前（2026-10-06）](https://github.com/DawnbrandBots/yaml-yugi-limit-regulation/blob/master/data/master-duel/2026-10-06.vector.json)、[改訂後（2026-11-05）](https://github.com/DawnbrandBots/yaml-yugi-limit-regulation/blob/master/data/master-duel/2026-11-05.vector.json)
- [マスターデュエル公式X](https://x.com/YuGiOh_MD_INFO)（2026-10-26改訂予告）、[公式告知引用](https://rojiuragame.com/2026/10/27/%E3%80%90%E9%81%8A%E6%88%AF%E7%8E%8B%E3%83%9E%E3%82%B9%E3%82%BF%E3%83%BC%E3%83%87%E3%83%A5%E3%82%A8%E3%83%AB%E3%80%91dc%E7%B5%82%E3%82%8F%E3%81%A3%E3%81%9F%E3%81%9D%E3%81%AE%E6%97%A5%E3%81%AB%E8%A6%8F/)
- [Master Duel Meta（10月26日）](https://mdm.app.duellinksmeta.com/articles/news/october-26-2026/master-duel-forbidden-list-update)、[Game8](https://game8.jp/yugioh-masterduel/423063)、[AppMedia](https://appmedia.jp/master_duel/27463944)、[Master Duel VN集計](https://masterduel.online/en/banlist)

## 非公開監査成果物（本番DBは未変更）

Drive `GPT/MasterDuel/DB/` に下記を保存。**公開Gitにはカード全215行・私有DB・所持個票は置かない**。

- `MD_BANLIST_FULL_215_PROVENANCE_AUDIT_20261110.json`（Drive ID `1BpbMOBINktvaWfZL9fHvrQKJascCSjp_`）、87870 bytes、SHA256 `86f572aaf5ef7c0169d6a61bc7bd2e4a84507802d0c4962db7076d618737d6fc`
- `MD_BANLIST_FULL_215_PROVENANCE_AUDIT_20261110.csv`（Drive ID `1Cl1XZNzCnp5HbFvRmbcE-6MMaEucAN-Z`）、27173 bytes、SHA256 `dd49d7ff37abd382797b5ed341aa6860072f4e385744ff7129e18ebc8b8430bc`
- 独立Drive読戻しで両SHA一致。JSON/CSVは全215カードについて日本語名・KONAMI ID・規制値・前回差分・確認レベルを記載。合計（禁止114/制限77/準制限24）、名前・IDは非公開ファイルでのみ提供。
- Drive HEADは**世代3のまま**、SQLite制限データも215件 `UNVERIFIED_SOURCE` のまま。inventory=5、history=5、card master=13948、日本語効果13948を維持。

## 残りの正式確認と次の運用

- **未完**：継承206件を含めてKONAMIゲーム内の現在の標準リミットレギュレーションと全件・同一IDで照合。公式の全件API/リストは今回公開範囲で取得できなかった。ゲームクライアントにアクセスできない今回のGitHub/Drive/検索環境では、公式全件確認と主張できない。
- 確認できた9変更も、公式発表の二次引用・独立解説との突合が主であり、公式ゲーム画面215件を直接閲覧したことにはならない。
- 今後の実運用は2026-11-05版候補のまま継続してよいが、**正式な合法性が確定したという表示は禁止**。未掲載を3枚合法とみなさず、コード上の厳格判断を維持。
- 新たな規制改訂が来たら、`regulation_m3/reconcile.py` で旧版・新版本文とprivate SQLiteの全行一致、追加削除・値変更を再計算し、変更告知と突合する。再現確認に必要な公開コードのみGitHubへ反映し、private JSONはDriveへ保存する。

## コミット・CI

- 新規再現コード・合成テスト導入コミット：`34cb01529f4ad6e8ab2db01a438d622635e35be5`。
- [GitHub Actions run 42763838424](https://github.com/yukki0113/GPT/actions/runs/42763838424)：**成功**。全180テスト、M3=70テスト、失敗0・スキップ1。スキップは非公開ZIPに依存する従来のテスト。追加の`test_reconcile.py`4件はPASS。
- 公開CIで実際の非公開215件・個人DBをテストしたという意味ではない。実215行の照合とDrive読戻し・SHA照合は別の私的実データ読取専用経路で実施した。
- 最終監査の公開コードは旧版未掲載カードを3枚合法と推定せず`prior=None`を保持する。改訂の9カードについてのみ一次告知の「無制限から」を別途突合。
