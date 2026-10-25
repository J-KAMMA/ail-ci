## 2026-10-25 - out-of-int64 constant expressions outside function bodies (job-pre184-10251542)

The first still-differing item from the fuzz47 list was `corpus/gdev/g22_012.py`: its class body
`_MASK: int = (1 << 64) - 1` compiled and stopped at run time with `integer overflow` on both builds,
while CPython prints the result; `def f(x=10**30)` had the same pre-existing difference. A constant
integer expression in a module/class assignment or a default argument that does not fit int64 is now
refused by name at compile time (`int64 constant expression out of range`). Expressions that fit int64
are unchanged, an out-of-int64 expression inside a function body keeps its old runtime stop (pre160),
and a class with a base (the enum case) keeps its own refusal. The evaluator handles + - * // % ** << >>
& ^ and unary + - ~ with a 4096-bit guard. Added `test_ail_pre184.py` with the class, module and
default refusals plus in-range class/default/module arithmetic.

Probes in `/tmp/probes`: `p3` huge default, `p4`/`p5` class masks, `p6` module mask, `p7` default
shift, `p8` negative huge default are refused by name on both builds; `p11`/`p14` class arithmetic and
`p15` default arithmetic match CPython; `p1` nested-def tuple default and `p2` class-scope method
default (the earlier fuzz47 items) now match or are refused. `corpus/gdev/g22_012.py` is refused by
name. Tests on the final commit: `test_ail_pre184`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`, `test_ail_pre97`, `test_ail_pre160` all ok.

## 2026-10-24 - CPython codec-name normalization (job-rbpre23-10242019)

The first still-differing item from the task's list was the encoding-name normalization: `b"abc".decode("utf\t8")`,
`"abc".encode("iso-8859-1:1987")`, `bytes("abc", "iso-8859-1:1987")` and `str(b"\xe9", "ISO\t8859-1")` failed
with LookupError (or a compile-time refusal) while CPython accepts them. The bytes prelude now normalizes a
name the way `encodings.normalize_encoding` does (punctuation runs become one underscore, leading/trailing
punctuation is dropped) and matches the normal form against CPython's aliases for UTF-8, ASCII and Latin-1.
The general path's literal-codec check and the typed path's UTF-8 literal check use the same normalization, so
a literal name and a dynamic name agree. Unsupported names still raise LookupError (a literal one is refused
by name at compile time).

Probes in `/tmp/probes` (`p1`-`p5`) covered literal and dynamic names through an argument, list item,
attribute and dict value, encode/decode, `bytes()`/`str()`/`bytearray`, empty input, non-str types, aliases,
normalized punctuation, unknown names and codec width boundaries on both `cmp.sh` builds; `p3`/`p5` are
refused by name. `p4` also matches CPython on the typed path (`AIL_NO_GENERAL=1`) and both IR builds.
`test_ail_pre23.py` runs the literal and dynamic cases on both IR builds.

# DEVLOG

## 2026-10-24 - round() negative ndigits boundary (job-pre160-10250349)

Review follow-up. The new `__index__` route made `round(float, ndigits)` reachable with any int64,
and the negative-scale loop multiplied `1.0` by 10 until it overflowed to `inf`; `inf/inf` then
produced `nan` for every ndigits at or below -309 (`round(2.5, -309)` was `nan`, CPython `0.0`).
The float branch now returns a signed zero for `nn <= -309` (10**309 exceeds DBL_MAX, so every
finite double is nearer zero than the first representable multiple) and raises
`OverflowError: rounded value too large to represent` when rescaling overflows, matching CPython.
The int branch's `-n >= 19` test overflowed for `n == INT64_MIN`; it now tests `n <= -19` directly.
Extended `test_ail_pre160.py` with the boundary program (literals, `__index__`, argument/list item/
attribute/dict routes, signed zero, INT64_MIN for float, overflow, int ndigits). The DIFFERENCES
row now says the `integer overflow` stop happens while evaluating the out-of-int64 expression
inside `__index__`, not on an already-returned index (base did not wrap either).

## 2026-10-24 - round() ndigits conversion (job-pre160-10250349)

CPython checks the number type before converting `round`'s ndigits: an instance with `__round__`
receives the ndigits object unchanged, an int/float converts it with `__index__` only afterwards,
and None means no ndigits. The general path read the ndigits value's raw int field, so `__index__`
was never called, `round(2.5, "2")` and `round(2.5, [1])` silently rounded, an instance without
`__round__` was named `instance`, and a `__round__` method got a garbage integer. `ail_bi_round` now
takes the ndigits object, converts it in the int/float branches (int/bool, `__index__`, or a
TypeError), treats None as omitted there, and the dunder patch passes the object and names the class
in the no-method error. Both builds match CPython on the ordering, type and route probes. An
out-of-int64 `__index__` result still cannot be represented, so it now stops with `integer overflow`
instead of silently wrapping (recorded in DIFFERENCES). Added `test_ail_pre160.py`.
## 2026-10-24 - bench table ratio bounds near 1.0 (job-pre163-10250352)

The pre130 review left the bench2 display quirk pre-existing on this tree: the
`numeric_scale_binary` ail/base row printed `0.990 [0.981, 1.000] faster` although the real
upper bound was 0.9996. Plain `%.3f` rounded 0.9996 to 1.000, so the row looked like a tie
while the verdict (computed from the unrounded bounds) said faster. `fmt` now uses
`_fmt_bound`, which adds decimals only when 3-decimal rounding would put a value on the wrong
side of 1.0; the recorded row reads `0.990 [0.981, 0.9996] faster` and ordinary ratios keep
three decimals, including negative, zero, non-finite and no-range values. No compiler or
runtime file is touched. `AIL_CURRENT/test_ail_pre163.py` pins the recorded row, both sides of
1.0, exact ties, the next floats around 1.0, and values arriving through an argument, a list
item, an attribute and a dict value.
## 2026-10-24 - pre165: forward call of a nested def is unbound

The pre141 reviewer recorded that a nested `def` called textually before its own `def` statement
printed its result on both builds, while CPython reads the still-unbound local and raises
`UnboundLocalError: cannot access local variable 'f' where it is not associated with a value`.
The general path's direct-call lowering resolved the function statically; each direct nested def
now gets a C flag that its `def` statement sets, and `_call_nested_function` checks the flag
before evaluating the arguments. When the same name can also be bound by a parameter, an
assignment, a loop target or `except ... as`, a zero flag reads the frame slot instead: an
unbound slot raises `UnboundLocalError`, any other value is called as CPython does, and every
such rebinding clears the flag. The typed path lifts nested defs out of the enclosing body, so
it refuses a call before the `def` by name and the default build falls back to the general path.
Calls after the def, recursion, caught `NameError`, and the parameter / assignment / argument /
list-item / dict-value shapes keep CPython's behaviour. Added `AIL_CURRENT/test_ail_pre165.py`
with the rebinding cases.
## 2026-10-24 - `in` shares the saved-genexpr cursor (job-pre166-10250412)

Review of the preceding commit found that `x in g` on a materialised generator expression still
scanned the whole backing list and ignored `gen_idx`, so it could report already-consumed items
and did not advance the shared cursor. `ail_op_contains` now searches from `gen_idx` and leaves
the cursor after a match (or at the end when absent); the dunder-aware runtime patch keeps the
same semantics when a user `__eq__` raises. `test_ail_pre166` gained plain and dunder membership
cases. Probes covered matches, misses, duplicate values, equality across int/float/bool, empty
generators, aliases, list items, slices, attributes, dict values, arguments, `iter()` mixing and
custom `__eq__` (including an exception), on both builds.

## 2026-10-24 - next() of a saved generator expression (job-pre166-10250412)

Both emitters materialise a generator expression as a list, so `next(g)` worked only when the
genexpr was written directly in the `next()` call. Stored in a name, an argument, a list item, a
dict value or an attribute, or returned inside a list, it hit `AIL internal error: iterator:
unknown kind`. The list now carries a `gen_idx` cursor, shared by `next()` and by iteration over
that object the way a real generator's cursor is, and `ail_it_next` raises CPython's
`TypeError: '<type>' object is not an iterator` for a value that is not an iterator (so
`next([1, 2])` is no longer an internal error). `AIL_CURRENT/test_ail_pre166.py` compares the
stored-genexpr shapes, aliasing, mixing `next()` with iteration, exhaustion/defaults and
non-iterator types with CPython on both builds. Existing `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3` still pass.
## 2026-10-24 - integer `%` by zero names modulo (job-pre167-10250412)

CPython 3.12 uses `integer modulo by zero` for integer `%`, while `//` and `divmod`
keep `integer division or modulo by zero`.  The boxed and unified `%` emitters still
used the combined `//` text, so `%` by zero through a callback lambda, an argument, a
list item, an attribute or a dict value printed the wrong message on both builds.
Changed the two message literals in `cruntime.py` (`ail_obj_mod`, `ail_op_mod`); the
typed path already had the right text.  Added `test_ail_pre167.py` with the callback
lambda case, the value routes and the `//`/divmod/float neighbours.  An uncaught typed
division trap still prints only its bare text (it reaches `ail_die` directly); that is
the separate pre-existing item recorded before pre138 and is unchanged here.
## 2026-10-24 - list(itertools.permutations(...)) on the typed path (job-pre168-10250413)

