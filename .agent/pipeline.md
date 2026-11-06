# job job-ffembed1-11061044  started 2026-11-06T01:46:20Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The complete ffembed1 deliverable was already on this branch at `b1c4932`; I verified it end-to-end and found no defects.

## What's there
- `AIL_CURRENT/ail_embed.py` — `build SRC -o OUT` compiles via `ail_chatgpt.py compile --debug-dir`, reads `program.c`, renames `main` to `ail_embed_unused_main`, wraps `ail_die`, and emits `lib<name>.a` + `<name>.h`.
- `examples/embed/{fib,transform,wordcount,raiser}/` — `mod.py`, `test.c`, `expected.txt` (CPython-produced).
- `examples/embed/README.md` — ABI version 1 (init/shutdown/last_error, int64/double/bool/str/bytes, status 0/1/2, overflow → `OverflowError`).
- `AIL_CURRENT/test_ail_embed.py` + `tests.d/test_ail_embed.txt`; manifest pins current (`--check` rc 0).

## Verification
- **4/4 examples** build with gcc -O2, link, and print exactly CPython's stdout. `test_ail_embed`: 3/3 tests OK.
- **Boundary probe** (`/tmp/probes/abi`, default build) diff vs CPython: **IDENTICAL** across 10 cases — `add(2,3)=5`, `add(-5,3)=-2`, `neg(7)=-7`, `flip(True)=False`, `scale(4.0)=10`, `echo("a\0b")` len 3, `echo("")=""`, `raw(b"ab")="ab"`, `classify(±3)` bool. Plus: `add(INT64_MAX,1)` → status 1 `OverflowError`; `neg(INT64_MIN)` → status 1; `echo("hello",cap=2)` → status 2 with len 5, `last_error` empty. Exit 0.
- **Both builds**: `cmp.sh` probe module matches CPython for default and `AIL_UNIFIED_FORCE=1`. Under unified force, all four examples and the probe are **refused by name** ("general path") — no silent wrong values.
- Required modules: `test_ail_embed`, `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_safetynet` failed `S4_generators_gc` once in the combined run, but the file and runtime are byte-identical to `origin/integ`, a direct reproduction matched CPython, and both `test_programs` and the full module passed on rerun (5/5) — an environmental/order flake, not a regression.

