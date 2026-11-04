# `ail_bindgen.py` on real system headers

The question this directory measures: for a real library, what share of its exported functions does
`AIL_CURRENT/ail_bindgen.py`, run on the library's own installed header, turn into an `@extern` stub
that the compiler accepts?

Two libraries:

| library | header | denominator |
|---|---|---|
| zlib | `/usr/include/zlib.h` | the `T` symbols of `libz.so.1` (`nm -D --defined-only`) that the preprocessed header declares |
| libm | `/usr/include/math.h` | the `math.h` functions with only `double` parameters and a `double` result, kept only when `nm -D` shows the name in `libm.so.6` |

The denominator is read from `cc -E` output, so a name that only appears in a comment, or behind a
macro the default preprocessor does not define, is not counted. That leaves 81 of libz's 88 `T`
symbols: the seven `*64` variants (`gzopen64`, `gzseek64`, ...) are declared only under
`_LARGEFILE64_SOURCE`, which neither the generator nor the adapter's `#include <zlib.h>` defines.
libm's denominator is all 52 double functions that `math.h` declares.

`measure.py` runs `ail_bindgen.py` on the header and compiles each stub it wrote in a small program
of its own. Accepted means `python3 -B AIL_CURRENT/ail_chatgpt.py compile` exits 0: the adapter C
file that `ail_ffi_lower.py` builds includes the header and checks every declaration with
`_Static_assert(_Generic(&symbol, RET (*)(PARAMS): 1, default: 0), ...)`, so a stub with the wrong
prototype does not build. The check runs for every declaration in the module, so one stub per program
is what makes a failure a statement about one stub; groups are tried together and bisected on
failure, which keeps the build count low when most pass.

```
python3 examples/ffi/bindgen/measure.py          # the default parser
python3 examples/ffi/bindgen/measure.py --cpp    # preprocess the header first
```

## Before

The default parser at commit `83767b0` (`strip_source` drops every preprocessor line); the current
default path (no `--cpp`) prints the same table, byte for byte — every new parsing rule below is
gated on `--cpp`:

| library | denominator | emitted | accepted | share |
|---|---|---|---|---|
| zlib | 81 | 3 | 3 | 3.7% |
| libm | 52 | 0 | 0 | 0.0% |

Skip reasons, largest first:

```
zlib: 93 skip reasons
  skipped   93  unknown or struct result type '...'
  skipped    1  variadic
libm: 6 skip reasons
  skipped    5  unknown or struct-by-value type '...' (use --typedef NAME=c_type)
  skipped    1  unknown or struct result type '...'
```

zlib declares its functions through `ZEXTERN`, `ZEXPORT` and `OF(...)`, so the parser reads the
whole macro name as the result type and skips the function; the three that survive
(`zlibVersion`, `zError`, `get_crc_table`) survive only because a pointer result falls back to
`c_void_p` with `trust=True`. `math.h` declares its functions through `__MATHCALL`, so the parser
sees no prototype at all.

## After

`measure.py --cpp`, with `--cpp` (preprocess the header, resolve typedefs, strip attributes with
balanced parentheses):

| library | denominator | emitted | accepted | share |
|---|---|---|---|---|
| zlib | 81 | 75 | 75 | 92.6% |
| libm | 52 | 44 | 44 | 84.6% |

Skip reasons, largest first:

```
zlib: 6 skip reasons
  skipped    2  unknown or struct-by-value type '...' (use --typedef NAME=c_type)
  skipped    2  the buffer length is size * nitems, not len(buf), which length() cannot express
  skipped    1  variadic
  skipped    1  a str result together with a bytearray parameter is refused by ail_ffi
libm: 333 skip reasons, 68 stubs written outside the denominator (the float and long double variants)
  skipped  232  a name reserved for the C implementation
  skipped   52  unknown or struct result type '...'        (long double)
  skipped   42  the header does not declare it under -std=c11, the mode the prototype check is compiled in
  skipped    7  unknown or struct-by-value type '...' (use --typedef NAME=c_type)
```

What changed:

- `--cpp` runs `$PIPE_CC` (or `cc`) with `-E` and the `-I`/`-D` options it was given, keeps the
  lines attributed to the target header and to the headers it includes directly (the `# N "file"`
  markers say which; `math.h` expands `__MATHCALL` inside `bits/mathcalls.h`), and parses those.
  Headers reached through those (the whole of `sys/types.h` behind `zconf.h`) are dropped, which
  keeps other libraries' prototypes out.
- `typedef` statements are resolved: `uLong`, `uInt`, `Bytef`, `z_size_t`, `z_off_t`, `voidpf` and
  `gzFile` read as the type they name, including typedef-of-typedef and pointer typedefs.
- attributes are stripped with balanced parentheses (`__attribute__ ((__const__))` used to leave a
  stray `)` behind, which silently lost `ceil`, `fabs`, `floor`, `round`, `trunc`, `fmax`, `fmin`
  and `copysign`); `__restrict`, `__extension__`, `_Nonnull` and the bare glibc `__THROW` family are
  qualifiers.
