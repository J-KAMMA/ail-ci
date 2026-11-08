# job job-rbfdlsp2-11082100  started 2026-11-08T12:03:03Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Re-applied `job-fdlsp2-11081741` on `job-rbfdlsp2-11082100`.

**Applied:** the LSP hover change (`packaging/ail_lang/lsp.py`, `docs/LSP.md`, `lab/lsp/RESULTS.md`, `lab/lsp/hover/`, `AIL_CURRENT/test_ail_lsp_hover.py` + `tests.d` registration). The `.github/workflows/agent-worker.yml` hunk was already present on this tree, so it was left unchanged. `tools/diff_ids.py` does not exist here; `tools/update_manifest.py` regenerated the two new-file pins and `--check` passes.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, general and default builds): `hover_types.py`, `hover_mutation.py`, `hover_dict_keys.py`, `hover_values.py` — all stdout/exit match CPython in both builds. The authoritative hover probe `test_ail_lsp_hover` checks all 45 `expect.json` cases (38 right, 7 deliberately empty) and passes.

**Tests on final commit, `-j 2`:** `test_ail_lsp`, `test_ail_lsp_def`, `test_ail_lsp_hover`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed, 211 s.

Committed as `45dfe1cc`; only `.agent/pipeline.md` remains untracked (excluded). DEVLOG entry added at the top of `DEVLOG.md` dated 2026-11-08.
[cost $0.0000, opencode tokens {"total": 1462638, "input": 65217, "output": 5989, "reasoning": 7240, "cache.write": 0, "cache.read": 1384192}]
    tool time: bash 8.7 min, edit 0.0 min, write 0.0 min
        284s bash   python3 tools/par_check.py -j 2 test_ail_lsp test_ail_lsp_def test_ail_lsp_hover test_ail_safetynet test_ail_f
        212s bash   python3 tools/update_manifest.py --check && echo MANIFEST_OK; python3 tools/par_check.py -j 2 test_ail_lsp tes
         10s bash   for p in /tmp/probes/hover_types.py /tmp/probes/hover_mutation.py /tmp/probes/hover_dict_keys.py /tmp/probes/h
          6s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-fdlsp2-11081741 2>&1 | tail -5; git diff --stat 9d53b559bd
          6s bash   cd AIL_CURRENT && python3 -X utf8 -B -m unittest -v test_ail_lsp_hover 2>&1 | tail -20
          0s bash   git add AIL_CURRENT/test_ail_lsp_hover.py AIL_CURRENT/tests.d/test_ail_lsp_hover.txt lab/lsp/hover && python3 
          0s bash   grep -rn "DEVLOG" .agent AIL_CURRENT/docs/spec/DEVLOG.md 2>/dev/null | head -20; echo ---; git show b52f7cf6 -
          0s bash   git status && git log --oneline -5 && git branch --show-current

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fdlsp2 re-application (`45dfe1cc`)

**What the change does.** Re-applies the accepted fdlsp2 LSP hover feature: `packaging/ail_lang/lsp.py` now maps a `--debug` build's C locals to Python types, keyed by Python scope/def line and cached per document version; plus docs, `lab/lsp/hover/`, `test_ail_lsp_hover.py`, `tests.d` registration, DEVLOG and two manifest pins. No compiler/runtime change.

**Re-application fidelity — verified.** `lsp.py`, `docs/LSP.md`, `lab/lsp/RESULTS.md`, `lab/lsp/hover/*` and `test_ail_lsp_hover.py` are byte-identical to `FETCH_HEAD`; `agent-worker.yml` already equals `FETCH_HEAD`. No other source edit. `tools/diff_ids.py` is absent here (confirmed; also absent from the source head). `update_manifest.py --check` passes. Commit has no Co-Authored-By (correct for this model); only `.agent/pipeline.md` untracked.

