# job job-onelangs2-11030752  started 2026-11-02T22:52:49Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `b5ad31c`.

Fixes:
- `same_file` now stats both paths before returning 0, so `miss-empty`/`miss-enotdir` raise `OSError`.
- `_BinaryFile` methods (`read/readinto/write/seek/tell/flush`) raise `ValueError` after `close()`.
- `from ail import X as Y` rewrites `Y` uses to `X`; rebinding an alias is a named refusal.

Probes (`rv_same2`, `rv_close2`, `rv_alias`) match CPython and the default AOT build; `AIL_UNIFIED_FORCE=1` refuses the AIL-only built-ins by name as before.

Verification:
- All ten converter `--check --flags "--strict"`: `identical`.
- `ail2py_cpython_check`: nine tasks `mismatches 0`; `tally_lang` only `hidden/long_unary_chain`.
- `test_ail_ail2py`, `test_ail_python_syntax`, `test_ail_heapq_bisect`, `test_ail_overflow_error`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet`: all pass.
- `update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 2021824, "input": 53413, "output": 10358, "reasoning": 5669, "cache.write": 0, "cache.read": 1952384}]
    tool time: bash 18.1 min, edit 0.0 min
        266s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1800 python3 ../tools/par_check
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1800 python3 ../tools/par_check
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 1 test_ail_saf
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 1 test_ail_saf
        101s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1800 python3 -B
         96s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && for t in berth_sim chain_relax echo_pack ledger_bin
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/rv_same2.py /tmp/probes/rv_close2.py /tmp/probes/rv
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/rv_same2.py /tmp/probes/rv_close2.py /tmp/probes/rv

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Diff summary.** The change fixes the three prior defects: `same_file` now evaluates both identities; `_BinaryFile` methods call `_ready()` and raise `ValueError` after `close()`; `_ail_imports` rewrites `from ail import X as Y` uses of `Y` to `X` and refuses detected rebinding. `DEVLOG`/manifest updated.

**Verified**
- `same_file`: HEAD `ail.py` matches CPython and the default AOT build for same/different/missing/empty/ENOTDIR/dir/list-item cases (`rv_same4.py`). Base gave `miss-empty 0`/`miss-enotdir 0`, so the defect was real.
- `_BinaryFile`: after `close()`, `read/readinto/write/seek/tell/flush` raise `ValueError`, `closed` is 1, double close is safe (`rv_close4.py`, `rv_close5.py`); base raised `AttributeError`.
- Alias use: `from ail import wrapping_add as w` rewrites normal uses and builds `program.c` byte-identical to the bare program (`/tmp/cid`, `bare==alias`); dict/list/argument uses match CPython (`rv_alias3.py`).
- No-feature C unchanged vs base (`nofeat`, `email` programs).
- All ten converter `--check --flags "--strict"`: `identical`.
- `ail2py_cpython_check`: nine tasks `mismatches 0`; `tally_lang` only `hidden/long_unary_chain`.
- `test_ail_ail2py`, `test_ail_python_syntax` pass; `test_ail_safetynet` passes without the VM cap.
- `update_manifest.py --check`: exit 0.

**Defect (new)**

1. `/tmp/rprobes/rv_alias_import_rebind2.py` — an import rebinds the alias but the rewrite still replaces its uses, giving a silent wrong result. Base refused this program at compile time; HEAD compiles it.
```python
from ail import wrapping_add as w
import os as w
def main() -> None:
    print(w(1, 2))
main()
```
Expected (CPython and base): `TypeError: 'module' object is not callable`, exit 1, no stdout.
Actual (HEAD default and unified build): stdout `3`, exit 0.
Same with `from math import sqrt as w` (`rv_alias_fromimport_rebind.py`) and `import ail as w` (`rv_alias_import_ail.py`). The report's “rebinding an alias is a named refusal” is therefore false for `ast.Import`/`ast.ImportFrom` aliases (and `except`/`match` bindings are also not detected, though those happen to refuse later).

**Pre-existing**
- `AIL_UNIFIED_FORCE=1` refuses the AIL-only built-ins by name (all `g` failures above), on base too.
- `test_ail_safetynet` `S4_generators_gc` fails under `ulimit -v 1500000`; passes without the cap (matches prior review).

**Unverified**
- TCP parity; `current_dir`/`monotonic_ms` exact values.
- `test_ail_files` and `test_ail_corpus_findings3` (not re-run).
- Speed: no compiler/runtime hot path changed, so no `icount` run.

VERDICT: FIX

