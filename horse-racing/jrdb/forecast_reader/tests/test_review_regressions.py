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


def test_unselected_pool_does_not_inflate_previous_cohort():
    races,rows,refs,runners=material()
    rows.append(dict(race_key='unselected',horse_id='other',race_date='2017-01-01',prev_race_key_1='unavailable'))
    out=build(TARGET,races,rows,runners,RULES,refs)
    assert out['history_coverage']['history_pool_starts']==11
    assert out['history_coverage']['cohort_starts']==10
    assert out['history_coverage']['previous_requested']==10
    assert out['history_coverage']['previous_missing']==0


def test_bac_manifest_hash_and_year_coverage(tmp_path):
    from warehouse_conditions import read_conditions
    from pathlib import Path
    manifest={'artifact_type':'jrdb_normalized_warehouse_final_generation','status':'PASS','assets':[]}
    with pytest.raises(ValueError,match='SOURCE_NOT_FOUND'):
        read_conditions(manifest,{},2026)
    p=tmp_path/'input.parquet';p.write_bytes(b'fake')
    manifest['assets']=[{'family':'bac','year':2025,'relative_path':'input.parquet','size_bytes':4,'sha256':'0'*64}]
    with pytest.raises(ValueError,match='HASH_MISMATCH'):
        read_conditions(manifest,{'input.parquet':p},2026)


def test_official_code_identity_keeps_class_codes_distinct():
    from race_condition_resolver import class_identity
    import json
    from pathlib import Path
    config=json.loads((Path(__file__).resolve().parents[1]/'config/jrdb_class_normalization_v1.json').read_text())
    assert config['verified_labels']['16']['previous']=='1600万下'
    assert config['verified_labels']['16']['current']=='3勝クラス'
    assert class_identity('16','5')=='16:5'
    assert class_identity('15','5')!='16:5'
    assert class_identity('UNKNOWN','5') is None


def test_accepted_bac_sed_condition_fallback(tmp_path,monkeypatch):
    import types,sys,hashlib
    from warehouse_conditions import read_conditions
    columns=['race_key_raw','date_raw','race_name','distance_raw','surface_code','turn_code','layout_code','race_type_code','race_class_code','symbol_code','weight_rule_code','grade_code']
    records={};assets=[];paths={}
    for year in range(2016,2026):
        p=tmp_path/f'bac{year}';p.write_bytes(str(year).encode());paths[p.name]=p
        record=[f'08{str(year)[2:]}1111',f'{year}1025','菊花賞','3000','1','1','2','12','OP','541','3','1']
        records[p]=[record]
        assets.append({'family':'bac','year':year,'relative_path':p.name,'size_bytes':4,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'row_count':1})
    p=tmp_path/'sed2025';p.write_bytes(b'sed');paths[p.name]=p
    sed_columns=['race_key_raw','date_raw','race_name','distance_m','surface_code','turn_code','layout_code','race_type_code','race_class_code','race_symbol_code','weight_condition_code','grade_code']
    sed=['06255301','20251213',None,1200,'2','1','1','11','A3','022','3','']
    assets.append({'family':'sed','year':2025,'relative_path':p.name,'size_bytes':3,'sha256':hashlib.sha256(b'sed').hexdigest(),'row_count':1})
    def query(path,sql):
        if path==p:
            assert 'finish' not in sql and 'payout' not in sql
            return sed_columns,[sed]
        return columns,records[path]
    monkeypatch.setitem(sys.modules,'data_storage.query',types.SimpleNamespace(execute_query=query))
    races,audit=read_conditions({'artifact_type':'jrdb_normalized_warehouse_final_generation','status':'PASS','assets':assets},paths,2026)
    assert len(races)==11
    assert audit[-1]['supplement_races']==1
    assert next(r for r in races if r['race_key']=='06255301')['race_class']=='A3:'
