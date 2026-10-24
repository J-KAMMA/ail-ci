# job job-pre139-10250110  started 2026-10-24T16:12:53Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"success","duration_ms":1536,"duration_api_ms":1403,"is_error":false,"num_turns":1,"result":"pong","stop_reason":"end_turn","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Fixed the first still-differing item (`r4`: non-BMP `chr()` from a list/dict/attribute on the general path) and committed as `a770e7f` on `job-pre139-10250110` (no push).

**Change**: the 16-bit v2 runtime now stores a non-BMP `chr()` value as a UTF-16 surrogate pair, and point-based string ops see one code point: print/write, repr, len, ord, index, slice, iterate, reversed, compare, find/count, startswith/endswith, pad, replace. The byte decoder behind `repr` stores pairs too. Non-BMP *literals* remain refused by name.

**Probes** (`bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`, both builds):
| probe | result |
|---|---|
| r4, diag, boundaries (0xFFFF/0x10000/0x10001/0x1F600/0x10FFFF), containers (arg/list/attr/dict/negative/empty/alias), types (bool, int), errors (range, TypeError), methods, iteration, bmp, chrdirect, chrlit | match CPython on general + default |
| lit (non-BMP literal) | general refused by name (`non-BMP string literal in the 16-bit v2 runtime`); default matches |
| r10 (`bytes.decode` astral) | still differs on general — separate cause, recorded open |
| r9 (lone surrogate `chr`) | still differs on both — separate cause, recorded open |

**Tests on the final commit**: `test_ail_pre139` 2 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skipped), `test_ail_corpus_findings3` 2 OK; `update_manifest.py --check` exit 0. DEVLOG entry added, DIFFERENCES rows use `C?-job-pre139-10250110-{1,2,3}`.

## review 0
[model qoder/DeepSeek-Flash]
## Review: pre139 non-BMP `chr()` on the general path

**What the change really does (one line):** it stores a non-BMP `chr()` value as a UTF-16 surrogate pair in the 16-bit v2 runtime and rewires `len/ord/index/slice/iter/reversed/cmp/find/count/startswith/endswith/pad/replace/repr/print/from_utf8` to a code-point view (matching the report), plus test/DEVLOG/DIFFERENCES/manifest.

**Claims checked:** r4 via arg/list/attr/dict matches CPython on both builds (p5); the listed point ops match (p1–p5, p7, p13); file write/read of an astral string matches (p10); non-BMP literal is refused by name on `g` and matches on `d` (p12); `test_ail_pre139` and `test_ail_safetynet` pass; `update_manifest.py --check` exits 0. **False premise:** the task/DEVLOG say the default build matched before — on base **both** builds die with `chr() non-BMP code point requires 32-bit strings` (p1 on `/tmp/base`), so this fixed both.

### Defects

1. **`len()` and indexing became O(n) for every string (hot-code regression, no astral char involved).** `ail_op_len`/`ail_str_index` now call `ail_s2_npoints`/`ail_s2_unit_at`, which scan all units. `/tmp/rperf2.py`: `"abcdefghij"*20000`, 20 000 × `len(s)` → general path **5.65 s** vs base **0.001 s** (same output 4000000000); `/tmp/rperf3.py`: 30 000-char string, `for i in range(len(s)): s[i]` → **1.26 s** vs **0.003 s** (quadratic). Default build is unaffected. Cache the point count (or keep a BMP-only fast path).
2. **Format width counts units.** p10: `f"{e:>3}"` / `"{:>3}".format(e)` expected `'  😀'`, actual `' 😀'`; `f"{e:^4}"` expected `' 😀  '`, actual `' 😀 '`.
3. **`expandtabs` counts units.** p8: `(chr(0x1F600)+"\tx").expandtabs()` expected `len 9, '😀       x'`, actual `len 8, '😀      x'` (both builds).
4. **`"%c" % chr(0x1F600)`** expected `😀`; actual `TypeError: %c requires int or char`, exit 1 (p9). (`"%c" % 0x1F600` already dies on base — see pre-existing.)

### Pre-existing (identical on base, not blocking)
- p15 `b'\xf0\x9f\x98\x80'.decode()`: general dies, default matches (r10).
- p16 `chr(0xD800)`: general dies / default ValueError (r9).
- p14 `"%c" % 0x1F600`: both builds die; base identical.

### Unverified
- Instruction counts: `perf_event_open` is denied here, so wall time was used instead.
- stdin path (`ail_bi_str_from_utf8`) and the worker's own probe set; `test_ail_files`/`test_ail_corpus_findings3` not re-run.

VERDICT: FIX
1. General-path `len()`/indexing is now O(n) (5.65 s vs 0.001 s; 1.26 s vs 0.003 s) — cache the point count or keep a BMP fast path.
2. `f"{e:>3}"`/`.format` width uses units: expected `'  😀'`, actual `' 😀'`.
3. `expandtabs` uses units: expected `9 '😀       x'`, actual `8 '😀      x'`.
4. `"%c" % chr(0x1F600)` raises TypeError; expected `😀`.

## worker report 1
[model qoder/DeepSeek-Flash]
Done. Fixed all four defects and committed as `579526b`.

**Fixes**
1. **O(1) `len()`/index restored**: `ail_strback.hdr.aux` now records "backing holds a high surrogate". Backings without one take the direct length/offset path; all pair writers mark it (`chr`, UTF-8 decoder, `ail_str_to_view`, every `ail_str_buf_done`, flattened concat).
2. **Format width/precision** count code points in `ail_obj_format` (f-strings, `.format`) and `ail2f_format`/`ail2f_pad_str` (`format()`, `%s`, `%c`).
3. **`expandtabs`** advances one column per code point and copies a pair whole.
4. **`%c`** accepts a one-code-point str; `%c` with an astral int now also works.