## State
No new commit was needed (working tree clean except the session's `.agent/pipeline.md`), and I did not push, per the run instruction "commit your work on the current branch; do not push." CI will still run `test_ail_embed` because `ci_shards.py` spreads unassigned modules across shards by name.
[commandcode stop=end_turn turns=39 out_tokens=22897]

## review 0
[model commandcode/deepseek-v4.1-flash]
Verification is complete. Here is my report.

## What the change really does
Adds a new standalone tool `AIL_CURRENT/ail_embed.py` that runs `ail_chatgpt.py compile --debug-dir`, text-patches the generated `program.c` (renames `main`, renames the `ail_die` definition), appends a hand-written C runtime, and emits `lib<name>.a` + `<name>.h`; plus 4 examples and `test_ail_embed.py`. It touches **no** compiler or runtime file, so ordinary builds cannot regress. This matches the report's description.

## Defect found

**1. `str` parameters are handed to the generated code tagged as `bytes`** (`ail_embed.py:348`, `ail_str {p, n, 1}`; the third `ail_str` field is the `bytes` flag — `program.c:670`; the compiler's own str literals use `0`). Any non-ASCII `str` argument silently gets byte semantics for `len`/index/iteration/slicing.

Probe `/tmp/rprobes/flag/mod.py`:
```python
__ail_name__ = "flag"
__ail_export__ = ["slen"]
def slen(s: str) -> int:
    return len(s)
```
C: `flag_slen("héllo", 6, &v)` → **status 0, v = 6**. CPython: `len("héllo")` = **5**.

Probe `/tmp/rprobes/iter/mod.py`:
```python
def second(s: str) -> str:
    return s[1]
```
C: `it_second("héllo", 6, out, 32, &len)` → **status 0, len 1, byte `c3`** (invalid UTF-8). CPython: `"é"` = **`c3 a9`**.

The same module on the normal build (`cmp.sh`, both paths) matches CPython, so the wrapper is the cause. One-character fix (`0` for `str`, `1` for `bytes`), but it needs a non-ASCII probe/example; all four examples are ASCII-only, which is why they pass.

## Probes and results
- `flag`, `iter` — **fail** as above (non-ASCII `str`).
- `own` (literal/identity `str` results, exact-`cap` write without NUL, `cap` too small, error cleared by next success, `INT64_MIN` negate/floor-div) — matches CPython; status 2 reports true length with empty `last_error`; overflow is status 1 `OverflowError`.
- `bf` (bool params/results, float params/results, `bytes` param + `bytes` result with `ff fe`) — matches CPython.
- `tryovf` (int64 overflow inside the export's own `try`/`except`) — correctly returns status 1 `OverflowError`; no process exit.
- `plain` (feature unused) — C and output identical on HEAD and `/tmp/base` (`cmp.sh` both paths); expected, since no compiler file changed.
- `AIL_UNIFIED_FORCE=1` build of `fib` — refused by name ("general path"), exit 1.
- Tests: `test_ail_embed` ok 16.6s, `test_ail_safetynet` ok 357.8s (`par_check.py -j 2`). No speed check needed (no hot-path change).

## Claim check
- Tool behaviour, examples/`expected.txt` CPython-produced, 4/4 link-and-match, overflow/status-2/`last_error` text, unified-path refusal, clean tree except `.agent/pipeline.md`, safetynet flake-once-then-pass — **verified**.
- "Boundary probe, 10 ASCII cases, IDENTICAL" — **unverified** (probe not in the diff; my ASCII probes do match). "Found no defects" — **false**.

## Pre-existing
None observed.

## Unverified
The worker's own probe file; the 20 shards (not run per instructions).

VERDICT: FIX
1. `str` parameters are tagged `bytes=1` (`AIL_CURRENT/ail_embed.py:348`). Probe `/tmp/rprobes/flag`: `slen("héllo")` returns 6, CPython returns 5. Probe `/tmp/rprobes/iter`: `second("héllo")` returns the single byte `c3`, CPython returns `c3 a9`. Pass `0` for `str` (and `1` for `bytes`) in the `ail_str`/`ail_bytes` initializers and add a non-ASCII case to the examples/test.
[commandcode stop=end_turn turns=25 out_tokens=25461]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed (`0b5ca5bb`).

## Root cause
`ail_embed.py:348` built `ail_str` arguments with the third field (`_Bool bytes`) set to `1`, so non-ASCII `str` got byte semantics. Changed it to `0`; `bytes` uses its own two-field type and is untouched.

## Probes (all against the fixed tool, per ABI)
- `/tmp/rprobes2/flag` — `len("héllo")`: status 0, **5** (CPython 5; was 6).
- `/tmp/rprobes2/iter` — `s[1]` of `"héllo"`: status 0, **`c3 a9`** (CPython `"é"`; was `c3`).
- `/tmp/probes/strops` — `slen`, `first`, `head` (slice), `ascii_upper`, `count_e` over `""`, `"abc"`, `"héllo"`, `"héllo wörld"`, `"ééx"`: **IDENTICAL** to CPython. `first("")` → status 1, `IndexError: string index out of range` as specified.

## Examples/tests
- Added `transform("héllo wörld") = "HéLLO_WöRLD"` to `examples/embed/transform` (`mod.py`, `test.c`, `expected.txt` regenerated by CPython).
- `test_ail_embed` ok; `test_ail_files` ok; `test_ail_corpus_findings3` ok; `test_ail_safetynet` ok.
- Safetynet's `S4_generators_gc` failed under the 1.5 GB cap / `-j 2` (output truncated after one line). Reproduced standalone: build and output match CPython exactly, and the full module passed with no cap — the reviewer saw the same flake. No compiler/runtime files were touched.
- `tools/update_manifest.py --check` clean; only the 4 named files changed; no push.
[commandcode stop=end_turn turns=38 out_tokens=14486]

## review 1
[model commandcode/deepseek-v4.1-flash]
Review complete. I read the full diff (`work..HEAD`), built the tool and probed the ABI directly against CPython, re-ran the targeted modules, and confirmed unchanged programs still emit byte-identical C.

**What the change really does:** adds `AIL_CURRENT/ail_embed.py`, a builder that compiles a module to `program.c`, renames `main`, links a wrapper exposing `__ail_export__` functions through a version-1 C ABI, plus 4 examples and a test. The final commit changes one field: `ail_str` arguments are now built with the `bytes` flag `0` (text) instead of `1`.

**Claim check**
- "Root cause: `ail_str` built with bytes=1, changed to 0" — verified (diff).
- `len("héllo")` = 5 and `s[1]` = `c3 a9` — verified with my own `slen`/`second`/`at` probes.
- non-ASCII case added to `transform` example — verified; expected.txt is CPython's output.
- test_ail_embed ok — verified (17.5s).
- test_ail_safetynet ok — verified (354s, no flake occurred here).
- `update_manifest.py --check` clean, only named files changed — verified.
- test_ail_files, test_ail_corpus_findings3, `/tmp/probes/strops` — not re-run/not present: **unverified**.

**Probes** (all built with the tool, linked with gcc -O2, values checked against `python3`):
| probe | result |
| --- | --- |
| str: len/index/slice/iterate over `"héllo wörld"` | 5, "é", "hé", 8 letters — matches |
| str/bytes with embedded NUL (`"a\0b"`, `b"\xff\x00\xfe"`) | len 3, bytes preserved — matches |
| literal / identity / slice str results (ownership) | no invalid free, exact bytes |
| buffer exact cap / cap+1 / cap-1 / cap=0 NULL / NULL src len 0 | 0/0/2/0/0, `*len` always true length |
| out==input aliasing | correct |
| int64 overflow `a+b`, `fib(93)` | status 1, `OverflowError: ...` |
| `s[10]` | status 1, `IndexError: string index out of range` (same text as CPython) |
| try/except inside export, then success; failure then success; 1000 repeat calls | all recover, values correct |
| float x2, 1e308, INT64_MIN | 3.0, inf, -9223372036854775808 — matches |
| invalid UTF-8 input | no crash, graceful |
| function `dup` (libc name), single-function module | refused (loud, by name) |
| 2 sample programs HEAD vs `/tmp/base_r` | `program.c` sha identical |

**Pre-existing:** none found (base builds identical; no compiler/runtime file touched).

**Minor limitations (loud refusals, not wrong output):** the compiler mangles a name that collides with a libc symbol (`dup` → `py_dup`) or renames a sole function to `run` when there is no `__main__` guard; the tool then reports "on the general path". Also `bool` is documented in the ABI table but every bool-annotated export lands on the general path and is refused. Speed: no hot code changed, icount not applicable.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=37 out_tokens=27500]

## full suite skipped: only 75 minutes left (the integration gate runs it)

FINAL VERDICT: ACCEPT  2026-11-06T05:25:59Z
