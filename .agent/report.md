# job job-pre39-10241004  started 2026-10-24T01:04:35Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the `p7_wrapper_kw.py` difference. The ported pre31 check now binds wrapper arguments by name as well as position, so both builds refuse `take(x=1e300)`, negative/keyword-only/identity variants, and out-of-range values reached through list items, tuple items, dict values and module constants.

**Verification on final commit `a4a5e04`**
- Tests: `test_ail_pre39`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 167s, 0 failed.
- `test_ail_pre39`: 12 refused programs and 4 CPython-matching programs across both builds.
- `tools/update_manifest.py --check`: passes.
- `/tmp/probes`: 32 probes, **11 refused by name on both builds, 21 matched CPython on both**.
  - Refused: `p7_wrapper_kw`, `p7_wrapper_kw_neg`, `p7_wrapper_kw_list`, `p7_wrapper_kw_dict`, `p7_wrapper_pos`, `p7_identity_kw`, `p7_kwonly_wrapper`, `pre39_direct_literal`, `pre39_module_const`, `pre39_keyword_variable`, `pre39_boundary_upper`.
  - Matched: `p6_shadow_int`, `p7_arith_kw`, `p7_arith_pos`, `p7_cache_kw`, `p7_ctor_kw`, `p7_dataclass_kw`, `p7_list_kw`, `p7_local_kw`, `p7_lru_kw`, `p7_lru_pos`, `p7_method_kw`, `p7_static_kw`, `p7_wrapper_kw_inrange`, `p7_wrapper_kw_pos`, `pre39_attribute_inrange`, `pre39_boundary_edge`, `pre39_expr_fit`, `pre39_keyword_rebound`, `pre39_nonfinite`, `pre39_shadow`, `pre39_shadowing2`.

Additional exploratory probes moved to `/tmp/probes-unrelated` and not claimed: an out-of-range **attribute** still overflows at runtime (the pre31 static-visibility limit), `range(x=1e300)` still differs, and `partial` still hits the unrelated `pyboxed2.py:1338` `Lambda.lineno` crash.

