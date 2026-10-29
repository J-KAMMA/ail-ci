# FFI stage 3: exact unsigned 64-bit values (design only, 2026-10-30)

Design note for step F3 of the modules/FFI plan. Nothing here is built yet. Oracle: CPython 3.12 running the same
file through the ctypes shim (`ail_ffi.py`), as for every other FFI step.

**Where the scope comes from.** F3 is defined in the owner-approved modules/FFI plan (the private design note
`ffi-modules.md`, section 3, 2026-10-28; owner decisions in its section 5). Its text, in short: map `uint64_bits`
results and `ptr(c_uint64)` reads to the exact-int path when big ints are on; remove the declared difference; turn
`test_uint64_above_int64_is_the_declared_difference` into a CPython-equality test (2**63, 2**64-1, `SIZE_MAX` from a C
source); leave the C of an int64 result unchanged; keep the old behaviour with big ints off and say so in the test;
measure the cost of one call in a loop with `tools/icount.c`. This note designs exactly that. It adds one thing the plan
did not name: the **argument** side, because reading the code shows a silent difference there today (section 2.2).
That addition is marked **[proposal]** wherever it appears.

Verification marks: **[verified 2026-10-30]** = read in the `integ` tree (d68453f7) or in the PR bodies while writing
this note; **[read, not run]** = follows from reading the code, no program was compiled or run (this task compiles
nothing); **[unverified]** = from memory or inference, to be checked in the step named.

The one rule, unchanged: **a program prints exactly what CPython prints, or it is refused at compile time by name**,
with file:line and a `write instead:` hint. A loud run-time stop (stderr, exit 1) is allowed only where A1 already
allows it for the typed path.

## 0. Words

- *u64 type*: any of `c_uint64`, `c_ulong`, `c_ulonglong`, `c_size_t` (64 bits, unsigned, on the LP64 targets AIL
  supports: Linux and macOS). `ail_ffi_lower.INTS` maps all four to the interface kind `uint64_bits`
  **[verified 2026-10-30]**.
- *bits*: the int64 that has the same 64 bits as the C value (`2**64 - 1` has bits `-1`).
- *exact*: the Python int CPython gives, `0 .. 2**64 - 1`.
- *typed path / general path / tagged lowering*: as in docs/design/BIGINT.md sections 4 and 10.

## 1. Scope

### 1.1 In

1. Results of u64 type: exact in every build that has exact ints (section 3.1).
2. Arguments of u64 type: range-checked like the shim, `OverflowError` with the shim's text, and a big int below
   2**64 accepted **[proposal]** (section 3.2).
3. `ptr(c_uint64)` / `cptr(c_uint64)` buffers read and written exactly: `get_u64` / `put_u64` in `ail_cbuf.py`
   (section 3.3).
4. `check=` on a u64 result: the rules that make `check` mean what it means under CPython (section 3.4).
5. Docs: the declared difference leaves `ail_ffi.py`, AIL_REFERENCE_MORE.md and the reference tests; the A63 row of
   docs/spec/DIFFERENCES.md is updated (it says `ptr(c_void_p)` handles are ints below 2**63; that stays).

### 1.2 Out (and where it goes)

- `@export` functions (C/Rust calling AIL) with u64 parameters or results. The export table has no u64 row today
  **[verified 2026-10-30, AIL_REFERENCE_MORE.md "Export"]**. Follow-up after F3, same conversions in the other direction.
- `uint64_bits` in the `compile-c` type JSON (`c_object.py`, LANGUAGE_QUICKSTART_JA.md section on `uint64_bits`). That
  is a different, documented interface: the signed mapping `-1-(UINT64_MAX-u)` is its contract. It stays as it is; F3
  adds a new kind beside it (section 3.1).
- Integers wider than 64 bits (`__int128`, `unsigned __int128`): not in `INTS`, refused by the stub reader today
  **[read, not run]**. Unchanged.
