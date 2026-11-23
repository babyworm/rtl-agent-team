#!/usr/bin/env python3
"""Exercise unit/integration template PASS, mismatch, zero-check and timeout paths."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PLUGIN=Path(__file__).resolve().parents[2]


def check(workspace, verilator):
    results=[]
    env={**os.environ,'PATH':str(verilator.parent)+os.pathsep+os.environ['PATH']}
    for kind,relative,top,summary in [
        ('unit','skills/rtl-p4s-unit-test/templates/sv-testbench-template.sv','tb_dut','    // ─── Summary'),
        ('integration','skills/rtl-p5s-integration-test/templates/integration-tb-template.sv','integration_tb_dut','    // ── Summary'),
    ]:
        root=workspace/kind;(root/'rtl').mkdir(parents=True,exist_ok=True);(root/'sim').mkdir(exist_ok=True)
        dut=root/'rtl/dut.sv';tb=root/'sim/tb.sv'
        dut.write_text('module dut(input logic sys_clk, input logic sys_rst_n); wire ready=sys_rst_n; endmodule\n')
        body=(PLUGIN/relative).read_text().replace('{{MODULE_NAME}}','dut').replace('{{TOP_NAME}}','dut').replace('{{DOMAIN}}','sys')
        stimulus='''    if ($test$plusargs("WAIT_FOR_TIMEOUT")) wait (1'b0);
    if (!$test$plusargs("NO_CHECKS")) begin
      if ($test$plusargs("NEGATIVE")) check("reset release",u_dut.ready,0);
      else check("reset release",u_dut.ready,1);
    end
'''
        assert summary in body;tb.write_text(body.replace(summary,stimulus+summary,1))
        command=['bash',str(PLUGIN/'scripts/run_sim.sh'),'--sim','verilator','--top',top,
                 '--tool-args','-Wno-fatal -j 2',str(dut),str(tb)]
        for name,flags,expected in [
            ('pass',[],'PASS'),('mismatch',['--run-only','--sim-args','+NEGATIVE'],'FAIL'),
            ('zero_checks',['--run-only','--sim-args','+NO_CHECKS'],'FAIL'),
            ('timeout',['--run-only','--timeout','20','--sim-args','+WAIT_FOR_TIMEOUT'],'TIMEOUT'),
        ]:
            run=subprocess.run(command+flags,cwd=root,env={**env,'RAT_PROJECT_ROOT':str(root)},
                               text=True,capture_output=True,timeout=180)
            (root/(name+'.log')).write_text(run.stdout+run.stderr)
            record=json.loads((root/'.rat/state/verify-evidence.json').read_text())['runs'][-1]
            passed=record['verdict']==expected and (run.returncode==0)==(expected=='PASS')
            results.append({'template':kind,'case':name,'exit_code':run.returncode,
                            'verdict':record['verdict'],'expected':expected,'passed':passed})
            (workspace/'results.json').write_text(json.dumps(results,indent=2)+'\n')
            print(f'{kind} {name}: {record["verdict"]} (exit={run.returncode})',flush=True)
            if not passed:
                print((run.stdout+run.stderr)[-3000:]);raise ValueError('template verdict mismatch')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verilator',type=Path,default=shutil.which('verilator'))
    p.add_argument('--workdir',type=Path)
    a=p.parse_args()
    if not a.verilator:p.error('Verilator is required')
    if a.workdir:
        a.workdir.mkdir(parents=True,exist_ok=True)
        check(a.workdir.resolve(),Path(a.verilator).resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='rat-template-eval-') as folder:
            check(Path(folder),Path(a.verilator).resolve())

if __name__=='__main__':main()
