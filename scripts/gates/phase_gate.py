#!/usr/bin/env python3
"""Check handoff artifacts and recorded judgments; never infer a functional PASS."""
import argparse
import json
from pathlib import Path
import re
import sys

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / 'scripts'))
from verify_evidence import atomic_json, POINT_PLAN
from gates.simulation_points import check_p3_criteria, simulation_point_checks

PHASE_DIRS = {1:'phase-1-research',2:'phase-2-architecture',3:'phase-3-uarch',
              4:'phase-4-rtl',5:'phase-5-verify',6:'phase-6-review'}
P5_REPORT = 'reviews/phase-5-verify/final-compliance.md'
VERDICT_FIELD = re.compile(r'(?i) {0,3}(?:[-*]\s+)?\**verdict\**\s*[:=]\s*\**(.*?)\**\s*')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')


def p5_report_passes(path):
    if not path.is_file():
        return False
    text = path.read_text(encoding='utf-8')
    if text.strip().upper() == 'PASS':
        return True
    verdicts = []
    fence = None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        field = VERDICT_FIELD.fullmatch(line)
        if field:
            verdicts.append(field[1].upper())
    return verdicts == ['PASS']


def settled_items(items):
    return isinstance(items, list) and all(
        isinstance(item, dict) and item.get('status') in ('resolved', 'user_confirmed')
        for item in items
    )


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def evaluate(root, phase, entry=False):
    registry = json.loads((PLUGIN / 'phase-registry.json').read_text())
    checks = []
    def check(name, passed, reason=''):
        checks.append({'check':name,'passed':bool(passed),'reason':reason})
    if entry:
        for item in registry['phases'].get(str(phase),{}).get('required',[]):
            check(item['role'], any(root.glob(item['path'])), item['path'])
    else:
        directory = root / 'docs' / PHASE_DIRS[phase]
        for pattern in registry['handoff_artifacts'][str(phase)]:
            matches = [p for p in root.glob(pattern) if p.is_file() and p.stat().st_size]
            check('artifact:' + pattern, bool(matches))
            for path in matches:
                if path.suffix != '.json': continue
                try:
                    data=json.loads(path.read_text())
                    if path.name == 'iron-requirements.json':
                        items = data.get('requirements', data.get('iron_requirements', [])) if isinstance(data,dict) else data
                        valid_items = isinstance(items, list) and all(isinstance(item, dict) for item in items)
                        check('requirements:' + str(path.relative_to(root)), valid_items and bool(items))
                        if valid_items:
                            for item in items:
                                check('acceptance:' + str(item.get('id','?')), bool(item.get('acceptance_criteria')))
                    elif path.name == 'open-requirements.json' and phase == 3:
                        items = data.get('open_requirements',data.get('requirements')) if isinstance(data,dict) else data
                        check('zero unresolved opens', settled_items(items))
                except (ValueError,AttributeError,TypeError) as exc:
                    check('json:' + str(path.relative_to(root)),False,str(exc))
        if phase in (1,2,3,5):
            path=directory/'judgment.json'
            try:
                judgment=json.loads(path.read_text())
                ambiguities=judgment['material_ambiguities']
                check('recorded confidence',judgment['confidence'] in ('high','low'))
                check('material ambiguity accounted for', settled_items(ambiguities) and all(
                    nonempty_text(item.get('id')) and nonempty_text(item.get('resolution')) for item in ambiguities))
                check('judgment settled',judgment['confidence']=='high' or nonempty_text(judgment.get('user_decision')))
                if phase == 5:
                    items=judgment.get('verification_items',[])
                    check('verification oracles',isinstance(items,list) and all(
                        isinstance(item, dict) and all(nonempty_text(item.get(key))
                        for key in ('id', 'requirement', 'expected_result')) for item in items))
            except (OSError,ValueError,KeyError,TypeError):
                check('judgment record',False,str(path.relative_to(root)))
    has_plan = (root / POINT_PLAN).exists()
    if not entry and phase == 3:
        if has_plan:
            checks.extend(simulation_point_checks(root, plan_only=True))
        else:
            try:
                check_p3_criteria(root, {})
            except (OSError, ValueError) as exc:
                check('simulation point plan', False, str(exc))
    needs_point_evidence = phase == 5 and not entry
    if phase == 6:
        judgment_path = root / 'docs/phase-5-verify/judgment.json'
        try:
            needs_point_evidence = has_plan or (judgment_path.exists() and
                'simulation_runs' in json.loads(judgment_path.read_text()))
        except (OSError, ValueError, TypeError) as exc:
            check('P5 judgment', False, str(exc))
    if needs_point_evidence:
        checks.extend(simulation_point_checks(root))
    if phase == 6 or (phase == 5 and not entry):
        try:
            check('P5 compliance', p5_report_passes(root / P5_REPORT), P5_REPORT)
        except (OSError, ValueError) as exc:
            check('P5 compliance', False, str(exc))
    return {'schema_version':1,'phase':phase,'scope':'entry' if entry else 'handoff',
            'verdict':'PASS' if all(c['passed'] for c in checks) else 'FAIL','checks':checks}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--phase',type=int,choices=range(1,7),required=True)
    parser.add_argument('--entry',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=evaluate(args.root.resolve(),args.phase,args.entry)
    if args.output: atomic_json(args.output,report)
    print(json.dumps(report))
    return int(report['verdict']!='PASS')

if __name__=='__main__': raise SystemExit(main())
