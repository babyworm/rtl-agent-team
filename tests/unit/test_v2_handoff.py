"""Behavioral v2 contracts: ambiguity, evidence scope, approval and hook isolation."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time

import pytest

from tests.conftest import REPO_ROOT, run_hook


def script(name, *args, root=None):
    return subprocess.run([sys.executable,str(REPO_ROOT/'scripts'/name),*map(str,args)],
                          cwd=root or REPO_ROOT,text=True,capture_output=True,timeout=15)


@pytest.mark.parametrize(("agent", "legacy_status"), [
    ("uarch-to-verify-orchestrator", 1),
    ("p5b-silicon-validation-orchestrator", 0),
])
def test_bundled_and_split_handoffs_require_current_point_evidence(tmp_path, agent, legacy_status):
    workflow = (REPO_ROOT / "agents" / (agent + ".md")).read_text().split("<!-- RAT_POLICIES_BEGIN")[0]
    command, = [s for s in workflow.split("`") if s.startswith("python3 {plugin_root}/scripts/gates/phase_gate.py ")]
    argv = [arg.replace("{plugin_root}", str(REPO_ROOT)).replace("<project>", str(tmp_path))
            for arg in shlex.split(command)]
    report = tmp_path / "reviews/phase-5-verify/final-compliance.md"
    report.parent.mkdir(parents=True)
    report.write_text("Verdict: PASS")
    assert subprocess.run(argv, capture_output=True, timeout=10).returncode == legacy_status

    docs = tmp_path / "docs/phase-5-verify"
    docs.mkdir(parents=True)
    (docs / "judgment.json").write_text(json.dumps({
        "confidence": "high", "material_ambiguities": [], "simulation_runs": ["missing-run"],
    }))
    result = subprocess.run(argv, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert any(not check["passed"] and "point" in check["check"]
               for check in json.loads(result.stdout)["checks"])


def p1(root, judgment):
    docs=root/'docs/phase-1-research';docs.mkdir(parents=True)
    for name,data in {'iron-requirements.json':{'requirements':[{'id':'REQ-F-001','acceptance_criteria':'sum includes carry'}]},
                      'open-requirements.json':[], 'io_definition.json':{},'judgment.json':judgment}.items():
        (docs/name).write_text(json.dumps(data))
    (docs/'feature-coverage.md').write_text('REQ-F-001: covered')
    review=root/'reviews/phase-1-research';review.mkdir(parents=True)
    (review/'research-review.md').write_text('Verdict: PASS')


@pytest.mark.parametrize('confidence,ambiguities,decision,expected',[
    ('high',[],None,0),
    ('high',[{'id':'REQ-F-001','status':'open','resolution':''}],None,1),
    ('low',[],None,1),
    ('low',[{'id':'REQ-F-001','status':'user_confirmed','resolution':'retain 9-bit carry'}],'retain carry',0),
])
def test_ambiguity_is_not_cleared_by_confidence(tmp_path,confidence,ambiguities,decision,expected):
    p1(tmp_path,{'confidence':confidence,'material_ambiguities':ambiguities,'user_decision':decision})
    result=script('gates/phase_gate.py','--root',tmp_path,'--phase',1)
    assert result.returncode==expected,result.stderr


def test_verification_item_requires_an_expected_result(tmp_path):
    (tmp_path/'docs/phase-5-verify').mkdir(parents=True)
    judgment=tmp_path/'docs/phase-5-verify/judgment.json'
    judgment.write_text(json.dumps({'confidence':'high','material_ambiguities':[],
        'verification_items':[{'id':'AC-007','requirement':'REQ-P-001'}]}))
    (tmp_path/'reviews/phase-5-verify').mkdir(parents=True)
    (tmp_path/'reviews/phase-5-verify/final-compliance.md').write_text('PASS')
    result=script('gates/phase_gate.py','--root',tmp_path,'--phase',5)
    assert result.returncode==1
    assert any(c['check']=='verification oracles' and not c['passed'] for c in json.loads(result.stdout)['checks'])


@pytest.mark.parametrize('body,expected', [
    ('PASS', 0),
    ('# Final compliance\n- **Verdict**: PASS\n\nAll checks completed.', 0),
    ('verdict=PASS', 0),
    ('# Final compliance\nPASS is required for entry.', 1),
    ('- Verdict: PASS\n- Verdict: FAIL', 1),
    ('Verdict: PASS with exceptions', 1),
    ('```markdown\nVerdict: PASS\n```', 1),
    ('    Verdict: PASS', 1),
])
def test_phase_six_requires_a_single_explicit_compliance_verdict(tmp_path, body, expected):
    path = tmp_path / 'reviews/phase-5-verify/final-compliance.md'
    path.parent.mkdir(parents=True)
    path.write_text(body)
    result = script('gates/phase_gate.py', '--root', tmp_path, '--phase', 6, '--entry')
    assert result.returncode == expected, result.stdout + result.stderr
    assert json.loads(result.stdout)['scope'] == 'entry'


@pytest.mark.parametrize('ambiguities', [[None], [False], {}, [{'status':'resolved','resolution':'x'}],
                                         [{'id':'req','status':'resolved','resolution':'  '}]])
def test_malformed_judgments_fail_with_a_structured_report(tmp_path, ambiguities):
    p1(tmp_path, {'confidence':'high', 'material_ambiguities':ambiguities})
    result = script('gates/phase_gate.py', '--root', tmp_path, '--phase', 1)
    assert result.returncode == 1, result.stderr
    assert any(c['check'] == 'material ambiguity accounted for' and not c['passed']
               for c in json.loads(result.stdout)['checks'])


def test_nested_filelist_preserves_package_and_include_order(tmp_path):
    for name in ('z_pkg.sv','a_dut.sv'):(tmp_path/name).write_text('')
    for name in ('first','second'):(tmp_path/name).mkdir()
    (tmp_path/'nested.f').write_text('+incdir+second\na_dut.sv\n')
    (tmp_path/'top.f').write_text('+incdir+first\nz_pkg.sv\n-f nested.f\n')
    flat=tmp_path/'flat.f'
    result=script('verify_evidence.py','inputs','--root',tmp_path,'--filelist','top.f','--write-filelist',flat)
    assert result.returncode==0,result.stderr
    lines=flat.read_text().splitlines()
    assert lines==['+incdir+'+str(tmp_path/'first'),'+incdir+'+str(tmp_path/'second'),
                   str(tmp_path/'z_pkg.sv'),str(tmp_path/'a_dut.sv')]


def test_exclusion_approval_is_bound_to_current_set(tmp_path):
    folder=tmp_path/'reviews/phase-5-verify';folder.mkdir(parents=True)
    manifest=folder/'coverage-exclusions.json'
    rows=[{'id':'bin-1','requires_user_approval':True,'reason':'out of scope'}]
    manifest.write_text(json.dumps({'exclusions':rows}))
    assert script('coverage_approval.py','check','--root',tmp_path).returncode==1
    assert script('coverage_approval.py','approve','--root',tmp_path,'--decision','User approved bin-1').returncode==0
    assert script('coverage_approval.py','check','--root',tmp_path).returncode==0
    rows.append({'id':'bin-2','requires_user_approval':True,'reason':'spec ambiguity'})
    manifest.write_text(json.dumps({'exclusions':rows}))
    assert script('coverage_approval.py','check','--root',tmp_path).returncode==1


def test_exclusion_category_column_is_not_a_reason_keyword_search(tmp_path):
    folder=tmp_path/'reviews/phase-5-verify';folder.mkdir(parents=True)
    path=folder/'top-coverage-exclusions.md'
    path.write_text('| Bin | Reason | Category |\n|---|---|---|\n| x | not ambiguous | Parameter guards |\n')
    assert script('coverage_approval.py','check','--root',tmp_path).returncode==0
    path.write_text(path.read_text()+'| y | pending scope | Out-of-scope |\n')
    assert script('coverage_approval.py','check','--root',tmp_path).returncode==1


def tracked_project(root):
    state=root/'.rat/state';state.mkdir(parents=True)
    (root/'rtl').mkdir()
    (root/'rtl/dut.sv').write_text('module dut; endmodule')
    (state/'rtl-modified-files.txt').write_text('rtl/dut.sv\n')
    return state


def test_stop_budgets_do_not_cross_sessions(tmp_path):
    state=tracked_project(tmp_path)
    hook=REPO_ROOT/'hooks/rtl-verify-stop-gate.sh'
    first={'cwd':str(tmp_path),'session_id':'session-A','prompt_id':'p','stop_hook_active':False}
    assert run_hook(hook,first,env={'RAT_STOP_BLOCK_LIMIT':'1'}).get('decision')=='block'
    continued={**first,'stop_hook_active':True}
    assert run_hook(hook,continued,env={'RAT_STOP_BLOCK_LIMIT':'1'}).get('systemMessage')
    second={**first,'session_id':'session-B'}
    assert run_hook(hook,second,env={'RAT_STOP_BLOCK_LIMIT':'1'}).get('decision')=='block'
    assert len(list(state.glob('stop-budget-verify-*.txt')))==2


def test_linked_state_does_not_truncate_external_file(tmp_path):
    root=tmp_path/'project';root.mkdir();state=tracked_project(root)
    victim=tmp_path/'victim';victim.write_text('keep this')
    (state/'stop-budget-verify.txt').symlink_to(victim)
    run_hook(REPO_ROOT/'hooks/rtl-verify-stop-gate.sh',{'cwd':str(root)})
    assert victim.read_text()=='keep this'


def test_hook_owned_team_identity_ignores_authored_leader(tmp_path):
    state=tracked_project(tmp_path)
    config=state/'team-config.json'
    config.write_text(json.dumps({'team_mode':True,'leader_session_id':'wrong-session'}))
    payload={'cwd':str(tmp_path),'session_id':'real-leader','tool_input':{'file_path':str(config)}}
    run_hook(REPO_ROOT/'hooks/rtl-team-owner.sh',payload)
    assert json.loads((state/'team-owner.json').read_text())['session_id']=='real-leader'
    result=run_hook(REPO_ROOT/'hooks/rtl-verify-stop-gate.sh',{'cwd':str(tmp_path),'session_id':'real-leader'})
    assert result.get('decision')=='block'


def test_user_decision_precedes_active_automatic_loop(tmp_path):
    state=tracked_project(tmp_path)
    (state/'rat-auto-design-state.json').write_text(json.dumps({'status':'in_progress',
        'orchestration_control':{'needs_user_decision':True}}))
    (state/'ultraloop-state.json').write_text(json.dumps({'mode':'ultraloop',
        'last_cycle_timestamp':int(time.time()),'auto_continue_minutes':30}))
    result=run_hook(REPO_ROOT/'hooks/stop-gate.sh',{'cwd':str(tmp_path)})
    assert result.get('systemMessage')
    assert 'needs your decision' in result['systemMessage']
    assert result.get('decision')!='block'


def test_unknown_readiness_scope_is_not_ready(tmp_path):
    result=script('eda_runner.py','capabilities','--root',tmp_path,'--phase','unknown')
    assert result.returncode!=0
    assert 'unknown readiness phase' in result.stderr


def test_p1_readiness_does_not_require_eda(tmp_path):
    result=script('eda_runner.py','capabilities','--root',tmp_path,'--phase','p1')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['capabilities']=={}


def test_generated_policy_sources_match_runtime_agents():
    result=script('sync_agent_policies.py','--check')
    assert result.returncode==0,result.stdout
    assert not list((REPO_ROOT/'skills').glob('*policy/SKILL.md'))
    assert not list((REPO_ROOT/'agents').glob('*team-orchestrator.md'))