Commits: `da47b51` (fix), `a4a5e04` (DEVLOG count). Not pushed; only harness file `.agent/pipeline.md` is untracked.
[cost $0.0000, opencode tokens {"total": 6404230, "input": 413515, "output": 28512, "reasoning": 13787, "cache.write": 0, "cache.read": 5948416}]
    tool time: bash 15.4 min
        214s bash   python3 tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        169s bash   python3 tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         87s bash   python3 tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet
         84s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre39.py') s = p.read_text() old = ""
         81s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre39.py') s = p.read_text() old = "d
         78s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre39.py') s = p.read_text() s = s.re
         70s bash   cat > /tmp/probes/pre39_direct_literal.py <<'EOF' print(int(1e300)) EOF cat > /tmp/probes/pre39_module_const.p
         66s bash   cat > /tmp/probes/pre39_keyword_variable.py <<'EOF' def take(x):     return int(x)   v = 1e300 w = v print(tak

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (what the diff really does):** adds a new front-end AST pass that refuses `int()` of a constant float outside int64, propagating module constants, literals, list/tuple/dict items and identity/passthrough calls, and binding wrapper parameters by position or keyword. It is **not** just a “port of the pre31 check plus keyword binding”: the base has no `int()`-of-float check at all (`git grep` on `work`), so this diff adds the whole 344-line machinery, which explains the broader constant folding.

**Defect (caused by the change; base matches CPython):**

1. False refusal of a valid program. During module-constant collection `known.get` returns `None` for an unresolved name instead of `_UNKNOWN` (`ail_chatgpt.py:413`, `_constant_value` at `ail_chatgpt.py:158`), so an unknown dict key becomes the literal `None` and selects the wrong dict entry:
```python
k: str = "a"
x = {None: 1e300, "a": 1.5}[k]
print(int(x))
```
Expected (CPython and base): stdout `1`, exit 0.
Actual (HEAD, both `g` and `d`): compile fails with `p.ail:3:7: int() of a float outside int64: 1e+300 (CPython makes a big integer)`, exit non-zero. The same false refusal occurs through a keyword wrapper (`take(v=x)`). Fix: make constant collection treat missing names as `_UNKNOWN`.

**Verified claims**
- `p7_wrapper_kw.py`: base overflows at runtime; HEAD refuses by name on both builds — target fixed.
- Negative, keyword-only, identity, list-item, dict-item, tuple-item, module-constant variants: refused by name; worker probes reproduced (11 refused / 21 matched exactly).
- In-range, shadowing, non-finite and expression-fits cases match CPython on both builds.
- `test_ail_pre39` + `test_ail_safetynet`: 2 modules, 79s, 0 failed. `tools/update_manifest.py --check`: pass. Plain program’s `program.c` identical to base.
- **False:** “The ported pre31 check now binds …” — the whole check is newly added, not ported.
- **Not run:** `test_ail_files`, `test_ail_corpus_findings3` (per reviewer scope); no icount run (front-end only).

**Pre-existing (identical on base):** runtime-only out-of-range values, wrapper defaults (`take()`), augmented-assignment tracking, nested-closure values, and module list/dict mutation all still overflow or compile as before. Refusing dead code (`def unused(): return int(x)`) matches the base’s existing int64-literal refusal policy.

**Unverified:** the worker’s `test_ail_files` / `test_ail_corpus_findings3` claims; the admitted unrelated `range`/`partial`/attribute cases.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1260238, "input": 95201, "output": 16231, "reasoning": 15238, "cache.write": 0, "cache.read": 1133568}]
    tool time: bash 5.0 min
         80s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet 2>&1 | tail -20; 
         68s bash   date; for f in /tmp/probes/*.py; do r=$(bash ~/tools/cmp.sh "$f" "$PWD" 2>&1); if echo "$r" | grep -q 'int() o
         43s bash   date; for f in /tmp/rprobes/*.py; do echo "===== BASE $(basename $f)"; bash ~/tools/cmp.sh "$f" /tmp/base 2>&1
         34s bash   date; for f in /tmp/rprobes/*.py; do echo "===== HEAD $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | 
         26s bash   date; for f in /tmp/rprobes/p_*.py /tmp/rprobes/q_*.py /tmp/rprobes/r_*.py /tmp/rprobes/s_*.py /tmp/rprobes/t_
         21s bash   date; for f in /tmp/rprobes/p_*.py /tmp/rprobes/q_*.py /tmp/rprobes/r_*.py /tmp/rprobes/s_*.py /tmp/rprobes/t_
          6s bash   cat > /tmp/rprobes/bug_nonekey.py <<'EOF' k, = ("a",) def take(x):     return int(x) print(take(x={None: 1e300
          6s bash   cat > /tmp/rprobes/bug_nonekey2.py <<'EOF' k, = ("a",) x = {None: 1e300, "a": 1.5}[k] def take(v):     return 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer’s defect: unresolved module constants now map to `_UNKNOWN` instead of `None`, so an unknown dict key no longer selects the `None` entry.

**Commit:** `900660d` on `job-pre39-10241004`

**Probes** (`bash ~/tools/cmp.sh`, both `g` and `d`):
- 11 matched CPython exactly: `fix_unknown_key_{direct,wrapper_kw,wrapper_pos,unpacked,list_index,tuple_index,attribute,boundary,negative}`, `fix_known_numeric_key_inrange`, `fix_known_list_index_inrange`
- 3 refused by name on both builds: `fix_known_numeric_key_outofrange`, `fix_known_list_index_outofrange`, `fix_propagated_numeric_key`
- Existing `p6`/`p7`/`pre39` probes retained their results; the review’s `bug_nonekey{2,3,4}` now match CPython.

**Tests on final commit:** `test_ail_pre39`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 177s, 0 failed. `test_ail_pre39` now covers 13 refused and 12 matching programs. `tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 1022122, "input": 55636, "output": 12176, "reasoning": 838, "cache.write": 0, "cache.read": 953472}]
    tool time: bash 9.6 min, edit 0.0 min
        178s bash   cd /home/runner/work/ail-ci/ail-ci; python3 tools/update_manifest.py --check && echo manifest-ok; python3 tool
        170s bash   cd /home/runner/work/ail-ci/ail-ci; python3 tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet test_ail
         83s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/p*.py /tmp/probes/pre39_*.py; do [ -e "$f" ] || conti
         68s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/*.py; do r=$(bash ~/tools/cmp.sh "$f" "$PWD" 2>&1); 
         33s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/fix_*.py; do echo "===== $(basename $f)"; bash ~/tool
         31s bash   cd /home/runner/work/ail-ci/ail-ci; for b in i_shadow.py j_runtime.py k_default.py p_dead_literal.py s_augassi
          5s bash   rm /tmp/probes/fix_known_key_inrange.py /tmp/probes/fix_known_key_outofrange.py cat > /tmp/probes/fix_known_nu
          3s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/bug_nonekey*.py; do echo "===== HEAD $(basename $f)"

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change really does:** The branch adds a new front-end static check (`AIL_CURRENT/ail_chatgpt.py:79-423`, commit `da47b51`) that refuses `int()` of a statically-known out-of-int64 float, with module-constant folding and wrapper/identity argument binding by position and keyword; `900660d` then maps unresolved constants to `_UNKNOWN` instead of `None`. The report's first line only describes the `_UNKNOWN` fix; the p7 fix is the larger `da47b51` change. Its probe list/DEVLOG do describe that, so this is incomplete emphasis, not a false claim.

**Target (`/tmp/probes/p7_wrapper_kw.py`):**
- base `g`/`d`: runtime `integer overflow`, exit 1, missing the big integer (differs from CPython).
- HEAD `g`/`d`: named compile refusal `int() of a float outside int64: 1e+300 (CPython makes a big integer)` at the `int(x)` line. Fixed as the task allowed.

**My probes** (`bash ~/tools/cmp.sh`, both builds vs base):

| probe | HEAD | base |
| --- | --- | --- |
| `rev_multi.py` (`take(x=1e300, y=1.5)`, converts `y`) | matches CPython | matches |
| `rev_match_shadow.py`, `rev_match_shadow_fn.py` (match pattern rebinds module `x` to 1.5) | matches | matches (surface desugars binding to `Assign`, so no false refusal) |
| `rev_cond_dead.py` (`int(x)` in `if False`) | named refusal | matches CPython |
| `rev_try_overflow.py` (out-of-range call in `try`) | named refusal | runtime overflow (differs from CPython) |
| `rev_method.py` (keyword wrapper method) | runtime overflow | runtime overflow (pre-existing) |
| `rev_kwargs.py` (`take(**{...})`) | refused “**kwargs call argument” | same refusal (pre-existing) |
| `rev_globals.py` | named `int()` refusal | refused “globals unknown” (both refuse) |

The only new differences are named compile-time refusals of a statically out-of-int64 `int()` conversion, including dead code (`rev_cond_dead`, `d_unused_fn`, `m_cond_int`). The review rules accept named compile-time refusals, and the base already refuses dead huge-int literals (`p_dead_literal`), so I do not count these as defects.

**Tests on HEAD:** `python3 ../tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet` → 2 modules, 77s, 0 failed. `tools/update_manifest.py --check` → passes.

**Report claims:**
- `_UNKNOWN` fix and `bug_nonekey{2,3,4}` now match — **verified** (re-ran; all match on both builds).
- 11 `fix_*` probes match, 3 refused — **verified** by re-running all 14 in `/tmp/probes`.
- p6/int-shadow and in-range wrapper results retained; p7 out-of-range now refused — **verified**.
- 4-module test run 177s/0 failed — pre39+safetynet **verified**; `test_ail_files` and `test_ail_corpus_findings3` **unverified** (not re-run, per review instruction).
- Front-end-only, no hot-code effect — **verified**: generated `program.c` is byte-identical to base for `plain.py` and `~/corpus/gdev/g00_000.py` (only temp paths differ in `native_report.json`), so no icount run was needed.

**Pre-existing (not caused):** runtime-only values (`j_runtime`), default arguments (`k_default`), local/nested values (`y_nested`), augmented/annotated assignment (`s_augassign`, `u_annassign`), and keyword method wrappers (`rev_method`) still hit `integer overflow`; `**kwargs` calls are refused on both builds.

**Unverified:** worker's `test_ail_files` / `test_ail_corpus_findings3` claims; full suite (CI); `param_int.py` (not present).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1836720, "input": 97654, "output": 7249, "reasoning": 37609, "cache.write": 0, "cache.read": 1694208}]
    tool time: bash 8.5 min
        201s bash   cd /home/runner/work/ail-ci/ail-ci; export AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1; rm -rf /tmp/gdscan; mkdir /tmp
         78s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre39 test_ail_safetynet 2>&1 | tail -25; 
         60s bash   for f in a_target b_list_mutate c_dict_mutate d_unused_fn e_list_alias f_inrange g_boundary h_boundary_neg i_s
         31s bash   for f in /tmp/probes/fix_*.py; do out=$(bash ~/tools/cmp.sh "$f" "$PWD" 2>&1); s=$(echo "$out" | grep -cE 'sam
         29s bash   for f in /tmp/probes/pre39_*.py /tmp/probes/p7_wrapper_kw*.py /tmp/probes/p7_identity_kw.py /tmp/probes/p7_kwo
         26s bash   for f in d_unused_fn g_boundary m_cond_int q_class_int r_two_params x_kw_int_shadow_local y_nested s_augassign
         15s bash   for f in /tmp/rprobes/rev_*.py; do echo "########## $(basename $f) BASE"; bash ~/tools/cmp.sh "$f" /tmp/base 2
         13s bash   cd /home/runner/work/ail-ci/ail-ci; export AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1; time (ls ~/corpus/gdev/*.py | 

FINAL VERDICT: ACCEPT  2026-10-24T02:06:56Z
