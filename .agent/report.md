# job job-pycomp1-11040105  started 2026-11-03T16:07:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds pinned Codon 0.20.6, mypy 2.4.1 (mypyc) and Nuitka 4.3.4 to compare-lab: workflow install, `toolchains.env` pins, `run_task.py` build/run paths (Codon gets a `compat/codon/ail.py` shim), `merge.py --langs`, and `docs/COMPARISON-PYCOMP.md`. It touches no compiler or runtime source.

**Probes run** (real tools installed from the new pins; same runner image as the worker):
- `chain_relax` smoke, python+mypyc+nuitka+codon: 32/32 each, reference match.
- `berth_sim`, `ledger_bin`, `tally_lang`, `term_rank` smoke, mypyc+codon: all public+hidden match.
- `echo_pack`, `rail_transfer`, `ticket_audit` mypyc+codon: `echo_pack` mypyc fails `bytearray is not a valid sequence`; `rail_transfer`/`ticket_audit` Codon fail — as reported.
- `echo_pack`, `ledger_bin` nuitka smoke: all cases match.
- `chain_relax` perf, ail/codon/mypyc/python: 1432/1300/10356/11097 ms; docs 1437/1358/10267/11218 — reproduced.
- Codon int overflow probe: wraps exactly like AIL; chain_relax `seed_max` hidden case matched.
- Codon tarball sha256 matches the workflow line; pip pins install; `check_tools.py --langs codon,mypyc,nuitka` passes.
- `tools/update_manifest.py --check`: ok. `test_ail_safetynet`: 187 s, 0 failed.

**Claims.** Verified: pins/install, same `typed.py`, build failures, correctness counts for the eight tasks, wall-time spot-check, no Codon 64-bit output difference, no compiler change. **False:** the docs' “valgrind is not installed … instruction counts are not available on this runner” — the workflow installs valgrind (`compare-lab.yml:78`) and even runs `valgrind --version` (`:104`), so callgrind is available. **False:** the generated merge report still says best-other covers “C, Rust, Go, Nim and Python” and “median of 5 runs” after the new columns. **Unverified:** exact wall/RSS/compile numbers for every row, and the `scar_life`/`tree_fold` timeout claims.

**Pre-existing.** None observed; the diff cannot change C output for programs not using the feature.

**Defects.**
1. Instruction counts are missing for every new row (`icount_method: none`, `instructions: null`), and the docs' stated reason is wrong for the compare-lab runner. Probe: `run_task.py` as changed on any completed task, e.g. `chain_relax --langs ail,codon,mypyc,nuitka`; expected `icount_method=callgrind` and a numeric Ir per row (the workflow installs valgrind), actual `none` for all rows.
2. `merge.py` hard-codes the old competitor list and run count, so the workflow's actual report misstates its method. Probe: `python3 lab/compare/merge.py /tmp/rdir --langs ail,ail-py,c,rust,go,nim,python,codon,mypyc,nuitka`; expected “Best-other covers … Codon, mypyc, Nuitka” and “3 runs for the Python compilers”, actual “Best-other covers C, Rust, Go, Nim and Python” and “median of 5 timed runs”.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2120438, "input": 48200, "output": 5240, "reasoning": 28086, "cache.write": 0, "cache.read": 2038912}]
    tool time: bash 23.1 min
        394s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; for t in echo_pack ledge
        261s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; for t in berth_sim ledge
        240s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; time /tmp/pcvenv/bin/pyt
        188s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; timeout 1200
        156s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; timeout 800 /tmp/pcvenv/
        102s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; for t in echo_pack rail_
         28s bash   export PATH=/tmp/pcvenv/bin:/tmp/codon/bin:$PATH; cd /home/runner/work/ail-ci/ail-ci; timeout 300 python3 lab/
         12s bash   python3 -m venv /tmp/pcvenv && /tmp/pcvenv/bin/python -m pip install -q --no-cache-dir 'mypy==2.4.1' 'nuitka==

## worker report 1
[model commandcode/deepseek-v4.1-flash]

## review 1 failed to run: (free quota used up; paid model from here) [model commandcode/deepseek-v4.1-flash] 

## review 1
[model commandcode/deepseek-v4.1-flash]

FINAL VERDICT: ERROR  2026-11-03T21:03:01Z
