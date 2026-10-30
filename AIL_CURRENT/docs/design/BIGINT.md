# Big integers (branch `bigint`, 2026-10-21)

Python `int` is arbitrary precision; AIL's was int64 with a stop ("integer overflow", exit 1; DIFFERENCES A1). This note
is the design of the replacement. Oracle: CPython 3.12.

## 1. Representation

- **General (boxed) runtime, `cruntime.OBJ2`.** `AIL_T_INT` stays the inline tagged int64 (`ail_obj.i`). A value outside
  int64 is `AIL_T_BIG`: `ail_obj.o` points at a GC object (`AIL_K_BIG`, `ail_bigobj`: header, `int32 sign` -1/+1, `uint32 n`,
  `uint32 d[n]`, little-endian base 2^32 limbs, normalised: no zero top limb, `n >= 1`). `type(x)` / `isinstance(x, int)` / the
  type name see one type, `int`.
- **Canonical form.** A result that fits int64 is always the small form (demotion, in the one function every operation
  ends in: `ail_big_finish`). So a given value has exactly one representation: `==`, hash, dict keys, `is None` tests and
  `case` patterns on the small form stay valid, and `hash(2**64 - 2**64 + 5) == hash(5)`.
- **Core, `bigint_core.py` (`CORE`).** Plain C on magnitudes (`ail_limb *`, length, caller-provided output):
  add, sub, schoolbook multiply with Karatsuba from 40 limbs (and chunking of a lopsided operand), Knuth algorithm D
  (single-limb fast path), shifts, decimal conversion, two's-complement helpers, correctly rounded `double` conversion.
  64-bit intermediates only; no external library, no `__int128` outside the hash (guarded). The core is unit-tested alone as a
  shared library against CPython (`test_ail_bigint.py`, ~50k checks) before it is wrapped.
- **Typed runtime** keeps C `int64_t`. It never sees a big value (section 4).

## 2. Promotion and demotion points (general path)

Promote when the int64 operation overflows: `+ - *` (`__builtin_*_overflow`), `//` (`INT64_MIN // -1`), unary `-`,
`abs`, `**` (any int exponent >= 0; negative exponent gives a float), `<<`, `int(str)` / int literal that does not fit,
`int(float)` / `math.floor|ceil|trunc` of a float beyond int64, `sum`, `math.factorial|comb|perm|prod|isqrt|gcd|lcm`,
`int.from_bytes`, `1 << n` and friends, `pow(a, b, m)`.
Demote in `ail_big_finish` whenever a result's limbs fit int64 (so `x - x`, `x // y`, `x % m`, `x >> k` land back small).
The fast path of every operator is unchanged: one tag test on each operand, the overflow builtin, a cold call.

## 3. Algorithms

- Sign rules as CPython: `//` floors, `%` takes the divisor's sign, `divmod` agrees, `ZeroDivisionError` texts unchanged.
- `**`: left-to-right square and multiply; `pow(a, b, m)`: modular square and multiply with a reduction after every step,
  negative exponent through the modular inverse (extended Euclid); `m == 0` is `ValueError: pow() 3rd argument cannot be 0`.
- Bitwise `& | ^ ~` and `>>` with negative operands: two's complement over `max(n)+1` limbs, op, convert back. Floor shift of a
  negative number rounds toward minus infinity (low bits lost -> subtract one).
- Comparison: sign, then limb count, then limbs. With a float: exact, never through `(double)big`. NaN is unordered;
  +-inf are beyond every int; a finite double is split into integer part (exact, `ldexp` of the 53-bit mantissa) and fraction.
- `float(big)`: round-to-nearest-even from the top 64 bits and a sticky bit; above 2^1024 `OverflowError: int too large to convert to float`.
- `str` / `repr` / `f"{x}"`: repeated division by 10^9 on a copy. CPython's limit applies: more than 4300 digits is
  `ValueError: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit`
  (and for `int(s)`: `...conversion: value has N digits; ...`). The limit is what makes the schoolbook conversion enough:
  at most ~450 limbs, about 100k limb operations. A divide-and-conquer conversion would need a sub-quadratic division to
  gain anything, so it is not built (measured in section 7). Binary, octal and hex have no limit and are linear.
- `hash(int)`: CPython's, `x mod (2^61 - 1)` with the sign applied and -1 mapped to -2. The containers' own hash is a mixed
  function of the same value; a big value that equals a float (`2**70 == 2.0**70`) hashes like that float, so lookups agree.
- `gcd`: Euclid on divmod; `isqrt`: Newton from a bit-length estimate; `factorial`: product of the odd part
  with a balanced product tree and a shift; `comb`/`perm`: exact products and one division.

## 4. The typed path and the unified (unboxed) path (no hand-off)