The default build generated `ail_list_push(int64_t)` with an `ail_list` value for
`out = list(itertools.permutations(<literal>, r))` and `return list(...)` (also for
`combinations`, `combinations_with_replacement` and `product` of two scalar pools), so the C
compiler rejected the program while the general path matched CPython. The typed lowering now
refuses materialising a tuple-yielding stream with `list(...)` by name, which sends the default
build to the general path and makes `AIL_NO_GENERAL=1` report the refusal. Added
`test_ail_pre168.py`: literal and variable `r`, a return, pools and `r` from an argument /
list item / attribute / dict value, int, float, str, tuple and empty pools, all compared with
CPython on the general and default builds, plus the typed refusal.
## 2026-10-24 -- pre173: bytes start/end bounds use CPython's slice-index rules

The general path's bytes/bytearray `find`, `rfind`, `count`, `index`, `rindex`, `startswith` and
`endswith` read the optional start/end bounds straight from the boxed value, so `b"abc".find(b"a",
"x")` raised `'<' not supported between instances of 'str' and 'int'` instead of CPython's
`slice indices must be integers or None or have an __index__ method`.  One C primitive
(`ail2b_index` in safetyrt.py) now converts a bound exactly as `_PyEval_SliceIndex` does: an int, a
bool or an instance's `__index__` (with CPython's `__index__ returned non-int (type ...)` when the
result is not an int); `None` keeps its default.  `_ail_b_rng` keeps the clamping, and all seven
methods share it.  `test_ail_pre173.py` covers both builds and keeps the case.
## 2026-10-24 - pre175: a frozenset of tuples as a dict key (job-pre175-10250446)

