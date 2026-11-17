"""Strict non-predictive M7 research *preview* projection, never a live addon.

Returns provenance and evidence availability without suitability interpretation.
Do not connect to RaceNote/PWA/Newspaper; the v0.1 consumer stays frozen.
"""
from __future__ import annotations

from brdb_m7_relatives_detail_candidate import (
    RelativesDetailError, check, digest, CONTRACT, build as build_detail,
)

VERSION = 'brdb-m7-research-consumer-preview-v0.1'
ROLES = ('sire', 'broodmare_sire', 'pairing', 'relatives')


def build_preview(v03, sidecar):
    check(isinstance(v03, dict) and isinstance(sidecar, dict), 'objects required')
    check(v03.get('contract_version') == 'brdb-integrated-blood-review-v0.3-candidate'
          and v03.get('release_status') == 'RESEARCH_CANDIDATE',
          'research v0.3 required')
    check(sidecar.get('contract_version') == CONTRACT and
          sidecar.get('research_only') is True and
          sidecar.get('release_status') == 'RESEARCH_SIDECAR_ONLY' and
          sidecar.get('prediction_safe') is False and
          sidecar.get('historical_asof_status') == 'AS_OF_UNVERIFIED' and
          sidecar.get('no_forecast_or_score') is True and
          sidecar.get('integrated_v03_canonical_sha256') == digest(v03),
          'unverified or altered relative sidecar')
    source_rebuilt = {**sidecar.get('source_metadata', {}), 'horses':sidecar.get('horses')}
    check(sidecar.get('source_canonical_sha256') == digest(source_rebuilt) and
          build_detail(v03, source_rebuilt) == sidecar,
          '④ sidecar content integrity drift')
    check(len(v03.get('horses', [])) == len(sidecar.get('horses', [])) ==
          v03['race']['field_size'], 'cohort mismatch')
    rows = []
    for horse, detail in zip(v03['horses'], sidecar['horses']):
        check((horse.get('horse_id'), horse.get('horse_no')) ==
              (detail.get('horse_id'), detail.get('horse_no')),
              'horse ID or number drift')
        check(horse.get('status') == 'AS_OF_UNVERIFIED' and
              horse.get('factors') == {'positive': [], 'negative': [], 'unknown': []} and
              horse.get('summary') is None and
              horse.get('confidence') == 'UNASSESSED',
              'prohibited source interpretation')
        check(horse.get('supplemental_status') == 'AS_OF_UNVERIFIED' and
              all(x.get('interpretation_status') == 'OBSERVATION_ONLY_AS_OF_UNVERIFIED'
                  and x.get('contribution_to_score') is None
                  for x in horse.get('supplemental_insights', [])),
              'D4 interpretation promotion')
        lanes = {}
        for role in ROLES:
            status = horse['components'][role]['availability']
            check(status == horse['coverage'][role], 'component coverage drift')
            if role in ('pairing', 'relatives'):
                check(status in ('AS_OF_UNVERIFIED', 'SOURCE_UNAVAILABLE'),
                      '③④ historical as-of illegally promoted')
                label = 'HISTORICAL_AS_OF_UNVERIFIED' if status == 'AS_OF_UNVERIFIED' \
                    else 'SOURCE_UNAVAILABLE'
            else:
                check(status in ('AVAILABLE', 'LOW_SAMPLE', 'NO_SAMPLE',
                                 'SOURCE_UNAVAILABLE'), 'unsupported ①② status')
                label = {'AVAILABLE': 'DESCRIPTIVE_SAMPLE_ONLY',
                         'LOW_SAMPLE': 'SMALL_SAMPLE_ONLY',
                         'NO_SAMPLE': 'NO_RECORDED_STARTS',
                         'SOURCE_UNAVAILABLE': 'SOURCE_UNAVAILABLE'}[status]
            lanes[role] = {'source_status': status, 'display_reason': label,
                           'evidence_items': len(horse['components'][role]['evidence_ids']),
                           'may_infer_suitability': False}
        check(lanes['relatives']['evidence_items'] == len(detail['relatives']),
              '④ relative count mismatch')
        rows.append({'horse_id':horse['horse_id'], 'horse_no':horse['horse_no'],
                     'overall_status': 'AS_OF_UNVERIFIED',
                     'lanes':lanes, 'd4_observation_items':len(horse['supplemental_insights']),
                     'qualified_interpretation': 'NO_FIT_VERDICT_PERMITTED',
                     'score':None, 'rank':None, 'probability':None})
    return {'contract_version': VERSION, 'release_status': 'RESEARCH_PREVIEW_ONLY',
            'research_only':True, 'prediction_safe':False,
            'production_authorized':False, 'as_of_status':'AS_OF_UNVERIFIED',
            'source_contracts': {'integrated':v03['contract_version'],
                                 'relatives_detail':sidecar['contract_version']},
            'source_sha256': {'integrated_v03':digest(v03),
                              'relatives_detail':digest(sidecar)},
            'race':dict(v03['race']), 'horses':rows}