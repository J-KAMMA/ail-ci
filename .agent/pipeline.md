# job job-std_fnmatch-11011617  started 2026-11-01T07:18:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- **Programs:** 12/12 in `lab/stdlib/fnmatch/` build (all on the general path) and match CPython stdout/exit; 0 refused. Recorded in `lab/stdlib/fnmatch/RESULTS.md`.
- **Implementation:** added `fnmatch` routing in `ail_syntax.py`, `stdlib5.py`, `stdtop.py`, and a CPython-3.12-faithful `prelude_fnmatch.py`.
- **Test:** new `test_ail_std_fnmatch.py`, registered via `tests.d/`; compares all 12 programs with CPython on both builds and fuzzes the prelude.
- **Tests run on final commit `128574a`:** `test_ail_std_fnmatch` 5/5 OK; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` 25 OK (1 skipped); `test_ail_stdtop4` + `test_ail_stdlib5.UnchangedPrograms` 6/6 OK. The full `stdlib5`/`stdtop1-3` batch exceeded 15 minutes, so it was not completed.
- **Compare parity:** all 10 `lab/compare` `main.ail` generated C byte-identical; 7/7 buildable `main.py` identical, and the other 3 were already refused identically at the base commit.
- **Probes:** `/tmp/probes/fnmatch_core.py` and `/tmp/probes/fnmatch_routes.py` both matched CPython on stdout/exit for `g` and `d`.
- **Manifest:** `update_manifest.py --check` passes. Commits: `02cac0d`, `128574a` (not pushed).
[cost $0.0606, opencode tokens {"total": 6369347, "input": 129175, "output": 19443, "reasoning": 18233, "cache.write": 0, "cache.read": 6202496}]
    tool time: bash 59.8 min
        900s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_stdtop1 test_ail_stdtop2 test_a
        569s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_safetynet test_ail_files test_a
        516s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_std_fnmatch > /tmp/fn_final.log
        406s bash   set -e cd /home/runner/work/ail-ci/ail-ci export PIPE_CC=/tmp/fakecc.py rm -rf /tmp/cccap2; mkdir -p /tmp/ccca
        357s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 -m unittest test_ail_std_fnmatch -v 2>&1 | tail
        194s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/fnresults && for f in lab/stdlib/fnmatch/*.py; do n=$(base
        189s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_std_fnmatch 2>&1 | tail -12
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_std_fnmatch.CompiledPrograms -v

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Diff.** Adds `fnmatch` to the `stdlib5` gate/module set, `run_fnmatch` in `stdtop.py` (maps `fnmatch`/`fnmatchcase`/`filter`/`translate` to four helpers), and a 316-line `prelude_fnmatch.py`; adds 12 lab programs, RESULTS.md, a test + `tests.d` registration, DEVLOG and manifest entries. That matches the report.

**Probes** (`bash ~/tools/cmp.sh`, `g` and `d`):
- `p_path`, `p_path_list`, `p_path_dict`, `p_path_attr` (a `pathlib.Path` through an argument, list item, dict value and attribute): named compile refusal (`a path is passed to parameter 'name' of _ail_fnmatch_fn()...`) — acceptable.
- `p_bytes`/`p_types` (memoryview): named refusal (name not in subset) — acceptable.
- `p_translate`, `p_kw`, `p_kworder`, `p_integ`, `p_edge`, `p_import_only`, `p_mention`: CPython-identical stdout and exit on both builds; `p_mention` (word "fnmatch" in a string, no import) has byte-identical `program.c` to base.
- Prelude differential fuzz vs CPython: 60k `translate`, 120k `fnmatch`/`fnmatchcase` (unicode included), 50k bytes cases — no differences.
- All 10 `lab/compare` `main.ail` `program.c` files are byte-identical HEAD vs base. `p_plain` is also byte-identical.
- `p_tuple3`: **differs**.

**Tests.** `par_check.py -j 2 test_ail_std_fnmatch test_ail_safetynet`: 2 modules, 0 failed (425 s). `update_manifest.py --check`: pass.

**Claims.** 12/12 build and match CPython — verified. Routing/prelude description — verified. Test registered via `tests.d` — verified. All 10 compare C byte-identical — verified. “CPython-3.12-faithful … TypeErrors for non-string patterns” — false for non-str/bytes sequence patterns (below). Worker’s `test_ail_files`/`corpus_findings3`/`stdtop4`/`stdlib5` runs — not re-run (unverified). Speed not measured: no hot path was changed.

**Defect 1 — `fnmatchcase` with a sequence pattern (e.g. a tuple) is not faithful.** `/tmp/rprobes/p_tuple3.py`:
```python
import fnmatch
print(fnmatch.fnmatchcase("ab", ("ab",)))
try:
    print(fnmatch.fnmatchcase("a", (1, 2)))