- a name reserved for the implementation (`__acos`, `__roundf`, ...) is skipped: those are not the
  library's exported symbols.
- a declaration the header does not make under `-std=c11` is skipped by name: the FFI adapter is
  compiled with `-std=c11` (`c_object.py`), so a stub for it cannot pass the check (Finding 1).

What is still missing, exactly:

- zlib: `gzprintf` (variadic), `gzvprintf` (variadic, `va_list`), `inflateBack` (takes the `in_func`
  callback typedef); `gzerror` is refused by `ail_ffi` because it returns a `str` and takes a
  `bytearray` output parameter (Finding 2); `gzfread` and `gzfwrite` are skipped because the C byte
  count is `size * nitems`, which `length("buf")` cannot express — binding `size` to `len(buf)`
  passed an 8-byte buffer with `nitems=4` as 32 bytes, and the compiled `gzfread` stub aborted with
  `double free or corruption` (exit 134), so no stub is written for either. 75 of 81 is the whole rest.
- libm: `drem`, `gamma`, `j0`, `j1`, `scalb`, `significand`, `y0`, `y1` are the eight double
  functions `math.h` declares only under `__USE_MISC`, which a `-std=c11` compile does not reach
  (Finding 1). Against the 44 double functions the check can see, the share is 100%.

## The examples

```
zlib_gen.py  imports zlib_gen_ffi.py, written by
             python3 AIL_CURRENT/ail_bindgen.py /usr/include/zlib.h --cpp --header-name zlib.h --link z -o examples/ffi/bindgen/zlib_gen_ffi.py
libm_gen.py  imports math_gen_ffi.py, written by
             python3 AIL_CURRENT/ail_bindgen.py /usr/include/math.h --cpp --header-name math.h --link m -o examples/ffi/bindgen/math_gen_ffi.py
```

Both modules are committed with that command in their first line; nothing in them is hand-written.
The programs call only generated stubs, and `AIL_CURRENT/test_ail_bindgen_headers.py` runs each under
`python3` and as the compiled program and requires the same stdout and exit status. `zlib_gen.py`
prints `zlibVersion().split(".")[0]`, so the output does not move with the patch level.

## Findings

### 1. `ail_ffi_lower.py` defines `_DEFAULT_SOURCE` after its preamble, so `-std=c11` hides glibc's `__USE_MISC` declarations

`Session.build()` writes `#ifndef _DEFAULT_SOURCE / #define _DEFAULT_SOURCE 1 / #endif` and then the
includes (`ail_ffi_lower.py`, the `code = [...]` list), but `c_object.py` prepends its own preamble
(`#include <stdint.h>` first) to that source, and the adapter is compiled with `-std=c11`. Under
`-std=c11` glibc defines `__STRICT_ANSI__` and does not set `_DEFAULT_SOURCE`; by the time the
adapter defines it, `features.h` has already been read, so `__USE_MISC` stays off. Reproducer:

```
$ printf '#include <stdint.h>\n#define _DEFAULT_SOURCE 1\n#include <math.h>\n_Static_assert(_Generic(&j0, double (*)(double): 1, default: 0), "j0");\n' > repro.c
$ cc -std=c11 -c repro.c -o /dev/null
repro.c:4:26: error: 'j0' undeclared here (not in a function)
$ printf '#define _DEFAULT_SOURCE 1\n#include <stdint.h>\n#include <math.h>\n_Static_assert(_Generic(&j0, double (*)(double): 1, default: 0), "j0");\n' > ok.c
$ cc -std=c11 -c ok.c -o /dev/null        # no error
```

The effect on this page: `j0`, `j1`, `y0`, `y1`, `drem`, `scalb`, `significand` and `gamma` are
exported by `libm.so.6` and declared by `math.h`, but no `@extern(header="math.h")` stub for them can
pass the prototype check. Not fixed here (this lane does not edit `ail_ffi_lower.py`).

### 2. `ail_ffi` refuses a `str` result together with a `bytearray` parameter

`gzerror(gzFile, int *)` returns `const char *` and writes through `int *errnum`, which `@extern`
spells `ptr(c_int)`, a `bytearray` parameter. `ail_ffi_lower.py` refuses the pair:

```
$ printf 'from ail_ffi import *\n\nlink("z")\n\n@extern(header="zlib.h", trust=True)\ndef gzerror(file: c_void_p, errnum: ptr(c_int)) -> c_char_p: ...\n\ndef main():\n    print(gzerror(0, bytearray(4)))\n\n\nmain()\n' > repro_ffi.py
$ python3 -B AIL_CURRENT/ail_chatgpt.py compile repro_ffi.py -o /tmp/repro_ffi.out
repro_ffi.py:6:1: gzerror: a str result together with a bytearray parameter is not supported
```

`ail_bindgen.py` now skips such a declaration by name instead of writing a stub that cannot build.
Not fixed here.
