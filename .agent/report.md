# job job-docffiq1-11060317  started 2026-11-05T18:17:53Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed on `job-docffiq1-11060317` (3 commits); not pushed, per the runner instruction at the end of the brief.

**What landed**
- `docs/FFI_QUICK.md` — 8 numbered steps, each with a marked code block (file byte-for-byte), a build/run command, and its exact stdout. Steps: libm `sqrt`; own `add.c` with two `int64`; `double` in/out; `str`; `bytes` + `bytearray`; out-of-range `int32`; `check="negative", errno=True` → `OSError`; bindgen from `add.h`. Ends by linking `docs/FFI.md#what-is-not-supported-yet`.
- `examples/ffi_quick/` — `add.c`, `add.h`, `step1..step8` programs, and the generated `add_gen_ffi.py`.
- `AIL_CURRENT/test_ail_docs_ffi_quick.py` + `tests.d/test_ail_docs_ffi_quick.txt`, registered; manifest pins refreshed (`update_manifest.py --check` = 0).

**Verified**
- `test_ail_docs_ffi_quick`: 3 tests OK. Each step's command is run in a temp copy; its stdout equals the page's output block; the same program under `python3` (ctypes) prints the same.
- Probes (both default and `AIL_UNIFIED_FORCE=1`, all equal to CPython):
  - `p_int_bounds`: int64 edges `±9223372036854775807/-9223372036854775808`; int32 edges; `2147483648` and `-2147483649` refused with `OverflowError` — no truncation.
  - `p_text`: `strlen` of `""`/`hello`/`héllo` → 0/5/6; embedded NUL refused (`ValueError`).
  - `p_buffers`: empty, 1-byte, 5-byte reverse; `length()` binding.
  - `p_errno`: parse `0`/`1234`; `""` and `"12a4"` → `OSError errno 22`, `[Errno 22] Invalid argument`.
- Required tests: `test_ail_files` OK (1 skip), `test_ail_corpus_findings3` OK, `test_ail_safetynet` OK uncapped. Under `ulimit -v 1500000` its pre-existing `S4_generators_gc` subtest prints only its first line and fails (program killed by the cap, 5530537 vs 5 lines) — same test passes uncapped and my diff touches no compiler code.
- `git diff --stat e324466` (the exported `staging:integ` base): 16 files, all the allowed files plus two `manifest.d` pins.

No CI shard results — pushing is disallowed for this runner.
[commandcode stop=end_turn turns=40 out_tokens=38006]

## review 0
[model commandcode/deepseek-v4.1-flash]
All checks are done. Here's my review.

## What the change does

Adds a docs-only quick guide (`docs/FFI_QUICK.md`, 8 steps), its example C/AIL files (`examples/ffi_quick/`), and a new test module that parses the page, proves each marked block equals its file, then builds/runs each step and compares stdout with the page and the ctypes path. No compiler, runtime or benchmark file is touched.

## Probe results (`bash ~/tools/cmp.sh … $PWD`, HEAD)

| Probe | Covers | Result |
|---|---|---|
| `p_int_bounds` | `c_int32` ±edges, 2147483648/-2147483649, `c_int64` min/max | g=d=CPython exit 0, same stdout; both refused with `OverflowError` |
| `p_int_paths` | out-of-range via arg, list item, attribute | same stdout; `OverflowError` each |
| `p_str_basic` | `""`, ascii, `héllo`, emoji, 100-char list item | same stdout (0,5,6,4,100) |
| `p_str_nul` | embedded NUL and `"\0"` | same stdout, `ValueError` twice |
| `p_str_attr`, `p_str_dict` | str via attribute / dict value | named subset refusal, byte-identical on `/tmp/base` (pre-existing) |
| `p_buf_alias` | empty/1-byte, slice sharing, mutate after call, buffer reuse | same stdout |
| `p_bytes_list` | `bytes` via list item | same stdout |
| `p_errno` | `"0"`, `"1234"`, `""`, `"12a4"` | same stdout; `OSError 22 [Errno 22] Invalid argument` |
| `p_double_paths` | double via arg/list, `-0.0`, `inf`, `0.1+0.2` | same stdout |
| `p_noffi` | no FFI | `--debug-dir/program.c` identical HEAD vs `/tmp/base` |

Named refusals (dict subscript, class-attribute values, int literal for a float parameter) are pre-existing typed-path limits, reproduced identically on `/tmp/base`.

## Tests

`test_ail_docs_ffi_quick` 3 tests OK (6.6 s); `test_ail_safetynet` OK (155 s); `test_ail_files` OK; `test_ail_corpus_findings3` OK. All 8 steps compile on the typed path (no `general path` note) and print the page's output. Regenerating `add_gen_ffi.py` with the page's bindgen command is byte-identical to the committed file.

## Report claims

- **Verified:** 8 steps with code/command/output; blocks byte-for-byte; typed path; 3 tests OK; out-of-range int refused without truncation; embedded NUL `ValueError`; `OSError` errno 22; bindgen output committed; `update_manifest.py --check` = 0; 16 files all in the allowed set (base `e324466` = `work`); the three required modules pass.
- **Unverified:** the 20 CI shards (worker did not push, no CI results); the `ulimit -v 1500000` safetynet failure claim (I ran uncapped only).
- **False:** none.

Minor, non-blocking: step 5's `ail_quick_reverse` (user C, matching lengths) does not check `len(dst) >= n`, and step 8's `cc` line leaves an untracked `libadd_quick.so` in the checkout. Neither contradicts a claim; both builds behave like CPython.

## Pre-existing

Typed-path refusals for dict subscripts, class-attribute values and int-for-float arguments; identical on the base. No speed check: no hot compiler/runtime code changed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=38 out_tokens=32041]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T20:13:48Z
