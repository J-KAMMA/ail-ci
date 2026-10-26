## 2026-10-26 - re-apply pre255: class constant routes through a list item, attribute or dict value (job-rbpre255-10261620)

Re-applied the accepted pre255 change on this tree, keeping the current tree's exact class-level
folding from pre227/pre246.  A class constant built through a list item, attribute or dict value
(`N = 2**62; xs = [N]; class C: X = xs[0] * 4`) still kept checked int64 arithmetic and stopped
with `integer overflow` where CPython prints the bignum.  `fold_constants` now refuses the route
by name at compile time on both builds (`class-level constant built through a list item, attribute
or dict value`); the scan walks each class body but prunes methods, nested classes and deferred
lambda bodies, and treats a call's `Attribute` callee (including its receiver) as the callee while
still scanning the call's arguments.  In-range routes and empty containers are refused too;
arithmetic outside a class body, a method body and class-level arithmetic without such a route
are unchanged.  Added `AIL_CURRENT/test_ail_pre255.py` and registered it in `ail_check.MODULES`.

Probes in `/tmp/probes`: `pre255_list_out`, `pre255_dict_out`, `pre255_attr_out`,
`pre255_list_in`, `pre255_neg_out`, `pre255_empty`, `pre255_nested_arg`, `pre255_call_arg`,
`pre255_unary`, `pre255_tuple_route` and `pre255_nested_class` are refused by name on both
builds; `pre255_outside`, `pre255_method`, `pre255_lambda_list`, `pre255_lambda_dict`,
`pre255_str_method`, `pre255_list_receiver_method` and `pre255_plain` match CPython on both
builds.  `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run
and `--check` passes.

## 2026-10-26 -- reapply pre225: grouping with an unrecognised type code (job-rbpre225-10261321)

Re-applied the accepted pre225 change. Its safetyrt.py fix is already present on this tree from
the pre206 review: `ail2f_parse` checks the grouping against the type before an unknown code (its
whitelist gives the same result as pre225's `bcdeEfFgGnosxX%` once the `n`/`s`/`c` and
`,`+`b/o/x/X` conflicts are applied), and `ail2f_code_text` already escapes a space code as
`\x20` (`c <= 0x20`). The code therefore needed no further edit, keeping both sides' fixes. Added
`AIL_CURRENT/test_ail_pre225.py` (1 test, both builds) and registered it in
`ail_check.MODULES`. Probes `/tmp/probes/pre225_*` (group matrix, value routes, NUL/code points,
boundaries) match CPython on both builds. Tests: pre225, safetynet, files, corpus_findings3.
## 2026-10-26 -- re-apply pre243: full "Invalid format specifier" text (job-rbpre243-10261424)

Re-applying pre243 on this tree: the runtime change it proposed is already present from the
pre206 parser fix (`ail2f_raise_invalid`, the parser's `-2` whole-spec code and the value-type
name), so no `safetyrt.py` edit was needed; pre243's base-only note about a single non-ASCII type
code is superseded by pre206's CPython `Unknown format code '\x..'` text.  Added the accepted
`test_ail_pre243.py` and registered it in `ail_check.MODULES`; it passes on both builds.
Probes `/tmp/probes/p243_invalid_spec.py` and `p243_extra.py` (multi-character, empty, control,
NUL, quote, long and non-ASCII specs; int/bool/float/str values, negative/zero/empty; literal,
argument, list item, attribute, dict value and alias routes) match CPython on both builds.
## 2026-10-26 -- pre251 reapply: bool constants in constant integer shifts (job-rbpre251-10261432)

Re-applied the accepted pre251 change on this tree. The three `pyfunc.py` edits are already
present here: `_maxsplit_const` and `_const_int_expr` accept a bool constant as CPython's 0/1,
and `fold_int_constant` still leaves a bool-only result (`True & True`) to the run time so its
type stays bool. The current tree's later wider-intermediate and unary-plus fixes are kept.
Added `test_ail_pre251.py` (6 tests, both builds) and registered it in `ail_check.MODULES`.

Probes `/tmp/probes/pre251_accept.py`, `pre251_contexts.py`, `pre251_boolops.py`,
`pre251_module_const.py`, `pre251_maxsplit.py` and `pre251_pow.py` match CPython on both builds;
`pre251_refuse_shift.py` and `pre251_refuse_wide.py` are refused by name on both builds.
Final-state tests: test_ail_pre251, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3; `tools/update_manifest.py --check` passes.

## 2026-10-25 -- pre227 suite fix: the constant check owns the refusal wording (job-pre227-10260534)

The class-constant fix still folds `N = 2**62; class C: X = N * 4` to a literal, but the
current integration tree's `_check_int64_constants` now sees that folded module/class
assignment before `_check_int64_literals`, so it refuses it as
`int64 constant expression out of range` instead of `int64 literal out of range`.
`test_ail_pre227.py` now accepts either named refusal (and still rejects `integer overflow`
and a traceback); the in-range, shadowed, rebound and dynamic-route cases are unchanged.
Probes `pre227_*` in `/tmp/probes` match CPython or are refused by name on both builds, both
here and on a copy of the current integration branch with this fix applied. Tests: pre227,
safetynet, files, corpus_findings3.

## 2026-10-25 -- pre227: class constants built from a module name (job-pre227-10260119)

The first still-differing item in the rbpre184 review was the class constant built through a
name: `N = 2**62; class C: X = N * 4` compiled and then stopped with `integer overflow`, while
CPython keeps an unbounded int. `2**63 - 1` in a module/class/default already matched (folded)
and the nested default `def f(x=10**30)` was already refused by name, so only this item was left.
`fold_constants` now carries the module constants it already knows into class-level assignment
expressions and folds them exactly (`_fold_int_exact`, wide intermediate steps allowed, 4096-bit
cap): `N = 2**61; class C: X = N * 2 - 1` emits 2**63-1, `(N * 4) // 4` emits 2**62, and a value
that cannot fit int64 is rewritten to its literal and refused by name (`int64 literal out of
range`) on both builds. A name the class body itself bound earlier, a module name rebound later,
non-int constants (str/float/bool) and a plain `X = N` are left untouched; a value that only
reaches the class body at run time keeps the fixed-width trap, and a nested class definition is
refused by name.

