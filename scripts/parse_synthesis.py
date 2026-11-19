#!/usr/bin/env python3
"""Call the synthesis report parsers directly, without an agent wrapper."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

PLUGIN=Path(__file__).resolve().parents[1]


def load(path):
    spec=importlib.util.spec_from_file_location('rat_synthesis_parser',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--tool',choices=['yosys','dc_shell','genus'],required=True)
    p.add_argument('--log',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args();root=args.root.resolve()
    output=args.output or root/'syn/summary.json'
    if args.tool=='yosys':
        if not args.log: p.error('--log is required for Yosys')
        module=load(PLUGIN/'skills/rtl-synth-check/scripts/parse_yosys_stat.py')
        config=root/'rat_config.json'
        tech=json.loads(config.read_text()).get('technology',{}) if config.is_file() else {}
        result=module.parse_stat_output(args.log.read_text())
        area=tech.get('nand2_area_um2')
        result.update(technology=tech.get('target') or 'unspecified',library=tech.get('liberty') or None,
                      nand2_area_um2=area, gate_count_nand2=round(result['area_um2']/area) if area and result['area_um2'] is not None else None)
        result['verdict']=module.generate_verdict(result)
    else:
        module=load(PLUGIN/'skills/rtl-ppa-optimize-dc/scripts/parse_dc_reports.py')
        result=module.run(root/'syn/rpt',output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(output)
    return int(str(result.get('verdict','')).startswith('FAIL'))

if __name__=='__main__': raise SystemExit(main())
