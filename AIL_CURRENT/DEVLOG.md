# DEVLOG

## 2026-10-24 - pre51 review: invalid-spec message built from code units

The reviewer found the new invalid-spec text was built as UTF-8 bytes in a C string and then
re-read by `ail_str_from_cstr`: non-ASCII specs were double-encoded (`8\xe2\x98\x83x` became `8\xc3\xa2\xc2\x98\xc2\x83x`) and an embedded NUL truncated the message. `ail2f_bad_spec` now
copies the spec into the 16-bit string buffer as code units (through `ail_str_buf1`, which roots
the spec object), so non-ASCII, surrogate pairs and an embedded NUL survive verbatim. Extended
`test_ail_pre51.py` with non-ASCII and NUL invalid specs for int/str/float and through an
argument, list item, attribute and dict value. Probes match CPython on both builds. The separate
single-NUL format-code difference (`format(1, '\x00')`) is still open on both builds.

## 2026-10-24 - pre51: format spec errors and the float z flag

Reproducing the first pre-existing difference from pre29 found that the float `z` flag already
matched CPython on both builds, but three format-spec diagnostics did not. A space sign on a str
said "Sign not allowed..." where CPython says "Space not allowed..."; an invalid spec said only
"Invalid format specifier" instead of naming the spec and value type; and an unknown format code
printed the raw code point rather than CPython's `\xNN`. The general path's spec parser now keeps
the whole spec, decodes a surrogate pair as one code point, and lets the caller add the value's
type; unknown codes use CPython's escaping (control/space and non-ASCII as `\xHEX`). Valid `z`
forms, widths, precision and empty specs are unchanged. Added `test_ail_pre51.py` (two programs,
both builds). The separate NUL code-point difference (`format(1, '\x00')`) is still open.

## 2026-10-23 -- fuzz37: ordering TypeError names the written operator

Fuzzing while loops and counters against CPython on both builds found that an
ordering comparison between built-in values that cannot be ordered raised
`TypeError '<' not supported ...` for every operator.  `while s > 0` with
`s = "5"` printed `'<'` where CPython prints `'>'`, and `<=`, `>`, `>=` and
chained comparisons had the same wrong symbol.  The general-path comparison
helper now receives the operator symbol from `ail_op_lt/le/gt/ge`, passes it
through nested list/tuple comparisons, and uses it in the message; callers such
as sorting keep `<`.  Both builds now match CPython.  `test_ail_fuzz37.py`
keeps the probe.  Also seen but not changed: the general build refuses an
integer literal outside int64 range that the default build accepts, and
`sorted([1, "x"])` names the operand types in the opposite order from CPython
(`'int' and 'str'` instead of `'str' and 'int'`); both are pre-existing.