Probes `/tmp/probes/pre227_*` (out mult/shift/power/negative/alias/annotated, in-range widths and
wide steps, non-int constants, plain name, rebound/shadowed name, class before the assignment,
dynamic list/dict/attribute/argument routes) match CPython or are refused by name on both builds,
except the dynamic routes, which keep the documented int64 runtime trap. Added
`test_ail_pre227.py` (2 tests, both builds) and registered it in `ail_check.MODULES`. Final-state
tests: test_ail_pre227, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, plus
test_ail_nested_functions, test_ail_modconst, test_ail_pre113/172/177 pass; test_ail_pre121 keeps
its two pre-existing general-build failures (identical on HEAD).
## 2026-10-25 -- pre246: v1 boxed runtime builds; INT64_MIN is a legal index (job-pre246-10260358)

Two pre-existing differences from the rbrbpre204 review were fixed.  The v1 emitter
(`AIL_GENERAL=v1`, reached only when the typed path falls back) pulled in the DIE block and then
redefined its `ail_exc_top`/`ail_exc_stack`/`ail_die`/`ail_alloc`, so every v1 program failed to
compile (`redefinition of 'ail_exc_top'`).  The v1 frame stack and current-exception slot now use
`ail_v1_*` names (with the v1 emitter updated) and rely on the DIE `ail_die`/`ail_alloc`, so v1 C
builds and runs; probes cover mixed-type values, `try`/`except` with an exception variable,
nested `try`/`finally`/re-raise, an uncaught `ValueError` and an uncaught `IndexError`.

The pre177 constant-index check folded unary minus per step, so `d[-(1 << 63)]` was refused with
`int64 index out of range: 9223372036854775808` although -9223372036854775808 is representable.
Unary `-`/`~` now fold their operand exactly and range-check only the result, so INT64_MIN (and
`~INT64_MIN` = INT64_MAX) work as list/tuple/str/bytes/dict indexes, including through a parameter,
a list item, an attribute, a dict value and an alias; a positive `1 << 63`, `-(1 << 63) - 1` and
other out-of-int64 results keep the by-name refusal.  Added `AIL_CURRENT/test_ail_pre246.py` (5 v1
programs and the index boundaries) and registered it in `ail_check.MODULES`.  Probes are
`/tmp/probes/pre246_*`; both cmp.sh builds match CPython or refuse by name.

## 2026-10-25 -- pre199: range() with a zero step raises ValueError (job-pre199-10252047)

