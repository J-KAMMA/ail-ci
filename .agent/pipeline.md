# job job-std_bisect-11011433  started 2026-11-01T05:35:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `d18e803` on `job-std_bisect-11011433`.

- Wrote 12 realistic `bisect` programs in `lab/stdlib/bisect/`; **12/12 build and match CPython stdout + exit code** (target was 9).
- Before the fix 11 built; `key_records.py` was refused. Added general-path `key=` support for all six `bisect`/`insort` functions (`BISECTKEY_C` in `pyboxed2.py`), calling keys only on visited elements and once for `insort`.
- `RESULTS.md` records typed/general results, the pre-fix refusal text, and two typed-path follow-ups with exact `--strict` messages.
- Compare-task C check vs `HEAD`: 17 task/language pairs byte-identical; the 3 Python-column pairs `scar_life`, `tally_lang`, `tree_fold` are refused by both revisions.
- Probes run via `cmp.sh` on both builds: `p_bisect_key_tuples`, `p_bisect_key_calls`, `p_bisect_key_types`, `p_bisect_key_routes`, `p_bisect_key_errors` — all match CPython (or stop with its exception).
- Added `test_ail_std_bisect.py` + `tests.d` registration.
- Final-commit tests: `test_ail_std_bisect`, `test_ail_heapq_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **0 failed**. Also `test_ail_py_typed_gaps` and `test_ail_builtin_api` — 0 failed. `update_manifest.py --check` passes.

`.agent/pipeline.md` remains untracked (pre-existing job file, not committed).
[cost $0.0000, opencode tokens {"total": 7201115, "input": 102448, "output": 20278, "reasoning": 23157, "cache.write": 0, "cache.read": 7055232}]
    tool time: bash 22.0 min, edit 0.0 min, write 0.0 min
        502s bash   cd /tmp && rm -rf /tmp/cmpgen && mkdir -p /tmp/cmpgen && cat > /tmp/cmpgen/check.sh <<'EOF' #!/bin/bash set -u
        360s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_heapq_bisect tes
        271s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo MANIFEST_EXIT:$
         30s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_py_typed_gaps test_ail_builtin_api >
         30s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_bisect_key_*.py; do echo "===== $p"; bash ~/tools/cmp.
         29s bash   cd /home/runner/work/_temp/w2 && for n in key_records leaderboard lookup_helper star_import event_log grade_re
         26s bash   cd /home/runner/work/_temp/w2 && for f in lab/stdlib/bisect/*.py; do n=$(basename "$f" .py); log=/tmp/final_$n
         18s bash   cd /home/runner/work/_temp/w2 && for f in lab/stdlib/bisect/*.py; do echo "=== $f"; python3 AIL_CURRENT/ail_ch

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review of `d18e803` (std_bisect: `key=` for bisect/insort)

**What the diff really does.** Adds `BISECTKEY_C` (`ail_bisect_{left,right,insort_left,insort_right}_key`) to the general path, emitted only when `needs_bisect_key`; `_bisect_call` now accepts `key=`, wraps it with `_wrap_cfunc`, and appends `_key` to the runtime function name. `insort` keys `x` once, then reuses the search with `key(element)`. Non-key code paths are untouched. This matches the report.

**Probes run** (`cmp.sh`, both general and default builds, HEAD vs `/tmp/rbase`, CPython 3.12 oracle):
- `q2_builtins` (`abs`, `str.lower`, `len`), `q3_edges` (hi=-1/-2/None, lo<0 ValueError, hi past end IndexError, empty), `q4_raise` (raising key mid-search, list unchanged), `q5_calls` (visited-only key calls, insort key-once, duplicates), `q6_insort_bounds`, `q15_objects` (key on attribute, x from dict/argument), `q16_alias` (`bisect.bisect`), `q18_bounds_types` (float/str bounds, bool bounds, key not called before TypeError), `q9_mutate` (key appends/pops during search), `q7_alloc` (key allocates heavily): all match CPython in both builds.
- `q10_keyparam`: `key=` as a passed function parameter works.
- `q1_keynone`: `key=None` is a **named compile-time refusal** (acceptable refusal, but a limitation).
- C-unchanged check: generated C for `error_edges` (typed) and `lookup_helper` (general) is byte-identical HEAD vs base.

**Defect found** — str sequence + `key=` crashes.

```
import bisect

def main():
    print(bisect.bisect_left("abcd", "b", key=str))
    print(bisect.bisect_right("abcd", "c", key=str.lower))

