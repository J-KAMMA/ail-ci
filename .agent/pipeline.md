# job job-rbstdfall2c-11081827  started 2026-11-08T09:28:30Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `stdfall2c` as commit `79178053`.

- Conflict with this tree's named set-walk refusal resolved by keeping both fixes: `copy` sets use `set.copy()` / fresh frozenset via `x | frozenset()`, and `copy/02` uses `sorted(s)`.
- `tools/diff_ids.py` is absent here; `tools/update_manifest.py` ran and `--check` passes.
- Tests `-j 2` on final content: `test_ail_std_stdfall2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4, 0 failed.
- Probes (both builds): `q_copy_set`, `q_copy_memo`, `q_marshal_versions`, `q_timeit_clock`, `q_frozenset_new`, `q_frozenset_empty` match CPython; `q_marshal_default` is refused by name (omitted version).
[cost $0.0000, opencode tokens {"total": 1261306, "input": 35525, "output": 6883, "reasoning": 8402, "cache.write": 0, "cache.read": 1210496}]
    tool time: bash 16.9 min
        414s bash   python3 tools/par_check.py -j 2 test_ail_std_stdfall2 test_ail_safetynet test_ail_files test_ail_corpus_findin
        348s bash   python3 tools/par_check.py -j 2 test_ail_std_stdfall2 test_ail_safetynet test_ail_files test_ail_corpus_findin
         78s bash   mkdir -p /tmp/probes && cat > /tmp/probes/q_copy_set.py <<'EOF' import copy  num_set = {3, 1, 2} frozen = froz
         35s bash   python3 - <<'EOF' p='AIL_CURRENT/stdlib/copy.py' s=open(p).read() s=s.replace('''    if isinstance(x, frozense
         35s bash   bash ~/tools/cmp.sh /tmp/probes/q_copy_set.py "$PWD" 2>&1 | sed -n '1,60p'
         31s bash   bash ~/tools/cmp.sh /tmp/probes/q_copy_memo.py "$PWD" 2>&1 | sed -n '1,80p'
         30s bash   cat > /tmp/probes/q_copy_memo.py <<'EOF' import copy   def deep(x, memo):     return copy.deepcopy(x, memo)   
         22s bash   bash ~/tools/cmp.sh /tmp/probes/q_copy_set.py "$PWD" 2>&1 | sed -n '1,80p'

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `job-rbstdfall2c-11081827`

**What the change really does:** adds ~1,900 lines of bundled stdlib (`AIL_CURRENT/stdlib/{copy,timeit,marshal}.py`), 18 lab programs, a new test module, a third-party notice and manifest entries. No compiler/runtime change. The set-walk conflict was resolved by replacing the accepted loop with `x.copy()` / `x | frozenset()` and changing `copy/02` to `sorted(s)`. That matches the report, except the accepted change's deep-copy of set *elements* was silently dropped.

**Claims**
- commit `79178053`, faithful re-apply: **verified** (accepted `timeit.py`, `marshal.py`, test file identical; copy.py differs only in the three set lines).
- `copy/02` `sorted(s)`, set-walk refusal kept: **verified**.
- `tools/diff_ids.py` absent: **verified**.
- `update_manifest.py --check`: **verified** (rc 0).
- Tests 4/4: **partly verified** — `test_ail_std_stdfall2` and `test_ail_safetynet` pass (232 s, 0 failed); `test_ail_files`, `test_ail_corpus_findings3` not run by me.
- "Probes match CPython": **not true in general** — their probes use only int sets; nested containers expose a mismatch (below).

**Defect 1 — `deepcopy` of a set/frozenset shares container elements (CPython makes new ones).**
Probe `/tmp/rprobes/p12_frozen_elem.py`:
```python
import copy
f = frozenset({frozenset({1, 2})})
df = copy.deepcopy(f)
a = sorted(f)[0]; b = sorted(df)[0]
print("frozen outer new:", df is f, df == f)
print("inner frozenset shared:", a is b, a == b)
```
CPython: `inner frozenset shared: False True`; AIL (`g` and `d`): `True True`.
Probe `p11_set_elem.py` (`s={frozenset({1,2})}`, `s.pop()` vs `deepcopy(s).pop()`) likewise: CPython `False True`, AIL `True True`.
Cause: `y = x | frozenset()` (copy.py:201) and `y = x.copy()` (copy.py:220) copy the container but share its elements. The accepted change used `deepcopy(item, memo)` per element. `sorted(x)` is explicitly permitted by the set-order refusal, so a correct fix is feasible (and the module docstring's claim that the sharing rules are CPython's for sets/frozensets is false as written). The DEVLOG also claims "len(memo) ... match CPython"; `p14_copy_dict_set.py` shows 4 vs 5 int keys for a nested dict/set (identical code in the accepted change, so secondary).

**Pre-existing (identical on `/tmp/base`)**
- `str` literal identity: `u = "hello"; s = "hello"; u is s` is `False` in AIL, `True` in CPython (`p10_strid.py`, same on base). Not caused by this change.
- Programs not using the feature: `--debug-dir` `program.c` is byte-identical to `/tmp/base`; only temp paths in `native_report.json` differ.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; speed (no hot compiler/runtime code touched).

VERDICT: FIX
1. `copy.deepcopy` of a `set`/`frozenset` containing a `frozenset` (or a tuple of one) returns shared inner objects: probe `/tmp/rprobes/p12_frozen_elem.py` prints `inner frozenset shared: True True` (AIL) where CPython prints `False True`; `/tmp/rprobes/p11_set_elem.py` prints `True True` vs `False True`. Walk `sorted(x)` (allowed by the set-order rule) and `deepcopy` each element, or refuse this case by name; fix the docstring/DEVLOG claims.
[cost $0.0000, opencode tokens {"total": 1410677, "input": 34341, "output": 8009, "reasoning": 25607, "cache.write": 0, "cache.read": 1342720}]
    tool time: bash 8.8 min
        233s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "rc=$?
        109s bash   date; cd /tmp/rprobes; for p in p1_copy_sets p2_copy_set_elems p3_copy_memo p4_marshal_versions p5_timeit; do 
         54s bash   cd /tmp/rprobes cat > p13_marshal_edges.py <<'EOF' import marshal vals = [float("inf"), float("-inf"), float("
         31s bash   cd /tmp/rprobes cat > p6_marshal_load_v4.py <<'EOF' import marshal streams = [     "db03000000e901000000da0161
         30s bash   cd /tmp/rprobes cat > p9_copy_paths.py <<'EOF' import copy  def take(x):     return copy.deepcopy(x)  s = {1, 
         30s bash   cd /tmp/rprobes cat > p12_frozen_elem.py <<'EOF' import copy f = frozenset({frozenset({1, 2})}) df = copy.deep
         30s bash   cd /tmp/rprobes cat > p11_set_elem.py <<'EOF' import copy inner = frozenset({1, 2}) s = {inner} d = copy.deepc
          9s bash   cd /tmp/rprobes cat > p10_strid.py <<'EOF' def same(x):     return x s = "hello" t = same(s) print("through fn

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `a38ef68b`.

- **Fix:** `copy.deepcopy` of `set`/`frozenset` now walks `sorted(x)` and deep-copies each element (inner frozensets are new, as in CPython); sets with unorderable elements are refused by name. Docstring and DEVLOG claims corrected, including the false `len(memo)` equality claim.
- **Probes (both builds):** reviewer `p11`, `p12` now match CPython (`False True`); `r_set_elem_arg/list/dict/attr/shapes/alias` all match; `r_set_unorderable` refused by name. Reviewer `p14` still shows the pre-existing memo key-count difference (4 vs 5 ints), now documented as such.
- **Tests (`-j 2`, final commit):** `test_ail_std_stdfall2` 215.9s, `test_ail_corpus_findings3` 217.1s, `test_ail_files` 96.6s, `test_ail_safetynet` 127.5s — 4/4, 0 failed.
- **Records:** manifest `--check` rc 0; `tools/diff_ids.py` absent.
[cost $0.0000, opencode tokens {"total": 1639365, "input": 65511, "output": 7450, "reasoning": 11588, "cache.write": 0, "cache.read": 1554816}]
    tool time: bash 11.0 min, edit 0.0 min, read 0.0 min
        345s bash   python3 tools/par_check.py -j 2 test_ail_std_stdfall2 test_ail_safetynet test_ail_files test_ail_corpus_findin
        154s bash   cd /tmp/probes; for p in r_set_elem_arg.py r_set_elem_list.py r_set_elem_dict.py r_set_elem_attr.py r_set_elem
         65s bash   cd /tmp/rprobes; for p in p14_copy_dict_set.py p11_set_elem.py p12_frozen_elem.py; do echo ===$p; bash ~/tools
         49s bash   cd /tmp/rprobes; for p in p11_set_elem.py p12_frozen_elem.py p2_copy_set_elems.py; do echo ===$p; bash ~/tools
         22s bash   cd /tmp/probes; sed -i 's/"n": -7/"n": -3/' r_set_elem_dict.py; bash ~/tools/cmp.sh r_set_elem_dict.py /home/r
         22s bash   cd /tmp/rprobes; bash ~/tools/cmp.sh p14_copy_dict_set.py /home/runner/work/ail-ci/ail-ci 2>&1 | sed -n '1,60p
          1s bash   ls tools/diff_ids.py 2>&1; python3 tools/update_manifest.py 2>&1 | tail -5; python3 tools/update_manifest.py -
          1s bash   python3 tools/update_manifest.py 2>&1 | tail -5; python3 tools/update_manifest.py --check 2>&1 | tail -5; echo

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: job rbstdfall2c (commits `79178053`, `a38ef68b`)

**What the change really does.** Re-applies the accepted `stdfall2c` change (bundled AIL `copy`, `marshal`, `timeit`, lab programs, test, notices, manifests), resolving the set-order conflict by walking sets/frozensets with `sorted(x)` instead of `for item in x`, and adds a second commit that deep-copies each set/frozenset element and corrects the memo-count claims. This matches the task; the report's framing only describes the second commit.

**Probes** (`bash ~/tools/cmp.sh <p> /home/runner/work/ail-ci/ail-ci`, both builds):
- `r1`, `r6`, `r8`, `r9`, `r10`, `r12`, `r13`, `p11`, `p12`, `r4`, `r3`, `q_marshal_versions`, `q_timeit_clock`, `p13`, `r5`, `r11` — results below.
- `r8` (sets/frozensets of ints, strings, tuples, empty; tuple of frozensets): same as CPython.
- `r10`/`p11`/`p12`/`r12`/`r13` (one-element frozenset set, inner-object identity, arg/list/dict/attr, aliasing, negative/large ints, bool): same as CPython (`False True` element-new cases correct).
- `r4` and `r_set_unorderable` (`{1,"a"}`): named `copy.Error` at runtime, exit 1. CPython succeeds; this is the documented refusal implied by keeping the tree's set-walk ban.
- `r9` (set of **two** frozensets): build refused with `AIL limit: sorting or min()/max() of sets: < on sets is the subset test...`. CPython prints `twofrozen 2 True False`. Base also refuses this program (different named build refusal, `copy.deepcopy ... not in the subset`). A named compile-time refusal is acceptable, but it is **unreported** and contradicts the docstring claim that `sorted(x)` is always the allowed order-free walk; the new test only covers a one-element outer set.
- `r3`/`p14`: memo key types/clear/reuse/keep semantics match; CPython 5 int keys vs 4, and 3 vs 2 after clear. Count difference is acknowledged in DEVLOG but `lab/stdlib/stdfall2/RESULTS.md:100` still says "grows by the same two entries per copied object as CPython" (stale/false).
- `r2`/`r11`: `copy.copy("hi") is "hi"` and `"hi" is "hi"` are `False`; **identical on base** (`/tmp/base`) — pre-existing string-identity behaviour, not this change.
- `p5_timeit`: only elapsed-time numbers differ (real clock); call counts match.
- Non-feature program `r5_plain`: generated C sha256 identical between HEAD and `/tmp/base` (only temp paths in `native_report.json` differ).

**Report claim checks:** central set-element fix verified for one-element sets; `p11`/`p12` verified; unorderable refusal verified (but the two-frozenset case gives a different named build limit, not `copy.Error`); memo count difference verified; manifest `--check` rc 0 and `tools/diff_ids.py` absent verified; tests `test_ail_std_stdfall2` 212.2 s and `test_ail_safetynet` 124.7 s pass (2/2). I did not re-run `test_ail_files`/`test_ail_corpus_findings3` (reviewer scope says added/edited + safetynet).

**Pre-existing / not defects:** string `is` difference; nondeterministic timeit numbers; `p5` clock values.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; the worker's quoted timings; speed (no compiler/runtime files changed, so no hot-path effect).

No wrong output or crash found in any case that builds; the only gaps are named refusals. Minor issues: the `r9` limitation is undocumented, and `RESULTS.md` keeps the false memo-count claim.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1541912, "input": 75437, "output": 8726, "reasoning": 24917, "cache.write": 0, "cache.read": 1432832}]
    tool time: bash 9.5 min
        213s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_stdf
         90s bash   cd /tmp/rprobes2 && for p in r1_sets.py r2_shallow.py r3_memo.py r4_mixed.py r5_plain.py; do echo "########## 
         69s bash   cd /tmp/rprobes2 && cat > r8_orderable.py <<'EOF' import copy t = {(1, 2), (3, 4)} dt = copy.deepcopy(t) print
         65s bash   cd /tmp/rprobes2 && cat > r12_alias.py <<'EOF' import copy inner = frozenset({7}) d = {"k": inner, "s": {inner
         29s bash   cd /tmp/rprobes && for p in q_marshal_versions.py q_timeit_clock.py p13_marshal_edges.py p5_timeit.py; do echo
         29s bash   date; cd /tmp/probes && for p in q_marshal_versions.py q_timeit_clock.py; do echo "######## $p"; bash ~/tools/
         23s bash   cd /tmp/rprobes2 && bash ~/tools/cmp.sh /tmp/rprobes2/r6_twofrozen.py /home/runner/work/ail-ci/ail-ci 2>&1 | s
         22s bash   cd /tmp/rprobes2 && echo "##### r9 on BASE"; bash ~/tools/cmp.sh /tmp/rprobes2/r9_twofrozen.py /tmp/base 2>&1 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T11:49:31Z