The pre-existing `t4h` defect was still on this tree: the tuple pass lowers `frozenset({(1, 'a')})` to its
`_AilS_Pi_sQ` table class, but a table cannot be keyed by a set, so a dict keyed by that frozenset stays a
plain object while the same expression used as the *lookup* key is lowered. The one-element module constant
`D = {frozenset({(1, 'a')}): 'v'}` then made `D[frozenset({(1, 'a')})]` raise `KeyError`, `... in D` print
False and `D.get(...)` return None; the two-element literal happened to fall back already. The pass now
refuses a set / frozenset of tuples used as the key of a container that is not a table dict
(`tupexpr.ex_Subscript`, `tupstmt.assign_one`) and bails on a module-level constant whose type cannot be told
and that mentions a tuple (`tuplib.module_assign`), so the whole program is left as written and the general
path keeps the dict and the key boxed. Added `test_ail_pre175.py` (5 programs, two builds each). The
frozenset's own repr order remains the separate, documented insertion-order difference (A2); the test compares
lookup / membership / length results, not a raw set print.

## 2026-10-24 - getattr chain reads: refuse computed names too (job-pre179-10250449 review fix)

The first pre-179 change made computed chain names return hardcoded values, which was silently
wrong for a real chain (`raise ... from`, nested `except`), and made `hasattr` report
`__traceback__` true while the following `getattr` still failed.  The runtime helpers no longer
invent values: a chain name that is not an ordinary field and reaches an exception is refused by
name ("reading __context__ (exception chaining is not kept here)") from both `getattr` and
`hasattr`, with or without a default, so `hasattr` and `getattr` agree.  Literal chain names keep
their compile-time refusal.  Ordinary fields, including a computed `setattr` of a chain-named field
followed by a read, are unchanged.  `test_ail_pre179.py` now covers the run-time refusals through
an argument, a list item, an attribute and a dict value on both builds.

## 2026-10-24 - getattr chain reads refused by name (job-pre179-10250449)

The fuzz60 reviewer's r02 was still a silent difference on this tree: `getattr(e, "__context__")`
(and the same read through `hasattr`, with a default, or through `setattr`) built and then raised
`AttributeError` or returned the default where CPython returns None/False.  The general path's
builtin attribute helpers now refuse a literal chain name by name on both builds, matching the
existing direct `e.__context__` refusal.  The first attempt also made a computed name return
None/False (and hasattr true for `__traceback__`); that was still wrong for a real chain and is
corrected by the entry above.  r04 (`continue` out of try/finally) and r09 (`del e.__context__`)
were already named refusals on both builds.  `test_ail_pre179.py` covers the literal refusals,
run-time names through an argument, a list item, an attribute and a dict value, and ordinary
fields.

## 2026-10-24 - GC rooting in the statistics helpers (job-gcroot-10241807)

