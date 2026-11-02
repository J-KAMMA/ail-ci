# job job-rbprog9-11021624  started 2026-11-02T07:31:27Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Applied and committed as `f782d94`.

- Re-applied the fetched `job-prog9-11021016` change; verified its added/removed lines exactly match the job diff, with only context/line-number and manifest-hash differences. Kept both sides' fixes.
- `tools/diff_ids.py` does not exist on this tree; skipped. `tools/update_manifest.py` ran clean and `--check` passes.
- Tests on final commit: `test_ail_prog9`, `test_ail_bugs7`, `test_ail_debug_flush`, `test_ail_flush_exit`, `test_ail_mixed_bounds`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **71 passed, 1 skipped** (no zig), exit 0.
- Probes (7, each on both `g` and `d` builds, 14/14 matched CPython): `p_dict_text`, `p_dict_container`, `p_sorted_owned`, `p_optional_in`, `p_optional_while`, `p_method_row`, `p_int_float_union`.
- Strict-path checks confirmed by-name refusals for a dict literal holding a list and for `int | float` returns. Working tree clean except pre-existing `.agent/pipeline.md`.
[cost $0.0359, opencode tokens {"total": 1584409, "input": 139214, "output": 7530, "reasoning": 10337, "cache.write": 0, "cache.read": 1427328}]
    tool time: bash 14.6 min
        828s bash   AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS=-Werror=incompatible-pointer-types python3 -m unittest -v test_ail_prog9 test_
         36s bash   for p in p_dict_text p_dict_container p_sorted_owned p_optional_in p_optional_while p_method_row p_int_float_u
         10s bash   python3 - <<'PY' from pathlib import Path p = Path('/tmp/probes/p_optional_in.py') s = p.read_text() s = s.rep
          1s bash   repo=$PWD; for f in dict_container union while_else typed_shapes; do echo "===== $f"; (cd /tmp/strict && AIL_N
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "rc=$?"
          0s bash   grep -c "^test_" /tmp/test_prog9.log; grep -n "test_ail_prog9\|skipped\|FAIL\|ERROR" /tmp/test_prog9.log | hea
          0s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-prog9-11021016 2>&1 | tail -5; echo "FETCHHEAD=$(git rev-p
          0s bash   git add AIL_CURRENT/DEVLOG.md AIL_CURRENT/manifest.d/34.txt AIL_CURRENT/manifest.d/36.txt AIL_CURRENT/manifest

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** faithfully re-applies the accepted prog9 diff (Optional method returns, Optional `in`/`while`, method SROW unpack with owned str fields, `sorted(dict)` and dict repr, container-dict / `int|float` refusals) plus manifest, tests and DEVLOG. The added/removed lines match the fetched job diff; only index/context line numbers and the recomputed `pyfunc.py`/`cruntime.py` manifest hashes differ.

**Verified claims**
- Re-application fidelity: verified (`git diff 29d859d FETCH_HEAD` changed lines equal `git diff work..HEAD`, except expected manifest hashes).
- `tools/diff_ids.py` absent: verified. `update_manifest.py --check`: rc=0.
- Tests on HEAD: `test_ail_prog9`, `test_ail_bugs7`, `test_ail_debug_flush`, `test_ail_flush_exit`, `test_ail_mixed_bounds`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 8/8 modules ok, 0 failed (568 s).
- Strict refusals by name for container dict literal and `int | float` return: verified (rc=3, exact messages).
- Unused-feature C unchanged: `plain.py` `--debug-dir` `program.c` identical to `work` (only `native_report.json` temp paths differ).
- Memory ownership: `sorted(d)` then overwrite/`del`/`clear`; row str field after later calls and source mutation: matched CPython on both builds.
- Dict/sorted/optional-in/optional-while/row probes: matched CPython.

**Not verified**
- Worker's own 7 probes/“14/14” (their files are not present). My probes found two mismatches below.
- Speed (instruction counts): `tools/icount.c` fails with `perf_event_open: Permission denied` in this runner.

**Defects (new relative to `work`; base matches CPython)**
1. A bool row field that is rebound on a branch/loop that *does* execute keeps its bool text. Probe `/tmp/rprobes/p_bool_if_taken.py`:
```
class P:
    def __init__(self) -> None: self.s = "z"
    def pair(self) -> tuple[bool, str]: return (False, self.s)
def main() -> None:
    p = P(); a, b = p.pair(); flag = 1
    if flag == 1: a = 7
    print(a)
main()
```
Expected `7`; HEAD default build prints `True`. `/tmp/rprobes/p_bool_loop_taken.py` (rebind in a taken `while`, and `for a in range(1)`) expected `7 0`; prints `True False`. `work` matches CPython on both.

2. A call to an Optional-returning method on a receiver other than `self`, used directly, yields the raw `(flag, value)` pair. Probe `/tmp/rprobes/p_opt_method_min.py`:
```
class P:
    def __init__(self) -> None: self.s = "ab"
    def peek(self) -> str | None: return self.s
def main() -> None:
    p = P()
    print(p.peek())
    print(p.peek() in ("ab", "z"))
main()
```
Expected `ab` / `True`; HEAD (both `g` and `d` builds) prints `(True, 'ab')` / `False`. Assigning the result to a name first works; only the direct use is wrong. `work` matches CPython.

VERDICT: FIX
1. `_bool_flow_after` never clears a row bool name for a rebind inside a conditional body, so a taken `if`/loop rebind prints `True`/`False` instead of the int (`p_bool_if_taken.py`, `p_bool_loop_taken.py`).
2. Optional method returns are lowered to a pair ABI, but external callers (`p.peek()`, not `self.peek()`) are not adapted, so direct `print`/`in` use of such a call returns the pair / wrong membership (`p_opt_method_min.py`).
[cost $0.0571, opencode tokens {"total": 2259320, "input": 233823, "output": 10197, "reasoning": 16452, "cache.write": 0, "cache.read": 1998848}]
    tool time: bash 8.2 min, write 0.0 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_prog9 test
         90s bash   sleep 90; date; cat /tmp/par_check_review.log; ps aux | grep -E 'par_check|test_ail_mixed' | grep -v grep | he
         60s bash   sleep 60; date; tail -20 /tmp/par_check_review.log; ps aux | grep -E 'par_check|unittest' | grep -v grep | hea
         45s bash   sleep 45; date; cat /tmp/par_check_review.log; ps aux | grep -E 'par_check|unittest' | grep -v grep | head
         42s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p"
         27s bash   for p in /tmp/rprobes/p_sorted_unannotated.py /tmp/rprobes/p_opt_method.py; do echo "===== HEAD $p"; bash ~/to
         15s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && setsid python3 ../tools/par_check.py -j 2 test_ail_prog9 tes
         14s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_opt_method3.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -25; echo "=====

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Done.

- Fixed bool row rebinding with a runtime is-bool flag, so taken `if`/`while`/`for` rebinds print the int, while untaken branches and zero-iteration loops keep `True`/`False` (including value `0`). `print`/`str`/`repr`/f-strings use it.
- Fixed external Optional method calls (`p.peek()`, annotated parameters, list elements) to use the pair ABI; ambiguous receivers are refused. Attribute/dict-value receivers are refused by name under `--strict`.
- Probes: 8/8 matched CPython on both `g` and `d` builds (`p_bool_if_taken`, `p_bool_loop_taken`, `p_opt_method_min`, `p_opt_method`, `p_opt_method2`, `p_opt_method3`, `p_bool_runtime_flow`, `p_opt_external_receivers`).
- Tests on final commit `00bd57c9`: 10 modules, 0 failed, 605s — including `test_ail_prog9`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_boolfield`, `test_ail_optional_locals`.
- `tools/diff_ids.py` is absent; `update_manifest.py --check` rc=0. Commits: `580516ef`, `bb87fdae`, `00bd57c9`.
[cost $0.1418, opencode tokens {"total": 7514466, "input": 617585, "output": 16538, "reasoning": 31191, "cache.write": 0, "cache.read": 6849152}]
    tool time: bash 19.5 min
        607s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog9 test_ail_b
        479s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog9 test_ail_b
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_bool_if_taken.py /tmp/rprobes/p_bool_loop_taken.
         16s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog9 2>&1 | tai
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_bool_runtime_flow.py /tmp/probes/p_opt_external_r
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_opt_method.py /tmp/rprobes/p_opt_method2.py /tmp
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for b in job-rbprog14-11021836 job-rbprog16-11021900 job-rbprog20-110218
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_bool_if_taken.py /tmp/rprobes/p_bool_loop_taken.

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: re-applied prog9

**What the change really does.** It re-applies prog9 (Optional `in`/`while` tests, method-row SROW unpack, `sorted(dict)`/dict repr, `int|float` and container-dict refusals) and then adds review-fix commits that replace the static bool-row tracking with per-name runtime flags and extend Optional-method resolution beyond `self`. That matches the report's summary, except the refusal claim for attribute/dict-value receivers.

**Checks run**
- `test_ail_prog9` + `test_ail_safetynet` on HEAD: **2 modules, 0 failed** (177 s).
- Worker probes re-run on HEAD: all listed `p_*` plus `/tmp/probes/p_bool_runtime_flow.py`, `p_opt_external_receivers.py` matched CPython on both `cmp.sh` builds.
- My probes: Optional-`in` type mismatches/empty containers, dict text (empty, INT64_MIN, aliasing), sorted ownership, bool index 1, `a = 1/True/False/-1`, walrus, conditional/zero-iteration unpack, ambiguous method names — all matched or were refused by name.
- Non-feature program `plain.py`: generated `program.c` byte-identical to `/tmp/base`.
- `tools/diff_ids.py` absent; `update_manifest.py --check` rc=0; commits `580516ef`, `bb87fdae`, `00bd57c9` present.

**Pre-existing:** none found (the two defects below are correct on `/tmp/base`).

**Defects**

1. **Bool row flag is codegen-order dependent across a loop back-edge.**  
   `/tmp/rprobes3/w_loop_backedge.py`:
   ```python
   class P:
       def __init__(self) -> None: self.s = "z"
       def pair(self) -> tuple[bool, str]: return (True, self.s)
   def main() -> None:
       p = P(); a = 0
       for i in range(2):
           print(a)
           a, b = p.pair()
   main()
   ```
   CPython: `0`, `True`. HEAD default build: `0`, `1` (base: correct). Same with the `while` variant. `_bool_flow_after` only sees the `print` before the textual unpack, so iteration 2 still emits the integer path.

2. **Unique-name Optional-method fallback ignores the receiver's class and reinterprets an unrelated SROW return.**  
   `/tmp/rprobes3/s_fallback_int2.py`:
   ```python
   class P:
       def __init__(self) -> None: self.x = 0
       def peek(self) -> int | None: return None
   class Q:
       def __init__(self) -> None: self.s = "q"; self.n = 5
       def peek(self) -> tuple[str, int]: return (self.s, self.n)
   def make() -> Q: return Q()
   def main() -> None:
       q = make()
       print(q.peek())
   main()
   ```
   CPython: `('q', 5)`. HEAD `cmp.sh` `g` and `d`: `5` (base: correct). The `method_info` fallback picks `P.peek` because its name is unique among Optional-returning methods; the SROW pair from `Q.peek` is then treated as `(flag, value)`. `/tmp/rprobes3/v_fallback_dictrecv.py` (`d["k"].peek()`) shows the same. This also makes the report's “attribute/dict-value receivers are refused by name” claim false for dict-value receivers.

**Report claims:** runtime bool rebinding — verified for the report's probes, false for the loop back-edge; external Optional methods/ambiguous refusal — verified, but the attribute/dict refusal claim is false (defect 2); 8/8 probes — verified for the probes I re-ran; tests — verified for `test_ail_prog9`/`test_ail_safetynet`, the other eight modules unverified; absent `diff_ids.py` and manifest check — verified.

**Unverified:** the eight additional test modules in the report, and wider corpus/suite effects.

VERDICT: FIX
1. `/tmp/rprobes3/w_loop_backedge.py` (and `w_loop_backedge_while.py`): expected `0` then `True`; HEAD default build prints `0` then `1`.
2. `/tmp/rprobes3/s_fallback_int2.py` (and `v_fallback_dictrecv.py`): expected `('q', 5)`; HEAD prints `5`; the unique-method-name fallback must check the receiver class or refuse.
[cost $0.0781, opencode tokens {"total": 3827246, "input": 291243, "output": 11146, "reasoning": 28793, "cache.write": 0, "cache.read": 3496064}]
    tool time: bash 5.3 min
        178s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_prog9 te
         44s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_bool_if_taken.py /tmp/rprobes/p_bool_loop_taken.
         23s bash   cat > /tmp/rprobes3/t_ambiguous.py <<'EOF' class P:     def __init__(self) -> None:         self.i = 0     def
         18s bash   cat > /tmp/rprobes3/h_bool_one.py <<'EOF' class P:     def __init__(self) -> None:         self.s = "z"     de
         17s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in /tmp/rprobes3/*.py; do echo "===== $p"; timeout 300 bash 
          6s bash   cd /tmp && for p in /tmp/rprobes3/w_loop_backedge.py /tmp/rprobes3/w_loop_backedge_while.py; do echo "===== ba
          6s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes3/v_fallback_dictrecv.py $PWD 2>&1 | hea
          4s bash   cat > /tmp/rprobes3/w_loop_backedge.py <<'EOF' class P:     def __init__(self) -> None:         self.s = "z"  

FINAL VERDICT: FIX  2026-11-02T11:24:28Z
