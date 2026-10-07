import json
from types import SimpleNamespace
import pytest
from agent.core import DEMOS, apply_edits, decide, parse_proposal, run_tests, validate_files, verify
from agent.model import propose, generate

@pytest.mark.parametrize('demo', DEMOS, ids=lambda d:d['id'])
def test_offline_end_to_end(demo, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    before = run_tests(demo['files'])
    p = propose({'files':demo['files'],'task':demo['task']})
    result = verify(demo['files'], p['edits'], before)
    assert [len(before['passing']),len(before['failing']),len(result['after']['passing']),len(result['after']['failing'])] == demo['expected']
    assert result['accepted'] and result['regressions'] == []
    assert p['mode'] == 'offline' and result['diff']


def test_regression_rejected(monkeypatch):
    monkeypatch.setenv('ALLOW_TRUSTED_CODE','1')
    monkeypatch.delenv('VERCEL', raising=False)
    d=DEMOS[0]
    bad=d['fixed']['cart.py'].replace('self.items = {}','self.items = {"extra": (1, 1)}')
    v=verify(d['files'],[{'file':'cart.py','content':bad}])
    assert not v['accepted'] and v['regressions']

@pytest.mark.parametrize('path',['../escape.py','/tmp/escape.py','a/../../x.py','a\\b.py','a//b.py','.hidden.py','x.txt'])
def test_bad_path(path):
    with pytest.raises(ValueError):
        apply_edits(DEMOS[0]['files'],[{'file':path,'content':'pass'}])


def test_existing_test_protected():
    with pytest.raises(ValueError,match='protected'):
        apply_edits(DEMOS[0]['files'],[{'file':'test_cart.py','content':'pass'}])


def test_new_test_allowed():
    assert 'test_new.py' in apply_edits(DEMOS[0]['files'],[{'file':'test_new.py','content':'def test_new(): assert True'}])

@pytest.mark.parametrize('text',['broken','[]','{"edits":[]}','```json\nnope\n```'])
def test_bad_json(text):
    with pytest.raises(ValueError): parse_proposal(text)


def test_fenced_json():
    assert parse_proposal('```json\n{"explanation":"x","edits":[]}\n```')['explanation']=='x'


def test_skipped_passing_test_is_regression():
    v=decide({'passing':['a'],'failing':['b'],'valid':True},{'passing':[],'failing':[],'valid':True})
    assert not v['accepted'] and v['regressions']==['a']


def test_collection_error_rejected():
    assert not decide({'passing':['a'],'failing':['b'],'valid':True},{'passing':['a'],'failing':[],'valid':False})['accepted']


def test_no_progress_rejected():
    b={'passing':['a'],'failing':['b'],'valid':True}
    assert not decide(b,b)['accepted']


def test_size_limit():
    with pytest.raises(ValueError): validate_files({'main.py':'x'*200001})


def test_custom_public_execution_blocked(monkeypatch):
    monkeypatch.setenv('VERCEL','1')
    monkeypatch.setenv('ALLOW_TRUSTED_CODE','1')
    with pytest.raises(ValueError,match='Hosted demo safety'): run_tests({'test_custom.py':'def test_a(): assert True'})


def test_modified_offline_task_blocked(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(ValueError,match='Offline mode'): propose({'files':DEMOS[0]['files'],'task':'invent another task'})


def test_duplicate_edits():
    with pytest.raises(ValueError,match='Duplicate'): apply_edits(DEMOS[0]['files'],[{'file':'cart.py','content':'x'}]*2)


def test_model_retry_fallback(monkeypatch):
    monkeypatch.setattr('agent.model.time.sleep',lambda _:None)
    calls=[]
    class Busy(Exception): code=503
    def call(**kwargs):
        calls.append(kwargs['model'])
        if len(calls)<=3: raise Busy()
        return SimpleNamespace(text='{}')
    client=SimpleNamespace(models=SimpleNamespace(generate_content=call))
    assert generate(client,'prompt')[1]=='models/gemini-3.7-flash'
    assert len(calls)==4


def test_model_not_found_discovers_flash(monkeypatch):
    class Missing(Exception): code=404
    def call(**kwargs):
        if kwargs['model']!='models/current-flash': raise Missing()
        return SimpleNamespace(text='{}')
    client=SimpleNamespace(models=SimpleNamespace(generate_content=call,list=lambda:[SimpleNamespace(name='models/current-flash',supported_actions=['generateContent'])]))
    assert generate(client,'prompt')[1]=='models/current-flash'


def test_no_secrets_in_subprocess(monkeypatch):
    monkeypatch.setenv('ALLOW_TRUSTED_CODE','1')
    monkeypatch.delenv('VERCEL',raising=False)
    monkeypatch.setenv('GEMINI_API_KEY','not-a-real-key')
    e=run_tests({'test_env.py':'import os\ndef test_env():\n    assert "GEMINI_API_KEY" not in os.environ\n'})
    assert e['valid'] and len(e['passing'])==1