The general path's native `statistics` helpers kept a heap result in a C local across an
allocating call. `ail2q_partials` built its result list and then boxed every float in it, and
`ail2q_ssd_dd` boxed its first tuple element before allocating the second; both relied on
`AIL2Z_PAUSE` to stop collection. `AIL_GC_STRESS` collects at every allocation regardless of
the threshold, so the unrooted list/tuple elements were freed and overwritten:
AddressSanitizer reported a heap-use-after-free in `ail2q_partials` on
`corpus/gdev/g03_000.py` and `g03_018.py`. Both now register the live locals with
`AIL_ROOT1` / `AIL_ROOT_N` until the last allocation. Added
`test_ail_gcstress.PROGRAMS['statistics_partials']` and its test; it fails with the old
runtime and passes now. The analogous code in `jsonbrt.py` was checked: `ail_tuple_new`
already roots the item array it is given, so no change was needed there.
## 2026-10-24 - bytes.count memmem: self-contained declaration (job-perf7-10240917)

Review found the short-needle `bytes.count` path called `memmem` without a declaration in the
emitted C, so `gcc -std=c11` (a mode AIL uses for `to_c` and C-object builds) assumed an implicit
`int` return and truncated the pointer (segfault). The `BYTES` block now declares `memmem`
itself on non-Windows, after `<string.h>`; glibc and musl both export the symbol, and the
declaration is compatible with the header's when `_GNU_SOURCE`/`_DEFAULT_SOURCE` is set.
`rp7_count_small.py` now prints `4 2 2` under `-std=c11 -O2` and `-std=gnu17`; all count probes
match CPython on both builds, and `binary_search` is unchanged at 64.9 ms vs base 92.0 ms
(`ail/base 0.711 [0.706,0.717]`). Required tests pass.

## 2026-10-24 - bytes.count: memmem for short needles (job-perf7-10240917)

`binary_search` (`count` of a 7-byte needle over a 64 MiB file) spent ~69 ms of its 94 ms in
`ail_bytes_count_range`, which used the byte-pair Horspool scan. For a short needle glibc
`memmem` is about twice as fast on the same data (38 ms vs 71 ms), so the non-Windows
short-needle path now uses the same non-overlapping `memmem` loop as the C reference; Windows
keeps Horspool. `bench/compare.py --app binary_search`: base 98.2 ms, new 69.2 ms
(AIL/C 1.414 -> 0.994, ranges non-overlapping). Probes for empty, negative, windowed and
64-byte needles through arguments, list items, attributes and dict values match CPython on both
builds.
## 2026-10-23 - str format spec: a space sign names CPython's ValueError (job-pre18-10240245)

The first pre-existing difference recorded by the fuzz66 reviewer still reproduces on this tree:
`format('x', ' z')` raised `ValueError: Sign not allowed in string format specifier`, where CPython
says `Space not allowed in string format specifier`. The same wording bug covered every str spec
with a space sign.

`AIL_CURRENT/python/pkg-v12/safetyrt.py` now distinguishes the space flag from `+`/`-` in
`ail2f_format`'s str branch. `AIL_CURRENT/python/pkg-v12/pyboxed2.py` sends a str spec that carries
any sign to `safetyrt.FMT` instead of the core formatter, which silently ignored the flag (so
`format('x', '+')` returned `x` and `format('x', ' ')` padded it). Numeric sign flags and str specs
without a sign are unchanged.

`test_ail_pre18.py` covers the recorded case, all sign spellings, literal and computed specs,
widths/alignment, empty and non-ASCII values, values from an argument/list item/attribute/dict
value, and numeric sign formatting on both builds. It and `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` pass on the final commit.
## 2026-10-24 - pre96: a parameter shadows a class name (job-pre96-10242044)

The general emitter's `expr_Name` returned the module-lifetime class value for every name
that matched a class definition, even when the current function had a local slot for that
name.  In `class U: ...; def f(U): return U.m()` the argument was ignored: both builds read
the class object and raised `AttributeError: 'type' object has no attribute 'm'`, where
CPython returns 42 from the instance's class attribute or method.  A class name now becomes
a class value only when the activation has no parameter, local, cell or closure binding for
it; a shadowing binding is loaded from its own slot.  This also covers a nested function's
parameter, a method parameter, and values arriving through a list item, an attribute and a
dict value.  `test_ail_pre96.py` keeps the probes; no emitted C changes for a program that
does not shadow a class name.
## 2026-10-24 - pre97: constant str.split/rsplit maxsplit

