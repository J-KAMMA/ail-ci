# Calling C from AIL: a quick guide

`docs/FFI.md` shows four finished programs against real libraries. This page is the path to get there: eight
numbered steps from a C function you can see to a compiled AIL program that calls it. Every program here is a
file in `examples/ffi_quick/`, each code block is that file byte for byte, and every command and output was run
by `AIL_CURRENT/test_ail_docs_ffi_quick.py`.

You need a C compiler (`cc`), `python3`, and libm. Nothing else is installed or generated except where a step
says so.

The shape is always the same: import the FFI names, write one `@extern` stub whose annotations are the C
prototype, call it. `python3 program.py` runs the stub through `ctypes`; `ail_chatgpt.py compile program.py`
builds a native executable that calls C directly. Both print the same bytes.

## Step 1 — Call `sqrt` from libm

The smallest program: one declaration, one call. `link("m")` is `-lm` when compiled and `libm` under `ctypes`.

<!-- ffi-quick: program examples/ffi_quick/step1_sqrt.py -->
```python
from ail_ffi import *

link("m")

@extern(header="math.h", symbol="sqrt")
def c_sqrt(x: c_double) -> c_double: ...


print(c_sqrt(9.0))
print(c_sqrt(2.0))
```

Build it, then run it:

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step1_sqrt.py -o step1_sqrt.out >/dev/null
./step1_sqrt.out
```

<!-- ffi-quick: output -->
```text
3.0
1.4142135623730951
```

`python3 examples/ffi_quick/step1_sqrt.py` (with `PYTHONPATH=AIL_CURRENT`) prints the same two lines.

## Step 2 — Call a C function you wrote

Two files of your own: the header carries the prototype the compiler checks against, and `sources=["add.c"]`
compiles the C into both the shared library `ctypes` loads and the native executable.

<!-- ffi-quick: file examples/ffi_quick/add.h -->
```c
#ifndef AIL_QUICK_ADD_H
#define AIL_QUICK_ADD_H

#include <stddef.h>
#include <stdint.h>

int64_t ail_quick_add(int64_t a, int64_t b);
int32_t ail_quick_add32(int32_t a, int32_t b);
double ail_quick_average(double a, double b);
size_t ail_quick_strlen(const char *text);
void ail_quick_reverse(const unsigned char *src, size_t n, unsigned char *dst);
int64_t ail_quick_parse(const char *text);

#endif
```

<!-- ffi-quick: file examples/ffi_quick/add.c -->
```c
#include "add.h"

#include <errno.h>

int64_t ail_quick_add(int64_t a, int64_t b)
{
    return a + b;
}

int32_t ail_quick_add32(int32_t a, int32_t b)
{
    return a + b;
}

double ail_quick_average(double a, double b)
{
    return (a + b) / 2.0;
}

size_t ail_quick_strlen(const char *text)
{
    size_t n = 0;
    while (text[n] != '\0')
        n++;
    return n;
}

void ail_quick_reverse(const unsigned char *src, size_t n, unsigned char *dst)
{
    size_t i;
    for (i = 0; i < n; i++)
        dst[i] = src[n - 1 - i];
}

int64_t ail_quick_parse(const char *text)
{
    int64_t value = 0;
    size_t i;

    if (text[0] == '\0') {
        errno = EINVAL;
        return -1;
    }
    for (i = 0; text[i] != '\0'; i++) {
        if (text[i] < '0' || text[i] > '9') {
            errno = EINVAL;
            return -1;
        }
        value = value * 10 + (text[i] - '0');
    }
    return value;
}
```

<!-- ffi-quick: program examples/ffi_quick/step2_add.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_add(a: c_int64, b: c_int64) -> c_int64: ...


print(ail_quick_add(2, 3))
print(ail_quick_add(-40, 2))
```

