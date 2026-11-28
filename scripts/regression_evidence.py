#!/usr/bin/env python3
# rat-version: 1.0.0-pre20
"""Bind regression evidence to the sources expanded by the actual cocotb Makefile."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

from verify_evidence import begin, POINT_PLAN, runtime_state_root


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--tb-dir',type=Path,required=True)
    p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--tool',required=True)
    p.add_argument('--top',required=True)
    p.add_argument('--seeds',default='')
    p.add_argument('--runner-pid',type=int,required=True)
    args=p.parse_args();root=args.root.resolve();tb=args.tb_dir.resolve()
    helper=Path(__file__).with_name('eda_runner.py')
    # A unique dry target expands the same Makefile variables without compiling.
    probes=runtime_state_root(root)/'source-probes';probes.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-',dir=probes) as directory:
        work=Path(directory)
        probe=work/'probe.mk';dump=work/'sources.txt'
        probe.write_text('.PHONY: rat_evidence_inputs\nrat_evidence_inputs:\n\t$(file >$(RAT_SOURCE_DUMP),$(VERILOG_SOURCES))@:\n')
        status=subprocess.run([os.environ.get('RAT_PYTHON','python3'),str(helper),'run','--root',str(root),'--',
            'make','--no-print-directory','-s','-C',str(tb),'-f','Makefile','-f',str(probe),
            'rat_evidence_inputs','SIM='+args.tool,'RAT_SOURCE_DUMP='+str(dump)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={**os.environ,'RAT_CONTEXT_TOOL':args.tool},timeout=30)
        if status.returncode or not dump.is_file():
            raise ValueError('cannot expand VERILOG_SOURCES; declare sources in the test Makefile before a gating regression')
        values=shlex.split(dump.read_text())
        sources=[str((tb/value).resolve()) for value in values]
        if not sources: raise ValueError('VERILOG_SOURCES is empty; no source-bound functional evidence is possible')
        # Test oracle and build files are dependencies too, not claimed RTL coverage.
        dependencies=[str(path) for path in tb.rglob('*') if path.is_file() and path != root / POINT_PLAN and
                      (path.suffix in ('.py','.mk','.json') or path.name=='Makefile') and
                      not any(part in ('__pycache__','build','sim_build','regression') for part in path.relative_to(tb).parts)]
        config=root/'rat_config.json'
        if config.is_file():dependencies.append(str(config))
        scope=argparse.Namespace(root=str(root),outdir=str(args.outdir.resolve()),tool=args.tool,top=args.top,
            runner_pid=args.runner_pid,source=sources,filelist='',dependency=dependencies,run_only=False,
            compile_only=False,artifact=[],context='cocotb Makefile; SIM='+args.tool,include_dir=[],seeds=args.seeds,
            runtime_args=json.dumps({key: os.environ[key] for key in
                ('TESTCASE', 'COCOTB_TESTCASE', 'COCOTB_TEST_FILTER', 'COCOTB_TEST_MODULES', 'MODULE')
                if key in os.environ}, sort_keys=True))
        return begin(scope)

if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print('regression evidence error: '+str(exc),file=__import__('sys').stderr)
        raise SystemExit(2)
