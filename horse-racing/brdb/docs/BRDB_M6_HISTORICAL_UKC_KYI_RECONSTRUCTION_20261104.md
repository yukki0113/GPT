# BRDB M6 — 2016〜2025年開催日別UKC/KYI再構成・実データ監査（2026-11-04）

## 判定

**歴史的な血統入力候補の構築は481,503/481,627件まで進展（研究用PASS）。M6の予測用as-of独立証拠は依然0件（HOLD）。**

2016〜2025年のGoogle Drive正本`UKC_YYYY.zip` 10本と `KYI_YYYY.zip` 10本を取得し、各年の両ZIPに収録された日付別テキスト1,082組を、BRDBの独自固定長解釈ではなく既存`jrdb_ukc.parse_ukc_record`／`jrdb_raw.raw_field`で検査した。

### 日付別履歴候補の実データ監査

| 項目 | 実測 |
|---|---:|
| KYI出馬表レコード | **481,627** |
| UKCから血統を対応付けた候補 | **481,503** |
| 同じ開催日UKCに血統があったレコード | **480,904** |
| 当日UKCにないため、過去UKCの最後の観測から補ったレコード | **599** |
| 過去の日付のUKCにも見つからなかったレコード | **124** |
| 対象日次テキスト組数 | **1,082** |
| 当日UKC `data_date`不一致 | **0** |
| as-of配信時点を独立証明できたレコード | **0** |

2016〜2024年の各年は全KYIレコードを同日UKCへ対応付けた。**2025年の2開催日だけ**はUKCとKYIの内容・母数が異なった。

- **2025-12-13**：`KYI251213.txt` 499件に対し`UKC251213.txt` 167件。馬IDを直接照合すると同日UKCから129件、過去UKCから309件、未対応61件。
- **2025-12-14**：KYI 496件に対しUKC 183件。同日143件、過去290件、未対応63件。
- 同日のUKCにはKYI出走馬に含まれないプロフィールも存在し、同一馬プロフィールの重複（同じ意味値）も確認された。**レコード順による1対1結合や、件数不足を単純なファイル末尾欠損とみなすことは禁止**する。
- UKCは2025-12-13／14を名乗るが、ZIP内日時は2025-12-07。先行して生成された暫定登録版の可能性があり、JRDB原本配信の独立証明にはならない。

private runtimeで作成した候補`private_historical_daily_ukc_kyi_candidate.csv.gz`は、`target_date/race_key/horse_no/horse_id`と父・母・母父・父系コード・母父系コード、採用UKCの`data_date`、元ZIP SHA、日次member SHA、`SAME_DAY_MEMBER`／`PRIOR_DATE_LAST_OBSERVED`を保持する。全行に`UNATTESTED`を刻印し、**血統の事後調達を将来予測の教師データに自動昇格させない**。

### 追跡調査：同一馬のデータ表現は実際に変化する

同一馬の初回観測と後続日次UKCを照合した結果、2016〜2025年の保持履歴の範囲で、父名140頭、母名265頭、母父名282頭、父系コード3頭、母父系コード24頭に値の相違があった。これはデータ訂正・別表記・登録情報変更などの理由を特定したものではないが、**「血統は生物学的に不変だから後日のマスタ値を過去にそのまま充当して安全」という仮定を棄却する具体的観測**となる。

独立の2026年14開催日PACIでも、複数回登場した906頭のうち1頭に父名の異なる表記があり、父系コード等は一致した。ZIP収録日時・UKC`data_date`の値はメタデータにすぎず、当時配信された版そのものの証明ではない。

### 実装・再現

