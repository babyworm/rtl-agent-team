#!/usr/bin/env python3
"""Keep installed template hashes paired with an explicit rat-version revision."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'template-catalog.json'


def current():
    folder=ROOT/'skills/rat-init-project/templates'
    files=[ROOT/'scripts'/name for name in ('run_sim.sh','verify_evidence.py','eda_runner.py','regression_evidence.py','eda_setup.py','merge_coverpoint_logs.py')]
    files += [ROOT/'hooks/lib/python-util.sh',ROOT/'skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh']
    files += [folder/name for name in ('Makefile','lib/tool-runner.sh','run_cdc.sh','run_lint.sh','run_syn.sh','run_formality.sh','run_conformal.sh')]
    files += list((folder/'rules').glob('*.md'))+list((folder/'guides').glob('*.md'))
    values={}
    for path in sorted(files):
        text=path.read_text();match=re.search(r'rat-version:\s*(\d+\.\d+\.\d+)',text)
        if not match:raise ValueError('missing rat-version: '+str(path.relative_to(ROOT)))
        values[str(path.relative_to(ROOT))]={'version':match[1],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return values


def validate(old,new):
    errors=[]
    for path,entry in new.items():
        prior=old.get(path)
        if prior and prior['sha256']!=entry['sha256'] and tuple(map(int,entry['version'].split('.')))<=tuple(map(int,prior['version'].split('.'))):
            errors.append(path+': content changed without a rat-version bump')
    return errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args();new=current()
    old=json.loads(CATALOG.read_text())['templates'] if CATALOG.is_file() else {}
    errors=validate(old,new)
    if errors:print('\n'.join(errors));return 1
    if args.write:
        CATALOG.write_text(json.dumps({'schema_version':1,'templates':new},indent=2)+'\n');return 0
    if old!=new:print('Template catalog drift; run scripts/template_catalog.py --write after revision bumps.');return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
