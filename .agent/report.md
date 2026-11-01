# job job-std_array-11020204  started 2026-11-01T17:06:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects:

- `array(...)` keywords now evaluate arguments before raising (`p_kweval`, `p_kweval3`); `**mapping` remains a named compile-time refusal.
- Reflected ordering keeps the original operator/order and prints `array.array` (`p_cmp`, `p_cmp2`).
- Sequence-left multiplication names the array (`p_mul`, `p_mul2`).

All probes match CPython on both `cmp.sh` builds. Final test run: 9 modules, 0 failed (`test_ail_std_array`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_dunders`, `test_ail_cmp_classname`, `test_ail_array_ref`, `test_ail_array_t2`, `test_ail_stdlib5`). `update_manifest.py --check` passes.

Committed as `8d7bb7f`.
[cost $0.0000, opencode tokens {"total": 7561246, "input": 169841, "output": 13595, "reasoning": 28306, "cache.write": 0, "cache.read": 7349504}]
    tool time: bash 40.7 min
        837s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_array test_ail_safetynet test_ail_files test_ail_cor
        722s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_array test_ail_safetynet test_ail_files test_ail_cor
        292s bash   timeout 900 python3 tools/par_check.py -j 2 test_ail_stdlib5
        177s bash   python3 tools/update_manifest.py >/dev/null && cd /tmp/probes && for p in p_kweval p_kweval3 p_cmp p_cmp2 p_mu
        171s bash   cd /tmp/probes && for p in p_kweval p_kweval3 p_cmp p_cmp2 p_mul p_mul2; do echo "===== $p"; bash ~/tools/cmp.
         87s bash   cat > /tmp/probes/p_kweval2.py <<'EOF' from array import array   def note(tag):     print("eval", tag)     ret
         69s bash   cd /tmp/probes && for p in p_kweval p_cmp p_mul; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py /ho
         36s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_kweval.py <<'EOF' from array import array   def boom():     raise 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** keeps `array(...)` keyword-call arguments (rewriting to `_ail_arr_bad_kw(*args, **kwargs)`), adds an `_AilArray` early return in the shared reflected-comparison helper, renames `_AilArray` to `array.array` in comparison/type/multiply messages, adds `_ail_arr_tname` cases for array/bytes/bytearray/range, adds sequence-left `__rmul__` errors, plus manifest/DEVLOG/RESULTS.

**Probes** (HEAD `g`+`d`, base `/tmp/base` where noted):
- `p_kweval`, `p_kweval3`, `p_kweval4`: same stdout as CPython; `p_kweval2` (`**m`) refused by name. Base dropped the side effects.
- `p_cmp`, `p_refl`: reflected list/int/str/tuple/dict/float/bool/None/range ordering now matches, including through an attribute, list item, dict value and argument. Base had the wrong operator/order.
- `p_mul`, `p_mul2`: str/list/tuple/bytes/bytearray/float/range cases match; base named the left class.
- `p_plain`: same stdout.
- `p_cmp2`, `p_tname`: differences identical on base (pre-existing).
- `p_namecollide2` (does not use `array`): **HEAD wrong, base matches CPython** — defect below; the two guard lines even appear in its `program.c`.
- All 10 `lab/compare` `program.c`: byte-identical HEAD vs base.
- Tests: all 9 reported modules 0 failed; `update_manifest.py --check` rc 0.

**Defect 1: array detection keys on a bare class name and leaks into non-array programs.**
```python
class _AilArray:
    pass
obj = _AilArray()
for name, fn in [("str", lambda: "x" * obj), ("list", lambda: [1] * obj),
                 ("bytes", lambda: b"x" * obj),
                 ("bytearray", lambda: bytearray(b"x") * obj)]:
    try:
        print(name, fn())
    except Exception as e:
        print(name, type(e).__name__, e)
```
Expected (CPython and base) for the last two: `TypeError can't multiply sequence by non-int of type '_AilArray'`; actual HEAD: `... 'array.array'`. `pyboxed2.py` applies the replacement whenever any `ClassDef` named `_AilArray` exists, without checking the array prelude. The same name test in `dunderrt.py` (`p_namecollide`) changes comparisons of such a class: HEAD raises `TypeError ... 'array.array'` instead of invoking its `__gt__`. Gate both edits on the actual array prelude (or a runtime marker), not a class-name match.

**Pre-existing** (identical on base): reflected bytes/bytearray `<=` still prints `_AilArray`, and `bytearray(b"x") <= array` raises instead of returning `False`; array-vs-user-class comparison dispatch; `append_arr` `int()` message; `type(a[1:]).__name__`.

**Claims:** keyword evaluation, `**mapping` refusal, reflected list ordering, sequence-left multiply, 9 test modules and manifest are verified. "All probes match CPython" is false in general (`p_namecollide2`); "prints `array.array`" is not true for reflected bytes/bytearray (pre-existing).

**Unverified:** instruction-count speed (`perf_event_open` denied); rest of the suite (not run, per instructions).

VERDICT: FIX
1. Non-array program defining `class _AilArray` gets `bytes`/`bytearray` multiply errors naming `array.array` (and comparison dispatch suppressed). Probe `p_namecollide2`: expected `bytes TypeError can't multiply sequence by non-int of type '_AilArray'`, actual `bytes TypeError can't multiply sequence by non-int of type 'array.array'`; base matches CPython. Fix by gating the `pyboxed2.py` replacements and the `dunderrt.py` skip on the array prelude actually being present, not on the class name alone.
[cost $0.0000, opencode tokens {"total": 1119887, "input": 45711, "output": 8358, "reasoning": 19418, "cache.write": 0, "cache.read": 1046400}]
    tool time: bash 22.5 min
        474s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        341s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        122s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rout/head && for p in p_kweval p_kweval2 p_kweval3 p_cmp p
         83s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbg_head/* /tmp/dbg_base/* && for t in lab/compare/src/*/mai
         81s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rout/base && for p in p_kweval p_kweval2 p_kweval3 p_cmp p
         76s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rout/head2 && for p in p_mul2 p_cmp2 p_kweval4 p_tname; do
         47s bash   cd /tmp/rprobes cat > p_refl.py <<'EOF' from array import array a = array("i", [1]) class Holder:     def __in
         36s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_cmp2 p_tname; do echo "===== BASE $p"; bash ~/tools/cmp.sh /t

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed review-2 defect: array-specific behavior is now gated on the real `_AIL_ARRAY_PRELUDE` marker instead of a bare `_AilArray` class name.

- `p_namecollide2`: matches CPython on both builds; `p_namecollide` matches `/tmp/base` (pre-existing CPython difference).
- All other `/tmp/rprobes` probes match CPython or match `/tmp/base` where pre-existing.
- 9 required test modules: 0 failed (721s).
- All 10 `lab/compare` generated C files byte-identical to `/tmp/base`.
- `update_manifest.py --check`: rc 0.
- Committed as `9b07c2a`.
[cost $0.0171, opencode tokens {"total": 1113156, "input": 51621, "output": 4237, "reasoning": 6034, "cache.write": 0, "cache.read": 1051264}]
    tool time: bash 19.9 min, edit 0.0 min
        722s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        278s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do n=$(basename "$p" .py); echo "===== $n"; 
         99s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_namecollide2 p_namecollide p_cmp p_mul p_kweval p_kweval2; do
         41s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cghead /tmp/cgbase && mkdir -p /tmp/cghead /tmp/cgbase && fa
         28s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cgbase && mkdir -p /tmp/cgbase && fail=0; for t in $(ls lab/
         21s bash   ls -d /tmp/base 2>/dev/null && cd /home/runner/work/ail-ci/ail-ci && for p in p_namecollide p_namecollide2; do
          2s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cgtest && mkdir -p /tmp/cgtest && python3 AIL_CURRENT/ail_ch
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 tools/update_manifest.py --check; echo che

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** Two commits on top of `work`. `8d7bb7f` fixes the three review-1 defects: `array(..., kw=...)` keeps and evaluates all arguments before raising; reflected ordering of a non-array against an array no longer enters the array's `__lt__` and names the original operator/order; sequence-left `*` names `array.array`. `9b07c2a` gates the array-specific runtime edits on the injected `_AIL_ARRAY_PRELUDE` marker rather than the bare `_AilArray` class name. Matches the report.

**Probes** (`cmp.sh`, HEAD and `/tmp/base`):
- Review-1 defects: `p_kweval`, `p_kweval3`, `p_kweval4`, `p_cmp`, `p_mul`, `p_mul2` — same stdout as CPython on both builds; `p_kweval2` refused by name. All three defects fixed.
- `p_namecollide2` — same as CPython on both builds (review-2 defect fixed).
- `r_ops` (`list/tuple/int <=/>=/</> array`) — now same as CPython; was wrong on base.
- `r_left` (`set/frozenset/str/bytes/... <=/>= array`) — all match except `bytes`/`bytearray`, identical on base.
- `r_tname2` (`a[float]`, `del`/`set`, `contains`, `index`, `remove`, `append str`) — same as CPython. `p_tname` only `append_arr` message text differs (base differs too; the type name itself is now correct).
- `p_plain` same; `p_cmp2`, `p_namecollide`, `p_plainclass` residual differences identical on base.

**Tests:** `test_ail_std_array` (248s), `test_ail_safetynet` (176s), `test_ail_dunders` (55s), `test_ail_cmp_classname` (103s) — 0 failed. All 10 `lab/compare/src/*/main.ail` `program.c` byte-identical to `/tmp/base`. `update_manifest.py --check` rc 0.

**Claims:** report claims for `p_namecollide2`, `p_namecollide`, the required modules, byte-identical C and manifest are verified. The report omits the earlier three fixes, but they are in the diff (commit `8d7bb7f`) and verified. Not blocking: a program that itself assigns `_AIL_ARRAY_PRELUDE = True` can spoof the gate (`r_marker`), but that is an internal name outside the Python surface.

**Pre-existing:** user class `_AilArray` comparison dispatch (`p_namecollide`); `array < R()` / `R()` naming `object`; `bytes`/`bytearray <= array`; `append_arr` message wording; `p_plainclass` list-vs-R attribute error.

**Unverified:** the other five of the nine modules (`files`, `corpus_findings3`, `array_ref`, `array_t2`, `stdlib5`), the 12 lab programs' runtime output, and instruction counts (non-array C is byte-identical, so no hot-path change).

VERDICT: ACCEPT
[cost $0.0207, opencode tokens {"total": 933146, "input": 56282, "output": 6138, "reasoning": 10054, "cache.write": 0, "cache.read": 860672}]
    tool time: bash 16.0 min
        249s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
        178s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_kweval p_kweval2 p_kweval3 p_kweval4 p_cmp p_mul p_mul2 p_nam
        114s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/r_ops.py <<'EOF' from array import array  def show(tag, fn):     t
        104s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         82s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cgh /tmp/cgb && mkdir -p /tmp/cgh /tmp/cgb && fail=0; 
         78s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_tname p_refl p_plain p_plainclass; do echo "######## $p"; tim
         55s bash   cd /tmp/base && for p in p_tname p_refl p_plainclass p_namecollide; do echo "######## BASE $p"; timeout 240 ba
         48s bash   cat > /tmp/rprobes/r_left.py <<'EOF' from array import array  def run():     a = array("i", [1, 2])     lefts 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T20:22:28Z