- `src/build_brdb_historical_ukc_kyi_candidate.py`：20 ZIPをprivate runtimeで検証し、原本上の当日プロフィール、なければ過去の最後の観測のみを利用する研究用候補の組み立て。未来のUKCを使用しない。相反する同日重複を拒否し、追加の原本・データ漏洩をGitHubへ公開しない。
- `tests/test_build_brdb_historical_ukc_kyi_candidate.py`：部分的な日付別UKC・過去観測からの復元、SHA変化、重複矛盾、ZIP不一致を合成データだけで検証。
- 初回private replay出力：14,876,259バイト、SHA `da79a08e535ee463b69ad1e11991201f5fd05b39dc2968b606d25f142c2e5f96`。同一ロジックの初期ローカル版によるもの。**GitHub版とのバイト同一性は未検証**であり、主に件数と安全境界の相互確認に用いる。
- licensed row-level CSVと原本ZIPはGitHubにコミットせず、ユーザーの私的研究領域でのみ扱う。

```bash
python horse-racing/brdb/src/build_brdb_historical_ukc_kyi_candidate.py \
  --ukc-root <PRIVATE_UKC_YYYY_ZIP_FOLDER> \
  --kyi-root <PRIVATE_KYI_YYYY_ZIP_FOLDER> \
  --years 2016:2025 \
  --out <PRIVATE_OUT_FOLDER>
```

### 残る本質的な外部ブロッカー

1. **当時配信された版の独立証拠**：JRDBに、2016〜2025年の日付別UKC/KYI/JRDBパックの過去原本が配信後の修正を反映しているか、原配信版・配信ログ・訂正履歴やoriginal hashを提供可能か確認する。JRDB公式の金土19時・前日データ提供スケジュール（https://jrdb.com/data_introduction/）だけでは、手元の年次ZIPの内容がその時点の版と同一と立証できない。
2. **2025-12-13/14の不足124件**：当時の完全なUKC原本またはその開催前の別履歴が必要。レース後のマスタで埋めるなら研究用仮補完として明示し、as-ofとは認定しない。
3. **P1-7のモデル確率**：既存RaceNote v0.5.6は印・ConfidenceのFreezeを実装しているが、同一馬の`p_baseline`・`p_blood_challenger`を生成・事前凍結する学習済みモデルは未受入。後から印を勝率へ変換することは禁止。実データ前向き取得が必要。

**M6全体・P1-5/6/7予測効果は依然HOLD。今回のPASSは483k規模の研究入力候補の組み立てに限定。**
BRDB CURRENT、RaceNote、PWA、予想・販売ロジックは未変更。

## GitHub正本の20 ZIP実データ実行と決定性確認

GitHub正本 `src/build_brdb_historical_ukc_kyi_candidate.py` の**Git blob SHA `f6e8300f33a4d5edee6815a7a009359c2f3b4545`**と一致する実ソースを、Source-only transport [Issue #2401](https://github.com/yukki0113/GPT/issues/2401) / [Actions run 41798327664](https://github.com/yukki0113/GPT/actions/runs/41798327664) を経由して私的実行環境へ取得。初回のSHA計算がUKC各馬行ごとで非効率だった点を修正し、日次メンバーごとに一度だけ計算するようにした。変更後のGit blobを照合し、合成テスト4/4 PASS。

2016〜2025年の20 ZIP・1,082対の実データを正本コードで**2つの独立出力ディレクトリにて再実行**。次の結果がそれぞれ一致し、出力バイトも同一だった。

- `kyi_entries=481627`、`matched_entries=481503`、`same_day_ukc_entries=480904`、`prior_day_ukc_entries=599`、`missing_ukc_entries=124`。
- `private_historical_ukc_kyi_candidate.csv.gz` SHA-256: `9b59a097bd8883fb771fcf2baf23df6e7dad0c4b52163af2ca7f5467ba87c805`、サイズ14,883,720バイト。ユーザーの非公開環境に限り保存し、GitHubにコミットしない。
- `historical_daily_candidate_aggregate.json` SHA-256: `35bbbe9e79b2d02de5552d012e25624b987344c953275bff2cf3222b594914f8`。
- 同日UKC重複は2025年12月13日14件、12月14日6件であり、同じ馬の内容は意味論的に一致している。矛盾プロフィールはfail-closed。
- 古い試作ファイルのSHAは正本実行のSHAとして採用しない。

以上が通っても**独立した当時の配信原本受領・訂正履歴の証明は依然0件**。データ再構成をP1-5/6/7予測性能のPASSに改ざんしない。
