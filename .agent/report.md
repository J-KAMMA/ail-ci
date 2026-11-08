# job job-fdlsp2-11081741  started 2026-11-08T08:45:43Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `b6d31f2`.

- Dict iteration now types from keys: `/tmp/rprobes/pD.py` → `` `k`: `bool` `` (was `int`).
- Nested functions are matched by Python scope/def line, not mangled C name: `/tmp/rprobes/pQ.py` → nested `` `x`: `bool` ``, top-level `` `x`: `float` ``.
- Added `dict_iter.py`, `nested_name.py`, and 4 regression cases to `lab/lsp/hover/expect.json`; updated `RESULTS.md` and `docs/LSP.md`.

Verification:
- `oracle: 42 cases, 36 must be shown, 0 CPython mismatches`
- `test_ail_lsp_hover.py`: pass (42 cases)
- `test_ail_lsp.py`: 37 pass
- `test_ail_safetynet.py`: 5 pass
- `test_ail_files.py`: 18 pass, 1 skip
- `test_ail_corpus_findings3.py`: 2 pass
- `python3 tools/update_manifest.py` and `--check`: clean
[cost $0.0000, opencode tokens {"total": 3926334, "input": 97654, "output": 12178, "reasoning": 15286, "cache.write": 0, "cache.read": 3801216}]
    tool time: bash 10.3 min
        243s bash   cd /home/runner/work/ail-ci/ail-ci && (ulimit -v 1500000; python3 AIL_CURRENT/test_ail_corpus_findings3.py) 2>
        136s bash   cd /home/runner/work/ail-ci/ail-ci && (ulimit -v 1500000; python3 AIL_CURRENT/test_ail_safetynet.py) 2>&1 | ta
        107s bash   cd /home/runner/work/ail-ci/ail-ci && (ulimit -v 1500000; python3 AIL_CURRENT/test_ail_files.py) 2>&1 | tail -
         50s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp.py 2>&1 | tail -20
         33s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp.py 2>&1 | tail -10
          7s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp_hover.py 2>&1 | tail -30
          6s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/lsp/hover/oracle.py && python3 AIL_CURRENT/test_ail_lsp_hove
          6s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp_hover.py 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fdlsp2 fix (b6d31f2)

**What the change really does.** `_for_iter_kind` now resolves a name's assignments (and aliases) to the element kind of a literal, taking a dict's *keys*, and `_compiler_type_map` re-keys its `{local: C type}` maps by `(Python function name, def line)` recovered from the `#line` directives instead of the mangled C function name. That matches the report.

**Review defects checked (both fixed).**
- pD (`for k in d`, `d={True:1}`): `/tmp/rprobes/pD.py:3` → ``` `k`: `bool` ``` (was `int`). Fixed.
- pQ (nested `helper` beside top-level `helper`): nested `/tmp/rprobes/pQ.py:8` → `bool`, top-level line 2 → `float`. Fixed.

### Defects

1. **A name with a bool-key dict assignment and a later unknown-name assignment is typed from the dict only.** `_combine_bool` drops `"unknown"`, so `BooleanDict then Name(param)` becomes `bool`. New wrong type (base gave the right `int`).
   `/tmp/rprobes/pZ6.py`:
   ```python
   def make() -> dict[int, int]:
       return {2: 3}

   def f(base: dict[int, int]) -> None:
       d = {True: 1}
       d = base
       for k in d:
           print(k)

   f(make())
   ```
   Hover on `k` at line 8: **expected** `` `k`: `int` `` (CPython prints `2`; base prints `` `k`: `int` ``), **actual** `` `k`: `bool` (inferred by the typed path) ``. Program output itself still matches (cmp.sh clean).

2. **A correct inferred type disappears when a lambda shifts the `main`/`run` line numbers into the function's span.** The `main` C function's `#line` set is `[2,3,4,5]`, inside `f`'s `1..5`, so it resolves to scope `f` and overwrites `f`'s map with `{}`. Regression: base shows `float`, HEAD shows nothing.
   `/tmp/rprobes/pX2.py`:
   ```python
   def f() -> None:
       x = 1 / 2
       h = lambda x: x + 1
       print(x)
       print(h(2))
   f()
   ```
   Hover on `x` (line 2 or line 4): **expected** `` `x`: `float` (inferred by the typed path) `` (base), **actual** nothing. Not a wrong type, but a caused loss of a previously-correct answer.

