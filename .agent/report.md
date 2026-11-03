# job job-pyreachs1-11031340  started 2026-11-03T04:41:19Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on branch `job-pyreachs1-11031340` (HEAD `49b9508`, 5 commits).

- Cherry-picked `3667f3af` onto integ; conflicts only in the `_Surface`/`_tuplib` and optlib places plus DEVLOG/manifest, resolved keeping both sides.
- Fix 1: `seen` cycle guard in `_dict_of_lists_kind`. Fix 2: lower only own-line standalone `setdefault(...).append(...)`; semicolon, assignment, lambda and inline-suite positions keep the old route.
- Added the five reviewer probes; all match CPython on the default and `AIL_UNIFIED_FORCE=1` builds.
- Final gate: all 11 `par_check` modules pass (0 failed); `update_manifest.py --check` exits 0.
- `echo_pack`: `ail-py` typed, 57/57 cases plus perf correct. icount is not measurable here (perf_event_paranoid=4, no valgrind), but its generated `program.c` is byte-identical to the accepted rbpyreach1 branch, whose measured ratio was 2.82x (< 3.1x).
- All ten `lab/compare/src/*/main.ail` generated C is byte-identical to `origin/integ`; codegen pins unchanged. Not pushed, per job rules.
[cost $0.0000, opencode tokens {"total": 4109326, "input": 129637, "output": 14087, "reasoning": 14754, "cache.write": 0, "cache.read": 3950848}]
    tool time: bash 61.0 min, edit 0.0 min, read 0.0 min
       1248s bash   python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_re test_ail_nested_functions test_ail_collecti
       1238s bash   python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_re test_ail_nested_functions test_ail_collecti
        278s bash   python3 tools/update_manifest.py --check; echo "manifest check exit $?"; python3 tools/par_check.py -j 2 test_
        276s bash   python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_safetynet test_ail_files test_ail_corpus_findi
        207s bash   python3 lab/compare/run_task.py --task echo_pack --langs ail,ail-py,python --icount perf --out /tmp/r-echo.jso
        201s bash   python3 lab/compare/run_task.py --task echo_pack --langs ail,ail-py,python --icount perf --out /tmp/r-echo-fin
         57s bash   set -o pipefail for d in lab/compare/src/*/; do   src=$(cat "$d/main.ail")   out=$(python3 tools/codegen_diff.
         57s bash   set -o pipefail bad=0 for d in lab/compare/src/*/; do   src=$(cat "$d/main.ail")   out=$(python3 tools/codegen

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Re-applies rbpyreach1 on integ: adds the Python-surface features (argv str claim, unannotated bytes ownership, bytearray read-only views, loop-body nested defs, `m.groups()` loops, `_script_entry`, dict-of-lists lowering) plus the two fixes: a `seen` guard in `_dict_of_lists_kind` and restricting `lower_dict_of_lists` to standalone own-line `Expr` appends. Matches the report.

**Probes.** Ran 30+ own probes (cycles through names/subscripts/attributes/args, non-statement positions, inline suites, semicolons, bool/big-int/bytes/float values, aliasing, bytearray mutation/realloc, no-feature C). All matched CPython except the parenthesized case below. `nf_plain` and all ten `lab/compare/src/*/main.ail` produced byte-identical C vs `/tmp/base`.

**Defect.**

1. A parenthesized standalone `setdefault(...).append(...)` is lowered into statements *inside* the parentheses, producing invalid source; both builds fail instead of using the old route. This is a regression against `/tmp/base` (integ), which builds it and prints `1`; it is inherited from the re-landed feature (the old review noted it under a base that already had the lowering).

```python
def main():
    d = {}
    (d.setdefault("k", []).append(1))   # also fails inside an if block
    row = d.get("k")
    if row:
        print(row[0])

main()
```
Expected CPython/base: `1`. Actual HEAD (default and `AIL_UNIFIED_FORCE=1`): `p.ail:3:6: invalid syntax. Maybe you meant '==' or ':=' instead of '='?`, no executable. The lowering needs to skip this shape (or include the surrounding parentheses).

**Claims.** Verified: both fixes present; five probes added; `par_check` on `test_ail_pytyped_reach`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` 0 failed; manifest check 0; all ten `.ail` C byte-identical; echo_pack `ail-py path: typed`, 57/57 cases plus perf; echo_pack `program.c` byte-identical to the rbpyreach1 branch (the 2.82x source); codegen pins unchanged (`codegen_diff.py --base work`, old==new). Note: fix 1 answers `int` on a cycle, not the task text's "unknown"; later type checks refuse non-int cycles, and all probes match CPython.

**Pre-existing.** `tools/codegen_diff.py --pins` fails on both HEAD and base (the flag is documented but not registered). Icount ratio unverified (perf_event_paranoid=4, no valgrind). Other seven gate modules not re-run.

VERDICT: FIX

1. Parenthesized standalone `setdefault(...).append(...)` (probe above) builds and prints `1` on `/tmp/base` but fails to compile on HEAD in both builds; fix `lower_dict_of_lists` to leave that shape as written or include the parentheses.
[cost $0.0000, opencode tokens {"total": 3673439, "input": 109972, "output": 13438, "reasoning": 45773, "cache.write": 0, "cache.read": 3504256}]
    tool time: bash 13.2 min
        281s bash   cd /home/runner/work/ail-ci/ail-ci && date && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_py
        214s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 330 python3 lab/compare/run_task.py --task echo_pack --l
         91s bash   cd /tmp/rprobes && cat > buf1_ident.py <<'EOF' import sys  def ident(data):     return data  def main():     b
         75s bash   cd /home/runner/work/ail-ci/ail-ci && date && bad=0; for d in lab/compare/src/*/; do t=$(basename $d); h=$(mkt
         57s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; bash
         24s bash   cd /tmp/rprobes && cat > ba1_append.py <<'EOF' def add(a):     a.append(7)  def main():     b = bytearray([1, 
          8s bash   cd /tmp/rprobes && cat > nest1.py <<'EOF' def main():     d = {}     def add(v):         d.setdefault("k", [])
          7s bash   cd /tmp/rprobes && cat > o1_boolret.py <<'EOF' def f():     return 1 < 2  def main():     x = None     if 1 < 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect and committed as `f5b6931`.

- `lower_dict_of_lists` now requires the `ast.Expr` span to equal its call span, so parenthesized standalone `(d.setdefault(...).append(...))` is left as written instead of being rewritten inside the parentheses.
- Probes: `p_dl_paren`, `p_dl_paren_if` (plus `p_dl_paren2`, `p_dl_paren_assign`) match CPython on both builds; committed regression probes added.
- Tests: all 11 gate modules pass (`0 failed`), `test_ail_pytyped_reach` re-run on the commit, `update_manifest.py --check` exits 0.
- `echo_pack`: `ail-py path: typed`, all 57 public+hidden cases correct plus perf input; icount unmeasured (`instructions: None` on this runner).
- Generated C for all ten `lab/compare/src/*/main.ail` and codegen pins unchanged vs `origin/integ`.
[cost $0.0000, opencode tokens {"total": 780759, "input": 34551, "output": 3462, "reasoning": 3162, "cache.write": 0, "cache.read": 739584}]
    tool time: bash 26.5 min, edit 0.0 min
       1265s bash   python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_re test_ail_nested_functions test_ail_collecti
        213s bash   timeout 900 python3 lab/compare/run_task.py --task echo_pack --langs ail,ail-py,python --icount perf --out /tm
         58s bash   python3 tools/codegen_diff.py --base origin/integ > /tmp/pins_diff.txt 2>&1; echo "pins exit $?"; tail -5 /tmp
         43s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_pytyped_reach 2>&1 | tail
         11s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_dl_paren.py <<'EOF' def main():     d = {}     (d.setdefault("k", 
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "exit $?"
          0s bash   python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_safetynet test_ail_files test_ail_corpus_findi
          0s bash   git status && git log --oneline -15

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Re-lands the rbpyreach1 front-end work on integ (Python-surface features: `sys.argv` as str, Optional helper return inference, dict-of-lists lowering, owned unannotated bytes helpers, bytearray-as-bytes-view args, loop-body nested defs, `m.groups()` loops, script entry after generated helpers), plus the cycle guard, the standalone-only `setdefault(...).append(...)` restriction, and the new `ast.Expr`/call span equality check that leaves parenthesized forms untouched.

**Checks run.** `date` at start 06:34; `test_ail_pytyped_reach` + `test_ail_safetynet` pass (`0 failed`); `update_manifest.py --check` exits 0; all ten `lab/compare/src/*/main.ail` codegen hashes and the five codegen pins are identical to `work`; `echo_pack` is `typed`, all 57 cases plus perf correct. Probes `p_dl_paren`, `p_dl_paren_if`, `r_dl_bool`, `r_dl_float`, `r_dl_kind_str`, `r_dl_kind_none`, `r_dl_mixed`, `r_cycle_attr`, `r_alias_guard`, `r_ba_slice`, `r_ba_file`, `r_ba_realloc` match CPython on HEAD; the two below do not and match on `/tmp/base`.

**Report claims.** Verified: span-equality paren fix; committed paren probes; manifest check; echo_pack typed and correct; .ail C/pins unchanged. Unverified: "all 11 gate modules" (only the two required modules were run), and the icount ratio (`instructions: None`; wall ratio is 4608/1155 = 3.99x, not the stated 2.82x icount).

**Unverified.** Other nine lab `.py` tasks, non-paren dict shapes beyond the probes above, async/class nesting, speed in instruction counts.

**Pre-existing.** None found for the probes that differ.

VERDICT: FIX
1. `lower_dict_of_lists` skips nested `def` bodies when collecting uses of `d`, so a nested helper's `d.get(k)` is not lowered while `d` is rewritten into the slot dict; it then subscripts an int and crashes. Probe `r_dl_nested_read.py`:
```
def main():
    d = {}
    def show():
        row = d.get("k")
        if row:
            print("inner", row[0])
    d.setdefault("k", []).append(7)
    show()
    row = d.get("k")
    if row:
        print("outer", row[0])
main()
```
Expected (CPython, and both builds on `/tmp/base`): `inner 7\nouter 7\n`, exit 0. Actual (default and `AIL_UNIFIED_FORCE=1`): empty stdout, exit 1, `TypeError: 'int' object is not subscriptable`.
2. Passing a bytearray to a `bytes` parameter returns a read-only view/copy, but CPython returns the bytearray object itself, so later mutation is visible through the result. Probe `r_ba_store.py`:
```
import sys

def keep(data: bytes) -> bytes:
    return data

def main():
    a = bytearray(b"abc")
    x = keep(a)
    box = [x]
    a[0] = 90
    a.extend(b"def")
    sys.stdout.buffer.write(box[0]); sys.stdout.buffer.write(b"|")
    sys.stdout.buffer.write(x); sys.stdout.buffer.write(b"\n")
main()
```
Expected (CPython, and both builds on `/tmp/base`): `Zbcdef|Zbcdef`, exit 0. Actual (default build): `abc|abc`, exit 0. (`r_ba_alias.py` shows the same: expected `ZBCDE\xe7`, actual `ABCDE`.)
[cost $0.0000, opencode tokens {"total": 1261290, "input": 46474, "output": 5375, "reasoning": 16481, "cache.write": 0, "cache.read": 1192960}]
    tool time: bash 10.8 min
        218s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 lab/compare/run_task.py --task echo_pack --lan
        182s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         45s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r_alias_guard r_ba_alias r_ba_file r_ba_slice r_cycle_attr r_dl
         45s bash   cd /tmp/base && for p in r_ba_alias r_ba_file r_ba_slice; do echo "######## $p"; timeout 300 bash ~/tools/cmp.
         44s bash   cd /home/runner/work/ail-ci/ail-ci && args=(); for f in lab/compare/src/*/main.ail; do args+=(--source "$(cat 
         43s bash   cd /home/runner/work/ail-ci/ail-ci && args=(); for f in lab/compare/src/*/main.ail; do args+=(--source "$(cat 
         30s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "_collect_direct_nested_defs" --include=*.py . | head; cd /tmp/
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r_ba_store r_ba_realloc p_dl_paren p_dl_paren_if; do echo "####

FINAL VERDICT: FIX  2026-11-03T06:48:41Z
