# job job-fdlsp2-11081517  started 2026-11-08T06:18:36Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `fa31802` on `job-fdlsp2-11081517`.

- Hover now reads compiler-inferred local types from a `--debug` build's C declarations, maps only one-to-one C types, and keeps source-certain answers. `int64_t` is only shown as `int` when the source rules out `bool`.
- Builds are cached per document version and run only after `didSave` or 1 s idle.
- Probe: **32/35 shown, 0 wrong** (3 deliberate empty: `sum()` numeric type, mixed int/float box, general-path name). Oracle: **35 cases, 0 CPython mismatches**.
- Tests pass: `test_ail_lsp_hover.py`, `test_ail_lsp.py`, `test_ail_lsp_def.py`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; manifest `--check` passes.
- `cmp.sh` on the probe and general-path files matches CPython in both default and `AIL_UNIFIED_FORCE=1` builds.
- Diff from the task base touches only the allowed files plus manifest shards.

Not pushed and CI was not run, per the runner instruction “commit your work on the current branch; do not push.”
[cost $0.0000, opencode tokens {"total": 6588493, "input": 75144, "output": 24146, "reasoning": 36723, "cache.write": 0, "cache.read": 6452480}]
    tool time: bash 9.7 min
        388s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && for t in test_ail_safetynet test_ail_files test_ail
         98s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && python3 AIL_CURRENT/test_ail_lsp_hover.py && python
         40s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && python3 AIL_CURRENT/test_ail_lsp.py 2>&1 | tail -20
         31s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && python3 AIL_CURRENT/test_ail_lsp_hover.py && python
          5s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && for f in lab/lsp/hover/probe.py lab/lsp/hover/gener
          4s bash   cat > AIL_CURRENT/test_ail_lsp_hover.py <<'EOF' """`ail lsp` hover with compiler-inferred types: the 35-name p
          3s bash   cd AIL_CURRENT && ulimit -v 1500000 && echo '--- interface ---' && python3 -B ail_chatgpt.py check ../lab/lsp/
          1s bash   mkdir -p /tmp/probes && cat > /tmp/probes/hoverprobe.py <<'EOF' def add_one(x: int) -> int:     return x + 1  

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I've finished reviewing. Here is what I found.

**What the diff really does:** `packaging/ail_lang/lsp.py` runs a cached `compile --strict --debug` per document version, parses the generated C declarations, and adds a second hover tier ("inferred by the typed path"); it also adds a hand-written bool/int source analysis (`_bool_kind`, `_subscriept_kind`, `_for_iter_kind`) to disambiguate `int64_t` (`bool` vs `int`). Everything else is docs, `lab/lsp/hover/*`, the new test, and manifest shards. No compiler/runtime file changed, so built programs are unaffected.

**Defects (change caused; base hover returns `None` for both):**

1. `/tmp/rprobes/p_mut_bool.py`
```python
def main() -> None:
    xs = [True, False]
    xs[0] = 1
    y = xs[0]
    print(y)
main()
```
CPython: `print(y)` → `1`, `type(y).__name__` = `int`; both AIL builds match CPython (`cmp.sh`). LSP hover on `y`: expected `int`, actual `` `y`: `bool` (inferred by the typed path) `` (verified through the real server). `_subscript_kind` reads only the list literal and ignores the mutation.
2. `/tmp/rprobes/p_dict_mut.py` (same shape with `d = {"a": True}; d["a"] = 1`) — CPython `1`/`int`, both builds match; actual hover `bool`. Same for `xs.append(1)` after `xs = [True, False]` (`/tmp/rprobes` batch3) — actual `bool`, CPython `int`.
   Related: after `f(a)` mutates a list (`/tmp/rprobes/p_param_mut.py`) hover says `int` while CPython is `bool`; the *value* mismatch there is pre-existing (see below), but the new type claim is still unsound.

**Report claims:** verified — reading types from `--debug` C declarations; `C`-type mapping; 32/35 shown and 0 wrong *for that probe*; oracle 35/0; per-version cache and didSave/1 s gate; `cmp.sh` on `lab/lsp/hover/{probe,general}.py` matches CPython in both builds; diff touches only allowed files + manifest (manifest `--check` passes). **False:** "`int64_t` is only shown as `int` when the source rules out `bool`" — mutation of a bool-containing literal is not considered, producing wrong `bool`/`int` hovers (defects 1–2). Also `ail_stab` (str-keyed dict) is not mapped, so `d = {"a": 1}` shows nothing (conservative, not wrong). Probe deviation: `n` is `round(1.234, 2)` (float), not the lsp1b `round(1.2)` (int); I checked `round(1.2)` separately and it correctly shows `int`.

**Tests:** `par_check -j 2 test_ail_lsp_hover test_ail_safetynet` → 2 modules, 0 failed on HEAD. `oracle.py` → 0 mismatches.

**Pre-existing:** `/tmp/rprobes/p_param_mut.py` prints `1` where CPython prints `True` in both the general and default build, and identically on base (`work` = `9d53b55`) — bool loss through an int list, not caused by this change. `b"ab"[0]` shows nothing (conservative).

**Unverified:** `test_ail_lsp.py`, `test_ail_lsp_def.py`, `test_ail_files`, `test_ail_corpus_findings3` (not re-run per instructions); no instruction-count check — this change only touches the LSP, not compiled hot code.

VERDICT: FIX
1. Wrong `bool` hover after a list literal is mutated: `/tmp/rprobes/p_mut_bool.py` — expected `int` (CPython prints `1`, type `int`), actual `` `y`: `bool` (inferred by the typed path) ``.
2. Wrong `bool` hover after a dict literal is mutated: `/tmp/rprobes/p_dict_mut.py` — expected `int`, actual `` `y`: `bool` (inferred by the typed path) ``. Same root cause for `append`/aliasing/`int(...)` mutations; the source-level bool analysis must not trust a mutable literal (or must show nothing) once the container can be mutated.
[commandcode stop=end_turn turns=34 out_tokens=42150]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed both defects and committed as `96b2ac0`.

**Root cause:** the source-level `int64_t` → `bool`/`int` disambiguation read a list/dict literal's items without noticing later mutation, so `xs[0] = 1` (etc.) left hover claiming `bool`.

**Fix (`packaging/ail_lang/lsp.py`):** `_scope_info` now records names the scope can mutate — item/attribute stores, `del`, method calls (`append`/`update`/...), calls that receive the name, and alias assignments. `_subscript_kind`/`_for_iter_kind` return `unknown` for a mutated container, so item reads from it show nothing instead of a guess.

**Verified through the real server** (`/tmp/probes`, both AIL builds via `cmp.sh`):
- `p_mut_bool.py`, `p_dict_mut.py`, `p_append.py`, `p_param_mut.py`, `p_alias.py` → hover NOTHING (CPython type `int`; previously wrong `bool`)
- `p_clean_list.py` → `y: int` (inferred); `p_clean_bool.py` → `y: bool` (inferred) — clean containers still work
- Note: `p_param_mut.py`/`p_alias.py` print `1` vs CPython `True` in the default build — the pre-existing bool-loss defect the reviewer confirmed exists on base (`9d53b55`); no compiler file changed here.

**Regression cases added** to `lab/lsp/hover/{probe.py,expect.json}` (3 mutated-container reads, expected null) and docs updated (`lab/lsp/RESULTS.md`: 32/38 shown, 0 wrong; `docs/LSP.md`).

**Tests:** `oracle.py` → 38 cases, 0 CPython mismatches. `par_check -j 2 test_ail_lsp test_ail_lsp_hover test_ail_lsp_def test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 6 modules, 0 failed. Diff touches only the allowed files; `update_manifest.py --check` clean (no new files).
[commandcode stop=end_turn turns=42 out_tokens=21007]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fdlsp2 hover from compiler-inferred types

**What the change really does.** `packaging/ail_lang/lsp.py` adds a per-uri cache of local types parsed from a `--strict --debug` build's `program.c` (`v_<name>` / `/* --debug: the Python local */` declarations, keyed by `native_report.json` C-function ranges), maps C types to Python names, and returns `x: T (inferred by the typed path)`. Because `int64_t` is both `int` and `bool` in C, a source heuristic (`_bool_kind`/`_int_kind`) decides between them. The build runs only after `didSave` or 1 s idle and is cached by version+digest. Also adds `lab/lsp/hover/*`, `test_ail_lsp_hover.py`, docs. That matches the report.

**Bug in the fix commit.** It also no longer shows a type for a *certain* source literal (note the diff line `if len(kinds) == 1 and not uncertain` where the `uncertain` early-return was removed) — but I found no probe showing that loses a case; the literal path still wins. Not a defect on evidence.

### Defects

1. **A for-loop over a dict literal claims `int` where CPython gives `bool`.** `_for_iter_kind` handles `List/Tuple/Set` by element kind but falls through a bare `Name` to `_bool_kind`, and `_bool_kind` classifies a `Dict` literal as `"not-bool"`; dict iteration yields its *keys*.
   Probe `/tmp/rprobes/pD.py`:
   ```python
   def f() -> None:
       d = {True: 1}
       for k in d:
           print(k)
   f()
   ```
   Hover on `k` (line 3): **expected** `k: bool` (CPython `type(k).__name__ == 'bool'`), **actual** `` `k`: `int` (inferred by the typed path) ``. Likely on base was nothing; wrong type is new. This is a *wrong type*, which the task says is worse than none.

2. **A nested function's hover takes the outer function's C declaration.** `_compiler_type_map` keys `ranges` by the C function name from `native_report.json` (`outer__helper__0`), but `_hover_in_chain` looks it up with the Python name (`helper`). When a nested `def` has the same name as a top-level `def`, `compiler_types["helper"]` resolves to the top-level C function, so the nested local shows the wrong type.
   Probe `/tmp/rprobes/pQ.py`:
   ```python
   def helper() -> None:
       x = 1 / 2
       print(x)

   def outer() -> None:
       def helper() -> None:
           x = not 1
           print(x)
       helper()

   helper()
   outer()
   ```
   Confirmed in `dbgQ/program.c`: `helper` declares `double x`, `outer__helper__0` declares `int64_t x`. Hover on the nested `x` (line 8): **expected** `x: bool` (CPython `type(x).__name__ == 'bool'`), **actual** `` `x`: `float` (inferred by the typed path) ``. Base showed nothing.

Both are the "wrong type" class the task makes a hard requirement (0 wrong). Other boundaries were clean: bytes/str (`ail_bytes`/`ail_str` distinct, p8), `bool(1)`/`int("3")`/`float(1)`/conditional exprs → nothing, tuple-unpack (pF) → nothing, slices (pS) and augmented assign (pT) → nothing, closure mutation of a list → nothing/no build, and the mutated-container fix itself (`xs[0]=1`, `append`, alias, parameter) → nothing.

**Claims checked.** "oracle 38 cases, 0 CPython mismatches" — verified (`oracle: 38 cases, 32 must be shown, 0 CPython mismatches`). "6 modules, 0 failed" — I ran the 3 relevant + safetynet, all pass, LSP tests fine. "Diff touches only allowed files" — verified by `--stat`. "0 wrong" — **false** (defects 1–2). "Both defects fixed" — the specific mutated-container cases are fixed; the general "never a wrong type" claim is not met.

**Pre-existing.** `pD.py` default build prints `1` vs CPython `True` — identical on base (`/tmp/basework`), so the bool-loss is pre-existing, not caused here.

**Not checked.** icount speed comparison (change is LSP-only, no compiler/runtime hot path); `expect.json` coverage of nested same-name functions and dict-key iteration (absent).

VERDICT: FIX
1. For-loop over a dict literal shows `int` for a `bool` key — `/tmp/rprobes/pD.py` line 3: expected `k: bool`, actual `` `k`: `int` (inferred by the typed path) ``; `_for_iter_kind` must take dict *keys* (and refuse when unknown), not `_bool_kind`'s "not-bool" blanket.
2. Nested function whose name matches a top-level function shows the outer's type — `/tmp/rprobes/pQ.py` line 8: expected `x: bool`, actual `` `x`: `float` (inferred by the typed path) ``; `_compiler_type_map` keys from `native_report.json` (`outer__helper__0`) while hover looks up the Python name (`helper`), so the lookup must match the mangled C name or the map must be keyed by Python name with scope identity.
[commandcode stop=end_turn turns=72 out_tokens=96031]

FINAL VERDICT: FIX  2026-11-08T08:40:15Z
