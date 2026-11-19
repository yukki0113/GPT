"""Research-only cross-lane observations from the common BRDB analysis contract.

The differences are *observed sample differences*, not breeding effects, causal
compensation, validated aptitude, betting signals or prediction features.
"""
from __future__ import annotations
import json
from pathlib import Path

from brdb_discovery import discover as discover_v01

VERSION = 'brdb-cross-discovery-v0.2-candidate'
SCOPES = ('VENUE_COURSE_EXACT', 'VENUE_DISTANCE', 'ALL_VENUES_DISTANCE')


def _guard(ok, msg):
    if not ok: raise ValueError(msg)


def _scope_index(component):
    output = {}
    for row in component['scopes']:
        _guard(row['scope_key'] not in output, 'duplicate scope_key')
        output[row['scope_key']] = row
    return output


def _observed(row):
    if row is None: return False
    n = row['counts']['starts']
    rate = row['rates']['top3_rate']
    return n > 0 and rate is not None and row['data_status'] == 'OBSERVED'


def _rate_consistency(row):
    n, top3 = row['counts']['starts'], row['counts']['top3']
    rate = row['rates']['top3_rate']
    _guard((rate is None if n == 0 else rate is not None), 'count-rate null mismatch')
    if n:
        _guard(abs(rate-top3/n) <= 0.001, 'inconsistent top3 rate')


def _observation_pair(kind, scope, a, b, labels, *, historical_status):
    for item in (a,b): _rate_consistency(item)
    return {
        'finding_id': f'{kind}:{scope}', 'kind':kind,
        'interpretation_status':'OBSERVATION_ONLY',
        'evidence_refs':[a['evidence_id'], b['evidence_id']],
        'scope_key':scope,
        'samples':[
            {'lane':labels[0], 'starts':a['counts']['starts'], 'top3':a['counts']['top3'],
             'top3_rate':a['rates']['top3_rate'], 'sample_status':a['sample_status']},
            {'lane':labels[1], 'starts':b['counts']['starts'], 'top3':b['counts']['top3'],
             'top3_rate':b['rates']['top3_rate'], 'sample_status':b['sample_status']}],
        'observed_delta_pp':round((a['rates']['top3_rate']-b['rates']['top3_rate'])*100,2),
        'historical_asof_status':historical_status,
        'cohort_overlap':'UNKNOWN_OR_POSSIBLE',
        'causal_claim':False, 'suitability_claim':False,
        'display_eligible':False, 'prediction_eligible':False
    }


def discover_cross(common):
    base = discover_v01(common)  # reuses v0.1 full-cohort, identity & temporal guards
    _guard(base['release_status']=='RESEARCH_ONLY', 'not research')
    output=[]
    for h, b in zip(common['horses'],base['horses']):
        _guard((h['horse_no'],h['horse_id'])==(b['horse_no'],b['horse_id']), 'identity pairing')
        comp=h['components']
        sire=_scope_index(comp['sire'])
        bms=_scope_index(comp['broodmare_sire'])
        pairing=_scope_index(comp['pairing'])
        observations=[]
        reasons=[]
        # Two distinct sampling populations; these are deliberately *not* additive.
        band=sire.get('ALL_VENUES_BAND')
        if band is not None:
            surf=common['race']['surface_code']
            distance_band=band['condition']['distance_band']
            other=bms.get(f'{surf}:{distance_band}')
            if other is not None and _observed(band) and _observed(other):
                _guard(band['condition']['surface_code']==surf and other['condition']['surface_code']==surf,'surface mismatch')
                _guard(other['condition']['distance_band']==distance_band,'band mismatch')
                observations.append(_observation_pair('SIRE_BMS_DISTANCE_BAND_COOBSERVATION',
                    f'{surf}:{distance_band}', band,other,('sire','broodmare_sire'),
                    historical_status=common['policy']['historical_asof_status']))
            else: reasons.append({'kind':'SIRE_BMS_DISTANCE_BAND_COOBSERVATION','reason':'MISSING_OBSERVED_SCOPE'})
        else: reasons.append({'kind':'SIRE_BMS_DISTANCE_BAND_COOBSERVATION','reason':'MISSING_SIRE_BAND'})
        # Pairing-vs-sire: comparable surface and scope, but overlapping populations.
        # This is *not* evidence that the pairing caused a change in performance.
        for key in SCOPES:
            a,brow=pairing.get(key),sire.get(key)
            if not (_observed(a) and _observed(brow)):
                reasons.append({'kind':'PAIRING_SIRE_SCOPE_COOBSERVATION','scope_key':key,
                                'reason':'MISSING_OBSERVED_SCOPE'})
                continue
            _guard(a['condition']==brow['condition'],'pairing/sire condition mismatch')
            observations.append(_observation_pair('PAIRING_SIRE_SCOPE_COOBSERVATION',key,a,brow,
                ('pairing','sire'),historical_status='AS_OF_UNVERIFIED'))
        # Current common contract has only relative coverage counts; it cannot
        # attest individual relative's condition or support a distance claim.
        reasons.append({'kind':'RELATIVES_CONDITION_LINK',
                        'reason':'RELATIVE_DETAIL_NOT_PROJECTED_IN_COMMON_CONTRACT'})
        reasons.append({'kind':'GOING_COMPARISON','reason':'GOING_DIMENSION_NOT_IN_COMMON_CONTRACT'})
        reasons.append({'kind':'DISTANCE_COMPLEMENT','reason':'NO_CAUSAL_OR_MATCHED_CONTROL_VALIDATION'})
        output.append({'horse_no':h['horse_no'],'horse_id':h['horse_id'],
                       'cross_observations':observations,'pending':reasons})
    return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY',
            'race':common['race'],'as_of_exclusive':common['as_of_exclusive'],
            'policy':{'prediction_safe':False,'production_authorized':False,
                      'display_authorized':False,'review_text_generated':False},
            'horses':output}


def run(input_file,output_file):
    obj=discover_cross(json.loads(Path(input_file).read_text(encoding='utf-8')))
    Path(output_file).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return obj

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();obj=run(args.input,args.output)
    print('PASS',len(obj['horses']),'horses',sum(len(h['cross_observations']) for h in obj['horses']),'cross-observations')