**Probes (cmp.sh, both builds)** — all match CPython: `p_fmtwidth`, `p_expandtabs`, `p_percent`, `p_bmp_len`, `p_perf_len`, `p_perf_index`; `p_stdin_astral` (astral `sys.stdin.read()`, len 1, both builds, manual pipe); regressions re-run clean: `containers`, `methods`, `boundaries`, `iteration`, `bmp`, `errors`, `types`, `r4`, `chrdirect`. Perf: `len` 5.65 s → 0.00 s, `s[i]` loop 1.26 s → 0.00 s with identical output. Pre-existing unchanged: `r9` dies both builds, `r10` general dies/default matches, non-BMP literal refused by name on the general path.

**Tests on final commit**: `test_ail_pre139` 2 ok; `test_ail_safetynet` 5 ok; `test_ail_files` 18 ok (1 skipped); `test_ail_corpus_findings3` 2 ok; `update_manifest.py --check` exit 0. DEVLOG and DIFFERENCES updated; working tree clean apart from the pre-existing untracked `.agent/pipeline.md`.

## review 1
[model qoder/DeepSeek-Flash]
All checks are complete. Here is my review report.

## What the change really does
It enables non-BMP code points on the 16-bit v2 runtime by storing them as UTF-16 surrogate pairs, adds an `aux` "backing has a high surrogate" flag so pair-free backings keep O(1) `len`/index, and makes ~20 string operations point-aware (write/repr/index/slice/iterate/reverse/compare/find/rfind/count/startswith/endswith/pad/replace/format width+precision/expandtabs/%c/stdin UTF-8 decode). It adds `test_ail_pre139.py` and docs. This is much broader than the task's "fix one cause", but the target r4 is fixed.

## Probes (cmp.sh, both builds)
- `p1_r4` (arg/list/dict/attr/local), `p2_slice`, `p3_methods`, `p4_format`, `p5_repr_cmp`, `p6a_case`, `p6b_encode`, `p7_bmp`, `p8_repr_edge`, `p9_misc`, `p10`–`p15`: general and default match CPython. r4 itself is fixed (base: both builds die with "chr() non-BMP…"; HEAD: prints the character).
- `p19_lit`: non-BMP literal refused by name on the general path; default matches — claim verified.
- `v3`/`v4` (repr of astral + a tuple in the program): see Pre-existing.
- `p17_sliceonly` / `p16_perf`: regression, below.
- Tests on HEAD: `test_ail_pre139` ok 13.2s, `test_ail_safetynet` ok 127.2s, `update_manifest.py --check` exit 0.

## Defects
1. **General path: slicing / startswith / endswith / ljust / rjust / center / zfill became O(n) for every string, including pair-free BMP backings.** `ail_str_getslice` calls `ail_s2_npoints(s)` unconditionally (cruntime.py:13001-13004) and `ail_s2_unit_at` twice even for `step == 1`, where the base returned a view in O(1); `ail_meth_str_startswith/endswith/find/rfind/count` (18209-18290) and `ljust/rjust/center/zfill` (18388-18437) likewise count points before the fast path. `len`/index got the `aux` guard, these were missed.
   - `p17_sliceonly.py`: `s = "abcdefghij"*20000; for i in range(5000): t += len(s[0:5])`. Expected (base): 0.00 s, O(1) per slice. Actual (HEAD general): **1.05 s**.
   - `p16_perf.py`: 5000 slices + 20000 `startswith("abc")` + 20000 `rjust(3)` on the same 200k string. Output identical to CPython, but expected (base general) 0.00 s; actual (HEAD general) **14.02 s** (default build 4.12 s both trees). A program that uses none of the new feature now pays O(n) per call.
   - Fix: in these functions take the same `if (!((ail_gcobj *)backing)->aux)` branch `ail_str_index`/`ail_op_len` use (`s.n` / `i` directly).

## Pre-existing (does not block)
- **repr of non-printable astral chars is wrong when the program pulls in the tuplegen prelude** (`print((s,))` etc.): `repr(chr(0x10FFFF))` and `repr(chr(0x1FFFF))` print the raw character instead of `'\U0010ffff'` / `'\U0001ffff'` (`v4.py`, both builds on HEAD). The runtime C `ail_str_repr` is correct; the untouched Python prelude `_ail_unprintable` in `tuplegen.py` lacks the noncharacter ranges. Identical output on the base default build (`v4` base: `d DIFF`, same wrong lines), so it pre-exists; the general path merely exposes it. The report's "repr sees one code point" claim is therefore false for that path.
- `format(x, 'c')` for a non-BMP int still dies (safetyrt.py, untouched line); not probed.

## Claim check
O(1) len/index (p18: 0.00 s both trees) — verified; width/precision, expandtabs, `%c`, `%s` — verified (p4); probe list — my equivalents match except the repr case above; r9/r10 unchanged — unverified; `test_ail_files` / `test_ail_corpus_findings3` — unverified (not run, per reviewer scope); manifest check — verified.

VERDICT: FIX
1. General-path O(n) regression in `ail_str_getslice` (step 1 and step ≠ 1), `ail_meth_str_startswith/endswith/find/rfind/count` and `ljust/rjust/center/zfill` for pair-free backings. Probe `p17_sliceonly.py`: expected 0.00 s (base, O(1) slice) vs actual 1.05 s; probe `p16_perf.py`: expected 0.00 s vs actual 14.02 s (identical output). Use the `aux` fast path these functions are currently missing.

FINAL VERDICT: FIX  2026-10-24T17:16:55Z
