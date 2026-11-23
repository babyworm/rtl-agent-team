#!/usr/bin/env python3
"""Approve the current non-standard exclusion set, bound to its content fingerprint."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from verify_evidence import atomic_json, runtime_state_root


def exclusion_set(root):
    directory=root/'reviews/phase-5-verify'
    manifest=directory/'coverage-exclusions.json'
    records=[]
    if manifest.is_file():
        data=json.loads(manifest.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('exclusions'),list):
            raise ValueError('coverage-exclusions.json must be an object with an exclusions list')
        for item in data['exclusions']:
            if not isinstance(item,dict):
                raise ValueError('each exclusion entry must be a JSON object')
            if item.get('requires_user_approval'):
                records.append(item)
    else:
        for path in sorted(directory.glob('*-coverage-exclusions.md')):
            category=None
            for line in path.read_text().splitlines():
                if not line.lstrip().startswith('|'):category=None;continue
                cells=[c.strip().strip('*`').strip() for c in line.strip().strip('|').split('|')]
                headings=[c.lower() for c in cells]
                if 'category' in headings:
                    category=headings.index('category');continue
                if category is None or category>=len(cells):continue
                kind=re.sub(r'[-_]+',' ',cells[category].lower())
                if re.fullmatch(r'(?:unimplemented(?: features?)?|out of scope|ambiguous(?: spec applicability)?|spec ambiguity)',kind):
                    records.append({'file':str(path.relative_to(root)),'cells':cells})
    records.sort(key=lambda item:json.dumps(item,sort_keys=True))
    fingerprint=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return records,fingerprint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','approve'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--decision',help='User confirmation text, required to record an approval')
    a=p.parse_args();root=a.root.resolve();records,fingerprint=exclusion_set(root)
    marker=runtime_state_root(root)/'state/coverage-exclusion-approved.json'
    if a.command=='approve':
        if not a.decision:p.error('--decision must contain the user confirmation')
        atomic_json(marker,{'schema_version':1,'fingerprint':fingerprint,'exclusions':records,'user_decision':a.decision})
        return 0
    try:
        loaded=json.loads(marker.read_text())
        approval=loaded if isinstance(loaded,dict) else {}
    except (OSError,ValueError):approval={}
    approved=bool(approval.get('user_decision')) and approval.get('fingerprint')==fingerprint
    print(json.dumps({'count':len(records),'fingerprint':fingerprint,'approved':approved,'records':records}))
    return 0 if not records or approved else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
