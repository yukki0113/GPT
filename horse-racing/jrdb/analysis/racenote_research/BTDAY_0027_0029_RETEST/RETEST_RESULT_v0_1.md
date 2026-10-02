# RaceNote BTDAY-0027〜0029 Retest v0.1

## Scope

Retest Set:
- BTDAY-0027: 2026-04-12 / 36R
- BTDAY-0028: 2026-06-07 / 24R
- BTDAY-0029: 2026-03-28 / 36R
- total: **96R**

Forecast:
- RaceNote-Human-Context-Reader-0.4.2-candidate
- rrdb-recommendation-signals-v0.3
- all sets FROZEN_CLEAN_BLIND

結果は対象抽出にのみ使用し、判定はPre-FreezeのForecast / reader_strippedへ戻って実施した。

## Mechanical population

Hierarchy failure candidate:
- 0027: 11R
- 0028: 14R
- 0029: 20R
- total: **45R**

winner role:
- ○ 16
- ▲ 9
- △1 12
- △2 8

Coverage failure:
- 0027: 32R / missed Top3 41頭
- 0028: 17R / missed Top3 20頭
- 0029: 22R / missed Top3 28頭
- total: **71R / 89頭**

3着無印: **24頭**

## Hierarchy Retest

Assessment:
- REVERSAL_WARRANTED: **6**
- NARROW_GAP: **6**
- PRE_RACE_JUSTIFIED: **24**
- PROMOTION_WARRANTED (▲): **1**
- SINGLE_SHOT_SUCCESS_NO_PROMOTION: **8**

Clear correction candidate:
- REVERSAL_WARRANTED 6
- ▲ PROMOTION_WARRANTED 1
- total **7 / 45 = 15.6%**

Boundary:
- NARROW_GAP **6 / 45 = 13.3%**

No clear correction:
- PRE_RACE_JUSTIFIED 24
- SINGLE_SHOT_SUCCESS_NO_PROMOTION 8
- total **32 / 45 = 71.1%**

### Discovery comparison (0023〜0026)

Discovery 64R:
- clear mainline correction candidate 12 / 64 = 18.8%
- boundary 11 / 64 = 17.2%
- original hierarchy reasonable or ▲ role success 41 / 64 = 64.1%

Retest 45R:
- clear 15.6%
- boundary 13.3%
- no clear correction 71.1%

**方向は再現。**
Discoveryで見えたエラー率がRetestで増幅しておらず、むしろやや低下した。

### ▲ role replication

Discovery:
- ▲ winner 11R
- single-shot success 9
- promotion 1
- ambiguous 1

Retest:
- ▲ winner 9R
- single-shot success **8**
- promotion **1**
- ambiguous 0

▲勝利を機械的Hierarchy失敗として学習しない方針は強く再現した。

### Reproduced correction patterns

1. **direct-condition evidence**
   - 0027 福島2R
   - 0027 阪神2R
   - 0028 東京12R
   - 0029 阪神9R

2. **visible finish vs hidden content**
   - 0029 中山2R
   - ○は5着でもTIME_CLASS_PLUS1 + RESULT_UNDERRATES_TIME
   - ◎の2着を表面上優先

3. **runs-well vs can-win**
   - 0029 阪神6R
   - ○は同距離の直近勝ち、◎は2着
   - Discoveryと同じ勝ち切り証拠の軽視

4. **▲ promotion gate**
   - 0029 中京12Rのみ明確
   - ▲が1600m勝ち直後 + デキ抜群 + above-class
   - ◎は1400m7着+HV02だが複数懸念
   - single-shot以上にmainline比較すべきケース

## Coverage 3rd-place Retest

3着無印24頭:
- SWAP_CANDIDATE: **7 / 24 = 29.2%**
- COMPLETE_MISS: **13 / 24 = 54.2%**
- AMBIGUOUS: **4 / 24 = 16.7%**

Discovery 3着無印68頭:
- SWAP 32 = 47.1%
- COMPLETE 30 = 44.1%
- AMBIGUOUS 6 = 8.8%

RetestではSWAP率が **47.1% -> 29.2%** に低下。
したがってDiscoveryだけを見て
「3着漏れの約半分はborderline challengerで救える」
と一般化するのは強すぎる。

一方でRetestでも7/24は事前に入替可能であり、
borderline challenger仮説自体は消えていない。

### Reproduced SWAP examples

- 0027 阪神7R バガン:
  1800m5着、能力は△末端以上、above-class/result-underrates-time。
- 0027 阪神10R バッデレイト:
  同距離2000m6着、能力近接、複数hidden strength。
- 0028 阪神12R ココロヅヨサ:
  同距離勝ち+FRONT_SURVIVE。
- 0029 中京12R キャッスルレイク:
  今回と同じ1400m5着で△2より条件直接性が高い。
- 0029 阪神8R オールザワールド:
  障害3390m4着で△1/△2の5・6着より直接成績が上。

### What did not replicate strongly

Discoveryではhidden strengthを持つ無印馬の候補境界漏れが多かったが、
Retestではhidden材料があっても能力差や直接条件差が大きく、
COMPLETE_MISSのままが多い。

したがってcoverage checkは
hidden flagの存在だけでchallengerを作ってはいけない。

## Updated hypothesis

### Hierarchy consistency pass

Retest支持。

Forecast変更前の分析仮説として維持:
1. race_modelが最重視した条件を◎○△のどれが最も直接満たすか
2. ◎が好走安定だけで、他馬に勝ち切り証拠がないか
3. 表面着順がhidden time/load evidenceを上書きしていないか
4. ▲はmainline級の直接勝ち切り証拠がある時だけpromotion gateへ

### Coverage borderline challenger

**弱めて維持。**

Discovery時:
> direct condition / hidden strength / ability proximity のいずれか

Retest後:
> **direct conditionを主軸**にし、
> ability proximity を必須に近い確認項目とする。
> hidden strength単独ではchallengerにしない。

推奨形:
- △2確定後に全無印馬を広く再走査しない
- 「今回条件への直接実績があり、かつ△2と能力差が大きくない馬」を優先
- hidden strength / 前走不利は補強材料
- challengerが明確に上でなければ元の5頭を維持

## Conclusion

Hierarchy仮説は0027〜0029で概ね再現した。
特に▲の役割分離は強い。

Coverage仮説は部分再現。
borderline challengerは存在するが、Discoveryほど頻繁ではないため、
適用範囲を狭めるべき。

Forecast v0.4.2本体はまだ変更しない。
次に変更候補を作るなら、
Hierarchy consistency passを中心にし、
Coverage checkは狭いgateとして組み込むのが妥当。