main()
```
Expected (CPython): stdout `1\n3\n`, exit 0. Actual on HEAD: both `g` (general) and `d` (default) builds **SIGSEGV, exit 139, empty stdout**. On base the same probe is a clean named refusal. Cause: `ail_bisect_*_key` casts `a.o` to `ail_vecobj *` unconditionally; `key=` forces the general path for a str (the typed path handled the no-key call), and the search reads the str as a vector. The change turns a refused program into a crash for a valid CPython call. Fix: refuse non-list sequences for `key=` by name at compile time (or implement sequence indexing).

**Pre-existing (not caused by this change, do not block):**
- General path (`AIL_UNIFIED_FORCE=1`) bisect on a str without `key=` segfaults on base and HEAD.
- `insort` on a tuple (with or without `key=`) mutates it instead of raising `AttributeError`; identical on base for the non-key form.
- `key=None` (CPython's default) is refused; was also refused before.

**Claim check:** 12/12 build+match — verified (`test_ail_std_bisect` passes). key-on-visited/once-for-insort/rooting — verified for list inputs (rooting indirectly: frame slots, heavy-allocation probe). "11 built before fix" — only `key_records` refusal re-verified on base; other 11 not re-run. Compare-task "17 byte-identical, 3 refused" — structurally guaranteed by the conditional emit; two representative C outputs spot-checked identical, full 17 not re-run. `test_ail_std_bisect` + `test_ail_safetynet`: 0 failed; `update_manifest.py --check`: passes. `RESULTS.md --strict` texts not re-run.

**Unverified:** the other 11 base builds, all 17 compare-task C pairs, the two `--strict` follow-up messages, and `test_ail_files`/`test_ail_corpus_findings3`/`test_ail_heapq_bisect` (not re-run here per review scope).

VERDICT: FIX

1. `key=` on a str sequence segfaults instead of matching CPython or being refused. Probe:
   ```python
   import bisect
   def main():
       print(bisect.bisect_left("abcd", "b", key=str))
       print(bisect.bisect_right("abcd", "c", key=str.lower))
   main()
   ```
   Expected: `1\n3\n`, exit 0. Actual HEAD: exit 139 (SIGSEGV), no stdout, both builds; base refused by name. Reject non-list sequences for `key=` (named refusal) or handle sequences properly.
[cost $0.0314, opencode tokens {"total": 1612972, "input": 63006, "output": 9415, "reasoning": 19527, "cache.write": 0, "cache.read": 1521024}]
    tool time: bash 5.2 min
        199s bash   date; cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetynet 
         29s bash   date; cat > /tmp/rprobes/rv/q16_alias.py <<'EOF' import bisect  def main():     a = [1, 2, 2, 4]     print(bis
         13s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/rv/q*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" 
         12s bash   cat > /tmp/rprobes/rv/q12b_tuple_nokey.py <<'EOF' import bisect  def main():     t = (1, 2, 2, 3)     print(bi
         11s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/rv/q6_insort_bounds.py /tmp/rprobes/rv/q7_alloc.py /tmp
          8s bash   cat > /tmp/rprobes/rv/q12_tuple.py <<'EOF' import bisect  def main():     t = (1, 2, 2, 3)     print(bisect.bi
          8s bash   cat > /tmp/rprobes/rv/q10_keyparam.py <<'EOF' import bisect   def by_first(r):     return r[0]   def find(rows
          6s bash   cd /tmp && rm -rf /tmp/dh /tmp/db && mkdir /tmp/dh /tmp/db && for d in dh db; do cp /home/runner/work/_temp/w2

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `ecb1d32`.

- `BISECTKEY_C` now reads length/elements through generic indexing for list, tuple, and str; `insort*` with `key=` on a non-list raises CPython’s `AttributeError` instead of writing through the cast.
- Probes (`p1_review`, `p2_str_paths`, `p3_tuple_paths`, `p4_insort_str`, `p5_list_key`) match CPython on both default and general builds. Reviewer’s str probe now prints `1\n3\n`, exit 0.
- `lab/compare` generated C: 17 buildable task/language pairs byte-identical to base; same 3 Python-column pairs refused.
- Final-state tests: `test_ail_std_bisect`, `test_ail_heapq_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. `update_manifest.py --check` passes.
- Added regression `test_key_on_str_and_tuple`; DEVLOG entry added.
[cost $0.0290, opencode tokens {"total": 2161881, "input": 74604, "output": 9931, "reasoning": 9378, "cache.write": 0, "cache.read": 2067968}]
    tool time: bash 21.0 min
        464s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpC && mkdir -p /tmp/cmpC/head /tmp/cmpC/base && for f in lab/co
        389s bash   cd /home/runner/work/_temp/w2 && date && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_heapq_bi
        340s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -10 && date && python3 t
         37s bash   cd /home/runner/work/_temp/w2 && for task in chain_relax rail_transfer; do f="lab/compare/src/$task/main.py"; 
         22s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p1_review.py /tmp/probes/p2_str_paths.py /tmp/probes/p3_
          5s bash   cd /tmp/probes && cat > p4_insort_str.py <<'EOF' import bisect   def main():     for name in ("insort", "insor
          3s bash   cd /tmp && rm -rf ctest && mkdir ctest && cd ctest && AIL_NO_CACHE=1 python3 /home/runner/work/_temp/w2/AIL_CU
          2s bash   cd /tmp && rm -rf p4t && mkdir p4t && cp /tmp/probes/p4_insort_str.py p4t/p.ail && cd p4t && AIL_NO_CACHE=1 AI

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds a general-path `key=` lowering for `bisect_left/right/bisect/insort*` (`BISECTKEY_C` in `AIL_CURRENT/python/pkg-v12/pyboxed2.py`), plus 12 lab programs, a CPython-comparing test, DEVLOG/RESULTS. The length is a manual list/tuple/str switch, not generic: other CPython sequences are not handled.

**Verification.**
- `test_ail_std_bisect` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` passes.
- Non-key codegen unchanged: `lab/compare/src/berth_sim` and `echo_pack` `program.c` byte-identical to `/tmp/rbase` (only spot-checked 2 of the claimed 17).
- Worker probes `p1_review`, `p2_str_paths`, `p3_tuple_paths`, `p5_list_key`, `p_bisect_key_tuples`: match CPython on both builds.
- My probes matching CPython on both builds: list/tuple/str keys, lo/hi (`-1`, `-2`, `>n`), `hi=None`, negative lo, empty, raising key, `insort` on str/tuple (`AttributeError`), mutation during key, key through argument/dict/attribute, NaN, reversed/non-monotonic keys, GC pressure, deque.
- Report claims mostly verified: list/tuple/str handling, insort `AttributeError`, 12/12 lab programs, DEVLOG/test registration. Exact `p4_insort_str` and the full 17-pair/five-module claims were not rerun.

**Pre-existing (identical on `/tmp/rbase`, not blocking).**
- General build, non-key `bisect_left("abc","b")`: segfault on both base and HEAD.
- Default build, `insort_left([1,2,3],0,5)`: `list assignment index out of range` on both.
- Non-BMP string literals / `chr(0x1F600)`: named compile refusal on both.

**Defects.**

VERDICT: FIX
1. `key=` on a `range` is accepted but aborts at run time (both default and general builds). Probe `/tmp/rprobes/v_range.py`:
```python
import bisect
def main():
    print(bisect.bisect_left(range(10), "5", key=str))
    print(bisect.bisect_right(range(10), "5", key=str))
    print(bisect.bisect_left(range(0), "5", key=str))
main()
```
Expected: `5\n6\n0\n`, exit 0. Actual: no stdout, exit 1, `TypeError: object of type 'range' has no len()`. Base refused by name, so the change introduced the wrong result. Fix `ail__bisect_len` to use generic length (range indexing already works via `ail_op_getitem`), or refuse by name.
2. `key=` on `bytes`/`bytearray` works in the default build but fails in the general build. Probe `/tmp/rprobes/v_bytes.py`:
```python
import bisect
def main():
    print(bisect.bisect_left(b"aceg", 100, key=int))
    print(bisect.bisect_right(bytearray(b"aceg"), 101, key=int))
    print(bisect.bisect_left(b"", 1, key=int))
main()
```
Expected: `2\n3\n0\n`, exit 0. Actual general build: no stdout, exit 1, `TypeError: object of type 'bytes' has no len()`; default build matches CPython. Base general refused by name. Same root cause as defect 1.
[cost $0.0535, opencode tokens {"total": 4052540, "input": 110645, "output": 11032, "reasoning": 30959, "cache.write": 0, "cache.read": 3899904}]
    tool time: bash 8.7 min
        241s bash   cd /home/runner/work/_temp/w2 && date && python3 tools/par_check.py -j 2 test_ail_std_bisect test_ail_safetyne
        120s bash   cd /tmp && rm -rf cg && mkdir cg && for task in berth_sim echo_pack ticket_audit rail_transfer grade_report; d
         41s bash   cd /tmp/probes && for f in p1_review p2_str_paths p3_tuple_paths p5_list_key p_bisect_key_tuples; do echo "===
         14s bash   cd /tmp/rprobes && cat > v_bounds.py <<'EOF' import bisect  def main():     a = [1, 2, 2, 4]     for lo, hi in
         14s bash   cd /tmp/rprobes && cat > v_range.py <<'EOF' import bisect  def main():     print(bisect.bisect_left(range(10),
          9s bash   cd /tmp/rprobes && cat > v_gc.py <<'EOF' import bisect  def main():     junk = []     def key(v):         junk
          7s bash   cd /tmp/rprobes && cat > v_deque.py <<'EOF' import bisect from collections import deque  def main():     d = d
          7s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > v_seq.py <<'EOF' import bisect  def main():     print(bisect

FINAL VERDICT: FIX  2026-11-01T07:04:05Z
