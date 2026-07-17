# run_bfm.py Worked Examples

Two examples with different prerequisites:

| Directory | Role | Prerequisite |
|-----------|------|--------------|
| `axi_stream_stub/` | Minimal SystemC TLM-2.0 LT BFM skeleton in the runnable shape run_bfm.py expects (Makefile referencing `$(SYSTEMC_HOME)`, `src/*.cpp`, `run` target writing `smoke_test_result.txt`). | **Local SystemC install** — NOT built in CI or by tests. |
| `selfcheck_fake_build/` | SystemC-free fixture: `all`/`run` targets are plain sh, so the wrapper's orchestration (build detection, `make run`, artifact capture, JSON report) runs anywhere `make` exists. | `make` only — regeneration-checked by `tests/unit/test_model_runners.py`. |

## axi_stream_stub (requires SystemC locally)

```sh
export SYSTEMC_HOME=/path/to/systemc   # install root containing include/ and lib*/
cd axi_stream_stub
python3 ../../scripts/run_bfm.py --bfm-dir . --report run_report.json
```

Without `SYSTEMC_HOME` exported, run_bfm.py exits 2 before building, with
install guidance — the Makefile references `$(SYSTEMC_HOME)`, and SystemC is
a hard local prerequisite (see the skill's Escalation rules). The stub sends
one LT write transaction end-to-end and writes a
`smoke_test_result.txt`-shaped verdict (`PASS` / `transport=LT` /
`latency=10ns` / `transactions=1`).

## selfcheck_fake_build (runs anywhere)

Run from `selfcheck_fake_build/`:

```sh
python3 ../../scripts/run_bfm.py --bfm-dir . --report run_report.json
```

Expected stdout:

```
Build: make OK
Run: make run exit=0 PASS
Report written: run_report.json
```

`expected_run_report.json` is the committed report for this command. Two
fields are normalized placeholders excluded from the regeneration-sync
comparison: `duration_seconds` (timing) and `systemc_home_set`
(host-dependent). Everything else — build system detection, argv lists,
`make run` routing, deterministic `stdout_tail`, and the captured
`smoke_test_result.txt` artifact with byte size — must match exactly.

Exit code contract (both examples): 0 = build + run OK; 1 = build failed or
run returned non-zero (report still written); 2 = environment/usage error
(no bfm dir, no build system, missing cmake/make, `SYSTEMC_HOME` required
but unset, no runnable binary).
