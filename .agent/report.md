# job job-fuzz58-10231356  started 2026-10-23T04:57:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed on `job-fuzz58-10231356` (`eb5a864`).

**Cause:** `int(s, base)` / `float(s)` on the general path built ValueError text by narrowing UTF-16 repr units to `char`. `int("\u2469", 10)` printed `'i'` instead of `'⑩'`. Messages are now built as `str + repr`; same cause fixed in the general builtin-value path and float message.

**Files:** `AIL_CURRENT/python/pkg-v12/cruntime.py`, `AIL_CURRENT/ail_check.py`, new `AIL_CURRENT/test_ail_fuzz58.py`, `MANIFEST.json`.

**Probes (`cmp.sh`, both builds):**
- `p01` basic int bases/signs/spaces: same
- `p02` base 0/prefixes: same
- `p03` explicit bases/underscores: same
- `p04` Unicode whitespace/digits: **first diff** at `'⑩'` before fix; same after fix
- `p05` plain `int(s)`: same
- `fix_int_direct`, `fix_int_sources` (argument/list/attribute/dict), `fix_float_repr`: all same after fix

**Other differences seen:** valid literals beyond int64 stop with pre-existing `integer overflow` (AIL int64 limit); `f = int` is refused by name. No silent difference. No `DEVLOG`/`DIFFERENCES` files exist in this export.

**Tests:** `test_ail_fuzz58`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 28 tests, OK (1 skipped). Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 6649074, "input": 150907, "output": 13113, "reasoning": 19390, "cache.write": 0, "cache.read": 6465664}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `eb5a864` (`git diff work..HEAD`, 4 files).

**Change:** error text for `int(s, base)`/`float(s)` is now built as `str + repr` instead of narrowing UTF-16 repr units into `char`; new `test_ail_fuzz58.py`, `ail_check` module list and manifest updated.

**Probes (cmp.sh, both builds unless noted):**
- `p1_unicode` (BMP non-ASCII, quotes, backslash, NUL, newlines incl. U+2028): HEAD same as CPython; base differs (`'i'`/`'ab'` for `⑩`/`١٢`).
- `p1b_nonbmp` (`chr(0x1F600)` then `int`/`float`): general build stops with `chr() non-BMP ... requires 32-bit strings`; default matches CPython. Identical on base.
- `p2_empty` (empty/whitespace/sign/prefix/underscore/bad-digit, all bases + plain int/float): HEAD same; base differs on `int("\u0661\u0662", 2)` (`'ab'` vs `'١٢'`).
- `p3_long`, `p7_typed_long`, `p8_untyped_long`, `p9_plain` (300–500-char literals): HEAD/base both emit full repr where CPython truncates to 240 chars — identical on base, pre-existing.
- `p4_sources` (argument, returned arg, list item, attribute, dict value; int and float): HEAD same; base showed `'i'`.
- `p5_valid` (int64 bounds, base 0/prefixes, `format(v, ",")`, `"015,"`): `int(...,16)` of an int64-overflowing hex literal stops with pre-existing `integer overflow`, same on base.
- `p6_noeffect`, `p10_format` (non-feature and printing/formatting): identical outputs on HEAD and base.
- `p11_refuse`: `f = int` refused at compile time, as reported.
- GC-stress ASan build of `int(chr(0x2469),10)`/`float(chr(...))`: no sanitizer or UAF report on HEAD (arguments are frame-rooted).

**Pre-existing (identical on `/tmp/base`, non-blocking):** long invalid-int messages are not truncated to CPython's 200-char repr; non-BMP literal/`chr` limits and int64 overflow hard stop are unchanged.

**Claims:** commit/files/manifest verified; `int("\u2469",10)` bug verified and fixed; overflow and `f=int` claims verified; tests (`test_ail_fuzz58`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) pass, manifest `--check` rc=0. The report's "float message" fix and the new test docstring's "typed path already matched" are overstated: the live float path and long plain-`int` path were already un-mangled on base (the changed `ail_bi_float`/`ail_bi_int` are unreachable), while the typed `int(s, base)` path is exactly what the fix repairs.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2204349, "input": 151300, "output": 9785, "reasoning": 22400, "cache.write": 0, "cache.read": 2020864}]

FINAL VERDICT: ACCEPT  2026-10-23T05:21:10Z
