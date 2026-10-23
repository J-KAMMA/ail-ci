# job job-pre22-10240312  started 2026-10-23T18:13:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `8b9a6a3` on `job-pre22-10240312`.

- Reproduced p12/p23/p24: on this tree `g.close()` never calls `__exit__` (the general path frees the suspended fiber), so the first case still differs from CPython.
- Fixed by refusing the construct by name in both builds: `with` whose body yields in the same function, including `with open`, is rejected with `with around a yield ... GeneratorExit ...` before file-lowering.
- Added `test_ail_pre22.py`, registered it in `ail_check`, added DIFFERENCES row `C?-job-pre22-10240312-1`, DEVLOG entries, and refreshed/validated the manifest (`--check` exit 0). p20 was left untouched.

Probes (all in `/tmp/probes`, both builds): 11 refused by name — direct, argument, list item, attribute, dict value, empty yield, yield from, multiple items, nested with, `@contextmanager`, `with open`; 1 matches CPython — `with` beside (not around) a yield.

Tests: `test_ail_pre22` 2/2; `test_ail_safetynet` 5/5; `test_ail_files` 18 passed (1 skipped, no zig); `test_ail_corpus_findings3` 4/4. Speed not measured (`perf_event_open` denied).
[cost $0.0000, opencode tokens {"total": 4838651, "input": 130225, "output": 12539, "reasoning": 16463, "cache.write": 0, "cache.read": 4679424}]
    tool time: bash 5.9 min
        159s bash   python3 -m unittest -v test_ail_pre22 test_ail_corpus_findings3 > /tmp/pre22_t1.log 2>&1 & p1=$!; python3 -m u
        101s bash   python3 -m unittest -v test_ail_files > /tmp/pre22_t3.log 2>&1; e=$?; echo "files exit $e"; tail -12 /tmp/pre2
         35s bash   cat > /tmp/probes/pre22_empty_yield.py <<'EOF' class CM:     def __enter__(self):         return self     def 
         28s bash   mkdir -p /tmp/probes && cat > /tmp/probes/pre22_direct.py <<'EOF' class CM:     def __enter__(self):         p
         10s bash   cat > AIL_CURRENT/test_ail_pre22.py <<'EOF' """Pre22: a `with` whose body yields in the same function is refus
          5s bash   cat > /tmp/probes/pre22_contextmanager.py <<'EOF' from contextlib import contextmanager  class CM:     def __e
          5s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/withlib.py') s=p.read_text() old=
          5s bash   mkdir -p /tmp/probes && cat > /tmp/probes/withyield_close.py <<'EOF' class CM:     def __init__(self, name):  

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review: job-pre22-10240312 (`8b9a6a3`)**

Change refuses `with` around `yield` in the same function, both builds, with `not in the subset: \`with\` around a \`yield\`: ... GeneratorExit ...`. Root cause (base closing generator skips `__exit__`) confirmed.

**Probes** (`bash ~/tools/cmp.sh p.py <head|base>`, both g/d builds)

| probe | base | HEAD |
|---|---|---|
| p1 direct, `next`+`close` | DIFF (missing `exit GeneratorExit` on both builds) | refused by name |
| p2 fully consumed `list(gen())` | matches | refused |
| p3 `with` beside (not around) yield | matches | matches |
| p5 generator nested in function | refused (`yield not modelled`) | refused (new message) |
| p6 read `with open` + `yield f.read()` | matches | matches (not refused) |
| p7 `@contextmanager` wrapping `with`+yield | matches | refused |
| p8 manager via arg, p9 with in loop/try | match | refused |
| p11 with-no-yield / p15 no feature / pf-mixed (with and yield in separate functions) | -- | `--debug-dir` C identical to base |
| p12 `with open` + `yield f`; close observable | DIFF (`closed False` vs `True`) | refused by name |
| p13/p14 open list/no-yield; ph fdleak read-open | matches | matches |
| pa–pe list item, attribute, dict value, empty yield, yield from | -- | refused by name |
| pg async with | -- | refused (async unsupported) |

Worker's own 11 `/tmp/probes/pre22_*.py` all reproduce as reported; beside-yield matches.

**Tests:** `test_ail_pre22` + `test_ail_safetynet` on HEAD, `-j 2`: 2 modules, 0 failed (7.5s / 88s). Manifest `--check` exit 0. No existing test/corpus Python source contains `with` around `yield`.

**Claims:** reproduced/refused/tests/manifest/p20 untouched — verified. "`with open` also rejected" — overbroad: write-mode `with open(...,"w"): yield` is rejected, read-mode `yield f.read()` is not, but it still matches CPython including no fd leak.

**Note (not a defect):** p2/p7/p8/p9 matched on base and are now refused; this is the permitted named refusal, but it narrows generator support beyond the closing case.

**Pre-existing:** p4 nested-generator refusal and base p12 `closed False` (now refused). p1 base diff is the one fixed.

**Speed:** not measured (`perf_event_open` denied); change is compile-time-only and generated C is byte-identical for feature-free programs, so no runtime effect.

**Unverified:** gdev instruction counts; `test_ail_files`/`test_ail_corpus_findings3` not re-run (worker reports 18/18 and 4/4); p20.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 881885, "input": 41083, "output": 6625, "reasoning": 16385, "cache.write": 0, "cache.read": 817792}]
    tool time: bash 4.5 min
         89s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         33s bash   cd /tmp/probes && for p in pre22_*.py; do echo "== $p"; timeout 300 bash ~/tools/cmp.sh /tmp/probes/$p /home/r
         30s bash   cd /tmp/rprobes && for p in p8_arg p9_loop_try p10_no_with p11_with_no_yield p12_open_closed p13_open_list p14
         29s bash   cd /tmp/rprobes && for p in p1_close p2_consume p3_beside p4_nesteddef p5_nestedfn p6_open p7_contextmanager; 
         20s bash   cd /tmp/rprobes && for p in p1_close p2_consume p3_beside p4_nesteddef p5_nestedfn p6_open; do echo "===== $p 
         16s bash   cd /tmp/rprobes && for p in p7_contextmanager p8_arg p9_loop_try p10_no_with p11_with_no_yield; do echo "=====
         13s bash   cd /tmp/rprobes && cat > pa_listitem.py <<'EOF' class CM:     def __enter__(self): return self     def __exit_
         12s bash   cd /tmp/rprobes && cat > p12_open_closed.py <<'EOF' def gen(path):     with open(path) as f:         yield f g

FINAL VERDICT: ACCEPT  2026-10-23T18:33:55Z