pre70's reviewer left qtest2's second item alone: a maxsplit constant above int64 compiled and
then stopped with `integer overflow` where CPython raises `OverflowError`, and `2**63 - 1` also
overflowed on the intermediate power although the final limit fits.  A constant maxsplit
expression is now folded exactly at compile time in the typed emitter and in the general
emitter (before its argument pre-evaluation): a value that fits is emitted as one int64 literal,
and a value above int64 is refused by name on both builds without evaluating a huge power.
`test_ail_pre97.py` covers both refusal forms and the in-range boundaries.
## 2026-10-24 - Counter missing keys through a dict value (job-pre98-10242046)

`table["k"]["y"] += 1` on a missing Counter key reached through a dict value raised `KeyError: 'y'`.
The general path's generic dict getitem only knew Counter's `__missing__` when the emitter could see
the static kind; a Counter reached through a dict value, an argument, a list item, an attribute, a
return value or an alias took the plain dict path. `ail_dict_getitem` now returns 0 without inserting
for a Counter (flag 1), and `ail2_aug_probe` does the same before the augmented store, so the missing
key starts at 0 and is inserted by the store. Plain dict misses and a missing outer key still raise
KeyError. Added `AIL_CURRENT/test_ail_pre98.py` (two programs, both builds) and registered it in
`ail_check.MODULES`. The separate `Counter({"a": "x"})` constructor difference was not changed.
## 2026-10-24 - pre109: negative shift count keeps CPython's ValueError

The typed `ck_shl`/`ck_shr` guards raised `ValueError` with no message, and `pymix` selected
a typed clone for a helper whose shift count was not a non-negative literal, so the clone's
`ValueError` could escape the caller's boxed `try` (also for `<<=`/`>>=`).  Both guards now
raise CPython's `negative shift count` (adopting the new exception, so a caught shift does not
leak), and `pymix` treats non-literal shift counts in `BinOp` and `AugAssign` as traps, so the
boxed caller keeps its handler.  `test_ail_pre109.py` covers constants, arguments, list items,
attributes, dict values, augmented shifts, valid shifts and an uncaught failure on both builds;
1,000,000 caught shifts keep maxrss at 11,564 KB.
## 2026-10-24 - bench table ratio bounds near 1.0 (job-pre110-10242223)

The bench2 review left one pre-existing display quirk: `numeric_scale_binary`'s ail/base ratio
printed `0.990 [0.981, 1.000] faster` even though the real upper bound was 0.9996.  A plain
`%.3f` rounded 0.9996 to 1.000, so the row looked like a tie while the verdict (computed from the
unrounded bounds) said faster.  `bench/compare.py`'s `fmt` now adds decimals only when 3-decimal
rounding would put a value on the wrong side of 1.0, so this row reads
`0.990 [0.981, 0.9996] faster`; ordinary ratios keep three decimals and the verdict rule is
unchanged.  No compiler or runtime file is touched.  `AIL_CURRENT/test_ail_pre110.py` pins the
below/above/tie/exact-one cases and the no-range median.
## 2026-10-24 -- pre128: %-format no longer uses __trunc__

A class that defines only `__trunc__` printed 5 for `%d` / `%i` / `%u` (and for
every width and sign spelling) on both builds, while CPython asks `__int__` then
`__index__` and raises `TypeError`. The general path's percent formatter
(`dunderrt.py`) no longer falls back to `__trunc__` for the decimal directives;
`int()` keeps its own valid `__trunc__` fallback, and `__int__` / `__index__`
still format. Added `test_ail_pre128.py`: literal directives, widths, signs, a
tuple argument, and values reaching the format through a function argument, a
list item, an attribute and a dict value, on both builds. Still open: a computed
format string (`spec % v` with `spec` held in a variable) is lowered as the `%`
operator and raises TypeError; this is the general dynamic-format limitation
recorded as DIFFERENCES `C?-job-pre128-10242352-2`.
## 2026-10-24 - bench table ratio bounds near 1.0 (job-pre130-10250026)

The pre110 review recorded the bench2 display quirk as pre-existing: `numeric_scale_binary`'s
ail/base ratio printed `0.990 [0.981, 1.000] faster` even though the real upper bound was 0.9996.
Plain `%.3f` rounded 0.9996 to 1.000, so the row looked like a tie while the verdict (computed from
the unrounded bounds) said faster. On this tree `bench/compare.py` still had the plain formatting.
`fmt` now uses `_fmt_bound`, which adds decimals only when 3-decimal rounding would put a value on
the wrong side of 1.0; the recorded row reads `0.990 [0.981, 0.9996] faster` and ordinary ratios
keep three decimals. No compiler or runtime file is touched. `AIL_CURRENT/test_ail_pre130.py` pins
the recorded row, both sides of 1.0, exact ties, the no-range median, the next float below 1.0 and
values arriving through an argument, a list item, an attribute and a dict value.
## 2026-10-24 - pre132: alternate-form repr for a type-less float field

