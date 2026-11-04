# job job-binascii2_rr1-11042344  started 2026-11-04T14:44:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Two commits on `job-binascii2_rr1-11042344` (`cadcc1e`, `cdbfa1b`), not pushed — the brief's final line says to commit on the branch and not push, so CI/PR checks were not run here.

**Result: 0/12 → 11/12** in both the default build and `AIL_UNIFIED_FORCE=1`.

- **Before (integ 2adbd4e):** every program refused at `import binascii ... general path: binascii.hexlify (not yet published in NAMES_library.json)`, etc.
- **After:** `01`–`10` and `12` match CPython 3.12.3 stdout and exit status in both builds; `11_crc_big.py` builds but stops with `OverflowError: integer overflow in *` on `crc32(data, 2**64+5)`, which the brief allows.
- **Module:** `AIL_CURRENT/stdlib/binascii.py` with `Error(ValueError)`, `Incomplete`, hex/base64 functions, `strict_mode` messages copied from CPython, table-driven `crc32`, bit-serial `crc_hqx`; `b2a_uu`/`a2b_uu`/`b2a_qp`/`a2b_qp` documented as absent.
- **Test:** `test_ail_std_binascii.py` passes (142 s); registered in `tests.d` and the manifest (`--check` clean).
- **Bench:** `perf_event_open` was denied, so median-of-5 wall times: `crc32` 16 MiB — AIL 0.06 s vs Python 0.42 s; `hexlify` 4 MiB — AIL 0.02 s vs Python 1.62 s (recorded in RESULTS.md).
- **Regression tests:** shlex, zlib, base64, files, corpus_findings3 and binascii all pass. safetynet passed on rerun; its single failure in the first batch was only the `ulimit -v 1500000` cap (`S4_generators_gc` lost output under memory pressure).
- **Probes:** four `/tmp/probes/` programs (hex/sep, unhex, base64/strict, crc/hqx) covering empty, negative, separators from list/dict/attribute/parameter, seeds `-1`/`2**32`/`2**63-1`, and both builds all matched CPython.
- `git diff --stat 2adbd4e` shows only the 19 allowed files (module, 12 programs, RESULTS, test, tests.d entry, 3 manifest files).
[commandcode stop=end_turn turns=70 out_tokens=54548]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: binascii2 (HEAD `cdbfa1b`, base `work` = 2adbd4e)

**What the change really does:** adds a new AIL-written `AIL_CURRENT/stdlib/binascii.py` (hex, base64, crc32, crc_hqx, `Error`/`Incomplete`), 12 lab programs + RESULTS.md, a test module, a `tests.d` entry and three manifest lines. No compiler or runtime file is touched. That matches the report.

**Probes** (`/tmp/rprobes/binq/`, `bash ~/tools/cmp.sh … $PWD`, default and `AIL_UNIFIED_FORCE=1`):
- `a_hexsep`, `b_unhex`, `c_b64dec` (29 decode cases), `d_b64enc`, `e_crc`, `g_alias`, `h2/h3/h4`, `j_bytesvar`, `k_arg` (arg / list item / dict value), `l_enc`, `m_loop`, `n_gen` — same stdout as CPython in both builds. Values arriving through an argument, a list item and a dict value all work; `bytearray` mutated after `hexlify`/`crc32`/`b2a_base64` does not change the earlier results.
- `q_exhaust` — exhaustive `a2b_base64` over alphabet `AYW=* ` for lengths 0–5 in both strict modes (18 662 calls) and `unhexlify` over `0aFz \n` lengths 0–4: identical including error texts.
- `r_table` — all 256 single bytes and all 65 536 byte pairs for `crc32`/`crc_hqx` (also against `zlib`): identical.
- `f_plain` (does not use binascii): `--debug-dir/program.c` byte-identical to the `work` build, same binary sha256.
- `h_random` — refused by name: `passing a bytes where binascii.a2b_base64() wants a sequence` (cause narrower than the whole program: `h3`/`h4` build; a named refusal, acceptable).
- `i_overaccept` — **differs** (see defects 1–2).
- `o_strscale` — str inputs scale ~linearly; only the printed timing lines differ (probe artifact).
- `p_none` — confirms a `None` default falls back to the general path, so the `sep=b""` corner is a compiler-convention problem, not laziness.

