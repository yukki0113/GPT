#!/usr/bin/env python3
"""Produce the fixed September v0.1 research report from audited outputs."""
import argparse,json
from pathlib import Path
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    out=a.output_dir;data=json.loads((out/'rrdb_202609_data_audit.json').read_text());audit=json.loads((out/'rrdb_202609_analysis_audit.json').read_text())
    assert data['status']==audit['status']=='PASS'
    summary=pd.read_csv(out/'rrdb_202609_time_pace_analysis.csv',dtype={'stratum':str})
    comparisons=json.loads((out/'rrdb_202609_matched_comparisons.json').read_text())
    ledger=pd.read_parquet(out/'rrdb_202609_all_runner_research_ledger.parquet')
    sections=[]
    def table(frame,columns=None):
        frame=frame[columns] if columns else frame
        def fmt(value):
            if pd.isna(value):return 'NA'
            if isinstance(value,float):return f'{value:.2f}'
            return str(value).replace('|','\\|').replace('\n',' ')
        header='| '+' | '.join(map(str,frame.columns))+' |\n'
        divider='| '+' | '.join(['---']*len(frame.columns))+' |\n'
        body=''.join('| '+' | '.join(fmt(v) for v in row)+' |\n' for row in frame.itertuples(index=False,name=None))
        return header+divider+body
    def add(text):sections.append(text.strip()+'\n')
    add('''# RaceReviewDB 2026年9月 前走タイム・展開逆行分析 v0.1

Status: ANALYSIS_COMPLETE / DATA_AUDIT_PASS / RESEARCH_ONLY
Date: 2026-10-01

9月全3,137エントリーを保持して分析を完了した。前走タイム上位20%は次走好走を拾うが、
上位10%に絞ることは市場価値の改善につながらなかった。前走6着以下×タイム上位20%は
複勝回収率114.47%で、着順だけでは見えない候補として残る。
前傾前受けをタイム評価へ足した追加価値は今回確認できない。
後傾後方は単独では弱く、上がりpercentile 90以上との組み合わせで初めて有望な結果になった。
これらは9月の探索的記述結果であり、S/Aの条件・凍結閾値は変更しない。

## 1. 母集団・精算・リーク境界

- 1行=target entrant。horse_idはJRDB血統登録番号8桁を文字列として保持し、馬名結合はしない。
- PACI/KYI + BACで全頭とtarget条件を形成する。前走はtarget_dateより厳密に前の直近完成済みJRA平地走。
- 全エントリーと取消・除外・障害を台帳から削除しない。主分析は平地・実出走・前走履歴あり。
- 取消/除外は返還扱いでstakeから除く。中止は実出走の不的中として残す。
- 前走特徴Parquetを確定・hash保存してからSED結果を結合する。
- 複勝hitは払戻>0で判定。小頭数3着の不的中を区別する。
- SEDの払戻欄空白は不的中の0円に正規化し、raw_blank列に原状態を残す。払戻対象着順の空白は監査で拒否する。
- DAY_TRACK_OPPOSITIONは今回未実装でNULL。既存タイム補正はRRDBのleave-one-race-out仕様を継承する。
''')
    items={k:data[k] for k in ['target_runner_count','target_started_count','target_flat_started_count','usable_previous_rrdb_start_count',
        'no_previous_history_count','usable_flat_started_count','duplicate_count','sed_join_missing_count','settlement_identity_mismatch_count',
        'pace_feature_missing_count','performance_feature_missing_count','corner4_feature_missing_count','closing_gain_missing_count',
        'previous_date_violation_count','historical_standard_date_violation_count','rrdb_object_hash_verified_count']}
    add(table(pd.DataFrame(items.items(),columns=['audit','count'])))
    add(table(pd.DataFrame(data['daily'])))
    add(f"RRDB generation: `{data['rrdb_generation']}`。収録は`{data['rrdb_period_to']}`まで。参照moduleの取得時mainは`{data['source_commit']}`。")
    add('''履歴あり2,686頭のうち主分析に入るのは2,590頭。タイム評価は全2,590頭にある。
ペース×4角位置が揃う共通母集団は1,848頭（71.35%）。欠損742頭を不利なし=0に補完しない。
RRDB全頭履歴に存在する前走レース1,082件を監査し、percentile有効865件・欠損217件。
percentile有効値は、source dateより前の同surface/distance・venue優先履歴から既存percentile_rankで再計算し、
sample_count / scope_levelを含め不一致0件。標準タイムsample_end_dateもsource dateより前である。
closing_gainは大半欠損であり、「後傾後方×上がり90×closing_gain>0」の観測対象は0頭。
これは条件の成績不良ではなく検証不能を意味する。

月全体の分位は特徴量だけから計算した記述用境界で、当時日次で固定されていた運用ルールではない。
target結果・人気・オッズで境界を選ばない。上位20%=signal>=q80、上位10%=signal>=q90で同値は分割しない。
そのため上位20%は519頭となる。Historical OOSへ進む場合は、この数値境界を固定して適用する。
''')
    add(table(pd.DataFrame([{ 'field':field,**values} for field,values in audit['quantiles'].items()])))
    add('''## 2. タイム評価単独

performance_signal=-horse_adjusted_delta_per_1000m。高いほど良い。
能力予測としてはbottom50→top10で複勝的中率が14.36%→37.45%へ上昇する。
一方でtop10の回収率は75.98%に下がり、人気平均4.80・単勝オッズ中央値7.9倍。
能力の強さと市場の過小評価は一致しない。
''')
    cols=['stratum','n','place_hits','place_hit_rate_pct','stake_yen','place_payout_yen','place_roi_pct','popularity_mean','popularity_median','win_odds_mean','win_odds_median']
    add(table(summary[(summary.section=='quantile') & (summary.signal=='performance_signal')],cols))
    add('### 前走着順×タイム分位')
    add(table(summary[summary.section=='finish_time'],['signal']+cols))
    add('### 上位20/10と前走敗退馬')
    names=['ALL_USABLE','PERF_TOP20','PERF_TOP10','FINISH_GE4','FINISH_GE4_PERF_TOP20','FINISH_GE4_PERF_TOP10','FINISH_GE6','FINISH_GE6_PERF_TOP20','FINISH_GE6_PERF_TOP10']
    add(table(summary[(summary.section=='signal') & summary.signal.isin(names)],['signal']+[x for x in cols if x!='stratum']))
    add('''前走6着以下×top20は94頭・20的中・払戻10,760円/購入9,400円。
同じ前走6着以下1,410頭のbaseline（的中率13.12%、回収率76.82%）を上回る。
ただしROI差のtarget-race cluster bootstrap 95%区間は-23.06～+103.90ppと広く、利益を確証しない。
top10は38頭・6的中・回収率52.63%で、9月ではtop20のほうが実用候補として残る。
70-80帯・80-90帯の高ROIはそのまま記述するが、結果を見てその帯だけを正式ルールに選ばない。

既存frozen numeric thresholdも参考として比較する。9月分位と同義ではない。
既存q80=-0.0930556を使う前走6着以下は116頭、回収率108.88%。
既存ルール・S/Aは不変であり、今回の結果で置換しない。
''')
    add(table(summary[(summary.section=='signal') & summary.signal.str.startswith('FROZEN_')],['signal','n','place_hit_rate_pct','place_roi_pct']))
    add('''## 3. 展開逆行単独

前傾前受け: pace percentile>=70 × corner4_frontness>=0.6。
後傾後方: pace percentile<=30 × corner4_frontness<=0.4。
90/10および0.8/0.2の狭い事前指定subtypeも出す。
rawはfront=(pct/100)×frontness、rear=(1-pct/100)×(1-frontness)。内容評価と掛けて単一scoreにしない。
''')
    names=['PACE_COMPLETE','FRONT_HIGH','FRONT_VERY_HIGH','FRONT_EXTREME','REAR_HIGH','REAR_VERY_HIGH','REAR_EXTREME','POSITION_RECOVERY','POSITION_RECOVERY_LAST3F80','CURRENT_HV07']
    add(table(summary[(summary.section=='signal') & summary.signal.isin(names)],['signal','n','place_hits','place_hit_rate_pct','place_roi_pct','popularity_mean','win_odds_median']))
    add('### Pace shape × 4角frontness')
    add(table(summary[summary.section=='pace_position'],['signal','stratum','n','place_hit_rate_pct','place_roi_pct']))
    add('### Raw exposure分位')
    add(table(summary[(summary.section=='quantile') & summary.signal.str.contains('opposition_raw')],['signal','stratum','n','place_hit_rate_pct','place_roi_pct']))
    add('''前傾前受け単独は共通baseline比で的中率+2.79pp、ROI+5.76pp。
bootstrap区間はいずれも0を跨ぎ、強い独立効果は確認できない。
後傾後方単独はbaselineを下回る。very-rearのROI108.60%はハクタカ3,110円が払戻の33.30%を占める。
POSITION_RECOVERY単独はROI62.28%、上がり80との組み合わせでも68.05%。
今回の9月では市場価値の改善が乏しいが、PACE_OPPOSITIONの全系統が一律に優れるとは判断しない。
''')
    add('''## 4. タイム×展開逆行・上がり×展開逆行

追加価値は欠損のない共通母集団の親signalと比較する。全519頭のtop20と73頭の組み合わせを
直接比較すると母集団差が混じるため、ペース有効のtop20=362頭を親baselineとする。
''')
    comp=[]
    for c in comparisons:
        sm=c['selected'];pm=c['parent_metrics'];ci=c['uncertainty']
        comp.append(dict(signal=c['signal'],n=sm['n'],hit_pct=sm['place_hit_rate_pct'],roi_pct=sm['place_roi_pct'],
            parent=c['parent'],parent_n=pm['n'],parent_hit_pct=pm['place_hit_rate_pct'],parent_roi_pct=pm['place_roi_pct'],
            hit_lift_pp=c['hit_lift_pp'],roi_lift_pp=c['roi_lift_pp'],roi_lift_ci95=str(ci.get('roi_lift_ci95_pp','NA'))))
    add(table(pd.DataFrame(comp)))
    add('''前傾前受け×top20は73頭、的中率36.99%、ROI95.89%。親のtop20共通362頭は36.19%、96.91%。
タイム評価への明確な追加価値はない。top10との組み合わせでも不確実性区間は広い。
後傾後方×タイムはtop20=13頭・ROI20.00%、top10=7頭・18.57%。極小標本で、好材料とはいえない。
後傾後方×上がり90以上は43頭・20的中・ROI134.88%。親の上がり90共通324頭は34.57%、77.01%。
的中率差+11.94pp、ROI差+57.88pp。ROI差bootstrap区間は+1.28～+125.74ppだが、
多数の事前指定signalを同時比較した探索結果であり、有意性や独立性の確定として扱わない。
上がり80では67頭・ROI99.10%で、90のほうが集中するが、閾値を探索して選んだものではない。
''')
    add('### Source / market matched baseline')
    matched=[]
    for c in comparisons:
        sm=c['selected'];s=c['source_matched'];m=c['source_odds_matched']
        matched.append(dict(signal=c['signal'],n=sm['n'],hit_pct=sm['place_hit_rate_pct'],roi_pct=sm['place_roi_pct'],
            source_expected_hit=s['expected_hit_rate_pct'],source_expected_roi=s['expected_roi_pct'],
            source_odds_expected_hit=m['expected_hit_rate_pct'],source_odds_expected_roi=m['expected_roi_pct'],min_cell_n=m['min_cell_n']))
    add(table(pd.DataFrame(matched)))
    add('''前走着順帯×前走芝/ダート×前走距離帯×前走クラスで親母集団を標準化し、さらにtarget odds帯を加えた比較も行った。
親は選択群を含むため、この比較は重み付けされた記述baselineであり、因果効果推定ではない。
最小セルN=1があり、細かいmatched結果は補助材料。
後傾後方×上がり90のsource-matched期待ROIは87.23%、oddsも揃えると120.04%。
市場構成を揃えた追加差は粗比較より縮小するため、独立した市場価値はOOSで再検証する。
parent-complement、hit/ROI bootstrapの全値はmatched_comparisons.jsonに保存した。

## 5. 人気・オッズ別市場価値

以下は主要signalの全odds帯。全signal/combinationについてodds帯・人気帯・開催日・前走着順帯・
芝/ダート・距離帯・class別集計をCSV/Parquetに保存した。欠損/小Nのセルを隠さない。
''')
    names=['ALL_USABLE','PERF_TOP20','PERF_TOP10','FINISH_GE6_PERF_TOP20','FRONT_HIGH','REAR_HIGH','FRONT_HIGH_PERF_TOP20','REAR_HIGH_LAST3F90']
    add(table(summary[(summary.section=='odds_band') & summary.signal.isin(names)],['signal','stratum','n','place_hits','place_hit_rate_pct','place_payout_yen','place_roi_pct','odds_roi_lift_pp']))
    add('### 人気帯')
    add(table(summary[(summary.section=='popularity_band') & summary.signal.isin(names)],['signal','stratum','n','place_hits','place_hit_rate_pct','place_roi_pct']))
    add('''前走6着以下×top20は5-9.9倍・10-29.9倍・30-99.9倍で各185.83/150.00/111.88%。
同odds帯の全usable baselineより高いが、各12/33/32頭と少ない。100倍以上は15頭全不的中である。
後傾後方×上がり90の100倍以上は2頭中1頭的中でROI695%。同帯liftは大きいが2頭だけなので一般化しない。

## 6. 高配当寄与・日別再現性

高配当を除いて主要評価を作り替えない。金額、日数、同odds baselineとの差を併記する。
高配当例は複勝1,000円以上。全該当signalとの対応をhigh_payout_examples.csvへ保存した。
''')
    names=['FINISH_GE6_PERF_TOP20','REAR_HIGH_LAST3F90','REAR_VERY_HIGH']
    add(table(summary[(summary.section=='signal') & summary.signal.isin(names)],['signal','n','place_payout_yen','max_place_payout_yen','largest_payout_share_pct','high_payout_hits','hit_days']))
    high=pd.read_csv(out/'rrdb_202609_high_payout_examples.csv',dtype={'target_race_key':str,'horse_id':str})
    add(table(high[high.signal.isin(names)],['signal','target_date','target_race_key','target_horse_no','horse_id','horse_name','previous_finish','target_finish','target_popularity','target_win_odds','target_place_payout_yen']))
    add(table(summary[(summary.section=='target_date') & summary.signal.isin(names)],['signal','stratum','n','place_hits','place_payout_yen','place_roi_pct']))
    add('''前走6着以下×top20の高配当3頭は9/5・9/12・9/27の別開催日。最大1頭は払戻の16.82%。
的中は7日、ROI>100は3日であり、1頭だけの高配当には依存していないが、日別収益は安定しない。
後傾後方×上がり90は全10日で的中、ROI>100は5日。最大シルバードン1,390円が払戻の23.97%。
全払戻5,800円から購入4,300円を引いた利益1,500円のうち1,390円をこの1頭が占めるため、
利益水準への寄与は大きい。的中の広がりと収益の集中を区別する。
very-rearは最大1頭3,110円が総利益740円を大きく上回り、特に収益の集中が強い。

## 7. Q1–Q8への回答

| 問い | 9月で得られた回答 |
|---|---|
| Q1 タイム単独は強いか | 能力予測は強い。top20的中率36.22%。市場価値は同じではなく全体ROI89.87%。 |
| Q2 前走6着以下×top20 | HVで母集団を限定せず94頭・的中率21.28%・ROI114.47%。検証候補として有望。 |
| Q3 top20とtop10 | 9月の市場価値ではtop20。top10は人気が高まり、败退馬の標本も縮小する。 |
| Q4 前傾前受け単独 | 小幅改善だが不確実。ROI87.16%で、利益や独立効果を支持しない。 |
| Q5 後傾後方単独 | 広い定義では弱い。ROI75.39%。狭い定義の高ROIは高配当集中が強い。 |
| Q6 タイムへ展開逆行を追加 | 前傾×top20は共通タイム単独に優位なし。後傾×タイムは極小N・低ROI。 |
| Q7 位置取り改善と比較 | POSITION_RECOVERYの市場価値は弱い。全PACE_OPPOSITIONが一律優位ではない。 |
| Q8 市場価値にもなるか | 後傾後方×上がり90と败退×タイム20は候補。独立した市場価値の確証には固定閾値OOSが必要。 |

## 8. 次の検証・正式ルールとの境界

2024-01-01～2025-12-31のHistorical OOSへ、q80=-0.0555555555555524、q90=0.21138888888889343と
今回のpace/position/last3f条件を変更せず適用する。9月で最良だった帯への再最適化は禁止。
優先候補は前走6着以下×time top20と後傾後方×last3f>=90。
time単独、finish-matched、同odds帯、common complete parent、半期block方向を再比較する。
closing_gain複合は0対象のため未検証として残し、NULL=0で判定を作らない。
正式S/Aへの昇格は行っていない。既存凍結条件と9月quantileは明確に分離する。

能力指標のtop3/top5は3着以内/5着以内の競走成績であり、複勝hitとは別指標。
中止馬はtop3/top5不成立として率の分母に残し、平均着順はfinish>0のみ。
不確実性はtarget race cluster 1,000回・seed20261001で概算。馬の反復出走や複数signalの多重性を完全には扱わない。
説明可能な固定条件の一次研究であり、ランダム化研究や因果的独立効果推定ではない。

## 9. 再現方法・成果物

```bash
python horse-racing/jrdb/src/jrdb_previous_start_research_ledger.py \
  --input-dir INPUT --current-zip INPUT/RaceReviewDB_CURRENT.zip \
  --rule-zip INPUT/frozen_rules.zip --output-dir OUTPUT --source-commit SOURCE_SHA
python horse-racing/jrdb/src/analyze_rrdb_time_pace.py \
  --ledger OUTPUT/rrdb_202609_all_runner_research_ledger.parquet --output-dir OUTPUT
python horse-racing/jrdb/src/report_rrdb_time_pace.py \
  --output-dir OUTPUT --report horse-racing/jrdb/docs/RaceReviewDB_202609_Time_PaceOpposition_Analysis_v0_1.md
python horse-racing/jrdb/tests/test_jrdb_previous_start_research_ledger.py
```

INPUTは9月10日のPACI/SED ZIP、RRDB CURRENT、既存frozen rule archive。Google Drive connectorで取得する。
Actions↔Drive direct transportは使わず、一時Issue/workflowは作成していない。
Common Readerと既存RRDB/Next-Watch helperを利用し、consumer独自のbyte sliceは追加していない。
台帳・features・集計・matched比較・audit・provenanceは`horse-racing/jrdb/analysis/tmp/`に保存する。
CSVはUTF-8 BOM、identityは文字列。表計算ソフトで開く場合は先頭ゼロを維持する。
Parquetを型保持の正本とする。
''')
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('\n'.join(sections).replace('败退','敗退'),encoding='utf-8')
    print(a.report)


if __name__=='__main__':main()