The exact build command, from the repository root:

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step2_add.py -o step2_add.out >/dev/null
./step2_add.out
```

<!-- ffi-quick: output -->
```text
5
-38
```

`sources=[...]` paths are relative to the file that declares the stub. One `-o` target gets both the C object
and the AIL program, so there is no separate `cc` line.

## Step 3 — Pass and return a `double`

`c_double` is both a parameter and a result type. The C function does the arithmetic; both builds call the same
machine code.

<!-- ffi-quick: program examples/ffi_quick/step3_double.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_average(a: c_double, b: c_double) -> c_double: ...


print(ail_quick_average(3.5, 4.25))
print(ail_quick_average(0.1, 0.2))
```

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step3_double.py -o step3_double.out >/dev/null
./step3_double.out
```

<!-- ffi-quick: output -->
```text
3.875
0.15000000000000002
```

## Step 4 — Pass a `str` and get its length back

`c_char_p` is a UTF-8, NUL-terminated copy made for the call; the C side sees an ordinary `const char *`. The
result is `c_size_t`, the C `size_t`.

<!-- ffi-quick: program examples/ffi_quick/step4_str.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_strlen(text: c_char_p) -> c_size_t: ...


print(ail_quick_strlen(""))
print(ail_quick_strlen("hello"))
print(ail_quick_strlen("héllo"))
```

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step4_str.py -o step4_str.out >/dev/null
./step4_str.out
```

<!-- ffi-quick: output -->
```text
0
5
6
```

`"héllo"` is six UTF-8 bytes even though it is five characters.

## Step 5 — Pass `bytes` and fill a buffer in C

`bytes` is a borrowed, read-only input. The output is a `bytearray`: C may write every byte of it, but the
length cannot change. The `n` parameter is not passed by the caller — `length("src", c_size_t)` binds it to
`len(src)`.

<!-- ffi-quick: program examples/ffi_quick/step5_bytes.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_reverse(src: bytes, n: length("src", c_size_t), dst: bytearray) -> None: ...


out = bytearray(5)
ail_quick_reverse(b"hello", out)
print(out.decode())
```

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step5_bytes.py -o step5_bytes.out >/dev/null
./step5_bytes.out
```

<!-- ffi-quick: output -->
```text
olleh
```

The compiled program copies the `bytearray` into C and back out around the call; the `bytes` argument is
borrowed and never copied.

## Step 6 — An int outside the C type's range

The annotation says how wide the C argument is. `c_int32` cannot hold `2147483648`, so the call is refused
before C runs — on the `ctypes` path and in the compiled program alike. Nothing is truncated.

<!-- ffi-quick: program examples/ffi_quick/step6_range.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_add32(a: c_int32, b: c_int32) -> c_int32: ...


print(ail_quick_add32(2147483647, 0))
try:
    ail_quick_add32(2147483648, 0)
except OverflowError as e:
    print(type(e).__name__)
```

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step6_range.py -o step6_range.out >/dev/null
./step6_range.out
```

<!-- ffi-quick: output -->
```text
2147483647
OverflowError
```

Only the exception's type is printed here because the exact message is an implementation detail; the type is
part of the contract.

## Step 7 — Turn a C error return into a Python exception

`check="negative"` says a negative result means failure. `errno=True` reads `errno` immediately after the call
and raises `OSError(errno, strerror)`. The C function returns `-1` and sets `EINVAL` for text that is not
decimal digits.

<!-- ffi-quick: program examples/ffi_quick/step7_error.py -->
```python
from ail_ffi import *

@extern(header="add.h", sources=["add.c"], check="negative", errno=True)
def ail_quick_parse(text: c_char_p) -> c_int64: ...


print(ail_quick_parse("1234"))
try:
    ail_quick_parse("12a4")
except OSError as e:
    print(type(e).__name__, e)
```

<!-- ffi-quick: command -->
```sh
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step7_error.py -o step7_error.out >/dev/null
./step7_error.out
```

<!-- ffi-quick: output -->
```text
1234
OSError [Errno 22] Invalid argument
```

`exc=ValueError` would make the same check raise `ValueError` instead; `check` also takes `"nonzero"`,
`"null"`, `"minus1"` and `"allones"`.

## Step 8 — Generate the declarations with bindgen

`AIL_CURRENT/ail_bindgen.py` reads a C header and writes the stubs. Build `add.c` as a shared library first so
the generated `lib=` names something that exists, then generate, then compile a program that imports the
generated module. This is the same generator `examples/ffi/bindgen/README.md` measures on `zlib.h` and
`math.h`.

<!-- ffi-quick: command -->
```sh
cc -shared -fPIC -I examples/ffi_quick -o examples/ffi_quick/libadd_quick.so examples/ffi_quick/add.c
python3 AIL_CURRENT/ail_bindgen.py examples/ffi_quick/add.h --cpp --header-name add.h --lib ./libadd_quick.so -o examples/ffi_quick/add_gen_ffi.py
PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/ail_chatgpt.py compile examples/ffi_quick/step8_bindgen.py -o step8_bindgen.out >/dev/null
./step8_bindgen.out
```

The generated module, committed so the program below has something to import:

<!-- ffi-quick: file examples/ffi_quick/add_gen_ffi.py -->
```python
# generated by AIL_CURRENT/ail_bindgen.py from add.h -- review before use
from ail_ffi import *

@extern(lib='./libadd_quick.so', header='add.h')
def ail_quick_add(a: c_int64, b: c_int64) -> c_int64: ...
@extern(lib='./libadd_quick.so', header='add.h')
def ail_quick_add32(a: c_int32, b: c_int32) -> c_int32: ...
@extern(lib='./libadd_quick.so', header='add.h')
def ail_quick_average(a: c_double, b: c_double) -> c_double: ...
@extern(lib='./libadd_quick.so', header='add.h')
def ail_quick_parse(text: c_char_p) -> c_int64: ...
# skipped ail_quick_strlen: unknown or struct result type 'long unsigned int'
# skipped ail_quick_reverse: unknown or struct-by-value type 'long unsigned int' (use --typedef NAME=c_type)
```

<!-- ffi-quick: program examples/ffi_quick/step8_bindgen.py -->
```python
from add_gen_ffi import *


print(ail_quick_add(20, 22))
```

<!-- ffi-quick: output -->
```text
42
```

The last two lines are the generator telling you what it did not write: `size_t` came out of the preprocessor
as `long unsigned int`, which it cannot map without `--typedef`. That is why the hand-written stubs in the
earlier steps spell `c_size_t` themselves. Check every generated stub before trusting it.

## What is not supported yet

The limits — annotations everywhere, no `bytes`/`bytearray` results, borrowed `bytes`, hand-laid-out structs,
callbacks, `errno` details, and the rest — are listed once, in
[`docs/FFI.md`](FFI.md#what-is-not-supported-yet). This page does not repeat them.