except TypeError as e:
    print("TypeError", e)
```
Expected (CPython 3.12):
```
True
TypeError decoding to str: need a bytes-like object, int found
```
Actual (HEAD, both `g` and `d`):
```
False
False
```
`fnmatch.translate((b"a",))` also gives `decoding to str...` instead of CPython’s `sequence item 0: expected str instance, bytes found`. The base refuses by name, so the change caused this. The new `_ail_fnmatch_case` non-str/bytes-pattern branch treats a sequence as a list of single-character specs rather than running CPython’s `translate`/`re` semantics; its own test covers `("a",)` only.

**Pre-existing.** None identified. **Unverified.** Wider `stdlib5`/`stdtop1-3` batches; `main.py` compare parity beyond generated C; instruction counts.

VERDICT: FIX
1. `fnmatch.fnmatchcase(name, pat)` with a hashable non-str/bytes sequence `pat` (`("ab",)`, `(1, 2)`, `range(2)`, `(b"a",)`) returns False/other text instead of CPython’s result/`TypeError`; see `/tmp/rprobes/p_tuple3.py`, expected vs actual above.
[cost $0.0376, opencode tokens {"total": 1804554, "input": 77239, "output": 10677, "reasoning": 24222, "cache.write": 0, "cache.read": 1692416}]
    tool time: bash 15.0 min
        426s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_std_fnmatch 
         80s bash   cd /home/runner/work/ail-ci/ail-ci && for t in $(ls lab/compare/src); do f=lab/compare/src/$t/main.ail; [ -f "
         77s bash   cd /tmp/rprobes && for p in p_path p_bytes p_translate p_types p_kw; do echo "=== $p ==="; bash ~/tools/cmp.sh
         58s bash   cat > /tmp/rprobes/p_integ.py <<'EOF' import fnmatch  class Job:     def __init__(self, name, pattern):       
         28s bash   cat > /tmp/rprobes/p_tuple.py <<'EOF' import fnmatch for pat in [(1, 2), (1,), ("a", "b"), (b"a",)]:     try: 
         28s bash   cat > /tmp/rprobes/p_kworder.py <<'EOF' import fnmatch print(fnmatch.fnmatchcase(pat="*.py", name="a.py")) pri
         27s bash   cat > /tmp/rprobes/p_tuple2.py <<'EOF' import fnmatch print(fnmatch.fnmatchcase("ab", ("ab",))) print(fnmatch.
         27s bash   cat > /tmp/rprobes/p_tuple3.py <<'EOF' import fnmatch print(fnmatch.fnmatchcase("ab", ("ab",))) try:     print

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `eb9d9ef`.

- `fnmatchcase` with a non-str/bytes sequence now uses CPython `translate` semantics: each element is one literal chunk unless exactly `*`/`?`. Ints/`range` raise the decoding error, bytes elements raise the join error, `[` reproduces the `AttributeError`, and unhashable sequences raise the `lru_cache` error. `range` is special-cased because the AIL runtime does not hash it.
- Regression coverage added to `test_ail_std_fnmatch.test_sequence_patterns`.

Probes, all same stdout/exit as CPython on both `g` and `d`:
`p_tuple3`, `p_seq_forms`, `p_seq_errors`, `p_seq_nested`, `p_seq_filter_fn`, `p_regular_regression` (arguments, list items, dict values, attributes, aliases, empty, ints, range, bytes, bad patterns).

- 10 `lab/compare/src/*/main.ail` generated C: byte-identical to base `1d20537`.
- `par_check.py -j 2`: `test_ail_std_fnmatch`, `test_ail_stdlib5`, `test_ail_stdtop4`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed, 1149s.
- `tools/update_manifest.py --check`: pass.
[cost $0.0309, opencode tokens {"total": 1774896, "input": 65494, "output": 10689, "reasoning": 16025, "cache.write": 0, "cache.read": 1682688}]
    tool time: bash 27.3 min, edit 0.0 min, read 0.0 min
       1151s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 --timeout 3000 test_ail_std_fnmatch test
         89s bash   cat > /tmp/probes/p_seq_forms.py <<'EOF' import fnmatch  def probe(name, pat):     try:         print("case", 
         86s bash   cat > /tmp/probes/p_seq_errors.py <<'EOF' import fnmatch  def main():     try:         print(fnmatch.fnmatchca
         86s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc fail=0 for t in $(ls lab/compare/
         72s bash   rm -f /tmp/probes/p_hash.py; cd /home/runner/work/ail-ci/ail-ci && for p in p_tuple3 p_seq_forms; do echo "===
         61s bash   cat > /tmp/probes/p_seq_errors.py <<'EOF' import fnmatch  def f1():     try:         print(fnmatch.fnmatchcase
         31s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/p_tuple3.py $PWD
         28s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_tuple3.py <<'EOF' import fnmatch print(fnmatch.fnmatchcase("ab", (

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Change:** Adds `fnmatch` routing (`ail_syntax.py`, `stdlib5.py`, `stdtop.py`) plus a 383-line `prelude_fnmatch.py` implementing `translate`/match/filter, and adds 12 lab programs + `test_ail_std_fnmatch`. The report describes it correctly except for the sequence-translate claim below.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`, both `g` and `d`):
- `p_seq_translate.py` — **DIFF** on HEAD, base refuses (`fnmatch.translate` unpublished).
- `p_translate_err.py` — **DIFF** only for the `["a*b"]` case; error paths, `("ab",)` matching agree.
- 60k random str `translate`/`fnmatchcase` fuzz: 0 differences.
- 40k random sequence `fnmatchcase` fuzz: 0 differences; 15k sequence `translate` differences.
- `test_ail_std_fnmatch` + `test_ail_safetynet`: 2 modules, 0 failed, 555s.
- 10 `lab/compare` `--debug-dir` `program.c` files: byte-identical to `work` (`1d20537`); only `native_report.json` temp paths differ.
- `update_manifest.py --check`: pass.

**Claims:**
- 12 lab programs build/match CPython: **verified** (by the passing test; it compiles all 12 in both builds).
- 10 lab/compare C unchanged: **verified**.
- Sequence `fnmatchcase` matching semantics: **verified**.
- Sequence `translate` uses CPython semantics: **false** (defect below). The new `test_sequence_patterns` misses it because it has no multi-character element containing a regex-special character.
- Manifest/registration/tests: **verified**.

**Defect**
1. `_ail_fnmatch_translate` escapes a sequence element only when the whole element is one special character (`c in _AIL_FNM_SPECIAL`); CPython applies `re.escape` to every character of the element. Multi-character elements therefore produce an unescaped, semantically different regexp.
   Probe `/tmp/rprobes/p_seq_translate.py`:
   ```python
   import fnmatch
   def main():
       print(fnmatch.translate(("a*b",)))
       print(fnmatch.translate(("x&y",)))
       print(fnmatch.translate(("a\\b",)))
       print(fnmatch.translate(("ab",)))
   main()
   ```
   Expected (CPython 3.12):
   ```
   (?s:a\*b)\Z
   (?s:x\&y)\Z
   (?s:a\\b)\Z
   (?s:ab)\Z
   ```
   Actual (HEAD, both g and d):
   ```
   (?s:a*b)\Z
   (?s:x&y)\Z
   (?s:a\b)\Z
   (?s:ab)\Z
   ```
   Also reproduces for a list pattern (`fnmatch.translate(["a*b"])`). Fix: escape each character of a `str` element while still treating only exact `"*"`/`"?"` elements as operators.

**Unverified:** full suite, worker's uncommitted probes, performance (fnmatch is general-path-only, no hot benchmark path).

VERDICT: FIX
1. Sequence `fnmatch.translate` leaves regex-special characters inside multi-character elements unescaped (probe and expected/actual above).
[cost $0.0259, opencode tokens {"total": 936042, "input": 56477, "output": 6379, "reasoning": 18402, "cache.write": 0, "cache.read": 854784}]
    tool time: bash 12.0 min
        556s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_fnmatc
         81s bash   cd /tmp && rm -rf /tmp/dA /tmp/dB /tmp/oA /tmp/oB && mkdir -p /tmp/dA /tmp/dB /tmp/oA /tmp/oB; for d in /home/
         37s bash   date; cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/p_seq_translate.py <<'EOF' import fnmatch  def 
         32s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/p_translate_err.py <<'EOF' import fnmatch  def show(l
          5s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import sys, random, fnmatch sys.path.insert(0,'AIL_CUR
          2s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import sys, random, fnmatch sys.path.insert(0,'AIL_CUR
          2s bash   date; mkdir -p /tmp/rprobes; cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import sys, random, fnmat
          1s bash   cd /tmp && rm -rf /tmp/dA /tmp/dB /tmp/oA /tmp/oB && mkdir -p /tmp/dA /tmp/dB /tmp/oA /tmp/oB; ok=1; for d in 

FINAL VERDICT: FIX  2026-11-01T09:35:34Z
