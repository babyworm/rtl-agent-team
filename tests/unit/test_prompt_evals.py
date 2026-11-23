"""Regression checks for the evaluation and template-revision contracts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from tests.conftest import REPO_ROOT


def module(name):
    spec=importlib.util.spec_from_file_location(name,REPO_ROOT/'scripts'/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_equivalent_plugin_route_spelling_is_not_a_behavior_failure():
    evaluator=module('eval_prompts')
    expected={'route':'p1-spec-research'}
    assert evaluator.grade({'route':'/rtl-agent-team:p1-spec-research'},expected)==[]
    assert evaluator.grade({'route':'rtl-agent-team:p1-spec-research'},expected)==[]
    assert evaluator.grade({'route':'/another-plugin:p1-spec-research'},expected)==['route']


def test_diagnostic_confidence_cannot_clear_a_material_ambiguity():
    evaluator=module('eval_prompts')
    cases=json.loads((REPO_ROOT/'evals/judgment/cases.json').read_text())
    expected=next(case for case in cases if case['id']=='ambiguity_beats_average')['expected']
    diagnostic={'decision':'clarify','confidence':'high','open_ids':['REQ-F-001'],'additional_review_rounds':0}
    assert evaluator.grade(diagnostic,expected)==[]
    assert 'decision' in evaluator.grade({**diagnostic,'decision':'proceed'},expected)
    assert 'open_ids' in evaluator.grade({**diagnostic,'open_ids':[]},expected)


def test_template_revision_is_required_when_managed_content_changes():
    catalog=module('template_catalog')
    old={'tool.sh':{'version':'2.0.0','sha256':'before'}}
    changed={'tool.sh':{'version':'2.0.0','sha256':'after'}}
    assert catalog.validate(old,changed)
    changed['tool.sh']['version']='2.0.1'
    assert catalog.validate(old,changed)==[]
    # The release is still 2.0.0, so the pre number is the revision.
    changed['tool.sh']['version']='2.0.0-pre17'
    assert catalog.validate({'tool.sh':{'version':'2.0.0-pre16','sha256':'before'}},changed)==[]
    assert catalog.validate({'tool.sh':{'version':'2.0.0-pre17','sha256':'before'}},changed)
    assert catalog.validate({'tool.sh':{'version':'2.0.22','sha256':'before'}},changed)==[]
    release={'tool.sh':{'version':'2.0.0','sha256':'released'}}
    assert catalog.validate(changed,release)==[]
    assert catalog.validate(release,changed)
    assert catalog.version_newer('2.0.1','2.0.0')
    assert not catalog.version_newer('2.0.0','2.0.22')
    assert catalog.version_newer('2.0.22','2.0.0')


def test_checked_in_catalog_matches_shipped_template_content():
    result=subprocess.run([sys.executable,str(REPO_ROOT/'scripts/template_catalog.py')],
                          capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