The exact-image hand-off is removed (`ail_ho_try`, `AIL_BIGINT_HANDOFF`, the second image). The typed path keeps C `int64_t` and its
loud stop (`integer overflow`, exit 1, stdout flushed). The general path boxes ints and promotes on overflow through cold,
noinline `ail__ov_*` / `ail_big_*` functions; the hot operators keep their int/float arms, a big operand is handled after them.
`ail_op_add/sub/mul` send everything after the hot arms (big ints and the type errors) to a cold `ail__*_slow`, so the hot
operator is no larger than before: with a larger body GCC stopped inlining `ail_op_add` at a hot call site (the cause of the
earlier 8-24% on general programs; g08_034 went from +3.9% to +0.5%). `exit()` was replaced by `_Exit()`: the extra libc import cost
about 1.5k start-up instructions in every general binary.

## 5. Marked functions (default build) and literals

`bigcap.py` marks a function big-int capable (int literal beyond int64; `**` with a non-constant or too large exponent -- not a
float constant base, which makes a float; `<<` by a variable; math.factorial/comb/perm unless every call has constant arguments
whose result fits int64 (`factorial(5)` does not mark, `factorial(21)` does); pow() with such an exponent; int() of a constant
string over 18 digits, also `'1' * 5000`; int.from_bytes; a call of a marked function, transitively). A marked function gets no typed clone and unified.py keeps its ints boxed (`demote`
`(name, '*')`); a marked module takes the whole program off unified. Python-syntax programs only (`AIL_SURFACE=python`).
Big literals are string constants parsed once at start-up (general path, marked functions).

## 6. Unified unboxing: the option measured

Option A (`AIL_UNIFIED_PROVEN=1`): an unboxed int local keeps int64 only where its range is proven (bounded range() index, len(),
small-step counters); everything else, parameters and returns included, stays boxed. Measured on 40 general-only gdev programs
against the base: +4.8% instructions (geomean; +18.6% total) with 52 programs compared; over the +1% budget. Chosen: option B,
keep the unboxing in functions that are not marked and make an overflow there a loud stop (DIFFERENCES C288). Option A stays
as an opt-in switch; it does not yet type expressions by bit width (`1 << 70` of constants is still a stop under it).

## 7. What is not covered

Division by a huge value in `//` of a float (`10**400 / 3` is `float / int` -> OverflowError as CPython), `int.to_bytes`
of lengths over 2^31, `sys.set_int_max_str_digits` (the limit is fixed at 4300), `round(big, -n)` beyond int64 rounding
digits beyond 18 (see the tests for the exact boundary).

## 8. Measurements

Sample: every 8th gdev program (64; 52 give the same output at base and now). Instructions by `tools/icount.c`, binary size.
Last measured tree (2026-10-22, `tools/icount.c`, default build, against `/tmp/base` at `work`): g00_012 +0.13% / +10.4 KB,
g11_014 +0.80% / +19.4 KB, g21_016 +0.09% / +19.1 KB, g22_040 -5.8% / +14.5 KB. The forced-general loop
`for i in range(10**6): s += i % 7` 198.05M -> 199.05M (+0.505%, one instruction per iteration) / +14.2 KB. g23_030 (+7.2% in the
older sample) is `math.comb`: it is marked, so its typed clone is gone by design; g22_006 (+37%) is typed-to-general because it is
marked. The requested mixed int/str/math probe grew 111,904 -> 135,776 B (+23,872 B, inside the +25,600 B limit). Census
(`tools/fallback_census.py`) not run.

## 9. Size gate

`biggate.py` selects the runtime per program. The emitters mark a source-level int arithmetic operator on the general path with
`/*I*/` when an operand is int/bool or is not proven to be another kind (two operands of unknown kind count, so a list item, a dict
value, an attribute and a function parameter keep the runtime). A proven float is not int arithmetic: a float literal, a field whose
every store is a float (a constructor parameter read from its call sites, a default argument of an omitted call, and a class-body
fallback all count), and a float-only list/dict literal (or a name bound to one) that is only read by index. A function whose call
sites prove its parameters float/str does not count either, and a function used as a value has unknown parameters (an unseen
callback can pass anything). Reachability
additionally finds constructs that make a big int without an int64 overflow (a literal beyond int64, `int(str)` of a long string,
`math.factorial/comb/perm` with an argument that can exceed int64, `int.from_bytes`; a constant call whose result provably fits
int64, such as `comb(1001, 1)`, does not).
The generic operators themselves are not a reason to link the core: a float `*` or a str `+` stops the reachability walk. A program
with neither gets byte-identical C and binary to the base (no-int programs n1/n2: 84,680 / 68,368 bytes in both builds). For a
program that does have the runtime, `pyc.py` compiles it with `-ffunction-sections -fdata-sections` and links with
`--gc-sections`, so the big routines that program never calls are not in the binary; the no-int builds keep the old command line.
A general-path binary that does int arithmetic may grow by at most 25 KB; the four measured programs and the mixed probe are all
inside that (section 8).