The first still-differing item left by pre186 was `range(0, 5, 0)`: both builds accepted it and
printed `range(0, 5, 0)`, where CPython raises `ValueError: range() arg 3 must not be zero` at
construction.  The general (v2) path's `range()` now evaluates its arguments in Python order,
converts each as `PyNumber_Index` does (int, bool or an instance's `__index__`, otherwise
`TypeError: '<type>' object cannot be interpreted as an integer`) and builds through the checking
`ail_bi_range`, so a zero step is refused before the range exists.  Non-zero ranges (negative,
empty, wide, bool bounds) are unchanged.  `AIL_CURRENT/test_ail_pre199.py` covers both builds;
probes are `pre199_range_*` in `/tmp/probes`.  The later reviewer items (the enumerate repr,
`-MAX - 1` literal and the `AIL_GENERAL=v1` duplicate `ail_exc_top`) were not touched.

# DEVLOG

## 2026-10-25 -- pre183 reapply: builtin/type tuple-member names, bytes membership (job-rbpre183-10252048)

Re-applied the accepted pre183 change on this tree. The bytes/bytearray membership message is
already fixed here (the current prelude's `_ail_bcontains` keeps the integer-byte path and uses
the bytes-like text for other operands, as the pre114 row records), so no prelude edit was needed.
The outstanding part, naming a builtin-function tuple member in `str.startswith`/`endswith` as
`builtin_function_or_method` (and the type-valued `bool` as `type`) instead of `function`, is now
applied: the lowerer marks the generated lambda, the FUNC object carries the builtin kind, and
`ail__tname_c` uses it. User-defined functions still name `function`. Error-only paths.

Probes in `/tmp/probes` covered literals, variables, arguments, list items, dict values and
attributes, both methods, the scalar form, an early matching member, invalid/negative windows,
empty tuples, `bool` and `len`, and user-defined functions, on both `cmp.sh` builds; all match
CPython. `test_ail_pre183.py` keeps the cases.

## 2026-10-25 - pre125 reapply: module-scope bare attribute/subscript annotations

The accepted pre125 change proposed refusing `obj.attr: note()` / `xs[i]: note()` by name because
the old surface evaluated neither the target nor the annotation. This tree already contains the
pre124 fix, which evaluates the target's base object and index expressions and then the annotation
in CPython order on both builds. Refusing here would regress that fix, so both changes are kept:
pre124's evaluation stands, and `test_ail_pre125.py` re-applies pre125's cases as CPython-parity
regressions (also a bare annotation on a plain name, `count: int`, unchanged). Probes:
`ann_attr_module.py`, `ann_sub_module.py`, `ann_attr_nested.py`, `ann_sub_empty_negative.py`,
`ann_sub_slice.py`, `ann_attr_alias.py`, `ann_sub_dict_str.py`, `ann_sub_arg_item_attr.py`,
`ann_attr_static.py`, `ann_sub_future.py`, and `ann_name_type.py`; all matched CPython on both
builds.

## 2026-10-25 -- pre186: enumerate counter past INT64_MAX stops by name (job-pre186-10251543)

The first still-differing pre-existing item from `fuzz48` was the `enumerate` counter: starting at
`9223372036854775806`, the general iterator wrapped through `INT64_MAX` and printed
`-9223372036854775808`, where CPython prints `9223372036854775808`.  AIL ints are 64-bit, so the
next value after `INT64_MAX` has no representation.  The shared `AIL_IT_ENUMERATE` step now keeps
the last representable index and, if another item exists, raises
`OverflowError: enumerate() index integer overflow`; the old materialised
`ail_builtin_enumerate` gets the same guard.  Every counter that fits still matches CPython
(including an empty iterable at `INT64_MAX`, one item at `INT64_MAX`, negative starts, and starts
reaching the call through an argument, list item, attribute, dict value, a for loop and `next()`).
`AIL_CURRENT/test_ail_pre186.py` covers both builds; probes are `pre186_enum_*` in `/tmp/probes`.
The second reviewer item, `range(0, 5, 0)` being accepted, was reproduced but left open.
## 2026-10-25 -- statically known unary int64 overflow (job-rbpre172-10251601)

The first pre-existing difference left by job-pre108 was pure unary overflow: `-MIN`, both on a
module constant and as `-(-9223372036854775808)`, compiled on the default build and then stopped at
run time with `integer overflow`, while CPython printed a bignum; the general path refused the
`MIN` literal with a different message. A new front-end check evaluates unary `+`/`-` over integer
literals and module-level int constants and refuses an out-of-int64 result by name (`int64 constant
expression out of range: ...`) on both builds. A module constant shadowed by a parameter is not
folded, and values that only reach the unary operation as variables keep the fixed-width trap.
Added `test_ail_pre172.py` and registered it in `ail_check.MODULES`.

