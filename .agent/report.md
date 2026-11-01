# job job-std_typing-11020445  started 2026-11-01T19:46:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `1613553`.

- Fixed NewType error text (exact CPython `_typing._idfunc()` messages, including starred-call counts).
- Made TypedDict/NewType lowering scope-aware; locals, parameters, comprehension targets and nested bindings now shadow correctly. Module rebinding and `global`/`nonlocal` become named refusals.
- Added `lab/stdlib/typing/13_errors.py` (caught/printed `TypeError` and `KeyError`) and registered it.
- Probes: 8 match CPython on both builds; `nt_module_rebind` and `nt_global` are refused by name. `nt_values` intentionally exits 1 and matches.
- Tests: `test_ail_std_typing`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed. `update_manifest.py --check` → 0. No compare program imports `typing`, so their C is unchanged.
[cost $0.0000, opencode tokens {"total": 1811276, "input": 42461, "output": 13159, "reasoning": 24200, "cache.write": 0, "cache.read": 1731456}]
    tool time: bash 7.1 min
        344s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_typing test_ail_safetynet test_ail_files test_ail_co
         30s bash   for p in nt_errors nt_shadow td_shadow nt_values td_values nt_scope td_scope nt_call_forms nt_module_rebind nt
         19s bash   cat > /tmp/probes/nt_values.py <<'PY' from typing import NewType  UserId = NewType("UserId", int) Name = NewTy
          8s bash   cat > /tmp/probes/td_values.py <<'PY' from typing import TypedDict   class Movie(TypedDict):     title: str   
          8s bash   for p in nt_errors nt_shadow td_shadow; do echo "#### $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"; done
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/nt_errors.py <<'PY' from typing import NewType  UserId = NewType("Us
          4s bash   cat > lab/stdlib/typing/13_errors.py <<'PY' from typing import NewType, TypedDict  UserId = NewType("UserId", 
          2s bash   for p in nt_errors nt_shadow td_shadow; do echo "#### $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"; done

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `work..HEAD` (`1613553`)

**What the change does.** Rewrites `typinglib.py` only: exact CPython `_typing._idfunc()` `TypeError` texts (arity, keywords, runtime counts for `*args`), a new scope analysis (`_Bindings`/`_shadowed`) so locals, parameters, comprehension targets, nested defs and `except` names shadow the module-level TypedDict/NewType declaration, named refusals for module-level rebinding and `global`/`nonlocal`, plus `lab/stdlib/typing/13_errors.py` registered in the test. Matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both builds). All in `/tmp/rprobes`:
- Same stdout/exit on HEAD: `r_nt_err` (0/1/2/3 args, `**{}`, `**{"x":1}`, `1,**{}`, `1,x=1`, starred forms), `r_shadow_kinds` (parameter, local, walrus, nested function, `except ... as`, comprehension target, lambda param), `r_td_shadow2`, `r_nt_values2`, `r_values` (arg/list/dict/attribute), `r_class_method`, `r_no_typing`.
- Refused by name: `r_rebind`, `r_global`, `r_shadow_td` (module-level loop target is a rebinding).
- `r_nt_err` confirms the exact CPython texts, including `(**{})` → `(0 given)`.
- Regression to a *named* refusal (not a crash, allowed by the rules): class bodies that bind a declared name after an earlier use (`r_class_min`, `r_class_min2`, `r_class_default`) matched on base but are now refused ("name 'UserId' is not a known function/class/builtin" / class-attribute message). Class-body statement support is already broken on base.

**C identity.** No `lab/compare/src/*/main.py` imports `typing`; `r_no_typing` `--debug-dir` `program.c` is byte-identical HEAD vs `/tmp/base`.

**Tests.** `par_check -j 2 test_ail_std_typing test_ail_safetynet` → 0 failed (32.5 s / 174.2 s). `test_ail_files test_ail_corpus_findings3` → 0 failed (102.9 s / 215.8 s). `update_manifest.py --check` → 0.

**Claims.** Exact error texts incl. starred counts: verified. Scope-aware local/parameter/comprehension/nested shadowing: verified. Module rebind and `global`/`nonlocal` named refusals: verified. `13_errors.py` added and registered: verified. “4 modules 0 failed”: verified. Manifest: verified. `nt_values` exit-1 match and the worker’s exact `/tmp/probes` files: unverified (files not available; equivalent `r_nt_err` matches). Speed: not applicable — change is compile-time lowering only.

**Pre-existing.** Class-body statements dropped by the compiler; general-path class-attribute constant restriction; `cast` used as a value/alias refused (from earlier review).

`VERDICT: ACCEPT`
[cost $0.0000, opencode tokens {"total": 822914, "input": 113245, "output": 5144, "reasoning": 16525, "cache.write": 0, "cache.read": 688000}]
    tool time: bash 7.9 min
        217s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_fil
        175s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         28s bash   cd /tmp && rm -rf dbgH dbgB && mkdir dbgH dbgB && for w in H B; do wt=/home/runner/work/ail-ci/ail-ci; [ $w = 
         13s bash   cd /tmp/rprobes && cat > r_class_before.py <<'PY' from typing import NewType, TypedDict UserId = NewType("User
         11s bash   cd /tmp/rprobes && for p in r_nt_err r_class_order r_shadow_kinds r_shadow_td r_rebind r_global; do echo "####
          8s bash   cd /tmp/rprobes && cat > r_td_shadow2.py <<'PY' from typing import TypedDict class Movie(TypedDict):     title
          6s bash   cd /tmp && rm -rf dbgH dbgB && mkdir -p dbgH dbgB && for w in H B; do wt=/home/runner/work/ail-ci/ail-ci; [ $w
          4s bash   cd /tmp/rprobes && cat > r_class_min.py <<'PY' from typing import NewType UserId = NewType("UserId", int)  cla

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T21:29:43Z
