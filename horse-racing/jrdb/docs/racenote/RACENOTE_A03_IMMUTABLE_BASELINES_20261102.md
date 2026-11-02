# A03: 期限付きActions artifactからの独立（受入済みimmutable baseline）

適用日: 2026-11-02
対象: RRDB Horse Course Fit validation、RaceNote v0.5.5 r6 / v0.5.6 shared T1、historical v0.5.2 equivalence

## 正本と固定条件

受入済みbaselineの輸送定義は `horse-racing/jrdb/config/public_drive/racenote_a03_accepted_baselines_v1.json`。
各ファイルのGoogle Drive ID、ファイル名、サイズとSHA-256を必須として、既存の `tools/gpt_io/public_drive/fetch.py` で取得する。取得した実物が一致しなければ停止し、別世代へ自動fallbackしない。

| 論理入力 | 長期保存先 | 元のActions artifact | SHA-256 (Drive ZIP) |
|---|---|---|---|
| RRDB Course Fit validation baseline | RRDB snapshots: `1xbOGJzGIQsXaHUYhKMuRfy1UfmgHEhYY` | `11780924435` (run `38327108923`) | `ea1d4e1f3f0efdebee512a3ba09f7f9fd253a3851b42c562698bc11102fb011a` |
| Course Fit part 1 | Course Fit folder: `1ljLg_jxVdZtpJ_Aqku0L93y8nwnfXUTQ` | `11799761734` (run `38370479179`) | `b27f2293a100755aa1ac0c902c2e6338a8393cd208c5de0912ff7a81f89783ba` |
| Course Fit part 2 | Course Fit folder: `1yxP0EtPRmcTnrAgmgBMlAAj257r3pgYE` | 同上 | `ddc07eca88fe1b56391efcaa3b84ff4cf34121f69c7262a024177b82702dea72` |
| RaceLap 2026-10-17 baseline | RaceLap folder: `1q7pmoTRsg27d--xi5HhtTaJXAI_TdzUi` | `12101869150` (run `39037137243`) | `a4b076e69e9d26c464b49fd8301640b07e89fbd28925a88229869a465a51ae96` |

### 受入証拠

- RRDB snapshotとRaceLapアーカイブのSHA-256は元Actions artifact digestと一致することを2026-11-02に実物で確認した。
- Course Fitは元Actions ZIPを2パッケージへ分割保存した既存受入成果物。Driveの `RRDB_Horse_Course_Fit_Storage_Receipt.json` が元ZIPのSHA-256 `18570ef9c366f78b2f8bb60c380e24b70f1b80e070ddf1961acaed7bde35627d` と各part SHAを記録する。両partのZIP CRCと個々のSHAは確認済み。2 ZIPのメンバー重複は `READ_FIRST.txt` だけで、内容が一致する。展開順はpart1→part2で、2回目は `unzip -n` で既存ファイルを上書きしない。
- 実行時のファイルチェックを省略しない。ネットワーク取得失敗、SHA不一致、ファイル欠損、Course Fit / RaceLapのデータ内容検証失敗はfail-closed。

### 手動再現の入口

```bash
python tools/gpt_io/public_drive/fetch.py \
  --manifest horse-racing/jrdb/config/public_drive/racenote_a03_accepted_baselines_v1.json \
  --artifact rrdb_validation_g38327108923 \
  --output-root /tmp/a03-baseline \
  --receipt /tmp/a03-rrdb-receipt.json
```

残りのartifact IDは `course_fit_v01_part1`、`course_fit_v01_part2`、`racelap_canonical_20261017`。

## 昇格ルール

1. 新しい成功runを無条件で選択しない。研究as-of、入力coverage、生成契約、validation statusを個別に受入判定する。
2. 受入済みbytesを消えることのない保存先へ保存し、SHA・サイズ・source run・世代ID・受入証拠を記録する。
3. **既存v1 manifestは上書きしない。** 新しいv2 manifestを作り、consumerの参照切替をPRでレビューする。
4. 取得時のSHA検証とRaceLapの `generation_id=racelap-forward-canonical-20261017-01` およびParquet SHAの検証は維持する。
5. 旧artifactの期限後でも同じbaselineをDriveから取得できることを確認した後に旧artifactへの運用依存を撤去済みとする。

## 対象外

- A01: v0.5.2 historical golden manifest内 `golden_20` の、更新可能なRRDB CURRENTを過去SHAで取得する問題（別修正）。
- A04: BTDAYで固定baselineを使う契約と、最新CURRENTを選択する契約の分離（別修正）。
- A05/A06: 最新性receiptのconsumer gate・RRDB CURRENTのID更新契約（別修正）。
