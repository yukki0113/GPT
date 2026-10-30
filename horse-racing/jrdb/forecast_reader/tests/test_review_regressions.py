import copy
import pytest
from test_sampling import TARGET, RULES, race
from forecast_orchestrator import build, publish
from input_source_resolver import verify_provenance
from contract_validator import validate_nested
from datetime import datetime


def material():
    races = [race(y,str(y)) for y in range(2016,2026)]
    rows = [dict(race_key=str(y),horse_id=str(y),race_date=f'{y}-10-25',finish=1,
                 final_win_popularity=1,frame_no=1,running_style='2',age=3,sire_name='S',jockey_name='J',
                 prev_race_key_1='previous'+str(y)) for y in range(2016,2026)]
    refs = [dict(race_key='previous'+str(y),horse_id=str(y),race_date=f'{y-1}-12-01',distance=2000,race_class='OP') for y in range(2016,2026)]
    runner = dict(horse_no=1,frame=1,running_style_code='2',age=3,sire_name='S',jockey='J',previous_run={'date':'2025-10-01','distance_m':2000,'race_class_code':'OP'})
    return races,rows,refs,[runner]


def test_reference_2015_not_in_cohort_and_eight_axes():
    races,rows,refs,runners=material()
    out=build(TARGET,races,rows,runners,RULES,reference_rows=refs)
    assert out['history_coverage']['previous_joined']==10
    assert out['history_coverage']['cohort_starts']==10
    assert out['trends']['exact_only']['previous_distance']['groups'][0]['starts']==10
    assert len(out['runners'][0]['trend_matches'])==8
    pop=out['runners'][0]['trend_matches'][0]
    assert pop['result']=='unknown' and 'forbidden' in pop['reason']
    for match in out['runners'][0]['trend_matches']:
        assert match['membership_only']
        for group in match['evidence']:
            assert sum(group['finishes'])==group['starts']


def test_reference_duplicate_future_and_missing_year():
    races,rows,refs,runners=material()
    with pytest.raises(ValueError,match='DUPLICATE'):
        build(TARGET,races,rows,runners,RULES,refs+refs[:1])
    refs[0]['race_date']='2016-10-25'
    with pytest.raises(ValueError,match='FUTURE_LEAK'):
        build(TARGET,races,rows,runners,RULES,refs)
    out=build(TARGET,races,rows[1:],runners,RULES,[])
    assert out['status']=='PARTIAL' and out['history_coverage']['years_missing']==[2016]


def test_timestamp_alone_is_not_evidence():
    with pytest.raises(ValueError,match='UNVERIFIED_AS_OF'):
        verify_provenance({'snapshot_at':'2026-10-01T00:00:00+09:00'},datetime.fromisoformat('2026-10-25T00:00:00+09:00'))


@pytest.mark.parametrize('payload',[{'nested':{'final_win_popularity':1}}, {'sources':[{'win_payout':1}]}, {'target':{'nested':{'finish':1}}}])
def test_nested_leaks(payload):
    with pytest.raises(ValueError,match='FUTURE_LEAK'):
        validate_nested(payload)


def test_legal_previous_finish_and_deterministic_bundle(tmp_path):
    validate_nested({'runners':[{'previous_run':{'finish':1,'date':'2025-10-01'}}]})
    races,rows,refs,runners=material()
    out=build(TARGET,races,rows,runners,RULES,refs)
    one=publish(tmp_path/'one',{},out,{}, {})
    two=publish(tmp_path/'two',{},out,{}, {})
    assert {p.name:p.read_bytes() for p in one.iterdir()}=={p.name:p.read_bytes() for p in two.iterdir()}


def test_metadata_mismatch_and_nested_audit_exception():
    source={'name':'x','size_bytes':1,'sha256':'a'}
    before={'id':'id','name':'x','size_bytes':1,'modified_time':'2026-10-01T00:00:00+09:00','parent_ids':['folder'],'version':'1'}
    source['provenance']={'provider':'native_drive','observation_id':'fixture','before':before,'after':{**before,'version':'2'},'download_sha256':'a'}
    with pytest.raises(ValueError,match='SOURCE_CHANGED'):
        verify_provenance(source,datetime.fromisoformat('2026-10-25T00:00:00+09:00'))
    with pytest.raises(ValueError,match='FUTURE_LEAK'):
        validate_nested({'source_audit':{'previous_run':{'finish':1}}})


def test_target_result_archive_kinds_never_requested(monkeypatch):
    from pathlib import Path
    from datetime import date
    import previous_run_reader as reader
    from test_previous_run_reader import fixture
    kinds=[]
    def records(path,kind,audit):
        kinds.append(kind)
        assert kind not in ('SED','HJC','SRB')
        if kind=='KYI':
            return [('fixture',fixture.make_kyi())]
        if kind=='ZED':
            return [('fixture',fixture.make_sed('20231001','20260810','0526A001','01'))]
        return []
    monkeypatch.setattr(reader,'iter_archive_records',records)
    reader.read_previous(Path('unused'),'0526A101',date(2026,8,30))
    assert kinds==['KYI','ZED','UKC']


def test_ukc_pre_race_profile(monkeypatch):
    from pathlib import Path
    from datetime import date
    import previous_run_reader as reader
    from test_previous_run_reader import fixture
    data={'KYI':fixture.make_kyi(),'ZED':fixture.make_sed('20231001','20260810','0526A001','01'),'UKC':fixture.make_ukc()}
    monkeypatch.setattr(reader,'iter_archive_records',lambda path,kind,audit:[('fixture',data[kind])])
    runners,_=reader.read_previous(Path('unused'),'0526A101',date(2026,8,30))
    # Fixture UKC belongs to another horse: identity join must not fill by name.
    profile=reader.Parser().ukc(fixture.make_ukc())
    if profile['horse_id']==runners[0]['horse_id']:
        assert runners[0]['sire_name']==profile['sire_name']
    else:
        assert runners[0]['sire_name'] is None
