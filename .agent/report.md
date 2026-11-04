# job job-rbmodval2b-11042200  started 2026-11-04T13:01:12Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed the four red modules from the suite run. They all traced to one pre-pass defect in `python/pkg-v12/pyfunc.py`: `_call_site_signature` treated a `str` argument as signature-propagation evidence, so a str passed to an annotated `int` parameter was reported as a `signature_override` at the declaration instead of an argument diagnostic at the call, and the generated `_ail_ctr_subtract_iter_str(c, "a")` made the typed path refuse with a `list[str]` message and fall back. STR claims are now skipped (the pass is for INT/FLT/BYTES/array; str parameters are settled by `_infer_strparam_pass`), leaving the per-call guard to report them. Positional float→int narrowing still reports `operation: parameter` at the declaration.

**Probes** (`/tmp/probes`, `bash ~/tools/cmp.sh`, general + default builds):
- `p1` positional str→int, `p2` keyword str→int, `p3` str→`list[str]`, `p5` int then str calls, `p7` str via list item, `p8` str via dict value → status 1 `type`, `operation: argument`, function `main`, correct line/column (`passing str where take() wants int` / `... wants a list of str`).
- `p4` positional float→int → unchanged `operation: parameter, inference_scope: signature_override` at `take` (1,1).
- `p6` unannotated str parameter and `p9` `list[str]` program → typed-only (`AIL_NO_GENERAL=1`) build, CPython-identical stdout.
- `p10` `Counter.subtract("a")` → CPython-identical via the general path; typed-only refused by name (`_ail_ctr_subtract_iter_str() wants a list of str`).

**Tests on the final commit:** argument_type_details 15, source_check 33, check_repair_context 8, collections 13, modules_values, modules, safetynet, files, corpus_findings3, refusal_messages, type_details, owned_type_details, sdk → 0 failed. `tools/update_manifest.py` refreshed `manifest.d/45.txt`; `--check` exit 0.

I also checked the review's one note: the `GH_MODELS_TOKEN` removal in `.github/workflows/agent-worker.yml` is part of the prescribed accepted diff, so I left it. Committed as `6feae63`; the untracked `.agent/pipeline.md` was left alone.
[commandcode stop=end_turn turns=78 out_tokens=36864]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** 9 lines in `AIL_CURRENT/python/pkg-v12/pyfunc.py` — `_call_site_signature` now drops **every** `STR` claim from signature propagation (`continue`), so a str argument no longer becomes a `sig_override`. That clears the 4 red modules but also deletes the *only* call-site inference path for unannotated parameters whose body offers no str evidence (INT-default params, e.g. `def f(x): return x`).

**Tests (HEAD):** `test_ail_argument_type_details` ok, `test_ail_source_check` ok, `test_ail_check_repair_context` ok, `test_ail_collections` ok, `test_ail_safetynet` ok — 0 failed. On base `test_ail_argument_type_details` fails 4 (the fix is needed). `tools/update_manifest.py --check` exit 0. Commit trailer present. All four red tests use annotated params, so a narrower (annotated-only) skip would have fixed them.

**Probes** (`/tmp/rprobes`, `cmp.sh` general+default, plus `AIL_NO_GENERAL=1` typed):

| probe | HEAD cmp.sh | typed-only HEAD vs base |
|---|---|---|
| p01 int+str, p02 float+str, p14 keyword/default int+str | CPython-identical (exit 1) | both refuse, message "passing str where … wants int/float" |
| p03/p12 bytes+str (incl. non-ASCII) | identical | both refuse, same message |
| p04 mixed call sites, p05, p06 list[str], p08 list/attr/dict/empty, p09, p13 method, p15, p16, p17 f-string, p18 slice, p19, p20 Counter | identical | identical |
| p23/p24/p25/p21 unannotated str, p29 `len`, p30 index | identical | both compile, CPython-identical |
| p10 no feature | `program.c` identical (only `AIL_DBG_SITE` paths differ) | — |
| p40 annotated str hot loop | — | `program.c` byte-identical base vs HEAD, 119 |

**Defect (caused by this change):** str call-site inference is lost for unannotated `INT`-default parameters. `_infer_strparam_pass` only revisits `'array'`/float-only params, so `return x` helpers get int.

- `p26_ident.py` (`def ident(x): return x` … `print(ident("a")+"b")`) — base typed build: exit 0, `ab`; HEAD typed build: exit 3 `p.ail:4:1: not in the subset: passing str where ident() wants int`.
- `p37_identity_list_item.py` (`items=["a","b"]; f(items[0]).upper()`) — base: `A`; HEAD: exit 3 `a method on Call`, and the **default** build now prints `note: … built on the general path (about 20x slower) because a method on Call` where base compiled typed C.
- `p38_identity_attr.py` (`c.s`), `p39_identity_strvar.py` (`s="ab"`), `p32_identity_argv.py` (`sys.argv[1]`) — same: base typed exit 0 (`HI`, `AB`, `é`), HEAD typed exit 3.

**Report claims:** "STR claims are skipped, leaving the per-call guard to report" — verified for annotated params; false as the comment states it, since the skip is not conditioned on an annotation. "Unannotated str call-site inference is `_infer_strparam_pass`, deliberately independent" — false (`ident`/`return x` is INT-default, outside that pass). Float→int narrowing still reports `operation: parameter` — verified (test passes). Tests → 0 failed — verified. Manifest — verified.

**Pre-existing:** p27/p28 (`x+y`, `x*2` with str), p33 `print(x)`, p34 `str(x)`, p31 dict[str,int], p41 str default, p20 typed module-scope Counter, p07 argv path — all refuse/behave identically on base.

