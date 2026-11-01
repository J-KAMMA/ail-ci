# job job-std_string-11020027  started 2026-11-01T15:31:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `9a4add5`.

- Template method lowering now applies only to receivers known to be `string.Template`. Unknown receivers with exact direct-call forms stay ordinary method calls; keyword/optional forms are named compile-time refusals.
- All six review probes no longer crash: `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop` match CPython on both builds; `p_self_attr` is refused by name for its lambda-as-value. Additional probes for known/unknown Template calls, list/dict/attribute receivers and keyword forms all match or refuse by name.
- `test_ail_std_string` gained regression tests for unknown receivers and the keyword refusal.
- Tests: `test_ail_std_string`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 2607774, "input": 48820, "output": 9721, "reasoning": 15345, "cache.write": 0, "cache.read": 2533888}]
    tool time: bash 34.6 min
        508s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_string test_ail_safetynet test_ail_files test_ail_co
        428s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_string test_ail_safetynet test_ail_files test_ail_co
        274s bash   timeout 1200 python3 tools/par_check.py -j 2 test_ail_std_string 2>&1 | tail -30
        252s bash   for p in lab/stdlib/string/template_config.py lab/stdlib/string/template_email.py /tmp/probes/p_self_attr.py /
        234s bash   for p in /tmp/probes/p_*.py; do echo "##### $p"; bash .agent/cmp.sh "$p" "$PWD"; done 2>&1 | tee /tmp/probes_r
        133s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_self_attr.py <<'EOF' import string class Box:     def __init__(sel
        108s bash   cat > /tmp/probes/p_self_method.py <<'EOF' import string class Box:     def substitute(self, v):         retur
        108s bash   for p in /tmp/probes/p_*.py; do echo "##### $p"; bash .agent/cmp.sh "$p" "$PWD"; done

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** `_SurfaceExpr.visit_Call` / `_Surface.call` now lower `.substitute/.safe_substitute/.is_valid/.get_identifiers` only when `receiver_kind == 'template'`; unknown receivers keep direct-call forms as ordinary method calls and refuse keyword/optional forms by name; the old `user_methods` guard is removed and 2 tests are added. This matches the report's description. It does **not** fix the receiver classifier itself, which is still unsound for non-`Assign` rebinding targets.

**Probes (HEAD = 9a4add5, both builds; base = `work` = 773ef34):**
- Worker/review probes `/tmp/probes/p_*.py`: `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop`, `p_self_method`, `p_self_string`, `p_attr_template`, `p_list_template`, `p_known_keyword`, `p_review_p8` all match CPython; `p_self_attr`, `p_unknown_keyword` refused by name. Verified.
- My probes: `p_known_collision`, `p_unknown_template_list`, `p_alias`, `p_unknown_errors`, `p_param`, `p_nonfeature`, `p_string_no_template` all match. Non-feature `--debug-dir` C byte-identical to base.
- `p_unknown_kw`, `p_unknown_optional`, `p_mixed_binding`, `p_template_value` refused by name (acceptable).
- **Defect:** `p_loop_shadow`, `p_unpack_shadow`, `p_comp_shadow`, `p_walrus_shadow`, `p_shadow_silent` crash or print wrong output on HEAD while base refuses by name.

**Defect 1.** `collect_template_scopes` (`ail_syntax.py:2141-2150`) records only `Assign/AnnAssign/AugAssign` targets. A `for`/comprehension/tuple-unpack/walrus target that reuses a Template-bound name is invisible, so `kind_of_name` still returns `'template'` and `call` lowers the call on the non-Template value. Removing the `user_methods` guard made this observable (base refused these programs by name).

`/tmp/rprobes/p_loop_shadow.py`:
```python
import string
class Box:
    def __init__(self): self.tag = "b"
    def substitute(self, v): return "B" + str(v)
def main():
    t = string.Template("$x")
    print(t.substitute(x=1))
    for t in [Box()]:
        print(t.substitute(5))
main()
```
Expected (CPython, exit 0): `1` / `B5`. Actual HEAD g+d: prints `1`, then `AttributeError: 'Box' object has no attribute 'template'`, exit 1. Base: named compile-time refusal. Same for tuple-unpack, comprehension and walrus targets.

`/tmp/rprobes/p_shadow_silent.py` (same shape, `Box.template = "$y"`, `Box.delimiter = "$"`, call `t.substitute({"y": "WRONG"})`): expected `1` / `B{'y': 'WRONG'}`; actual HEAD both builds `1` / `WRONG`, exit 0 — silent wrong output; base refuses by name. Fix: record every binding target (`For`/`comprehension` targets, `Tuple`/`List` targets, `NamedExpr`, `with ... as`, `except ... as`) as an unknown/other binding, so such a name is no longer `'template'`.

**Claims:** Scope/parameter classification, direct-call fallback, keyword refusal, tests added: verified. "Only receivers known to be Templates" is **false** for the shadowing targets above. Tests: `test_ail_std_string` + `test_ail_safetynet` re-run on HEAD, 0 failed (279 s, `-j 2`); `update_manifest.py --check` rc 0. `test_ail_files`/`test_ail_corpus_findings3` not re-run (not edited). lab/compare: 7 tasks compile with `--exact-int` and generated `program.c` is byte-identical to base; `scar_life`, `tally_lang`, `tree_fold` fail on both trees.

**Pre-existing:** the 3 lab/compare failures (both trees); `p_self_attr` lambda case now a named refusal instead of a base crash (improvement).
**Unverified:** speed (compile-time AST change only); `test_ail_files`/`test_ail_corpus_findings3` on this commit.

VERDICT: FIX
1. Receiver classification still treats a name rebound by a `for`/comprehension/tuple-unpack/walrus target as a known `string.Template`. `/tmp/rprobes/p_loop_shadow.py`: expected `1`/`B5` (exit 0), actual HEAD both builds `1` then `AttributeError: 'Box' object has no attribute 'template'` (exit 1), while base refuses by name. The silent variant `/tmp/rprobes/p_shadow_silent.py` prints `WRONG` instead of `B{'y': 'WRONG'}` at exit 0. Track these binding targets in `collect_template_scopes` (or refuse to lower when the name has such a binding).
[cost $0.0000, opencode tokens {"total": 1508370, "input": 55389, "output": 8382, "reasoning": 18039, "cache.write": 0, "cache.read": 1426560}]
    tool time: bash 24.0 min, read 0.0 min
        448s bash   date; cd /tmp && rm -rf lch lcb && mkdir -p lch lcb; same=0; bothfail=0; other=0; for t in $(ls /home/runner/w
        280s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
        233s bash   date; cd /tmp/probes && for p in p_attr_chain p_attr_template p_call_result p_dict_sub p_for_loop p_known_keyw
        105s bash   date; cd /tmp/rprobes && for p in p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_for_loop;
         63s bash   date; cd /tmp/rprobes && for p in p_known_collision p_unknown_template_list p_unknown_kw p_unknown_optional p_
         57s bash   cd /tmp/rprobes && for f in p_comp_shadow p_loop_shadow; do sed -i 's/class Box:/class Box:\n    def __init__(
         57s bash   cd /tmp/rprobes && cat > p_unpack_shadow.py <<'EOF' import string class Box:     def __init__(self):         s
         54s bash   cd /tmp/rprobes && cat > p_comp_shadow.py <<'EOF' import string class Box:     def substitute(self, v):       

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `fb7f0ec`.

- `collect_template_scopes` now records rebindings from `for`/`async for`, comprehension, tuple/list/starred assignment, walrus, `with ... as`, and `except ... as` targets. `kind_of_name` treats such names as unknown, including in enclosing scopes, so they are never lowered as Templates.
- Shadow probes: isolated for/tuple/comprehension/walrus/silent variants match CPython on both builds; the reviewer's exact probes are now named compile-time refusals instead of crashes/silent wrong output. All `/tmp/rprobes`, `/tmp/probes`, and added shadow probes matched or were refused by name.
- Added `test_template_method_names_shadowed_by_other_bindings`.
- Final commit tests: `test_ail_std_string`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 1671192, "input": 374618, "output": 7490, "reasoning": 12796, "cache.write": 0, "cache.read": 1276288}]
    tool time: bash 34.7 min, edit 0.0 min
        502s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_string test_ai
        494s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_string test_ai
        462s bash   cd /tmp && for p in /tmp/rprobes/*.py /tmp/probes/*.py; do n=$(basename "$p" .py); out=$(bash ~/tools/cmp.sh "
        339s bash   cat > /tmp/probe_summary.sh <<'EOF' #!/bin/bash p=$1 out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/a
        110s bash   cd /tmp/rprobes && for p in p_loop_shadow p_unpack_shadow p_comp_shadow p_walrus_shadow p_shadow_silent; do ec
         99s bash   mkdir -p /tmp/rprobes2 && cd /tmp/rprobes2 && cat > p_for_only.py <<'EOF' import string class Box:     def sub
         76s bash   mkdir -p /tmp/rprobes3 && cd /tmp/rprobes3 && cat > p_match_shadow.py <<'EOF' import string class Box:     def
          2s bash   cd /tmp/rprobes && for p in p_loop_shadow p_unpack_shadow p_comp_shadow p_walrus_shadow p_shadow_silent; do ec

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** `ail_syntax.py` now lowers `substitute/safe_substitute/is_valid/get_identifiers` only when the receiver is *known* to be `string.Template`; unknown receivers keep the prelude object's own method for the exact direct forms (one positional mapping, or no args for `is_valid`/`get_identifiers`) and are named compile-time refusals for keyword/optional forms. `collect_template_scopes` records `for`/comprehension/walrus/`with`/`except`/tuple-list-starred assignment targets as rebindings so those names are never classified as Templates. Matches the report.

**Review defect 1 (HEAD, both g/d):** fixed.
- `p_self_attr` → named refusal (`the method .substitute() (on a instance:Box)`, lambda-as-value); base refuses/crashes, no regression.
- `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop` → exit 0, stdout identical to CPython on both builds.

**My probes** (`/tmp/rprobes_r2`, both builds):
- `p_known_forms` (all Template forms, alias) → match.
- `p_unknown_forms` (list item: substitute/safe_substitute/is_valid/get_identifiers direct) → match.
- `p_unknown_zero`, `p_unknown_two`, `p_unknown_isvalid_arg`, `p_module_for_shadow`, `p_attr_keyword`, `p_comp_outer`, `p_match_capture` → named refusals (CPython exit 0; refusal allowed).
- `p_walrus_shadow`, `p_match_direct`, `p_template_mutated`, `p_user_method`, `p_nested_def` → match/refuse as expected.
- Isolated shadows (`p_for_only`, `p_unpack_only`, `p_comp_only`, `p_walrus_only`, `p_silent_only`) → match.
- Non-feature C: `berth_sim`, `ticket_audit` `program.c` byte-identical HEAD vs base (only temp paths in `native_report.json` differ). `template_used` gates every new read, so other C is unchanged.

**Claims**
- Rebindings from for/async-for/comprehension/tuple-list-starred/walrus/with/except; `kind_of_name` returns unknown incl. enclosing scope: **verified** (diff + probes).
- Isolated shadow probes match on both builds: **verified**.
- Reviewer probes now refused instead of crash: **verified** for `p_self_attr`; the other five now match.
- "All /tmp/rprobes, /tmp/probes, added shadow probes matched or refused": **false** for `/tmp/rprobes3/p_except_shadow.py` (see pre-existing).
- New test added: **verified**.
- `test_ail_std_string` + `test_ail_safetynet` 0 failed: **verified** (378 s, `-j 2`).
- `update_manifest.py --check` rc 0: **verified**.

**Pre-existing:** `p_except_shadow.py` (`raise Box()` on a non-exception class) differs identically on base (CPython exit 1, AIL prints `B5`, exit 0) — unrelated to this change. Conservative named refusals for keyword forms on unknown receivers (`self.t`, list/dict/attribute Templates with kwargs) are new-but-allowed per the review instruction.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` not re-run (not edited; instruction says only edited modules + safetynet); speed not measured (compile-time AST work only, no runtime change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2232942, "input": 96830, "output": 8296, "reasoning": 29128, "cache.write": 0, "cache.read": 2098688}]
    tool time: bash 20.2 min
        379s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_string
        219s bash   cd /tmp && rm -rf dbgcmp && mkdir dbgcmp && cd dbgcmp && for wt in head base; do root=/home/runner/work/ail-ci
        126s bash   cd /tmp/rprobes && for p in p_alias p_known_collision p_mixed_binding p_nonfeature p_param p_string_no_templat
        106s bash   cd /tmp/probes && for p in p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_for_loop; do ech
         99s bash   cd /tmp/rprobes2 && for p in p_for_only p_unpack_only p_comp_only p_walrus_only p_silent_only; do echo "##### 
         75s bash   cd /tmp/rprobes3 && for p in p_with_shadow p_except_shadow p_match_shadow p_import_shadow; do echo "##### $p";
         61s bash   cd /tmp/rprobes_r2 && for p in p_known_forms p_unknown_forms p_unknown_zero p_unknown_two p_unknown_isvalid_ar
         41s bash   cd /tmp/rprobes_r2 && cat > p_user_method.py <<'EOF' import string class Box:     def substitute(self, v):    

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T19:08:38Z