`format(1e300, '#')` and `format(1e300, '#\x00')` printed `1e+300` where CPython prints
`1.e+300`; the compile-time literal f-string path (`ail_fmt_gen`) had the same gap. Both
formatters now keep a decimal point in the mantissa when the alternate form is requested,
including `#.0`, widths, zero padding and grouping. Added `test_ail_pre132.py` (dynamic
specs, literal f-strings, values through arguments, lists, attributes and dicts, and
empty/int/str specs) on both builds.
## 2026-10-24 - pre133: Fraction prelude tuple notes

A reviewer of job `errmsgoc` listed two differences that predated it.  The non-empty container
class attribute (`class A__B: n = {1: 2}`, `n = [1, 2]`) already matches CPython on both builds
of this tree, so it was only added as a regression case.  The other one remained: when a program
that imports `fractions` is refused for an unrelated reason, the tuple pass processes the
injected `prelude_fraction.py` and leaves `cannot tell the type of element 0 of this tuple` notes
for `as_integer_ratio`, `__divmod__` and `__rdivmod__`; their line numbers are in the merged
prelude text, past the user's file.  The three methods now name the element types with locals
(`n: int`, `q: Fraction`), so the tuple pass has nothing to refuse; a refusal now shows only its
own note, and the returned tuples still match CPython on both builds.

Added `AIL_CURRENT/test_ail_pre133.py` (container class attributes, Fraction tuple returns, and
the refusal note) and registered it in `ail_check.MODULES`.  Probes in `/tmp/probes/`:
`classattr.py`, `classattr2.py`, `classattr4.py`, `classattr6.py`, `frac_divmod.py`,
`frac_misc.py`, `fr_note.py`.
## 2026-10-24 - pre134: refuse `del` of a class name by name

`class C: pass; del C` made both builds fail with the compiler's own `KeyError: 'C'`.
A class name is read from its dedicated class slot, not an ordinary frame/global slot,
so deleting the binding cannot be cleared the way a local or module variable is. This
also covers a class name that is rebound at module scope. The construct is now refused
by name at compile time (`del on the class name C`); deleting
ordinary globals, locals, list/dict items and slices is unchanged and still matches
CPython on both builds. Added `test_ail_pre134.py`.
## 2026-10-24 - pre138: integer `%` by zero names modulo

CPython 3.12 splits the ZeroDivisionError text of the integer operators: `1 % 0` says
`integer modulo by zero`, while `1 // 0` and `divmod(1, 0)` keep `integer division or modulo by
zero`. The boxed emitters in `python/pkg-v12/cruntime.py` (`ail_obj_mod`, `ail_op_mod`) raised the
combined `//` text for `%`, so a caught `x % 0` printed the wrong message on both builds; the typed
path already named modulo. Both helpers now raise the modulo text. `//`, divmod(), the three float
messages and `INT64_MIN % -1` (0) stay as they were. Added `test_ail_pre138.py` and its shard.

The two notes recorded by the pre21 reviewer no longer differ on this tree: `tools/ci_shards.py
--check` is clean (both fuzz modules and this one are mapped), and the float-`%` area that job
touched matches CPython on both builds. `perf_event_paranoid` is 4 here, so instruction counts
remain unmeasurable.
## 2026-10-24 - chr() non-BMP refusal (job-pre90-10242040)

The first difference from the reviewer's pre66 note that still reproduces is the general path's 16-bit v2
string unit. `chr(0x10000)`, `chr(0x1F600)` and `chr(0x10FFFF)` built and then died with
`AIL internal error: chr() non-BMP code point requires 32-bit strings`, while the same text as a string
literal was already refused by name at compile time. `chr(0xD800)`/`chr(0xDFFF)` similarly died with the
surrogate message. Constant surrogate and non-BMP `chr()` calls are now refused by name by both the
general emitter (`pyboxed2._b_chr`) and the typed emitter (`pyfunc`), which matches the existing literal
refusal; the runtime store now uses the host unit width (`sizeof(data[0])`) instead of an unconditional
16-bit cast, so the wide headers can store non-BMP values. BMP values through 0xFFFF, bool, range and
type errors are unchanged and compared with CPython on both builds in `test_ail_pre90.py`.

The second reviewer item, `len(str)` being O(n), no longer reproduces: 20000 `len()` calls on a
4000-character ASCII string took 0.00 s on both the forced-general and default builds, so nothing was
changed for it. The wide builds (`AIL_V2_WIDE_EMBED` / `AIL_V2_INCLUDE_ABS`) still cannot be built in
this export (their `out/boxed_rt/v2` headers and fold script are absent), so the width-generic store is
unverified in those modes; a run-time non-BMP value is still an open 16-bit limitation
(`DIFFERENCES` C?-job-pre90-10242040-2).

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
# Devlog