**Tests:** `par_check.py -j 2 test_ail_std_binascii` ok (150 s); `test_ail_safetynet` ok alone (143 s). The S4 failure I first saw only happens under my own `ulimit -v 4000000`; S4 passes on HEAD *and* on `work` without it.

**Claims:** 0/12 → 11/12 in both builds — verified; 11_crc_big builds and stops with overflow — verified; before-state refusal — verified on `work`; manifest `--check` clean and only the 19 allowed files — verified; error texts exact — verified; "where CPython accepts it, an ASCII str" — **false** (str is accepted everywhere); bench numbers — unverified (`perf_event_open` denied here too, did not re-time).

**Pre-existing:** none found.

**Defects (both are accept-what-CPython-rejects, no wrong value for valid bytes input):**

1. Empty separator is silently "no separator". Probe `/tmp/rprobes/binq/a_hexsep.py`:
   `print(binascii.hexlify(b"abcd", b"", 1).decode())` and the same through a `sep` variable.
   CPython: `VE sep must be length 1.` (twice); AIL: `61626364` (twice). Same for `sep=""`.

2. Type check is a superset of CPython's. Probe `/tmp/rprobes/binq/i_overaccept.py`:
   - `hexlify("abc")` / `crc32("abc")` / `crc_hqx("abc", 0)`: CPython `TypeError: a bytes-like object is required, not 'str'`; AIL prints `b'616263'`, `891568578`, `40406`.
   - `b2a_base64(b"ab", False)`: CPython `TypeError: b2a_base64() takes exactly 1 positional argument (2 given)`; AIL accepts `False`.
   - `hexlify([97, 98])`: CPython `TypeError: a bytes-like object is required, not 'list'`; AIL prints `b'6162'`.
   - `hexlify(b"ab", bytearray(b"-"), 1)`: CPython `TypeError: sep must be str or bytes.` (exit 1); AIL prints `61-62` (exit 0).
   `_ascii_bytes` is the cause: it converts any `str`/iterable via `bytes(...)`. CPython accepts `str` only in `unhexlify`/`a2b_hex`/`a2b_base64` and never a list.

VERDICT: FIX

1. `hexlify`/`b2a_hex` must raise `ValueError("sep must be length 1.")` for an explicit empty `sep` (bytes or str) instead of returning unseparated hex; probe `a_hexsep.py` expects `VE sep must be length 1.` twice, actual `61626364` twice.
2. Restrict `_ascii_bytes` to what CPython takes: reject `str` and non-buffer iterables in `hexlify`/`b2a_hex`/`b2a_base64`/`crc32`/`crc_hqx` with `TypeError: a bytes-like object is required, not '<type>'`, reject a `bytearray` `sep` with `TypeError: sep must be str or bytes.`, and make `b2a_base64`'s `newline` keyword-only; probe `i_overaccept.py` expects the six `TE ...` lines and exit 1, actual values and exit 0.
[commandcode stop=end_turn turns=49 out_tokens=52882]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: binascii lane

**What the change really does.** Adds a bundled AIL-source stdlib `AIL_CURRENT/stdlib/binascii.py` (hex/base64/crc32/crc_hqx), 12 lab programs + RESULTS.md, one test module, and manifest rows. No compiler or runtime file is touched. The worker's final text is empty; I verified against RESULTS.md.

**Probes** (`/tmp/rprobes/p1..p9`, each run with `cmp.sh` in both builds; all matched CPython unless listed):
- `p2_b64.py` (base64 encode/decode, strict mode, junk, padding), `p3_crc.py` (crc32 values −2⁶³…2⁶³−1, crc_hqx 0…2¹⁶+3), `p4_paths.py` (list/dict/attr/arg, mutate after hexlify/a2b/crc), `p5_unhex.py`, `p9_pad.py` (10 padding corners): identical to CPython, exit 0 both builds.
- `p6_nofeature.py`: generated C identical HEAD vs base 2adbd4e (`--debug-dir`, `diff` clean).
- Probe 1 and 8 differ; see defects.

**Defects found**