- Pointers as integers (`c_void_p`, `uintptr_t`): handles stay ints below 2**63 (A63). User-space addresses on x86-64
  and arm64 Linux/macOS are below 2**63 **[unverified per platform]**, so no exact path is needed. F4 (#209) wraps them.
- Structs, unions, buffers of structs: F5 (`@cstruct`). Rust crate builds: F6. Callbacks: F7 (#211). Externs in
  parallel code: F8 and #203 (merged: parallel bodies refuse `@extern` by name).
- Windows (LLP64: `c_ulong` is 32 bits there). AIL's FFI targets Linux and macOS; `INTS` hard-codes 64-bit
  `unsigned long` **[verified 2026-10-30]**. A Windows port must re-derive the table from `ctypes.sizeof`.

## 2. What happens today

### 2.1 Results (the declared difference)

`c_object.py` returns a u64 result as its bits: `result <= INT64_MAX ? (int64_t)result : -1 - (int64_t)(UINT64_MAX -
result)` **[verified 2026-10-30]**. The AIL wrapper returns that int. So `tiny_big()` (C returns `0x8000000000000001`)
prints `-9223372036854775807` where CPython prints `9223372036854775809`.
`test_ail_ffi.test_uint64_above_int64_is_the_declared_difference` pins exactly this **[verified 2026-10-30]**. The
difference is documented in the `ail_ffi.py` docstring, but it is still a different number on stdout.

Where it bites in real code: `(size_t)-1` is the error result of `iconv`, `mbstowcs`, `wcstombs`, `mbrtowc`; hashes
(FNV-1a, xxHash, SipHash) return `uint64_t` with the top bit set half the time; `strtoull`; file offsets and inode numbers
from Rust crates (`u64`).

### 2.2 Arguments (a silent difference found while writing this note) [proposal to fix in F3]

The shim checks every int argument against the C type's range and raises
`OverflowError("tiny_ul: x does not fit c_ulong")` for `-1` or `2**64` **[verified 2026-10-30, `ail_ffi.py` call path]**.
The compiled adapter casts a u64 argument with `(uint64_t)p` and has no check; the AIL wrapper adds none
**[read, not run]**. So `tiny_ul(-1)` raises under CPython and returns `0` (`(2**64 - 1) + 1` wraps) in the compiled
program. That is a silent difference, and it is not declared anywhere.

Two neighbours, found the same way:
- Narrow ints (`c_int`, `c_uint32`, ...) out of range stop with `ail_die("C int32 argument out of range")` in the
  compiled program and raise a catchable `OverflowError` with a different text in the shim **[read, not run]**. Loud,
  not silent, but stdout differs when the program catches it. F3a aligns these too, since it is the same code.
- A big int (general path, above 2**63 - 1) passed to any int parameter: what the boundary does with it is not known
  **[unverified; first thing F3a checks]**. If it truncates, that is a second silent hole.

### 2.3 Buffers

`ail_cbuf.py` has `get_u8 get_u16 get_i16 get_u32 get_i32 get_i64 get_f64` and the matching `put_*`, but no `get_u64` /
`put_u64` **[verified 2026-10-30]**. A user reads a `ptr(c_uint64)` out-parameter with `get_i64` (signed bits) or by
combining two `get_u32`. The second gives the exact value on the general path, and on the typed path it overflows into the
loud stop **[unverified]**.

### 2.4 Why the plan said "private only", and why that no longer holds

The plan (2026-10-28) put F3 on the private repo because exact ints lived only there. `integ` now carries the big-int
runtime: `python/pkg-v12/bigint_core.py`, `bigint_obj.py`, `bigcap.py`, `biggate.py`, `tint.py` and the A1 row that makes
ints exact on the general path **[verified 2026-10-30]**. F3 still touches compiler-core files (`c_object.py`, the
big-int gate, the tagged lowering), so by the standing rule it runs as **one sequential line**, not as parallel jobs.
Whether it may run on public workers is open question Q5.

## 3. Design

### 3.1 Results: a new interface kind `uint64`

`ail_ffi_lower.INTS` maps the four u64 annotations to a new interface kind `uint64` instead of `uint64_bits`.
`uint64_bits` stays for `compile-c` users (section 1.2). The C adapter is unchanged at the ABI level: the wrapper
function still returns the 64 bits in an `int64_t`, so the object format (ABI 11) and the build cache key format do not
change **[unverified: the cache key may include the interface JSON, which changes for u64 stubs only; that is wanted]**.

What changes is the conversion on the AIL side of the call, one per build kind:

| build of the calling function | value `0 .. 2**63-1` | value `2**63 .. 2**64-1` |
| --- | --- | --- |
| general path (boxed) | small int, as today | big int, built by a cold `ail_int_from_u64(uint64_t)` over `ail_big_from_limbs` (2 limbs, sign +1) |
| tagged lowering (default build, IR) | small tagged int | big tagged int, the same cold call; like `int(text)`, a source of an unproven int (BIGINT.md section 10) |
| legacy int64 emitter (`AIL_NO_GENERAL=1`, `_tint_legacy` retry) | int64, as today | loud stop: `integer overflow` on stderr, stdout flushed, exit 1 (A1); no `except` runs |
| AIL-syntax program (brace surface) | int64 | `OverflowError("C uint64 result does not fit int")`, catchable, as A1 says for that surface **[proposal: text to be fixed in F3b]** |
| `AIL_BIGINT=off` | int64 | the old bits (negative), as the plan says; the test names it as the declared behaviour of that switch (see Q1) |

The hot part is one compare on the result (`bits < 0`, i.e. top bit set) and a branch to a cold, `noinline` function. An
int64-typed result (`c_int64`, `c_long`, `c_ssize_t`) keeps its C byte for byte: it never goes through the new kind.

Why not do it in the AIL wrapper (`return ffi_rc if ffi_rc >= 0 else ffi_rc + 2**64`)? It needs no core change, but the
literal `2**64` marks the wrapper big-int capable, and marking is transitive (BIGINT.md section 5): every caller of a
`crc32` stub would lose its typed clone. The cost of that is not measured **[unverified]**. F3b measures both forms on one
program before choosing; the table above is the expected winner, not a measured one.

**Gate and size.** `biggate.py` links the big-int runtime only when a creator is reachable. A u64 stub becomes a creator
(like `int.from_bytes`), so a program with a u64 stub may link big-int pieces it did not link before: `from_limbs`, and
`text` if it prints the value. BIGINT.md section 9 sets a 25 KB budget for a general binary that gains the runtime; F3b
holds that budget and reports the measured delta for `crc32` (zlib, `c_ulong`) and `strlen` (`c_size_t`). A program with no
u64 stub is byte-identical.

### 3.2 Arguments: the shim's check, in the compiled program [proposal]

A u64 parameter accepts exactly what the shim accepts: an `int` with `0 <= v <= 2**64 - 1`.
- Typed path: the value is an int64; `v < 0` raises `OverflowError("NAME: PARAM does not fit TYPE")`, the shim's text
  (`ail_ffi.py`, `'%s: %s does not fit %s' % (function.__name__, name, kind)`). The check is in the AIL wrapper, which can
  already raise (it raises the `check=` exception today), so the exception is catchable on both sides.
- General path / tagged lowering: a big value is accepted when it is below 2**64 and converted by a cold
  `ail_int_to_u64`; a bigger one, or a negative one, raises the same `OverflowError`.
- The same `OverflowError` replaces `ail_die("C ... argument out of range")` for every narrow int kind, so all int
  parameters behave like the shim. The message names the stub and parameter, not the C kind.
- `bool` passed to an int parameter: the shim requires `type(value) is int` and raises `TypeError` for `True`
  **[verified 2026-10-30]**. The compiled program's handling is not known **[unverified]**; F3a adds a case and refuses
  by name at compile time where the argument is statically a `bool`.

### 3.3 Buffers: `get_u64` and `put_u64`

`ail_cbuf.py` gains `get_u64(b, at) -> int` and `put_u64(b, at, v)`, written in AIL like the others (the library policy:
small spec helpers in AIL). `get_u64` is `int.from_bytes(b[at:at + 8], "little")`, which is already a big-int creator and
marks its callers, the same price every `int.from_bytes` user pays today. `put_u64` raises the same `OverflowError` text as
`struct.pack('<Q', v)` for a value outside `0 .. 2**64 - 1` **[unverified: exact text to be taken from CPython in F3c]**.
Element reads of `ptr(c_uint64)` parameters go through these; no new annotation. Little-endian only, as the existing
helpers (both targets are little-endian).

### 3.4 `check=` on a u64 result

Under CPython a u64 result is never negative, so `check="negative"` and `check="minus1"` never fire. In the compiled
program today they fire on the bits (`(size_t)-1` is `-1`) **[read, not run]**. After F3b the compiled program agrees
with CPython (never fires), so such a check is dead code that looks alive. Proposal: refuse it by name.

    prog.py:12: check="minus1" on a c_size_t result never fires: the result is unsigned
    write instead: check="allones" (the C value (size_t)-1, CPython's 18446744073709551615)

`check="allones"` is new: the result equals `2**(8*sizeof) - 1` for its type. The shim implements it too, so the file
still runs the same under CPython. Whether to add it is Q2; without it, the refusal says `write instead: compare the
result with 18446744073709551615 yourself`.

### 3.5 User-visible syntax

No new annotation and no new decorator option, except `check="allones"` if Q2 says yes. A program changes behaviour only
where it printed a different number than CPython before. `get_u64` / `put_u64` are new names in `ail_cbuf.py`.

    from ail_ffi import extern, link, c_size_t, c_uint64, c_char_p
    link("./libhash.so")

    @extern(header="hash.h")
    def fnv1a64(data: bytes, n: length("data", c_size_t), seed: c_uint64) -> c_uint64: ...

    h = fnv1a64(b"hello", 14695981039346656037)   # seed above 2**63: accepted, as CPython does
    print(h, hex(h), h % 1000)                    # exact, as CPython

## 4. Type mapping across the boundary after F3

Only the integer rows change. The others are listed so the table is complete; they are today's rules
(`ail_ffi.py` docstring, AIL_REFERENCE_MORE.md) **[verified 2026-10-30]**.

| annotation | C | AIL/Python value, argument | result | changed by F3 |
| --- | --- | --- | --- | --- |
| `c_int8 .. c_int64`, `c_short c_int c_long c_longlong c_ssize_t` | signed | int in range, else `OverflowError` (shim text) | exact (fits int64) | argument error becomes `OverflowError` (was a stop) [proposal] |
| `c_uint8 .. c_uint32`, `c_ushort c_uint` | unsigned | int in range, else `OverflowError` | exact | as above |
| `c_uint64 c_ulong c_ulonglong c_size_t` | `uint64_t` etc. | `0 .. 2**64-1`, big ints accepted | exact, big above 2**63-1 | **yes** |
| `length("buf", T)` | T | supplied by the call | — | unchanged; `len()` fits int64 |
| `c_double` / `c_float` | double / float | int or float | float (`c_float` widened) | no |
| `c_bool` | `_Bool` | bool only | bool | no |
| `bytes` / `c_const_void_p` | `const unsigned char *` / `const void *` | borrowed for the call | — | no |
| `bytearray` / `c_mut_void_p` | `unsigned char *` / `void *` | copied in and out (declared difference) | — | no |
| `c_char_p` | `const char *` | UTF-8 copy, embedded NUL is an error | copied, decoded as UTF-8, NULL is `""` | no |
| `ptr(T)` / `cptr(T)` | `T *` / `const T *` | bytearray / bytes, whole number of T | — | `get_u64`/`put_u64` added |
| `c_void_p` | `void *` | int (0 is NULL), program owns it | int below 2**63 | no (F4 adds `Handle`) |
| `None` | `void` | — | `None` | no |
| lists, structs by value | — | refused by name | refused | no (structs: F5) |

Ownership and lifetime do not change: an int result owns nothing, and the cold big-int call allocates a GC object like any
other big int.

## 5. Errors and exceptions across the boundary

- F3 adds no foreign code that raises. The owner's rule (an exception raised in foreign code is re-raised on the AIL side)
  is F7's (#211); F3 only needs that a u64 argument or result inside a callback uses the same two conversions (section 8).
- The only new exception is `OverflowError` for an argument out of range, raised in the AIL wrapper before C is called.
  Nothing is half-done: no bytearray has been copied in, and errno is untouched.
- Results never raise on the general path or under the tagged lowering. The legacy int64 emitter stops loudly (A1).

## 6. Zero silent differences: what holds, what is refused

After F3 every u64 value prints as CPython prints it, or the program stops loudly where A1 already stops.

Refused at compile time, by name, with file:line and `write instead:`:
1. `check="negative"` or `check="minus1"` on an unsigned result (section 3.4).
2. A u64 parameter given a value that is statically negative or a `bool` (a literal, a constant) [proposal]:
   `write instead: pass an int in 0 .. 2**64 - 1`.
3. An `__int128` or other non-`INTS` integer type in a stub: already refused, message unchanged.

Not refused, declared in DIFFERENCES (unchanged or narrowed):
- A63: `c_void_p` handles are ints below 2**63 (no change).
- `AIL_BIGINT=off`: u64 results above 2**63-1 come back as bits. This is a debugging switch, not a language mode, and the
  test says so (Q1 asks whether it should stop loudly instead).
- The `uint64_bits` kind of the `compile-c` type JSON: signed by contract, documented in LANGUAGE_QUICKSTART_JA.md.

## 7. Build and linking

- No new library, no new link flag. The adapter object is built by `compile-c` as today.
- Static and dynamic builds are the same: the conversion lives in the AIL program's runtime, not in the adapter, so a
  `--lib` library (F1, #206, merged) that uses a u64 extern internally gets it too.
- Cargo is not involved. A Rust crate that returns `u64` through `extern "C"` arrives as `uint64_t` and is covered; one
  that returns `usize` arrives as `uintptr_t` or `size_t` depending on cbindgen's settings **[unverified]**. `uintptr_t` is
  not in `INTS` today, so `ail_bindgen.py` would skip or refuse it **[read, not run]**. F6 (offline cargo) adds the case
  to its crate test once F3 is in.
- Binary size: unchanged for programs without a u64 stub (byte-identical). With one, at most the BIGINT.md section 9 budget
  (25 KB); measured per program in F3b.

## 8. Testing plan (CI, no network)

Everything uses a C source beside the test (`sources=`, as `test_ail_ffi.SOURCES` does) or the existing `libtiny.so`. No
cargo, no network, no new system package.

New module `test_ail_ffi_u64.py`, registered in `ail_check.py` MODULES, compared with CPython running the shim. Each case
runs in the typed (default), general, IR and forced-general builds, as F2's `test_ail_classnames` does, plus the
typed-only build (`AIL_NO_GENERAL=1`), whose expected output is the loud stop where section 3.1 says so.

1. Results: `2**63 - 1`, `2**63`, `2**64 - 1`, `SIZE_MAX`, `ULONG_MAX` from C; printed, `hex()`, `%`, `//`, used as a dict
   key, compared with an int literal, summed in a loop.
2. Arguments: `2**64 - 1` round trip; `2**63` from a computation (big); `-1`, `2**64`, `-2**70` each raise `OverflowError`
   with the shim's text, caught and printed; a narrow `c_int` out of range, caught.
3. Buffers: `ptr(c_uint64)` out-parameter filled by C with `UINT64_MAX`, read with `get_u64`; `put_u64` then C reads.
4. `check=`: `check="minus1"` on `c_size_t` is refused with file:line; `check="allones"` (if Q2) raises on `(size_t)-1`.
5. `AIL_BIGINT=off`: the old bits, named in the test as that switch's declared behaviour.
6. Byte identity: six programs with only int64 stubs or no stubs, sha256 of the executable before and after, typed and
   general builds (as #209's `test_programs_without_handle_do_not_change`).
7. `test_ail_ffi.test_uint64_above_int64_is_the_declared_difference` becomes `test_uint64_results_equal_cpython`.

Cost: `tools/icount.c` on a loop of 10**6 calls of a `c_size_t` stub returning small values, against the base: target at
most one instruction per call on the typed path **[target, unmeasured]**. Same loop with values above 2**63 on the general
path, reported, no target (it allocates).

Targeted runs only during each step: `test_ail_ffi_u64`, `test_ail_ffi`, `test_ail_cratebridge`, `test_ail_lib_modules`,
`test_ail_bigint`, `test_ail_safetynet`. `par_check` once after the line merges.

## 9. Stage plan (each one PR)

**F3a. Argument checks** [proposal; core-light: `ail_ffi_lower.py` wrapper, `c_object.py` checks]. First, find out what a
big int does at an int parameter today (section 2.2) and record it. Then every int parameter raises the shim's
`OverflowError` text, catchable, instead of `ail_die`; u64 parameters reject negatives on the typed path.
*Done when:* cases 2 and 6 of section 8 pass in all four builds; `test_ail_ffi` unchanged otherwise.

**F3b. Exact results** (core: `c_object.py` new kind `uint64`, `ail_ffi_lower.INTS`, `biggate.py` creator rule, the
cold `ail_int_from_u64` / `ail_int_to_u64` in the big-int runtime, the tagged lowering's source rule). First measure the
two forms of section 3.1 on one program; keep the cheaper one that holds the size budget.
*Done when:* cases 1, 5, 6, 7 pass; the icount numbers and the size delta for `crc32` and `strlen` programs are in the PR
body; an int64 result's C is unchanged (codegen diff).

**F3c. Buffers** (public: `ail_cbuf.py`, tests). `get_u64`, `put_u64`, with CPython's `struct` texts.
*Done when:* case 3 passes; AIL_REFERENCE_MORE.md lists the two helpers.

**F3d. `check=` rules and docs** (`ail_ffi.py` shim, `ail_ffi_lower.py` refusal, docs). The refusal of section 3.4,
`check="allones"` if Q2 says yes, the declared difference removed from the `ail_ffi.py` docstring, A63 reworded, a DEVLOG
entry.
*Done when:* case 4 passes; `grep -n "2\*\*63 - 1 come back" AIL_CURRENT/ail_ffi.py` finds nothing.

Order: F3a → F3b → F3c → F3d, one line (core changes run sequentially). F3c could go first; it does not depend on the
others.

## 10. Dependencies on #206, #208, #209 (and #211)

- **#206 (F1, merged into `integ` as d68453f7)** **[verified 2026-10-30]**: library builds lower externs, so a `--lib`
  library can call a u64 extern. F3 needs nothing more from it; its tests add one `--lib` case.
- **#208 (F2, open)**: no shared logic. Both touch `ail_chatgpt.py`, `ail_check.py` and `MANIFEST.json`, so expect
  textual conflicts only. Either order works.
- **#209 (F4, open)**: edits `ail_ffi.py` and `ail_ffi_lower.py`, the same files as F3a/F3b/F3d (the `INTS` table, the
  wrapper generator). F3 should start after #209 merges, or rebase onto it. Handles stay `c_void_p`, so the semantics do
  not interact.
- **#211 (F7, open)**: callback arguments and results of u64 type must use the F3 conversions. Whichever lands second
  adds a callback case with a `size_t` argument above 2**63.

## 11. Risks

- **Marking cost.** If the cheap form of section 3.1 does not work and the wrapper must be marked, every caller of a
  `crc32`/`strlen`-like stub moves off the typed path. Measured in F3b before choosing; if both forms cost more than the
  budget, F3b stops and asks.
- **Size.** zlib users (`crc32` returns `c_ulong`) gain big-int pieces they never use for real values. Bounded by the
  BIGINT.md budget, but it is a cost on a common library (Q3).
- **The argument fix changes behaviour of working programs.** A program that passed `-1` as "all ones" to a `size_t`
  parameter compiled and ran; after F3a it raises, as CPython always did. That is the point, but the DEVLOG entry must say
  so.
- **Hidden third silent hole.** The big-int-to-int-parameter path (section 2.2) is not read to the end. If it truncates,
  every int parameter type is affected, not just u64. F3a starts there.
- **Callers of the conversion outside FFI.** `compile-c` objects keep `uint64_bits`; if a later change routes them through
  the new kind by mistake, their documented signed mapping changes. Keep the two kinds separate in `c_object.C_KINDS`.

## 12. Open questions for the owner

- **Q1. Big ints switched off.** With `AIL_BIGINT=off`, should a u64 result above 2**63-1 keep coming back as the negative
  number (what the plan says), or stop loudly with `integer overflow`? Recommendation: stop loudly. The switch is for
  debugging, but a loud stop keeps it from printing a wrong number.
- **Q2. `check="allones"`.** C functions such as `iconv` return `(size_t)-1` on error. May I add `check="allones"` (both in
  the compiled program and in the CPython shim), and refuse `check="minus1"` on unsigned results with a hint to use it?
  Recommendation: yes.
- **Q3. Size for zlib-style libraries.** A program that calls `crc32` (result `unsigned long`) would carry part of the
  big-int code, up to about 25 KB, even though CRC values always fit. Accept that, or add a stub option that says "this
  result always fits int64", checked at run time with a loud stop? Recommendation: accept the size for now; revisit only
  if the measured number is near the budget.
- **Q4. The argument-side fix.** The plan's F3 covers results only. Reading the code shows that `-1` passed to a `size_t`
  parameter is silently turned into 2**64-1 (CPython raises `OverflowError`). May F3 include that fix (F3a), and change the
  existing stop for out-of-range narrow ints into the same catchable `OverflowError` the shim raises? Recommendation: yes,
  F3a first.
- **Q5. Where the work runs.** The plan said "private only" because exact ints were private. They are now in public `integ`.
  May the F3 line run in public `ail-ci` (one sequential line, since it touches compiler-core files)? Recommendation: yes.
