# job job-rbpre1-10241812  started 2026-10-24T09:15:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-pre1-10240007` (same code diff) and committed as `799f393`.

- Probes: 8 in `/tmp/probes`; p1–p7 match CPython on both builds, p8 (positional-only passed by keyword) is refused by name on both.
- Tests on final commit: `test_ail_pre1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 29 passed, 1 skipped.
- `python3 tools/update_manifest.py` ran; `--check` passes.
- `tools/diff_ids.py` does not exist in this repo, so it could not be run.
- `DIFFERENCES.md` unchanged; no new difference was introduced. Not pushed.
[cost $0.0000, opencode tokens {"total": 829977, "input": 42149, "output": 5763, "reasoning": 5873, "cache.write": 0, "cache.read": 776192}]
    tool time: bash 12.4 min, write 0.0 min, edit 0.0 min, read 0.0 min
        476s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_pre1 test_ail_safetynet test_ail_files test_ail_corpus_fi
        201s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_pre1 test_ail_safetynet test_ail_files test_ail_corpus_fi
         35s bash   for p in /tmp/probes/p[1-7]_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E '^(cpytho
         26s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_pre1 2>&1 | tail -60
          4s bash   bash ~/tools/cmp.sh /tmp/probes/p8_keyword_refused.py "$PWD" 2>&1 | tail -30
          1s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre1-10240007 2>&1 | tail -5; echo "---"; git log --onelin
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "manifest exit $?"; git dif
          0s bash   pwd && git status && git log --oneline -5 && ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** It re-applies the accepted `job-pre1-10240007` patch: positional-only parameters are now bound (posonly before args) on the general/nested paths, a posonly name passed as a keyword is refused by name, and unified hints include posonly annotations. The code diff is byte-identical to the original job's (only hunk line offsets differ); MANIFEST pins and a new DEVLOG entry were added, plus the same `test_ail_pre1.py`.

**Claims checked**
- Same code diff as `job-pre1`: verified (`diff` of the two patches identical apart from hunk headers).
- Commit `799f393`, not pushed: verified (`origin..HEAD` = 1 commit).
- `update_manifest.py --check` passes: verified.
- `tools/diff_ids.py` absent: verified (not present anywhere in repo).
- `DIFFERENCES.md` unchanged: verified.
- Worker probes p1–p7 match CPython, p8 refused by name: re-ran all, verified.
- Tests on final commit: re-ran `test_ail_pre1 test_ail_safetynet test_ail_files test_ail_corpus_findings3` on HEAD — 4 modules ok, 0 failed (332 s).

**My probes** (`cmp.sh`, both builds)
- q1 defaults/types (int/str/float/bool/None/tuple/list/dict, empty/negative, defaults incl. keyword-only): same.
- q2c methods/staticmethod/classmethod/property, posonly `self`, defaults: same.
- q3 values via argument/list item/attribute/dict value, aliasing and mutation: same.
- q4 nested defs with posonly/defaults and recursion: same.
- q5b `**kwargs`/`*args` with posonly, star-unpacking: same; `f(1, a=2)` is refused by name (CPython puts it in `**kwargs`) — named refusal, acceptable.
- q6 `lru_cache` with posonly and recursive fallback: same.
- q7/q8 missing/extra args: named refusals, acceptable.
- q9 property setter and key function: same.
- No-feature program: `--debug-dir` `program.c` md5 identical between `/tmp/base` (work) and HEAD; only report paths differ.
- Runtime speed unaffected (generated C unchanged), so no icount run needed.

**Pre-existing:** `cls.__name__` / class attribute through `cls` crashes at runtime (`AttributeError: 'type' object has no attribute ...`) identically on the base with the same classmethod written without posonly; not caused by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1226035, "input": 45291, "output": 7805, "reasoning": 8688, "cache.write": 0, "cache.read": 1164251}]
    tool time: bash 7.9 min
        334s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         39s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p[1-7]_*.py; do echo "==$(basename $p)"; bash ~/too
         28s bash   cat > /tmp/rprobes/z_base_cm.py <<'EOF' class C:     @classmethod     def k(cls, a, b=3):         return (cls.
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q[1-5]_*.py; do echo "===== $p"; bash ~/tools/cmp.
         14s bash   cat > /tmp/rprobes/q6_lru.py <<'EOF' from functools import lru_cache  @lru_cache(maxsize=None) def fib(n, /, s
          7s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbg_head /tmp/dbg_base /tmp/nf_head* /tmp/nf_base*; AIL_NO_C
          6s bash   cat > /tmp/rprobes/q9_prop.py <<'EOF' class C:     def __init__(self, x, /):         self._x = x      @propert
          5s bash   sed 's/(cls.__name__, a + b)/(cls.marker, a + b)/; s/    @classmethod/    marker = 99\n\n    @classmethod/' /t

FINAL VERDICT: ACCEPT  2026-10-24T09:40:26Z