B3 adds a finer source-level split inside the runtime. A group of definitions may be written as

    /*P:div<*/ ...division... /*P|*/ /*P>*/

and `biggate.pieces_for` enables it only when the program's own text (after `USER_MARK`) names that operation: `div` for `//`, `%`,
`divmod`, true division and `range`; `pow` for `**` and `pow`; `shift` for `<<`/`>>`; `bits` for `& | ^ ~`; `text` for `str`, `repr`,
`print`, `int(str)` and `bin/oct/hex`. The definitions left out are replaced by their prototypes, so an unused caller in a math
helper still compiles; the linker then discards it. The pieces are resolved at the end of `build()`, after `dunderrt` and the other
patches have added their own references, and the typed tint runtime is already split by its own inline functions and `--gc-sections`.
A program that does not divide big ints no longer carries big division: `g01_006` went from 147,760 to 143,008 bytes and a big-int
add/print probe keeps only add/sub/mul and text. The 32 KB budget of section 5 is met on every measured program; the largest observed
delta is `g12_014` at +27,912 bytes, and float-only programs keep byte-identical C.

## 10. What the typed path does with a function the tagged lowering does not cover

A function whose ints are not proven to fit int64 needs the IR's tagged lowering (section 4). When the IR cannot lower it:

1. The default build tries the exact general path (unchanged).
2. If that cannot build the program either (a binary file, a socket, a construct only the typed path has), `pyc._build_unshadowed`
   builds the program once more with `info['_tint_legacy']`: no tagged signatures, every function on the legacy int64 emitter, whose
   overflow is the loud `integer overflow` stop. Nothing wraps. The hard constructs of `bigcap` (a literal beyond int64, `<<` by a
   variable, `math.factorial/comb/perm` that can be big) stay refused. A unit compile (`_want_units`: link units, module objects, the
   C export, `check`) does the same in `pyfunc.to_c`.
3. A typed-only build (`AIL_NO_GENERAL=1`) keeps its by-name refusals for a value that can grow past int64 into an int64 slot
   (a growing local, a literal), but not for an operand the proof could not type, a parsed `int(text)`, `2 ** k` or
   `int.from_bytes`: their int64 overflow is the loud stop they always had. `AIL_IR=0` asks for the legacy emitter, so the store
   gate is off there.

The lowering covers (each has a case in `test_ail_bigint.TintGaps`): tuple assignment of numeric values; a conditional
expression and a range index of tagged ints; `str.lower/upper` and `sep.join([...])`; comparisons of two bytes values; a function
with a tagged result whose body ends in a `try`; an object returned by a call (`obj.call`) and a list display passed to a list
parameter; a comprehension over a read-only list parameter (`sorted(xs, key=lambda ...)`) and a comprehension variable that is a
tagged local elsewhere; handlers for `Exception`, for a user class, and for any class together with the classes derived from it
(`P._handler_codes`); a named handler that only reads the text of what it caught (`e.__ail_text__` and friends, via
`ail_handled_value`); counters that copy each other (int64 again, which the input-window plan needs); a module int constant is a
known value for the local proof. Still on the general path in a default build (or on the legacy emitter in a typed-only one): a
handler that reads anything else of `e` (args, errno, passing it on), raising a user class, `str`-keyed dicts, a `list[str]`
result, tuple classes in expression position, lists of objects and nested records, generator expressions, `lambda` arguments of
`map`/`filter`/`max`. Programs of `bench/` that left the typed path because of them: collections/deque_bfs_tuples,
collections/group_indices, stdlib3/json_dumps and tuples/bfs; `AIL_NO_GENERAL=1` builds them on the legacy emitter.
Debug switches: `AIL_IR_TRACE=<file>` appends the traceback (and the tagged-int facts) of every function the IR refuses;
`AIL_NO_TINT_LEGACY=1` turns the legacy retry of item 2 off.

## 11. What the local proof knows about counters and floats (2026-10-30)

Two gaps kept float programs on the general path (20 to 200 times the instructions; measure-float-refcount.md):
- An attribute, a list item or a call result had no kind in the proof, so `dx = b1.x - b2.x` (dataclass `x: float`) and
  `round(acc.x, 6)` looked like unprovable int operations. `ir/driver.py` now gives the proof the typed emitter's own type
  (`bigcap._Defined.float_oracle`): what the emitter types float is float. Without the oracle (the source-level marking) nothing changes.
- The counter of `for i in range(...)` was unbounded unless every argument was. With a bounded start (0 for `range(n)`) and a
  constant step up to 256 it is within 2**48 steps of its start (`_lp_range_value`), the same physical limit as `len()` and the IR's
  int counters. `i + 1` is proven; `i * i` and `i << 20` are still not. The stop is not looked at, whatever its kind.
Tests: `test_ail_typedreach1.py`.