## 2026-10-22

* fuzz21 (unpacking): the general path's `UNPACK_SEQUENCE` errors now use CPython's wording and
  counts -- `too many values to unpack (expected N)`, `not enough values to unpack (expected N, got M)`,
  `(expected at least N, got M)` for a starred target, and `cannot unpack non-iterable X object`.
  Added `AIL_CURRENT/test_ail_fuzz21.py` and registered it in `ail_check.MODULES`.
## 2026-10-23 - fuzz45: float // and % use CPython's float_divmod

The general path's boxed operators and the unified pass emitted `floor(a / b)` for float `//` and a
bare `fmod` for float `%`.  `1.0 // 0.1` was 10.0 (CPython 9.0), `-0.0 % 2.0` was -0.0 (CPython
0.0), `-5.0 // inf` was -0.0 (CPython -1.0) and `inf // 2.0` was inf (CPython nan).  Both now use
one CPython float_divmod helper, so `//`, `%` and `divmod` agree, including zero-remainder signs,
infinities and NaNs.  Added `test_ail_fuzz45.py` (5 programs, two builds each).
## 2026-10-22

- job-fuzz39-10230820 (review fix): a name whose bindings mix a tuple and a number is no longer treated as a known
  tuple for the number check, so `x = (1,); x = 2.5; z = 2.5; x is z` is refused with C115 again instead of printing
  False. The `is(` spelling no longer bypasses the refusal in `numidentity.py` / `pyboxed2.py` (text gate is a word
  match, not the literal `' is '`). Added both cases to `test_ail_fuzz39.py`.
- job-fuzz39-10230820: `is` / `is not` with an equal tuple constant (including one passed to both parameters of a
  generic function) is refused by name instead of answering False where CPython answers True. Added
  `AIL_CURRENT/test_ail_fuzz39.py` and extended `numidentity.py`; `tuplib.py` leaves such a comparison for the refusal.
## 2026-10-23 - fuzz43: str.startswith/endswith tuple member type names

A non-str member of a tuple passed to `str.startswith`/`str.endswith` raised the right
`TypeError` but named the runtime tag rather than the member's class: a bytes member printed
`not instance` where CPython prints `not bytes`, and a user-class member was flattened to
`instance` too. The message now resolves the member object's class name (the prelude bytes class
or the user class) on both builds. Added `test_ail_fuzz43.py`, which also keeps valid tuples,
short-circuiting before a later bad member, empty receivers and windowed calls compared with
CPython. Other observed differences, not fixed here: `bytes.__contains__` with a str item and
bytes search with wrong-type bounds still print different TypeError text (different causes);
the non-ASCII `lower`/`upper` limit remains a documented pre-existing difference.
## 2026-10-23

- fuzz70: `assert cond, msg` now keeps the message object in `AssertionError.args` on the general
  path (`ail2x_raise_builtin`), so tuple/list/dict/None/custom messages match CPython's `str(e)`
  and `e.args`. A mixed-mode typed clone is no longer selected for a function that asserts, so a
  failed assert inside a helper is caught by the surrounding boxed `try`. Typed-only builds still
  refuse a tuple assert message by name. New coverage: `test_ail_fuzz70.py`.
## 2026-10-22 - fuzz8 review 2 fixes (job-fuzz8-10221632)

1. `_attribute_kind` / `_attribute_container` now add the attribute to the recursion guard `seen`
   and return `None` on a cycle instead of recursing forever.  `b.x = b.x + 1` (or `b.x = b.x`)
   together with `itertools.accumulate(..., initial=b.x)` or `groupby([b.x, ...])` no longer aborts
   every build with `RecursionError`; the typed path declines and the default build falls back,
   matching CPython (`[2, 3.5]`, `1 [1, 1]` / `2 [2]`).
2. Corrected `DIFFERENCES.md` row `C?-job-fuzz8-10221632-2`: mutable-element groupby keys do not
   run on a typed recompute.  `--strict` refuses the pattern (`'_ilN_gc' is read before it is
   assigned`) and the default build uses the general path.

`AIL_CURRENT/test_ail_fuzz8.py` covers self-referential and cross-name attribute cycles through
arguments, list items, dict values, nested attributes and groupby.  Probes:
`/tmp/probes/attr_cycle_acc.py`, `attr_cycle_self.py`, `attr_cycle_groupby.py`,
`attr_cycle_two_names.py`, `attr_cycle_nested.py`, `attr_cycle_float.py`,
`attr_cycle_dict_list.py`.

