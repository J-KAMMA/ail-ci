# job job-spec1-11030015  started 2026-11-02T15:18:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Final report

- **Outcome: no code landed.** The task’s stop rule applies: safe specialization gains are below 1.2×.
- **tally_lang profile** (`gprof`, 2 runs; perf/callgrind unavailable): `ev` 83.9%, parallel-list span work ≈25%, recursion check ≈6.4%, `py_run__try1` 16.1%.
- **Prototype gains** (hand edits of `/tmp` generated C, paired medians): popcount idiom 1.027×, shared span check 1.054× → safe combined ≈1.08×. Removing bounds + recursion checks reaches 1.305× but is not admissible and is still 4% slower than C (1194 ms vs 1148 ms).
- **Output check:** base and the unsafe max prototype match `reference.py` on all 76 tally cases; 0 mismatches.
- **echo_pack:** `pack` 92.6%; int-key hash table ≈46% of line samples; AIL 1077 ms vs C 613 ms (1.76×), RSS 354 vs 179 MiB.
- **Cost:** no shipped code; prototype binary +8 bytes, same RSS, same compile time.
- **Records:** `docs/design/SPEC1.md`, top `DEVLOG.md` entry, `DIFFERENCES.md` row, raw JSON in `lab/beatc/results/spec1-*`.
- **Tests on final commit `c4fafb0`:** `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (0 failed, 436 s).
- **Probes:** none needed for behaviour, since no behaviour changed; instead the output-equality check above covered all tally public/hidden/perf cases. Not pushed.
[cost $0.0000, opencode tokens {"total": 7302421, "input": 407076, "output": 16223, "reasoning": 23698, "cache.write": 0, "cache.read": 6855424}]
    tool time: bash 25.1 min, edit 0.0 min, write 0.0 min
        438s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u && time python3 ../tools/par_check.py -j 2 test_ail_
        407s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date -u && time python3 ../tools/par_check.py -j 2 test_ail_
        128s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/measure.py --tasks tally_lang,echo_pack --runs 5 --out
         73s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/profile.py --tasks echo_pack --runs 2 --out /tmp/spec1
         71s bash   cd /tmp/spec1 && python3 - <<'PY' src=open('dbg/program.c').read() def nokeep(s): return s.replace('        ai
         64s bash   cd /tmp/spec1 && python3 - <<'PY' import subprocess,time,statistics vs=['base','pop','cache','bounds','max'] r
         60s bash   cd /tmp/spec1 && python3 - <<'PY' src=open('program_bounds.c').read() start=src.index('int64_t ev(ail_obj_Prog
         52s bash   cd /tmp/spec1 && python3 - <<'PY' import subprocess,time,statistics vs=['base','bounds','depth','pop','all'] r

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** records only. It adds `docs/design/SPEC1.md`, a top `DEVLOG.md` entry, one measurement row in `DIFFERENCES.md`, and three raw result JSONs. `git diff work..HEAD -- AIL_CURRENT tools` is empty, so the compiler, runtime and generated C are untouched. This matches the report.

**Checks**
- Records: `tools/update_manifest.py --check` passes; DIFFERENCES placeholder matches the branch; no test module was added.
- Tests on HEAD `c4fafb0`: `test_ail_safetynet test_ail_files test_ail_corpus_findings3` -> 3 modules, 631s, 0 failed.
- Output equality: generated all 76 `tally_lang` cases from `gen.py`; `base`, `max`, `cache`, `pop` each matched `reference.py` stdout and exit status (0 mismatches).
- Data: JSON confirms `ev` 83.86% / `py_run__try1` 16.14%, `echo_pack` `pack` 92.59%, tally AIL/C 1542.4/1147.5 ms, echo AIL/C 1077.4/613.4 ms.
- Speed re-check: existing `/tmp` prototypes, 7 interleaved pinned-core rounds: `cache` ~1.09x, `pop` ~1.07x, `cache+pop` ~1.06x, `max` ~1.46x, C ~1.70x vs base. The safe-gain-below-1.2x conclusion holds; exact 1.054x/1.027x/1.305x figures were not reproduced under runner noise.
- No behaviour probes are applicable because no behaviour changed; the diff proves generated C cannot change.

**Claim status**
- Verified: no code landed; profile shares; AIL/C wall times; echo_pack share; 76-case output equality; tests on final commit; zero shipped cost.
- Unverified: exact prototype ratios; instruction counts (perf denied with `perf_event_paranoid=4`, no callgrind); echo_pack direct-mapped-table characterization; "max is 4% slower than C" not reproduced exactly (my run ~16% slower, still slower, so the conclusion is unchanged).

**Pre-existing:** none relevant (no source change).

**Unverified:** 10-task matrix (not applicable without landed code), exact prototype timings, hardware instruction counts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 852918, "input": 83855, "output": 5143, "reasoning": 12432, "cache.write": 0, "cache.read": 751488}]
    tool time: bash 15.5 min
        633s bash   date -u; time python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2
        150s bash   cd /tmp/spec1 && python3 - <<'PY' import subprocess,time,statistics vs=['prog_base','prog_cache','prog_pop','p
         88s bash   cd /tmp/spec1 && python3 - <<'PY' import subprocess,time,statistics,os vs=['prog_base','prog_cache','prog_pop'
         25s bash   cd /tmp/spec1 && python3 - <<'PY' import importlib.util,random,subprocess,tempfile,os,sys spec=importlib.util.
         24s bash   cd /tmp/spec1 && python3 - <<'PY' import importlib.util,random,subprocess,tempfile,os,sys spec=importlib.util.
          4s bash   cd /tmp/spec1 && ./prog_base perf.bin > /tmp/spec1/chk.out 2>/tmp/spec1/chk.err; echo rc=$?; wc -c chk.out; cm
          2s bash   cd /tmp/spec1 && python3 - <<'PY' import re src=open('program_cache.c').read() new='int64_t popcnt(int64_t v_x
          1s bash   python3 tools/update_manifest.py --check; echo "rc=$?"

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T17:25:17Z
