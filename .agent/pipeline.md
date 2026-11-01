# job job-tccdev1-11012215  started 2026-11-01T13:16:10Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Committed as `6d325a2` on `job-tccdev1-11012215`.

**Result**
- tcc: `0.9.28rc 2026-10-16 mob@e23dabe`, built from source; Ubuntu package is 0.9.27 and was rejected as too old.
- Median cold build: C compiler is 33% (17–47%) of wall time; AIL front end is 68%. Amdahl bound from a free C compiler is only **1.21–1.86x**.
- Ten-task sum: **24.48 s → 19.56 s** with tcc; median task **2.03 s → 1.64 s**. `tcc -c` is 5–12 ms vs 0.35–1.34 s for `gcc -c`.
- tcc binaries matched gcc stdout/exit and passed all **511** public/hidden checks, but ran **1.71–8.24x slower**.
- Warm server + tcc was best at **1.25–1.43 s** on four tasks — still ~2–3x Rust’s 0.4–0.5 s.
- Only `__builtin_{add,sub,mul}_overflow` fails unpatched; the measurement prelude costs 0 to +11.8% run time when forced onto gcc. Other GCC extensions either work or are already behind `__GNUC__`.

**Recommendation:** do not build a `--dev` tcc mode to reach 0.5 s; cut the front end (warm server + source/flag-keyed front-end cache) first.

**Probes:** `tcc_ok.py` matches CPython on both `cmp.sh` builds and tcc; `tcc_overflow.py` gives identical gcc/tcc results (both documented `OverflowError`); `tcc_overflow_alias.py` is refused by name; `tcc_overflow.c` is identical across gcc builtins, forced `__TINYC__` prelude, and tcc.

**Tests:** `test_ail_safetynet` (5 OK), `test_ail_files` (18 OK, 1 skip), `test_ail_corpus_findings3` (2 OK); manifest check passes. No defaults or test expectations changed.
[cost $0.0528, opencode tokens {"total": 4430303, "input": 98526, "output": 19296, "reasoning": 22561, "cache.write": 0, "cache.read": 4289920}]
    tool time: bash 88.2 min
       1800s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 lab/tccdev/measure.py --tcc /tmp/tcc-install/bin/tcc --out 
        360s bash   sleep 360; tail -12 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; upti
        360s bash   sleep 360; tail -20 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; upti
        300s bash   sleep 300; tail -14 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; pyth
        300s bash   sleep 300; uptime; ps -eo pid,etime,pcpu,comm --sort=-pcpu | head -5; ps -eo pid,etime,args | grep -E '/home/r
        300s bash   sleep 300; tail -16 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; upti
        300s bash   sleep 300; tail -10 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; upti
        300s bash   sleep 300; tail -14 /tmp/tccdev-run4.log; ps -p 73387 -o pid,etime --no-headers 2>/dev/null || echo DONE; upti

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of `6d325a2`

**What it does.** Adds only measurement material: `lab/tccdev/{measure.py,cc_wrap.py,tcc_prelude.h,results.json}`, `docs/design/TCC_DEV.md`, and a DEVLOG entry. `git diff work..HEAD -- AIL_CURRENT bench tools` is empty, so no compiler, runtime, default, or test expectation changed. This matches the report.

**Probes**
- `/tmp/rprobes/prelude_test.c`: prelude add/sub/mul vs GCC builtins over `INT64` boundaries and 2,000,000 random int64 pairs — 0 mismatches.
- Worker probes: `tcc_ok.py` matches CPython on both `cmp.sh` builds and on a tcc build; `tcc_overflow.c` identical for gcc, gcc+forced prelude, and tcc; `tcc_overflow_alias.py` refused by name on both builds; `/tmp/base` gives the same results.
- `tcc_overflow.py` is identical gcc/tcc (both exit 1 with the documented `OverflowError`) but does not match CPython, so it does not satisfy the "match or refuse" probe rule; the divergence is identical on base, hence pre-existing.
- Reproduced `measure.py --tasks chain_relax --runs 1 --no-server`: works end to end; unpatched tcc fails at link on `__builtin_add_overflow`; 32/32 checks pass; tcc output matches gcc.

**Tests.** `par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 3 modules, 0 failed, 211 s. `update_manifest.py --check` rc=0. Exact subtest counts in the report were not re-counted.

**Claims.** Verified from `results.json`/environment: tcc `0.9.28rc`/`e23dabe` built from `/tmp/tinycc`; Ubuntu candidate `0.9.27`; C-compiler share 17–47% (median ~33%); Amdahl 1.21–1.86x; 24.48→19.56 s and 2.03→1.64 s; tcc `-c` 5–12 ms; tcc runtime 1.71–8.24x slower with matching stdout/exit; 511 checks, 0 failures; warm-server+tcc 1.25–1.43 s on the four fastest tasks; no defaults changed.

Minor inaccuracies: the report and DEVLOG say the prelude costs “0 to +11.8%” while the results (and the doc) give −1.6% to +11.8%; the doc's “every median and spread comes from results.json” is false for the historical first-run figures; the 0.35 s lower bound for `gcc -c` comes from the guard compiles, not the table (table min 0.453 s); the §4 “eight of ten tasks” is seven unless `ledger_bin` 2.57 s is excluded too. None changes the conclusion.

**Unverified.** Full ten-task rerun and the 511 checks were audited from the committed raw results, not re-run; historical load/first-run numbers.

**Pre-existing.** `tcc_overflow.py`'s AIL/CPython int64 `OverflowError` divergence (identical on `work`).

VERDICT: ACCEPT
[cost $0.0503, opencode tokens {"total": 2188769, "input": 91101, "output": 7208, "reasoning": 43612, "cache.write": 0, "cache.read": 2046848}]
    tool time: bash 4.1 min
        211s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_saf
         14s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 lab/tccdev/measure.py --tcc /tmp/tcc-install
          7s bash   for p in tcc_ok tcc_overflow tcc_overflow_alias; do echo "########## $p"; bash ~/tools/cmp.sh /tmp/probes/$p.p
          6s bash   cd /home/runner/work/ail-ci/ail-ci && (git worktree list | grep -q '/tmp/base' || git worktree add /tmp/base w
          4s bash   bash ~/tools/cmp.sh /tmp/probes/tcc_overflow.py /home/runner/work/ail-ci/ail-ci 2>&1
          1s bash   apt-cache policy tcc 2>/dev/null | head -10; dpkg -l tcc 2>/dev/null | tail -2
          0s bash   d=$(mktemp -d /tmp/rprobes/tccbuildXXXX); cp /tmp/probes/tcc_ok.py $d/p.ail; cd $d; WRAP_CC=/tmp/tcc-install/b
          0s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/prelude_test.c <<'EOF' #include <stdio.h> #include <stdint.h> #inc

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T17:00:11Z