## 2026-10-22 - fuzz8 review fixes (job-fuzz8-10221632)

1. `itertools.groupby` no longer reuses a stale look-ahead key for a list of mutable elements.
   The typed path still declines that pattern (`--strict`: `'_ilN_gc' is read before it is
   assigned`) and the default build falls back to the general path, which matches CPython.
   Scalar/str element lists stay on the typed path and call the key once per element.  Probe
   `gb_cache_regress_len.py` prints `1 3` / `3 1`.
2. `itertools.accumulate(xs, initial=v)` on the typed path is refused by name when the types of
   `v` and the elements differ.  One-argument `round()` is now classified as `int` through local
   bindings, list items, attributes and dict values, so the float-list probe falls back to the
   general path and prints `[2, 3.5, 6.0]` instead of `[2.0, 3.5, 6.0]`.

`AIL_CURRENT/test_ail_fuzz8.py` has both cases; the typed groupby/accumulate modules, safetynet,
files and corpus_findings3 pass on the final commit.


## 2026-10-21 - fuzz8: iteration tools (job-fuzz8-10220554)

Ran 65 small differential programs over chain / islice / product / permutations / combinations /
combinations_with_replacement / accumulate / groupby / zip_longest / starmap / enumerate /
zip(strict=) / sorted / min / max / reversed / map / filter, each through `bash ~/tools/cmp.sh`
on the default build and `AIL_UNIFIED_FORCE=1`.  Fixed three causes (all now in
`AIL_CURRENT/test_ail_fuzz8.py`, with probes in `/tmp/probes`):

1. `itertools.accumulate(..., initial=None)` now treats None as "not given", as CPython 3.12 does
   (`cruntime.ail_it_accumulate`).  Constant, argument, list-item, attribute and dict-value routes
   are tested.
2. `sorted` / `list.sort` call their key on the input in the original order even for
   `reverse=True`, and call it once for a one-element list (`cruntime.ail_list_sort`).  Before, the
   elements were reversed before the key calls, which only showed with a key that has a side effect.
3. The typed path's `itertools.groupby` reuses the look-ahead key, so it calls the key exactly once
   per element instead of twice on each group boundary (`itlib.Groupby`).

Remaining differences found are recorded in `DIFFERENCES.md`; they were not fixed in this job.
## 2026-10-23

- job-fuzz82: typed path refuses `del` on an item of a module-level numeric list by name.
  Before, `del xs[-1]` was a silent no-op (the const table's `.n` write was dropped) and an
  earlier index memmoved over const data and crashed; the default build now falls back to the
  general path and matches CPython. Added `AIL_CURRENT/test_ail_fuzz82.py`.
# Development log

## 2026-10-23 — job-fuzz61-10231419

- String encoding: a run-time encoding name now accepts every CPython alias of `utf-8`, `ascii`
  and `latin-1` (`csascii`, `cp367`, `ibm367`, `csisolatin1`, `ibm819`, `utf8_ucs2`,
  `utf8_ucs4`, ...), on both builds. Literal spellings are accepted by `safetyrt.ENCODINGS`
  instead of refused by name. New test: `test_ail_fuzz61`.
# Development log

## 2026-10-23 — job-fuzz65-10231438 (heapq/bisect)

- Found: `heappush(h, "x")` on an annotated `list[int]` raises TypeError after CPython has already appended the string. When the same file also compares tuples (a `bisect` on `list[tuple[int, int]]`), `tuplegen.lrepr` generated an int-specialized `str(x)` for each element, so `print(h)` showed `x` instead of `'x'` (silent wrong stdout, exit 0, both builds). The same helper raised a spurious TypeError while printing a `list[str]` that held an appended int.
- Fixed `tuplegen.lrepr`: scalar list elements use `repr(x)`, so the value's own repr is used; compound elements keep their existing helper.
- Added `AIL_CURRENT/test_ail_fuzz65.py` and registered it in `ail_check.py`.
- Other observed, not fixed: `list[tuple]` heaps with a wrong-typed item still fail while printing (`int` not subscriptable) instead of printing CPython's list; `nan`/`inf` literals remain refused by name.
## 2026-10-23 -- job-fuzz89-10231611

- Fixed the general path's `bytes`/`bytearray` whitespace `split`/`rsplit` when `maxsplit` is
  reached: the remainder now keeps the outer whitespace, as CPython does
  (`b" a ".split(None, 0) == [b"a "]`, `b"  a  b  ".rsplit(None, 1) == [b"  a", b"b"]`).
  The typed-path loops already had CPython's rule.
- Added `test_ail_fuzz89.py` (both builds against CPython) and registered it in `ail_check.py`.