**Claims.** Verified: 45-case hover test passes; all six named modules pass on HEAD (`test_ail_lsp`, `_def`, `_hover`, `safetynet`, `_files`, `_corpus_findings3`; 0 failed, 240 s total). DEVLOG entry/date present. Not re-run: the four `cmp.sh` probes in `/tmp/probes` (not in repo; compiler untouched, and a plain program's `--debug` C is byte-identical base vs HEAD).

**Defects (new hover behaviour, base shows nothing).**

1. Method-name heuristic ignores the receiver's real return type. `_bool_kind` maps any `.isalpha()` to bool and any `.count()` to non-bool by name only.
   Probe `methodname2.py`: `class C: def isalpha(self)->int: return 5`; `x = c.isalpha()`; compiled output `6\n5` matches CPython, `type(x).__name__=int`. Hover x = `` `bool` (inferred by the typed path) ``. Expected `int`/nothing.
   Probe `methodname3.py`: `def count(self)->bool: return True`; hover x = `int`; CPython/built output is bool (`True\nTrue`). Expected `bool`/nothing.

2. `_mutated_names` does not mark a bare-name `AugAssign`, so a mutated list literal is still trusted.
   Probe `aug.py`: `xs = [True]; xs += [1]; x = xs[1]`; compiled output `1` matches CPython, `type(x).__name__=int`. Hover x = `bool`. Expected nothing (docs: no item type once the container is mutated) or `int`.

**Pre-existing (not blocking).** `collision.py` (top-level `f()->bool`, nested `f()->int`) is miscompiled on base (`True True` vs CPython `7 7`); the new hover mirrors that pre-existing compiler name-collision, so I do not count it.

No speed work relevant (LSP only; no gdev icount run).

VERDICT: FIX
1. `_bool_kind`'s method-name tables (`_BOOL_METHODS`/`_INT_METHODS`) must not guess from the method name alone; use the receiver type/return annotation. Probes `methodname2.py`, `methodname3.py` above.
2. `_mutated_names` must treat `AugAssign` to a bare container name (e.g. list `+=`) as mutation, or the item type must become unknown. Probe `aug.py` above.
[cost $0.0000, opencode tokens {"total": 1878411, "input": 41980, "output": 9715, "reasoning": 32924, "cache.write": 0, "cache.read": 1793792}]
    tool time: bash 4.9 min, write 0.0 min
        152s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_lsp test_ail_lsp_def te
         88s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_lsp_hover test_ail_safe
         18s bash   cd /tmp/rprobes && sed -i 's|AIL_SDK_DIR=str(ROOT)|AIL_SDK_DIR=str(ROOT / "AIL_CURRENT")|; s|stderr=subprocess
         16s bash   cd /tmp/rprobes && sed 's|ROOT = Path("/home/runner/work/ail-ci/ail-ci")|ROOT = Path("/tmp/base")|' hv_probe.p
         14s bash   cd /tmp/rprobes/hv && python3 - <<'PY' import re src = open('/tmp/rprobes/hv_probe.py').read() add = '''    ("
          2s bash   cd /tmp/rprobes/hv && for f in types.py attr.py collision.py mixed.py; do echo "=== $f"; AIL_SDK_DIR=/home/run
          1s bash   cd /tmp/rprobes/hv && cat > methodname2.py <<'PY' class C:     def __init__(self) -> None:         self.n = 0 
          1s bash   mkdir -p /tmp/rprobes/nofeat && cd /tmp/rprobes/nofeat && cat > plain.py <<'PY' def add(a: int, b: int) -> int

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `packaging/ail_lang/lsp.py` and committed as `843b4aea`.

- Method calls now use receiver type/return annotation; name-only guessing removed. Probes: `class.isalpha()->int` → int, `class.count()->bool` → bool, unknown/unannotated receiver → nothing, annotated `str`/bytes still correct.
- `AugAssign` to a bare container name now marks it mutated; `xs = [True]; xs += [1]; x = xs[1]` → nothing.

Verification (numbers):
- `/tmp/probes/hover_methods.py`: 10/10 passed.
- `methodname2.py`, `methodname3.py`, `aug.py` via `cmp.sh`: both builds match CPython stdout/exit.
- Required tests `-j 2`: 6/6 modules passed, 0 failed, 193 s (`test_ail_lsp`, `_def`, `_hover`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `update_manifest.py --check`: passed.
[cost $0.0000, opencode tokens {"total": 1045543, "input": 47998, "output": 6269, "reasoning": 13612, "cache.write": 0, "cache.read": 977664}]
    tool time: bash 3.3 min
        194s bash   date && python3 tools/par_check.py -j 2 test_ail_lsp test_ail_lsp_def test_ail_lsp_hover test_ail_safetynet te
          4s bash   cat > /tmp/probes/hover_methods.py <<'PY' import ast import re import sys  sys.path.insert(0, "/home/runner/wo
          0s bash   python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.read_text() entry = '''## 2026-11-08 -- 
          0s bash   cd /tmp/probes && PYTHONPATH=/home/runner/work/ail-ci/ail-ci/packaging AIL_SDK_DIR=/home/runner/work/ail-ci/ai
          0s bash   git add DEVLOG.md packaging/ail_lang/lsp.py && git commit -m "fdlsp2 hover: type methods by receiver, treat +=
          0s bash   git status && git log --oneline -5 && ls
          0s bash   cd /tmp/probes && sed -i 's/no_annotation, 10, "x"/no_annotation, 8, "x"/' hover_methods.py && PYTHONPATH=/hom
          0s bash   find . -name 'test_ail_lsp_hover.py' -o -name '*lsp*hover*' | head; sed -n '30,60p' docs/LSP.md

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Re-applies the accepted fdlsp2 LSP-hover feature (typed-path C locals → `int`/`float`/`str`/`bytes`/`list`/`dict`, cached per document version) plus docs, `lab/lsp/hover/`, `test_ail_lsp_hover`, `tests.d` registration, DEVLOG and manifest pins; commit `843b4aea` additionally types method calls from the receiver and treats a bare-name `+=` as mutation.

**Re-application fidelity — verified.** `lsp.py` equals `FETCH_HEAD` except the two review fixes; `docs/LSP.md`, `lab/lsp/RESULTS.md`, `lab/lsp/hover/*`, `test_ail_lsp_hover.py` and the `tests.d` file are byte-identical to `FETCH_HEAD`; `agent-worker.yml` already matches. `tools/diff_ids.py` is absent here; `update_manifest.py --check` passes.

**Claims.** Verified: `hover_methods.py` 10/10; end-to-end `methodname2`→`int`, `methodname3`→`bool`, `aug`→nothing; the three `cmp.sh` programs match CPython in both builds; 6 modules pass on HEAD (`test_ail_lsp`, `_def`, `_hover`, `safetynet`, `_files`, `_corpus_findings3`; 0 failed, 212 s). The `aug.py` example is refused by the strict typed path, so that claim is only unit-tested (fabricated `int64_t` map), not end-to-end. Neither review fix has a committed regression test; `expect.json` does not cover class methods or `+=`.

**Defects (both new: base hover is `null`, HEAD hover is a wrong type; compiled AIL matches CPython).**

1. `_function_returns` keys return annotations by bare name with `setdefault`, so a nested function shadowing a module function uses the module's annotation.
```
def f() -> bool: return True
def outer() -> None:
    def f() -> int: return 1
    x = f(); print(x)
outer()
```
CPython and the compiled AIL print `1` (`type(x).__name__ == 'int'`). HEAD hover on `x`: `` `x`: `bool` (inferred by the typed path) ``. Expected `int` or nothing. `/tmp/rprobes/probe_nestedfunc2.py`.

2. `_class_methods` uses `setdefault`, so with a duplicate method definition the first annotation wins while Python and the compiler use the last.
```
class C:
    def __init__(self) -> None: self.n = 0
    def count(self) -> int: return 1
    def count(self) -> bool: return True
def g() -> None:
    c = C(); x = c.count(); print(x)
g()
```
CPython and the compiled AIL print `True` (bool). HEAD hover on `x`: `` `x`: `int` ``. Expected `bool` or nothing. `/tmp/rprobes/probe_dupmeth.py`.

**Pre-existing (not counted).** `probe_subclass.py` (`B(A)` overriding `count()->bool`) is miscompiled on the base too (AIL prints `1`, CPython `True`); the hover mirrors the compiler's `int`. Same for the `collision.py` miscompile noted in review 0.

**Not checked.** No speed work: the diff is LSP-only and a plain program's `--debug` `program.c` is byte-identical base vs HEAD.

VERDICT: FIX
1. `_function_returns` must resolve a call in its scope chain (or return unknown when a name has different annotations), not the first same-named def in the file. Probe `probe_nestedfunc2.py`: expected `int`/nothing, actual `` `bool` ``.
2. `_class_methods` must take the last definition of a duplicate method (or return unknown), not `setdefault`'s first. Probe `probe_dupmeth.py`: expected `bool`/nothing, actual `` `int` ``.
[cost $0.0000, opencode tokens {"total": 6020573, "input": 62357, "output": 15497, "reasoning": 67391, "cache.write": 0, "cache.read": 5875328}]
    tool time: bash 5.1 min, write 0.0 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup bash -c 'python3 tools/par_check.py -j 2 test_ail_lsp_hover test_a
        120s bash   cd /home/runner/work/ail-ci/ail-ci && setsid bash -c 'python3 tools/par_check.py -j 2 test_ail_lsp_hover test_
         15s bash   cd /tmp/rprobes && timeout 300 python3 hv_probe.py 2>&1 | tail -50
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 env PYTHONUTF8=1 AIL_NO_CACHE=1 PIPE_CC=$(comman
          4s bash   cd /tmp && for f in methodname2.py methodname3.py aug.py; do echo "=== $f ==="; timeout 120 bash ~/tools/cmp.s
          3s bash   cd /tmp/rprobes && timeout 240 python3 lsp_probe.py /tmp/rprobes/probe_methods.py '[["a = c.isalpha()","a"],["
          2s bash   cd /tmp/rprobes && cat > probe_augscalar.py <<'PY' def f() -> None:     x = True     x += 1     y = x     z = 
          2s bash   cd /tmp/rprobes && cat > probe_annreassign.py <<'PY' class C:     def __init__(self) -> None:         self.n =

FINAL VERDICT: FIX  2026-11-08T12:51:24Z