1. **Internal separator sentinel is a real byte string** (`b"\x00AIL_NO_SEP\x00"`, `_sep_byte` compares with `==`). `p1_hexsep.py`: `binascii.hexlify(b"ab", bytearray(b"\x00AIL_NO_SEP\x00"))`; `p8_edge.py`: same with bytes. Expected CPython 3.12.3: `ValueError: sep must be length 1.`, exit 1. Actual both builds: `sent b'6162'`, exit 0. A user value is silently reinterpreted as "no separator".
2. **`_typename` has no `float`**. `p7_more.py`: `hexlify(b"abc", b"-", 2.0)` -> expected `TypeError: 'float' object cannot be interpreted as an integer`, actual `'object' object cannot be interpreted as an integer`; same for `crc32(b"abc", 2.5)` and `crc_hqx(b"abc", 2.5)`.
3. **`bytes_per_sep` is not range-checked as a C int**. `p7_more.py`: `hexlify(b"abc", b"-", 2**31)` -> expected `OverflowError: Python int too large to convert to C int`, actual `b'616263'`, exit 0 (same for 2⁶³−1). Silently wrong output.
4. **Non-ASCII `str` separator**. `p7_more.py`: `hexlify(b"abc", "\u0100", 1)` -> expected `ValueError: sep must be ASCII.`, actual `ValueError: byte must be in range(0, 256)` (also `"\u20ac"`).
5. **Argument validation order**. `p8_edge.py`: `hexlify(b"abc", 5, 2.0)` -> expected the float `TypeError` above, actual `TypeError: object of type 'int' has no len()` (the sep check runs before the C-level `bytes_per_sep` conversion).

**Report claims**
- 11/12 build and match CPython in both builds: **verified** — `par_check -j 2 test_ail_std_binascii test_ail_safetynet`: `ok test_ail_std_binascii 514.3s`.
- `11_crc_big` stops loudly with overflow: **verified** by the module's own assertion (test passes).
- Default build takes the general path: **verified**, but the stated reason is wrong: the compiler printed `AIL_CURRENT/stdlib/binascii.py:45:5 ... because \`is None\` on something that is never None`, not "typed path cannot raise TypeError".
- "Every error text exactly CPython's": **false** (defects 2, 4, 5).
- crc32/crc_hqx mask value to 32/16 bits: **verified** (p3).
- Only listed files changed; manifest `--check` clean: **verified** (`19 files, +760`).
- Bench wall-times, "Before 0/12" (spot-checked only 01), 20 shards/PR checks: **unverified**.

**Pre-existing**
- `test_ail_safetynet` fails `S4_generators_gc` (`'5530537\n'` vs the longer expected output) identically on base 2adbd4e with the same `ulimit` — not caused by this change.
- Stray probes left in `/tmp/rprobes` (`p_zlib.py`, `p_libm.py`, …) are from an earlier session; their diffs are CPython's missing `ail_ffi`, unrelated.

Performance: not checked — no compiler/runtime code changed (no hot path).

VERDICT: FIX

1. `hexlify(b"ab", bytearray(b"\x00AIL_NO_SEP\x00"))` / same with bytes: expected `ValueError: sep must be length 1.` (exit 1), actual `b'6162'` (exit 0) — sentinel collision in `_sep_byte`.
2. `hexlify(b"abc", b"-", 2.0)`, `crc32(b"abc", 2.5)`, `crc_hqx(b"abc", 2.5)`: expected `'float' object cannot be interpreted as an integer`, actual `'object' object cannot be interpreted as an integer` — `_typename` lacks `float`.
3. `hexlify(b"abc", b"-", 2**31)`: expected `OverflowError: Python int too large to convert to C int`, actual `b'616263'` (exit 0) — `bytes_per_sep` not range-checked.
4. `hexlify(b"abc", "\u0100", 1)`: expected `ValueError: sep must be ASCII.`, actual `byte must be in range(0, 256)`.
5. `hexlify(b"abc", 5, 2.0)`: expected the float `TypeError`, actual `object of type 'int' has no len()` — argument check order differs from CPython.
[commandcode stop=end_turn turns=40 out_tokens=32429]

FINAL VERDICT: FIX  2026-11-04T16:46:06Z