## 2026-10-24 -- bytes.count memmem: self-contained declaration (job-perf7-10240917)

Review found the short-needle `bytes.count` path called `memmem` without a declaration in the
emitted C, so `gcc -std=c11` (a mode AIL uses for `to_c` and C-object builds) assumed an implicit
`int` return and truncated the pointer (segfault). The `BYTES` block now declares `memmem`
itself on non-Windows, after `<string.h>`; glibc and musl both export the symbol, and the
declaration is compatible with the header's when `_GNU_SOURCE`/`_DEFAULT_SOURCE` is set.
`rp7_count_small.py` now prints `4 2 2` under `-std=c11 -O2` and `-std=gnu17`; all count probes
match CPython on both builds, and `binary_search` is unchanged at 64.9 ms vs base 92.0 ms
(`ail/base 0.711 [0.706,0.717]`). Required tests pass.

## 2026-10-24 -- bytes.count: memmem for short needles (job-perf7-10240917)

`binary_search` (`count` of a 7-byte needle over a 64 MiB file) spent ~69 ms of its 94 ms in
`ail_bytes_count_range`, which used the byte-pair Horspool scan. For a short needle glibc
`memmem` is about twice as fast on the same data (38 ms vs 71 ms), so the non-Windows
short-needle path now uses the same non-overlapping `memmem` loop as the C reference; Windows
keeps Horspool. `bench/compare.py --app binary_search`: base 98.2 ms, new 69.2 ms
(AIL/C 1.414 -> 0.994, ranges non-overlapping). Probes for empty, negative, windowed and
64-byte needles through arguments, list items, attributes and dict values match CPython on both
builds.
## 2026-10-24 -- pre173: bytes start/end bounds use CPython's slice-index rules

The general path's bytes/bytearray `find`, `rfind`, `count`, `index`, `rindex`, `startswith` and
`endswith` read the optional start/end bounds straight from the boxed value, so `b"abc".find(b"a",
"x")` raised `'<' not supported between instances of 'str' and 'int'` instead of CPython's
`slice indices must be integers or None or have an __index__ method`.  One C primitive
(`ail2b_index` in safetyrt.py) now converts a bound exactly as `_PyEval_SliceIndex` does: an int, a
bool or an instance's `__index__` (with CPython's `__index__ returned non-int (type ...)` when the
result is not an int); `None` keeps its default.  `_ail_b_rng` keeps the clamping, and all seven
methods share it.  `test_ail_pre173.py` covers both builds and keeps the case.
## 2026-10-24 -- pre100: `%d` of a float on the general path

CPython truncates a float for `%d` and prints the whole integer even past int64 (`"%d" % 1e20`
prints `100000000000000000000`). The literal-format path rejected a float with
`TypeError: unsupported format string passed to non-int`, and the run-time formatter stopped at
the int64 boundary with `AIL limit: integer overflow`. Literal `%d` conversions now go through
the run-time formatter (`pyboxed2._percent_format` -> `safetyrt.FMT`), and that formatter's
integer branch formats the truncated float as decimal digits directly instead of as an int64.
NaN and infinity keep CPython's ValueError / OverflowError. Probes:
`/tmp/probes/pre100_float_d*.py`, `pct_dynamic_float.py`; new test
`AIL_CURRENT/test_ail_pre100.py`.

## 2026-10-24 - pre104: round() of nan/inf raises CPython's exception

The pre54 review recorded the default build's one-argument `round()` of nan/inf as a
pre-existing difference: it stopped through `ail_die` with `round() of nan` or
`round() result does not fit in this language's int64`, so a `try` could not catch it and an
uncaught program printed the trap message instead of CPython's exception line.  `ail_round0`
now raises `ValueError("cannot convert float NaN to integer")` and
`OverflowError("cannot convert float infinity to integer")` through the normal exception path
on both builds.  Finite values, including the int64-boundary trap, are unchanged.  Added
`AIL_CURRENT/test_ail_pre104.py` and registered it in `ail_check.MODULES`.
## 2026-10-24 - pre44: unassigned Callable locals are UnboundLocalError