### Pre-existing (identical on `/tmp/base`)
- `/tmp/rprobes/pRows.py` (list of list of bool): `v` shows `int`, CPython `bool` — same on base.
- pD/pQ default build print `1`/`0` for `True`/`False` — same on base.

**Claims checked.** "Dict iteration from keys / pD bool" verified; "nested matched by scope/def line / pQ" verified; "`dict_iter.py`, `nested_name.py`, 4 regression cases" verified; "oracle 42 cases, 36 shown, 0 CPython mismatches" verified; `test_ail_lsp_hover`, `test_ail_lsp`, `test_ail_safetynet` pass (par_check -j 2, 3 modules, 0 failed); `update_manifest.py --check` clean. "Fixed both review defects" verified. "0 wrong" is **false** (defect 1).

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` (not run; not required for this change), speed (LSP-only, no hot path).

VERDICT: FIX
1. `/tmp/rprobes/pZ6.py` hover on `k` (line 8): expected `` `k`: `int` `` (CPython `2`, base `int`), actual `` `k`: `bool` (inferred by the typed path) ``; `_for_iter_kind`/`_combine_bool` must treat an unknown assignment of the iterated name as unknown, not drop it.
2. `/tmp/rprobes/pX2.py` hover on `x` (line 2/4): expected `` `x`: `float` (inferred by the typed path) `` (base), actual nothing; the `main`/`run` C function (whose `#line` set can fall inside a user function after a lambda line shift) must not overwrite that function's type map.
[cost $0.0000, opencode tokens {"total": 3455224, "input": 110816, "output": 14030, "reasoning": 43850, "cache.write": 0, "cache.read": 3286528}]
    tool time: bash 4.1 min
        138s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (ulimit -v 1500000; python3 ../tools/par_check.py -j 2 test_
          8s bash   for f in pA pB pC pE; do echo "== base $f"; AILROOT=/tmp/base python3 /tmp/rprobes/hover2.py /tmp/rprobes/$f.p
          8s bash   cat > /tmp/rprobes/pZ3.py <<'PY' def f() -> None:     d = {True: 1}     base = {2: 3}     d = {**base, 4: 5}  
          7s bash   cat >> /tmp/rprobes/pL.py <<'PY'  a() b() c() d() e() f() g() h() PY python3 /tmp/rprobes/hover2.py /tmp/rprob
          7s bash   cat > /tmp/rprobes/pL.py <<'PY' def a() -> None:     xs = [True, False]     for x in xs:         print(x)  def
          7s bash   cat > /tmp/rprobes/pShift.py <<'PY' def f() -> None:     x = 1 / 2     print(x)     a = lambda b: b     c = la
          7s bash   sed 's#ROOT=Path(.*)#ROOT=Path(os.environ.get("AILROOT","/home/runner/work/ail-ci/ail-ci"))#' /tmp/rprobes/hov
          6s bash   cat > /tmp/rprobes/pZ2.py <<'PY' def f() -> None:     d = {True: 1}     d = sorted([2, 3])     for k in d:    

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both remaining defects and committed (`7678420`).

- pZ6 (`for k in d; d={True:1}; d=base`): `_combine_bool` no longer drops `"unknown"`, so `k` shows nothing instead of a wrong `bool`. (The safe answer; CPython's `int` here can't be proven source-side.)
- pX2 (lambda line shift): C function names must now match the Python scope name, so `main`/synthetic lambda maps can't overwrite a function's map; `x` shows `float` again.

Added regression files/cases (`dict_unknown.py`, `lambda_scope.py`) and updated docs/RESULTS.

Verification on final commit:
- Probes: pZ6/pX2 hover now correct; `cmp.sh` pZ6/pX2 stdout+exit match CPython.
- `oracle.py`: 45 cases, 38 shown, 0 CPython mismatches.
- `par_check -j 2` on test_ail_lsp_hover, test_ail_lsp, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3: 5 modules, 0 failed.
- `tools/update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 2224146, "input": 69519, "output": 9501, "reasoning": 11238, "cache.write": 0, "cache.read": 2133888}]
    tool time: bash 11.5 min, edit 0.0 min, write 0.0 min
        355s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; python3 ../tools/par_check.py -j 2 test_a
        296s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; python3 ../tools/par_check.py -j 2 test_a
          8s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/lsp/hover/oracle.py 2>&1 | tail -8 && python3 AIL_CURRENT/te
          7s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp_hover.py 2>&1 | tail -20
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for p in pZ6 pX2 pD pQ; do echo "== $p"; bash ~/tools/cmp.sh /tmp/rprobe
          6s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp_hover.py 2>&1 | tail -20
          2s bash   cd /home/runner/work/ail-ci/ail-ci && echo "== pD"; cat /tmp/rprobes/pD.py; python3 /tmp/rprobes/hover2.py /tm
          2s bash   cd /home/runner/work/ail-ci/ail-ci && echo "== pZ6"; python3 /tmp/rprobes/hover2.py /tmp/rprobes/pZ6.py 6:8 7:

## review 1 failed to run:           1s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONPATH=packaging:AIL_CURRENT python3 -B           0s bash   cd /home/runner/work/ail-ci/ail-ci && PYTHONPATH=packaging:AIL_CURRENT python3 -B -c " import sys from pathlib           0s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_SDK_DIR=$PWD/AIL_CURRENT PYTHONPATH=packaging:AIL_CURRENT python3 -B 

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fdlsp2 fixes (b6d31f2, 7678420)

**What the change really does.** It makes the LSP's compiler-type lookup safe in three places: `_combine_bool` no longer drops an `unknown` binding (an ambiguous iterable yields nothing); `_for_iter_kind` follows aliases, guards cycles, and takes a dict literal's **keys** instead of its values; and `_compiler_type_map` keys a C function's locals by the Python scope `(name, def line)` recovered from `#line` directives plus a mangled-name check (`_c_name_is_scope`), rather than by the report's C name. That matches the report.

**Prior defects — both fixed.** `pD.py` (dict-literal loop) now `k: bool` (was `int`); `pQ.py` (nested same-name `helper`) now nested `x: bool` and top-level `x: float` (was `float`/wrong scope). `pZ6.py` now nothing (was `bool` in the intermediate commit, `int` on `work`); `pX2.py` `x: float` at both reads.

**Claims checked**
- "oracle 45 cases, 38 shown, 0 CPython mismatches" — verified exactly; per file `probe.py 32/37, general 0/1, dict_iter 2/2, nested_name 2/2, dict_unknown 0/1, lambda_scope 2/2`.
- "par_check 5 modules, 0 failed" — I re-ran 3 on HEAD: `test_ail_lsp` 63.5s, `test_ail_lsp_hover` 8.2s (compiler path ran, not skipped), `test_ail_safetynet` 141.9s — all ok. The other two not re-run.
- `tools/update_manifest.py --check` — rc 0; `lsp.py`/lab files are unpinned, so no shard change is needed.
- "Diff touches only allowed files" — verified (8 files; no restricted file, no `bench/apps`).
- "0 wrong" — verified on the 45 expect cases and on my probes below.

**New probes (HEAD, and base where the answer changed).** `pM1` `def main` + lambda → `x: float`; `pM6` bool key via list item (`{xs[0]:1}`) and via dict value (`{e[1]:2}`) → `bool` both; `pM7` nested `f` inside `f` → nested `bool`, outer `float`; `pM17` `def main`/nested `main` → nested `bool`; `pM8`/`pM18` method locals, incl. a method named like a top-level `helper` → `bool`/`float`; `pM20` negative int key → `int`; `pM21` tuple key → nothing; `pM15` empty list → nothing; `pM11` alias `append`, `pM4` set/tuple, `pM13` attribute dict, `pM14` argument dict, `pM16`, `pM22` nested-function store, `pM23` `|=` on a dict, `pM24` closure list store → named compile-time refusal or nothing. No crash, no wrong type found. `cmp.sh` on pZ6/pX2 matches CPython stdout+exit. Generated C for a non-feature program (`g00_000.py`) is byte-identical to base (`diff program.c`).

**Pre-existing.** `pD/pQ/pM6/pM7` default build prints `1`/`0` where CPython prints `True`/`False` — identical on `/tmp/base`.

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` (not re-run, per the review rule); icount (LSP-only change, no compiler/runtime hot path).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=74 out_tokens=59829]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T11:50:02Z