1. `/tmp/rprobes/rv_alias_import_rebind2.py` — detect `import X as w` / `from X import Y as w` (and `except ... as w`, `match` captures) as alias rebinding and refuse by name, or stop rewriting loads once the alias is rebound. Expected CPython/base: compile refusal (CPython `TypeError`, exit 1); actual HEAD: stdout `3`, exit 0.
[cost $0.0000, opencode tokens {"total": 1812140, "input": 32442, "output": 9852, "reasoning": 15734, "cache.write": 0, "cache.read": 1754112}]
    tool time: bash 9.1 min
        177s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 1 test_ai
        127s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1500 python3 ../tools/par
         97s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 900 python3 -B 
         95s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
          8s bash   cat > /tmp/rprobes/rv_close4.py <<'EOF' from ail import open_binary def main() -> None:     f = open_binary('/
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/rv_same3.py /tmp/rprobes/rv_close3.py /tmp/rprobes
          6s bash   cat > /tmp/rprobes/rv_same4.py <<'EOF' from ail import same_file def show(label: str, f: str, s: str) -> None:
          6s bash   rm -rf /tmp/rprobes/sf && mkdir -p /tmp/rprobes/sf/sub && : > /tmp/rprobes/sf/a && : > /tmp/rprobes/sf/b cat >

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect and committed as `bcaacd6`.

- `from ail import X as Y` now refuses any later rebinding of `Y`: `import Z as Y`, `from Z import W as Y`, `import ail as Y`, `except ... as Y`, `match` captures, plus assignment/`for`/`with`/lambda/`def`/args. Named refusal: `ail import alias Y is rebound`.
- Valid aliases and `import ail` still build `program.c` identical to the bare program and match CPython.

Probes: all 11 rebinding probes refuse by name in default and unified builds; valid alias/module probes match CPython in both builds; `rv_same2`/`rv_close2` still match CPython and refuse by name under `AIL_UNIFIED_FORCE=1`.

Tests: `test_ail_ail2py` 10/10 OK; `test_ail_python_syntax`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `test_ail_safetynet` passes. All ten converter `--check --strict` print `identical`; `ail2py_cpython_check` gives nine tasks `mismatches 0` and only `tally_lang hidden/long_unary_chain`. `update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 1461080, "input": 30794, "output": 7695, "reasoning": 10751, "cache.write": 0, "cache.read": 1411840}]
    tool time: bash 10.7 min, edit 0.0 min
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1200 python3 ../tools/par_check
        180s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 1 test_ail_saf
         97s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1200 python3 -B
         97s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
          9s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 test_ail_ail2py.py 2>&1 | tail -25
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/rv_alias_import_rebind2.py /tmp/rprobes/rv_alias_f
          4s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/alias_valid.py /tmp/probes/alias_import_module.py /
          4s bash   cd /home/runner/work/ail-ci/ail-ci && d=$(mktemp -d /tmp/ccmpXXXX) && cat > $d/bare.py <<'EOF' print(wrapping_

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review 3

**Diff summary.** `same_file` now stats both paths before returning 0, `_BinaryFile` methods raise `ValueError` after `close()`, and `from ail import X as Y` rewrites loads of `Y` to `X` while refusing later rebinding. Tests, DEVLOG and manifest hashes are updated. The structure matches the report, except that “any later rebinding” is not fully enforced.

**Verified claims**
- `same_file` probe (`same_typed2.py`): HEAD `d` matches CPython; base differs at `miss-empty`/`miss-enotdir` (`0` vs `OSError`). Fixed.
- `close_typed.py`: HEAD matches CPython; base raises `AttributeError` after close. Fixed.
- `alias_calls.py`, `alias_list.py`, `alias_nested.py`, `alias_unicode.py`, `import_ail.py`, `import_ail_alias.py`: match CPython in both builds; alias/`import ail` C is byte-identical to the bare program.
- All 11 rebinding forms (assign, for, with, lambda, def, arg, except, match, import, from-import, `import ail`) refuse with `ail import alias w is rebound` in both builds.
- `test_ail_ail2py` 10/10 OK; `test_ail_safetynet`, `test_ail_python_syntax`, `test_ail_files`, `test_ail_corpus_findings3` pass.
- All ten converter `--check --strict` print `identical`.
- `ail2py_cpython_check.py`: nine tasks `mismatches 0`; `tally_lang` only `hidden/long_unary_chain`.
- `update_manifest.py --check` exits 0.

**Defect**

1. `/tmp/rprobes/r3/alias_rebind_same_import.py` — a second `from ail import ... as` binding the same alias is not refused, and earlier loads are silently rewritten to the later target.
   ```python
   from ail import wrapping_add as w
   print(w(1, 2))
   from ail import wrapping_mul as w
   print(w(3, 4))
   ```
   Expected (CPython): `3`, then `12`. Actual (HEAD, both default and unified): `2`, then `12`, exit 0. Base refused the program by name, so this is introduced by the change. Cause: `from_aliases[asname]` is overwritten for each top-level `from ail` import, while the rebinding check exempts every dropped `from ail` alias. Fix: refuse a second binding of an alias whose source name differs (or resolve aliases by source position).

**Pre-existing**
- `from ail import wrapping_add; wrapping_add = 3; wrapping_add(1, 2)`: both base and HEAD silently print `3`, CPython raises `TypeError`.
- `AIL_UNIFIED_FORCE=1` refuses the AIL-only built-ins by name on base and HEAD.
- Untyped `same_file` probes are refused identically on base and HEAD (the built-in needs the typed/general path).

**Unverified:** TCP parity, exact `current_dir`/`monotonic_ms` values, and speed (only frontend/CPython-module code changed, no codegen or runtime hot path).

VERDICT: FIX
1. Refuse (or positionally resolve) a repeated `from ail import ... as Y` alias; probe `alias_rebind_same_import.py`, expected `3`/`12`, actual `2`/`12`.
[cost $0.0000, opencode tokens {"total": 1209095, "input": 51224, "output": 8883, "reasoning": 17724, "cache.write": 0, "cache.read": 1131264}]
    tool time: bash 11.3 min
        234s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pyt
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_ail
         98s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1200 python3 -B
         96s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
         14s bash   cd /tmp/rprobes/r3 cat > alias_rebind_for.py <<'EOF' from ail import wrapping_add as w for w in [1, 2]:     pr
         12s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/r3/*.py; do echo
          8s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/r3/same_typed.py
          7s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 test_ail_ail2py.py 2>&1 | tail -8

FINAL VERDICT: FIX  2026-11-02T23:53:50Z
