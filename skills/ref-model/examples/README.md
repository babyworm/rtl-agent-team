# run_ref_model.py Worked Example

Demonstrates the build-and-run wrapper for the Phase 2 C reference model
(Execution steps 3-4 automation: build the golden model, run it, capture a
JSON run report).

| File | Role |
|------|------|
| `sat_add/refc/sat_add_ref.c` | Input: self-testing 8-bit saturating adder (golden vectors embedded in `main()`, returns 0 on pass). |
| `sat_add/refc/include/sat_add_ref.h` | Model header — pure functional, C11, DPI-C compatible, `PARALLEL_LANES` parameterizable. |
| `sat_add/refc/Makefile` | Build file — `run_ref_model.py` invokes the default target and auto-detects the binary under `build/`. |
| `sat_add/expected_run_report.json` | Output: committed run report produced by the command below (regeneration-checked by `tests/unit/test_model_runners.py`). |

## Command

Run from `sat_add/`:

```sh
python3 ../../scripts/run_ref_model.py --refc-dir refc --report run_report.json
```

Expected stdout:

```
Build: make OK
Run: refc/build/sat_add_ref exit=0 PASS
Report written: run_report.json
```

Exit code 0 = build + run OK (model exited 0); 1 = build failed or the
model returned non-zero (report still written); 2 = environment/usage error
(no refc dir, no compiler/make, no runnable binary).

## What to check in the output

- `build_mode` is `make` (Makefile preferred; without one the script falls
  back to a direct `cc -std=c11 -O2 -Wall -Wextra` compile of `refc/*.c`
  into `refc/build/ref_model`).
- All command fields are argv lists with paths recorded exactly as given
  (relative in, relative out — never resolved to absolute paths).
- `stdout_tail` carries the model's deterministic self-test lines; the
  model's exit code lands in `exit_code`.
- `output_files` is empty here because the self-test writes no file; pass
  `--input`/`--output` to forward file arguments to the model — the
  `--output` file is then recorded with its byte size.
- `duration_seconds` is the only non-deterministic field on this example —
  the regeneration-sync test excludes it and compares everything else.
