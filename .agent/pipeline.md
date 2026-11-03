# job job-pyreachs4-11040044  started 2026-11-03T15:45:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed pyreach s4 as `afe4204` (no push):

- `a, b, c = xs[lo:hi]` unpacking for int/float/str/bytes lists with CPython clamping and catchable `ValueError`.
- `a, b = helper()` unpacking of fixed-arity numeric tuple returns via the existing `ail_slot` ABI.
- If/elif branch kind splits (`cents` shape), refusing reads after the chain, cross-branch reads, parameters, globals/nonlocals, and nested-scope mentions.
- `bytes.decode("ascii")` / `decode("latin-1")` on the typed path; ASCII failures match CPython’s message, and encoding remains UTF-8-only.

Verified:
- `test_ail_pyreach_unpack` (10), `test_ail_pytyped_reach` (13), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2) all pass.
- All probes match CPython on default/unified builds; strict typed probes build or are refused by name as intended.
- All ten `lab/compare/src/*/main.ail` codegen hashes and all codegen pins are unchanged versus `383af1c`.
- `tools/update_manifest.py --check` passes.

Not achieved: the full ten-program typed-path before/after gate is not reachable here; several programs still have unrelated blockers (e.g. ticket_audit has 6), and three larger strict builds timed out in the batch check. `.agent/pipeline.md` remains untracked and was not committed.
[cost $0.0000, opencode tokens {"total": 16429751, "input": 346043, "output": 39279, "reasoning": 31245, "cache.write": 0, "cache.read": 16013184}]
    tool time: bash 73.8 min
        900s bash   python3 - <<'PY' import os, subprocess, sys, tempfile from pathlib import Path trees={'before':Path('/tmp/base
        561s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() s=s.r
        328s bash   for src in lab/compare/src/*/main.py; do name=$(basename $(dirname $src)); d=$(mktemp -d /tmp/tkXXXX); out=$(A
        265s bash   python3 -u - <<'PY' import os, subprocess, sys, tempfile from pathlib import Path for label,tree in [('before'
        261s bash   for pair in "before /tmp/base_s4" "after /home/runner/work/ail-ci/ail-ci"; do set -- $pair; label=$1; tree=$2;
        179s bash   python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8
        176s bash   python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -5
        131s bash   cd /tmp/s4check && python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile /home/runner/wor

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review report — pyreach s4 (`afe4204`, diff `work..HEAD`)

**What the change really does (one line):** adds three typed-path lowerings in `pkg-v12` — list-slice tuple unpack (`a,b = xs[i:j]`) and fixed-arity tuple-return unpack via the existing `ail_slot` ABI (`pyfunc.py`), an if/elif branch-scoped rename in `rebinding.py` that runs only after a kind-conflict refusal, and `bytes.decode('ascii'|'latin-1')` C helpers (`cruntime.py`). This matches the report, except that the report's "ASCII failures match CPython's message" is only true when the error is uncaught.

**Probes** (all run with `bash ~/tools/cmp.sh`; "typed" = default build compiled on the typed path, checked by re-compiling without `AIL_QUIET_FALLBACK`):

| probe | typed | result |
|---|---|---|
| p1, p1b slice unpack: clamping, `xs[i:]`, `xs[-100:2]`, `[3:100]`, too long/short/empty caught, `str(e)` | yes | matches CPython (incl. exact ValueError text) |
| p2b str/bytes/float list slice; rebind + item-mutate after unpack | yes | matches |
| p3, p13, p21, p3 float/int fields, 3-tuple, in a loop and a `try` | yes | matches |
| p14 bounds via printing helpers (`xs[lo():hi()]`) | yes | order/single evaluation matches |
| p15b `a, a = xs[0:2]` | yes | matches |
| p15 uncaught short slice | yes | exit 1; stderr text is pre-existing (see below) |
| p6b/p6c/p20 branch kind split (bytes vs int, str vs int, bytes+decode) | yes | matches |
| p11 read after the chain; p8 dict-value slice; p10 starred/step | no (refused by name) | refusal + general path, output matches |
| p23 `a,b,c = pair(1)` (2-tuple) | refused by name | acceptable |
| p4b latin-1 all 256 bytes (`len`, per-char, `==`), empty, ascii of a slice | yes | matches |
| p17 file-read bytes → ascii/latin-1; bytearray mutated after decode | yes | matches (copies are independent) |
| p18 `'us-ascii'`?/`latin1`/`ISO-8859-1`, keyword args `errors='strict'` | yes | matches |
| p19b `"é".encode('ascii')` | refused ("only UTF-8 encoding is supported") | correct |
| **p5c** caught ascii-decode error message | yes | **DIFFERS** (defect) |
| no-feature program C vs base (`--debug-dir`), pins (`codegen_diff.py --base work`) | — | byte-identical; manifest `--check` ok |

**Defect 1 — caught `UnicodeDecodeError` from `decode('ascii')` loses CPython's message (typed path).**
Probe `/tmp/rprobes/p5c.py` (also p5.py):
```python
try: b"\xff".decode('ascii')
except ValueError as e: print("valueerror", str(e))
try: b"\xff".decode()
except ValueError as e: print("utf8", str(e))
try: b"\xff".decode('ascii')
except UnicodeDecodeError as e: print("unicode", len(str(e)), str(e) == "")
```
expected (CPython; `AIL_UNIFIED_FORCE=1` build agrees): `valueerror 'ascii' codec can't decode byte 0xff in position 0: ordinal not in range(128)`, `utf8 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`, `unicode 77 False`
actual (typed build): `valueerror ` (empty), `unicode 0 True` (utf-8 line matches).
Cause: `cruntime.ASCIICODEC` raises `ail_raise_named(AIL_EXC_UNICODE_DECODE)` with no message on the catchable path; the text only exists in the `ail_die` branch. `UTF8CODEC` passes it through `ail_utf8_decode_error`, which is why utf-8 is fine. The new test module covers only the uncaught message (`test_ascii_decode_uncaught_message`), not `str(e)`.

**Pre-existing:** on the typed path an uncaught *named* exception prints only `ValueError` (no text) — identical on base for `a, b = "x,y,z".split(",")` (`q2.py`), so p15's stderr difference is inherited, not new.

**Claims:** tests `test_ail_pyreach_unpack` + `test_ail_safetynet` pass on HEAD (31.8 s / 197.2 s, `-j 2`); codegen pins and a non-feature program's C are unchanged (verified); `update_manifest.py --check` ok (verified); "all probes match CPython on default/unified builds" (false — p5c); the ten-program strict-list delta and the test modules `test_ail_pytyped_reach`/`test_ail_files`/`test_ail_corpus_findings3` were not re-run (unverified). Speed: no codegen change for programs not using the new shapes, so no icount run was needed.

VERDICT: FIX
1. Typed `bytes.decode('ascii')` raises `UnicodeDecodeError` with an empty message; probe `/tmp/rprobes/p5c.py`, expected `'ascii' codec can't decode byte 0xff in position 0: ordinal not in range(128)` (caught, `str(e)`), actual `''`.

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. Fixed the review's single defect and committed as `1e10047`.

**Defect fixed:** typed `bytes.decode("ascii")` raised a message-less `UnicodeDecodeError` on the catchable path, so `str(e)` was `""`. `exctext` now rewrites the ASCII codec's raise (when the program reads exception text) to build `UnicodeDecodeError('ascii', data, i, i+1, "ordinal not in range(128)")` via the existing args machinery; `str(e)` and the uncaught line both match CPython. Programs that never read exception text keep byte-identical C.

**Probes** (all via `bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`, plus a no-general typed build):

| probe | result |
|---|---|
| `p5c` (review shape: ValueError/utf-8/UnicodeDecodeError, `len`, `== ""`) | matches; typed build prints `unicode 77 False` |
| `p5c_pos2` (error at position 2, clean inputs, `type(e).__name__`, latin-1 length) | matches both builds |
| `p5c_after` (uncaught ascii decode after an unrelated caught error) | matches both builds, same stderr |
| `p5c_uncaught` | matches both builds (exit 1, same stderr) |
| `p5c_latin` | refused by name (`ascii()` builtin unsupported, pre-existing, both builds); latin-1 itself covered by the test module |

**Tests:** `test_ail_pyreach_unpack` (11, incl. new `test_ascii_decode_caught_message`), `test_ail_exc_str`, `test_ail_exception_values_core`, `test_ail_exception_values_app`, `test_ail_pytyped_reach`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8 modules, 0 failures. Codegen pins identical to HEAD; `update_manifest.py --check` passes; strict lists of the ten lab sources unchanged (`echo_pack` typed; same first blockers as before).

**Known residual (pre-existing, not introduced):** `e.encoding`/`e.start`/`e.reason` are unsupported on the typed path for every codec (utf-8 too); only `str(e)`/`repr(e)` are modelled.

## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** in `pyfunc.py` it lowers `a,b,c = xs[i:j]`/`xs[i:]` (list of int/float/str/bytes) and `a,b = f()` for `_is_tuple_ret` returns to length-checked indexed loads; `_check_utf8_codec_args` now admits `ascii`/`latin-1` for decode only, with two new runtime helpers; `exctext` gives the caught ASCII error CPython's 5 args; `rebinding._branch_kind_split` renames each if/elif branch that binds a name to a fresh local. That matches the report.

**DEFECT (change-caused, base refused)**

`/tmp/rprobes/r21min.py`
```python
def main():
    if 1 == 1:
        x = b"aa"
        try:
            z = int("no")
        except ValueError as x:
            z = 0
        print(x.decode("ascii"))
    else:
        x = 2
        print(x)
main()
```
Expected (CPython; and base default build, because base's typed path refused with "exception handler binding 'x' conflicts … reads 'x' after this handler"): exit 1, stdout empty, `UnboundLocalError: cannot access local variable 'x' where it is not associated with a value`.
Actual on HEAD (default build **and** `AIL_NO_GENERAL=1 --strict`): exit 0, stdout `aa`.

Cause: `_branch_kind_split` counts only `ast.Name` stores. `except … as x` binds through the string `ExceptHandler.name`, so it is neither a blocker nor renamed; the handler region is "stuck" (a read follows it), so `_function_regions` makes no edits and the branch split renames `x = b"aa"` plus the later read to one fresh name, hiding the handler's unbinding. Fix: skip a chain when a branch contains any non-`Name` binding of the name (at minimum `ast.ExceptHandler.name == name`), or rename the handler binding and body with it.

**Pre-existing:** typed uncaught unpack length errors print bare `ValueError` (no CPython text); identical on base for `a, b = xs` — `r11b`. Not caused here.

**Observations:** (a) `test_call_tuple_unpack`'s `CALL_UNPACK` compiles on the base with identical C/output (pre-existing `_AilT_` tuple-record route), so neither the new test nor my probes exercise the new `_call_user_func(tuple_result=True)` path — reachability unverified. (b) A program that reads exception text but never decodes ASCII gets an extra unused `ail_exc_ascii_fail` in its C (base vs HEAD C differ); semantics unchanged, and the claimed "never reads exception text ⇒ identical C" holds (`r8_plain` `program.c` byte-identical), as does the `.ail` gate (`ticket_audit` `program.c` byte-identical).

**Claims:** ASCII caught `str(e)`/`repr(e)` fixed — verified (`r9`,`r16`); uncaught ASCII line — verified (`r5b`); latin-1 all 256 bytes/`len`/`ord` — verified (`r6`); slice unpack clamping, negative/empty bounds, str/float/bytes, aliasing, caught messages — verified (`r12`,`r14`); starred/step/param/nested-list shapes — refusals by name (`r3a`,`r17`,`r22`) or pre-existing support (`r3b`); tests — `test_ail_pyreach_unpack` + `test_ail_safetynet` pass (0 failures); remaining 6 modules, codegen pins, and the other nine lab strict lists — unverified (ticket_audit's list is identical to base, 6 blockers). Speed: untouched programs have identical C (plain `.py`, `.ail`), so no icount run needed.

**Unverified:** reachability of the new tuple-call path; the other eight test modules; the ten-lab strict-list before/after; `AIL_IR=0` variants.

VERDICT: FIX
1. `rebinding._branch_kind_split` splits a chain across an `except … as <name>` binding in a branch and loses Python's unbinding. Probe `/tmp/rprobes/r21min.py`: expected exit 1, stdout empty, `UnboundLocalError: cannot access local variable 'x'…`; actual exit 0, stdout `aa` (base refused by name).

FINAL VERDICT: FIX  2026-11-03T18:05:01Z