VERDICT: FIX
1. `_call_site_signature` drops `STR` for unannotated parameters too. Probe `/tmp/rprobes/p26_ident.py`: `def ident(x): return x` + `print(ident("a")+"b")` — expected (base, typed build) exit 0 printing `ab`; actual (HEAD, typed build) exit 3 `p.ail:4:1: not in the subset: passing str where ident() wants int`, and in the default build a fallback to the general path ~20x slower. Same with `p37_identity_list_item.py` (expected `A`, actual exit 3 `a method on Call`), `p38_identity_attr.py`, `p39_identity_strvar.py`, `p32_identity_argv.py`. Skip the STR claim only when the callee parameter has a real annotation (the four red tests all annotate), keeping call-site str inference for unannotated parameters.
[commandcode stop=end_turn turns=37 out_tokens=35523]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed.

**Defect:** `_call_site_signature` dropped *every* `STR` claim, killing call-site str inference for unannotated parameters (`def ident(x): return x`). Typed-only builds refused `ident("a")+"b"`, `f(items[0]).upper()`, `f(c.s)`, `f(s)`, `f(sys.argv[1])` where base compiled them.

**Fix:** `_call_site_signature(args, callee_params, ctx, annotated=())` now drops a str claim only when the callee parameter carries a real annotation, fed by `_ANNOTATED_PARAMS` (filled per program in `_signatures`). All four clone-dispatch sites pass it (`_call_user_func`, `_propagate_signatures_pass`, `_plan_clones`, `ir/lower.py`), so planned clones still resolve.

**Probes** (`/tmp/rprobes`, typed-only `AIL_NO_GENERAL=1`):
- Now exit 0 and match CPython (previously exit 3): p26_ident, p37_identity_list_item, p38_identity_attr, p39_identity_strvar, p32_identity_argv, p21_argv_unannot.
- Still named refusals: p01/p02/p13/p14/p17/p18/p19/p27/p28/p33/p34 (`passing str where … wants int/float`), p03/p12 (bytes), p06 (list[str]), p20 (Counter), p41 (str default).
- Unchanged: p09/p10/p11/p23/p24/p25/p29/p30/p40 match typed; general+default `cmp.sh` over all probes unchanged (p07 differs only because it prints argv[0]).
- Default build of p37 shows no general-path fallback note.

**Tests:** four targeted modules 69 tests OK; `test_ail_safetynet test_ail_files test_ail_corpus_findings3 test_ail_modules_values test_ail_modules` → 93 tests OK (1 skipped). `tools/update_manifest.py --check` exit 0. Committed as `17dbcb7`.
[commandcode stop=end_turn turns=62 out_tokens=33743]

## review 1
[model commandcode/deepseek-v4.1-flash]
All checks done. Report follows.

## Review

**What the change really does:** re-scopes the previous fix in `_call_site_signature`: a `str` call-site claim is dropped only when the callee parameter carries a real source annotation (`_ANNOTATED_PARAMS`, rebuilt wholesale per program in `_signatures`, threaded through `_call_user_func`, `_propagate_signatures_pass`, `_plan_clones` and `ir/lower.py`). Unannotated parameters get their STR call-site inference back; annotated ones keep the per-call argument diagnostic. Only `pyfunc.py`, `ir/lower.py`, DEVLOG and two manifest hashes change.

The report matches the diff. No forbidden edits (no tests/bench/example files).

**Probes** (`/tmp/rprobes/rv*.py`, HEAD vs base `/tmp/base`, general + default builds unless noted):
- rv02, rv04, rv06, rv08, rv09, rv10, rv11, rv12, rv14, rv15, rv16–rv18, rv20, rv21 (posonly/kwonly annotated, unannotated identity via list item / dict value / attribute / argument, annotated passthrough, empty and negative values, string/bool annotations): all match CPython, same output and exit as base.
- rv05, rv11, rv12 (annotated int/float fed a str): exit 1 with CPython's `TypeError`, same stdout as base.
- rv13 (no str-to-annotated call): matches; `program.c` byte-identical base vs HEAD (only temp-path metadata differs).
- Typed-only (`AIL_NO_GENERAL=1`): p26/p37/p38/p39/rv04 unannotated identity now compile and match (base also compiles them — regression restored); p01/p06 and rv06 second site refuse by name (`passing str where … wants …`).
- Worker probes p21/p32: match CPython, exit 0 **with** an argv (cmp.sh without an arg exits 1, exactly as CPython does — the report's "exit 0" is imprecise but not a defect).
- rv19 `Counter.subtract("a")`: default builds match; typed-only refuses by name on both base and HEAD (different message only).

**Tests on HEAD:** `test_ail_argument_type_details`, `test_ail_check_repair_context`, `test_ail_collections`, `test_ail_source_check`, `test_ail_safetynet` (5 modules, 0 failed); `test_ail_modules_values`, `test_ail_files`, `test_ail_modules`, `test_ail_corpus_findings3` (0 failed). `tools/update_manifest.py --check` exit 0.

**Speed:** generated C for `g00_000`, `g00_004`, `g00_020` is byte-identical base vs HEAD when built from the same source path ⇒ no runtime/icount change.

**Claims:** defect description verified; base-typed regression verified; fix implementation and all four call sites verified; typed refusals verified; manifest/test claims verified (per-test counts not re-checked); "p07 argv[0]" and "p37 no fallback note" unverified/immaterial.

**Pre-existing (identical on base):** required keyword-only parameters refused ("every keyword-only parameter must have a default"); module-level `collections` objects refused; typed-only `Counter.subtract(str)` refusal.

**Unverified:** per-test counts; p07; broader suite (not run per instructions).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=39 out_tokens=28855]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T15:30:57Z
