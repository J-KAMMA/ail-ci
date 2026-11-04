# `ail_bindgen.py` on real system headers

The question this directory measures: for a real library, what share of its exported functions does
`AIL_CURRENT/ail_bindgen.py`, run on the library's own installed header, turn into an `@extern` stub
that the compiler accepts?

Two libraries:

| library | header | denominator |
|---|---|---|
| zlib | `/usr/include/zlib.h` | the `T` symbols of `libz.so.1` (`nm -D --defined-only`) whose name also appears in `zlib.h` |
| libm | `/usr/include/math.h` | the `math.h` functions with only `double` parameters and a `double` result, kept only when `nm -D` shows the name in `libm.so.6` |

`measure.py` finds the denominator with a regex over `cc -E` output, runs `ail_bindgen.py` on the
header, and then compiles each stub it wrote in a small program of its own. Accepted means
`python3 -B AIL_CURRENT/ail_chatgpt.py compile` exits 0: the adapter C file that `ail_ffi_lower.py`
builds includes the header and checks every declaration with
`_Static_assert(_Generic(&symbol, RET (*)(PARAMS): 1, default: 0), ...)`, so a stub with the wrong
prototype does not build. The check runs for every declaration in the module, so one stub per program
is what makes a failure a statement about one stub; groups are tried together and bisected on
failure, which keeps the build count low when most pass.

```
python3 examples/ffi/bindgen/measure.py          # the default parser
python3 examples/ffi/bindgen/measure.py --cpp    # preprocess the header first (from step 2 on)
```

## Before

The default parser (`strip_source` drops every preprocessor line), commit `83767b0`:

| library | denominator | emitted | accepted | share |
|---|---|---|---|---|
| zlib | 88 | 3 | 3 | 3.4% |
| libm | 52 | 0 | 0 | 0.0% |

Skip reasons, largest first:

```
zlib: 0 stubs outside the denominator
  skipped   93  unknown or struct result type '...'
  skipped    2  unknown or struct-by-value type '...' (use --typedef NAME=c_type)
  skipped    1  variadic
libm: 0 stubs outside the denominator (float/long double variants of math.h)
  skipped    5  unknown or struct-by-value type '...' (use --typedef NAME=c_type)
  skipped    1  unknown or struct result type '...'
```

zlib declares its functions through `ZEXTERN`, `ZEXPORT` and `OF(...)`, so the parser reads the
whole macro name as the result type and skips the function; the three that survive
(`zlibVersion`, `zError`, `get_crc_table`) survive only because a pointer result falls back to
`c_void_p` with `trust=True`. `math.h` declares its functions through `__MATHCALL`, so the parser
sees no prototype at all.

## After

(filled in by step 4)

## Findings

(filled in as they are found)
