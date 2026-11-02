# job job-fz216-11021859  started 2026-11-02T10:06:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done, committed as `6c7d3cd` on `job-fz216-11021859`.

**Cause:** `_ListLowering` rewrote `list.count()` / `list.index()` into prelude statements placed at the start of the enclosing statement. Their argument side effects therefore ran before earlier operands that CPython evaluates first and that raise.

**Fix:** `index_or_count` now checks already-evaluated operands with `tryhoist._expr`. If any can raise or run code, the typed path refuses by name; the default build uses the general path and keeps source order. Safe earlier operands still build typed.

**Verification**
- Minimized reproducer now matches CPython; `fz216` matches through line 5 (`-34`), then still stops on the pre-existing int64 overflow at the final big multiplication (CPython makes an arbitrary-size int) — a separate documented limitation.
- Probes in `/tmp/probes`: `fz216_min`, `fz216_index`, `fz216_calls`, `fz216_types`, `fz216_safe`; all match CPython on default and `AIL_IR=1`, including int/float/str lists via item, attribute, dict value and argument.
- Tests on final commit: `test_ail_fz216` 6/6, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skipped), `test_ail_corpus_findings3` 2/2; `update_manifest.py --check` passes.
- Other differences seen: only the full fuzz program's int64 overflow at the end.
[cost $0.0000, opencode tokens {"total": 6338924, "input": 382194, "output": 15280, "reasoning": 20554, "cache.write": 0, "cache.read": 5920896}]
    tool time: bash 16.2 min
        223s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -20
        193s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -15
        187s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8
        111s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_files.py 2>&1 | tail -15
         38s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -8
         26s bash   cd /home/runner/work/_temp/w2 && for p in order4 order5 fz216; do echo "== $p"; bash ~/tools/cmp.sh /tmp/probe
         20s bash   cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/fz216.py $PWD 2>&1 | tail -50
         20s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && python3 -B AIL_CURRENT/test_ail_f

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fz216 list.count/index evaluation order

**What the change really does:** In `_ListLowering.index_or_count` (pyfunc.py:35080), it inspects operands already evaluated earlier in the same statement via `tryhoist._expr`; if any may raise or run code, it raises `Unsupported` for the typed lowering, so the default build falls back to the general path (source order). Matches the report.

**Probes (HEAD, `cmp.sh`, general `g` + default `d`):**

| probe | content | result |
|---|---|---|
| p1_count_index | `v[99]` before `count(side())` / `index(side())` | both match CPython; base default prints `side 99`, `side 2` (bug) |
| p2_mutate | `pop()` before/after `count()`; raising subscript before count | both match; base also matched |
| p3_provenance | int/float/str lists via item, attribute, dict value, argument | both match |
| p4_safe | safe earlier operands, index bounds | both match |
| p5_nested | nested calls, index-then-raise, ternary arm | both match |
| `/tmp/probes/fz216.py` | full fuzzer program | first 6 lines now match CPython (`-34` on line 5); then pre-existing int64 overflow. With `AIL_EXACT_INT=1` the whole program matches stdout and exit 0 |
| worker probes `fz216_min/_index/_calls/_types/_safe` | — | all match on both builds |

**Base/pre-existing:** fz216's final int64 overflow (`*`) is present on base's general path too, and is the documented int64 limitation (DIFFERENCES). p1/p5-style ordering is wrong on base default, fixed on HEAD. No new difference found.

**Tests on HEAD:** `test_ail_fz216` ok (19.9s), `test_ail_safetynet` ok (189.9s); `update_manifest.py --check` rc 0. Did not re-run `test_ail_files`/`test_ail_corpus_findings3` (per review instructions).

**Claims:** cause, fix, minimized result, probe results, and fz216 line-5 fix all verified. "Only remaining difference is int64 overflow" verified by exact-int full match.

**Observation (not a defect):** safe-but-arithmetic earlier operands (e.g. `xs.count(2) + len(xs)`) are conservatively treated as possibly raising, so such programs now take the general path; output still matches. C for a no-feature program is byte-identical to base.

**Speed:** `icount` unavailable (`perf_event_open: Permission denied`); binaries for gdev `g04_018` and `g15_022` (relevant list.index uses) are byte-identical HEAD vs base.

**Unverified:** instruction counts; broader suite modules; exhaustive corpus fallback behaviour.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1810105, "input": 119117, "output": 7379, "reasoning": 21529, "cache.write": 0, "cache.read": 1662080}]
    tool time: bash 5.3 min, write 0.0 min
        191s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_fz216 test_ai
         23s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/fz216.py /tmp/rprobes/p1_count_index.py; do echo "===== 
         20s bash   cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/fz216.py $PWD > /tmp/fz216_head.txt 2>&1; hea
         18s bash   cd /tmp && rm -rf sp && mkdir sp && cd sp && for w in h b; do wt=/home/runner/work/_temp/w2; [ $w = b ] && wt=
         13s bash   cd /tmp/base && bash ~/tools/cmp.sh /tmp/probes/fz216.py $PWD > /tmp/fz216_base.txt 2>&1; head -20 /tmp/fz216_
         10s bash   cd /tmp && rm -rf fx && mkdir fx && cd fx && cp /tmp/probes/fz216.py p.ail && python3 p.ail > py.out 2>py.err;
          8s bash   cd /home/runner/work/_temp/w2 && for p in fz216_min fz216_index fz216_calls; do echo "===== $p HEAD"; bash ~/t
          7s bash   cd /home/runner/work/_temp/w2 && for p in fz216_types fz216_safe; do echo "===== $p HEAD"; bash ~/tools/cmp.sh

## full suite
test_ail_boolfield
test_ail_list_ops

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed the regression by narrowing the `list.count()/index()` refusal to only trigger when both an earlier operand and the method call's own receiver/arguments may raise or run code.

Verified:
- `test_ail_list_ops` — OK
- `test_ail_boolfield` — OK
- `test_ail_fz216` — OK (original fix + test preserved)

Committed as `8f98cbe`.
[cost $0.0000, opencode tokens {"total": 1057251, "input": 85635, "output": 2887, "reasoning": 6553, "cache.write": 0, "cache.read": 962176}]
    tool time: bash 2.1 min, edit 0.0 min
         52s bash   python3 -m unittest -q test_ail_list_ops
         52s bash   python3 -m unittest -q test_ail_boolfield
         19s bash   python3 -m unittest -q test_ail_fz216
          0s edit   /home/runner/work/_temp/w2/AIL_CURRENT/python/pkg-v12/pyfunc.py
          0s bash   git add AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/manifest.d/45.txt && git commit -m "job fz216: only r
          0s bash   git show --stat HEAD && echo "---DIFF---" && git show HEAD --format=fuller | head -300
          0s bash   grep -rn "may raise or run code\|evaluates first\|tryhoist._expr" AIL_CURRENT/python/pkg-v12/*.py AIL_CURRENT/
          0s bash   git status && git diff -- AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/manifest.d/45.txt

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T13:09:45Z