The `test_ail_callable_values` failure recorded by the `regmods` review was a stale
expectation, not a compiler difference: a Callable local that the definite-assignment pass
has not assigned already raises CPython's `UnboundLocalError` (directly, through a list item,
a dict value or an argument, and after `if`/`for`/`del`) on both builds. The R570 test still
expected `RuntimeError`; it now catches `UnboundLocalError`. The same test module's refusal
list also still contained a managed-struct Callable field, which R594 supports and
`test_ail_exception_values_core` covers. Added `test_ail_pre44.py` with CPython comparisons
for the direct, annotation-only, container/argument and control-flow cases. No language
behaviour changed.
## 2026-10-24 - comprehension stores and binary64 copies (job-perf6-10240916)

`numeric_scale_binary` spends most of its time in the generated `float_values_scale`, whose
comprehension reserved the exact result size and then called `ail_flist_push` for every element.
For a counted, unfiltered comprehension over an int or float list, the compiler now writes
`list.p[list.n++] = value` directly when the element expression contains no calls (which is what
could move the source list under the loop). A float element built only from names, reads and
`+ - *` also gets `#pragma omp simd`; `pyc.py` adds `-fopenmp-simd` so GCC vectorizes that one
loop, while `-fno-tree-slp-vectorize` stays in force for the struct-of-doubles reason it was added.
`F64CODEC` now takes `unpack_float64`/`pack_float64` buffers from `ail_alloc_raw` instead of the
zeroing `ail_alloc`, since both paths overwrite every byte before anyone reads it.

`python3 bench/compare.py --app numeric_scale_binary`: ail/c went from 1.371 [1.360, 1.382] to
1.226 [1.217, 1.235], ail/base 0.895 [0.885, 0.906] (about 10.5% faster); output was identical and
the ranges do not overlap. Probes over int/float comprehensions (empty, negative, aliased, sliced,
argument/attribute/dict/list-item sources, calls, filters, mid-loop exceptions, repeated loops)
matched CPython on both builds.
## 2026-10-24 -- pre26: repr(e.args[i]) keeps the argument's kind

On the typed path `e.args[i]` reads as text, so `repr(e.args[i])` repr'd that text: a
`ValueError(3.0)` handler printed `'3.0'` where CPython prints `3.0`, and int, bool and None
arguments were quoted the same way.  The handler rewrite now lowers `repr(e.args[i])`,
`f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor that formats
the stored argument (a str keeps its quotes, a number does not).  Both builds agree with
CPython; `test_ail_pre26.py` keeps the probe, including negative and out-of-range indexes.

## 2026-10-24 - pre54: round() at the int64 boundary is refused by name

The pre35 review recorded `z_intmin` (`round(-9223372036854775808.0)` then `abs`, unary `-`, `* -1`)
as a pre-existing difference: CPython's unbounded int answers 2**63, while both builds compiled the
program and stopped later with `integer overflow`.  The rounded value is INT64_MIN, which is
representable, but its magnitude is not; the value is known at compile time, so a one-argument
`round()` of a constant float at or beyond the int64 boundary is now refused by name in
`pyc.build` on both builds rather than compiled into a program that stops later.  Values just
inside the boundary, two-argument `round()` (a float result) and a user-defined `round` are
unchanged.  Added `AIL_CURRENT/test_ail_pre54.py` and registered it in `ail_check.MODULES`.
## 2026-10-24 - qtest1: __index__ returning None is not a default bound

Review found that the str search window accepted any converted bound whose tag was
None. A class whose `__index__` returns None (`N()` in
`"abcabc".startswith(("bc",), N())`) was silently treated as "no bound" and returned
True/1/2/1 where CPython raises `TypeError: __index__ returned non-int (type NoneType)`.
The window's tag test now allows None only when the dunder lookup did not run (its
`had` flag is 0); test_ail_qtest1 covers startswith/endswith/find/count/index plus
values through a list item and a dict.

## 2026-10-24 - qtest1: str search start/end bounds use __index__

`str.startswith`/`endswith` (and `find`/`count`/`index`) read an instance start/end
as its pointer payload after the general path's tag check rejected `AIL_T_INST`.
`"abcabc".startswith(("bc",), Idx(1))` with an `__index__` class printed a caught
TypeError where CPython returns True. The shared str window now converts an
instance bound through `__index__` with CPython's slice-index messages (None still
means the default bound), and the static check admits instances so the runtime
conversion is reachable. Added `AIL_CURRENT/test_ail_qtest1.py`; tuple prefixes,
empty prefixes, None, negative/huge bounds and wrong types stay compared on both
builds.

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
