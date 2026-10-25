## 2026-10-25 - pre141 review follow-up: closure-context def flags (job-rbpre141-10251549)

Review defect: a nested `def` with a non-literal or mutable default inside an escaping nested
function (`outer` returned as a value) reached `boxclosure._emit_closure_function`, whose C
preamble never declared the `def`-binding flags that `stmt_FunctionDef` emits. The general path
failed to compile (`'_ndef1' undeclared`) and the default path then refused by name. The preamble
now declares every `cctx.def_flag_decls` entry, as `_emit_function` and `_register_nested`
already did. Probes `d1`-`d6` in `/tmp/probes` cover the review case, non-literal defaults built
from captured names, shared dict/set/bytearray/tuple-with-list defaults, keyword-only (refused by
name), redefinition, and literal defaults on both builds; all match CPython except the refusal.

## 2026-10-25 - pre141 re-applied: nested-def defaults evaluated once at the def (job-rbpre141-10251549)

The accepted pre141 change (nested `def` defaults evaluated once, when the `def` statement runs)
was re-applied on top of the current tree. A default that is not a literal scalar/tuple, and a
mutable literal default such as `[]`, `{}` or `set()`, is now evaluated into a hidden local at
the `def` statement; the call site reads that local, so reassigning the source name afterwards
does not change the default and a shared list stays shared between calls. The hidden name avoids
every name the enclosing function mentions (`ident_names`). Literal scalar/tuple defaults still
fill in at the call site. `**kwargs` and positional-only parameters remain refused by name.
Adapted to the tree's later def-binding flags and module-level default hoisting; added
`AIL_CURRENT/test_ail_pre141.py`, and the earlier pre89/pre117/fuzz94/fuzz87 checks now compare the
shared default instead of expecting a refusal. The same tree already had `round()` and other fixes,
which are unchanged.

## 2026-10-25 - int(bytearray, base) error text (job-pre192-10251808)

The first still-differing item from the memsafe2 review was the `int(bytearray, base)` invalid-literal
message: `int(bytearray(b"x"), 10)` printed `invalid literal for int() with base 10: bytearray(b'x')`
on both builds, where CPython prints `...: b'x'`.  CPython parses the bytearray as bytes and formats the
message with the bytes repr.  The prelude's `_ail_int2` now uses `"b" + _ail_b_repr(s)` for a bytearray,
and `bytearray.__int__` does the same for the no-base form.  Both `int` message paths also apply
CPython's 200-character `%.200R` cut; that was already missing for a long `bytes` argument as well.
`float(bytearray(...))` still names the bytearray repr, as CPython does, and bytes inputs are unchanged.

The new `test_ail_pre192.py` covers direct calls and an argument, list item, attribute, dict value and
alias, bases 0/2/8/10/16/36, empty, packed bytes (0, 255, quotes, controls), non-ASCII, signs,
whitespace, underscores, prefixes, lengths 199/200/201/300, valid values and the bytes baseline, on both
builds.  `/tmp/probes/p_intba*.py` match CPython on both builds (keyword `base` is a separate pre-existing
limitation and was not part of this fix).
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
## 2026-10-25 - constant int64 index overflow is refused by name (job-rbpre177-10251802)

Re-applied the accepted job-pre177 change on top of the current tree. `AIL_CURRENT/ail_chatgpt.py`
now evaluates constant integer arithmetic in the existing `_check_int64_literals` pass. A constant
subscript index whose value or an intermediate step leaves int64 is refused with
`int64 index out of range: <value>`; a constant `**` outside int64 is refused with
`int64 constant out of range: <value>` where it reaches an argument, a list item, an attribute or
a dict value. Both refusals exit 2 and build no executable. In-range constant index expressions
(`xs[2**1]`, `xs[1<<1]`, `xs[(2**62)//(2**61)]`, ...) are unchanged and match CPython on both builds.

The re-application had to reconcile later fixes that the accepted change predates: the whole
enclosing constant expression is folded exactly first, so `2**63 - 1`, `2**64 // 2 - 1` and
`2**65 - 2**65` still work (pre113); a simple assignment right-hand side keeps its run-time
overflow trap (pre160 and the multifile big-pow case); and a str.split/rsplit maxsplit keeps its
own `maxsplit constant does not fit` refusal (pre97). The new helpers live beside the existing
`_constant_int(node, known)` without changing it.

Probes in `/tmp/probes` cover list/str/bytes/tuple indexes, negative and shifted huge indexes,
an intermediate overflow whose final value is in range, the four value flows, the in-range
boundary, and the pre113/pre160 conflicts; every probe matches CPython or is refused by name.
`test_ail_pre177.py` is registered in `ail_check.MODULES` and `tools/ci_shards.json`.
## 2026-10-25 - re-apply pre89: mutable default of a nested def

Re-applied accepted job `pre89` on the current tree. The behavioural fix is already present from
the pre117 export: a nested `def` with a literal list/dict/set (or a tuple holding one, including a
`bytearray`) default is refused by name (`a nested def f with a mutable literal default ...`) on
both builds, instead of rebuilding the default per call, so the two fixes were kept together. The
job's `test_ail_pre89.py` is added and registered in `ail_check.MODULES`; it covers list, dict,
set, tuple-of-list and keyword-only defaults, immutable/top-level mutable defaults, and the p18
(instance-attribute callable) and p23 (keyword arguments through a function value) refusals. The
DIFFERENCES row is recorded with this branch's placeholder id.
## 2026-10-25 - re-apply pre93: bare annotation target subexpressions (job-rbpre93-10251804)

Re-applied job `pre93` on top of the current export. A function-local bare annotation such as
`box().x: int` or `xs[i()]: int` dropped the target's subexpressions, so the calls did not run.
The surface now emits the target's value and slice parts (recursively flattening a `Slice` or
`Tuple` inside a subscript, through the normal rewriter so imported names work) without reading
the attribute or performing the final subscript, and never evaluates the annotation, matching
CPython. The tree already had the later module-scope fix (`module_bare_annotation`), so both were
kept: module bare annotations still evaluate the target and a non-static annotation in CPython
order, while function-local targets use the new path; class-body attribute targets stay `pass`.
`test_ail_pre93.py` is registered in `ail_check.MODULES`, the DIFFERENCES row is restored, and the
function, future-annotation, imported-name, tuple-slice and module cases run on both builds.
## 2026-10-25 - re-apply fuzz94: mutable default of a nested def

Re-applied job `rbfuzz94` on top of the current export. The tree already refused a nested `def`
with a mutable literal default from the fuzz87/pre117 fixes, so both sides were kept: the existing
helper covers a list/dict/set/bytearray (including inside a tuple) and its message names a
"mutable literal default". Added `test_ail_fuzz94.py` and registered it in `ail_check.MODULES`;
immutable defaults, keyword calls, recursion, loop closures with `nonlocal` and early returns
still match CPython on both builds.

## 2026-10-25 - int(s, base) message GC rooting (job-pre180-10251520)

Review follow-up. The rewritten general-path `ail__int_badlit` built the message head string,
called `ail_str_repr` (which allocates), and only then rooted the parts array; with the normal
GC threshold the fresh head survived, but under `-DAIL_GC_STRESS` + ASan it was freed before
use. All three slots are now zeroed and registered as a frame before the first allocation, and
the repr view is cut into one of the rooted slots. The ASan GC-stress probe
(`int("\u2469", 16)`, `int("1_\u2469", 16)`, `int("", 16)`) now prints the three messages and
exits 0; the normal-build message, cut and route probes still match CPython.

## 2026-10-25 - int(s, base) error message (job-pre180-10251520)

The first still-differing item from the fuzz58 review was the `int(s, base)` invalid-literal
message. `int("\u2469", 10)` printed `invalid literal for int() with base 10: 'i'` (the low
byte of U+2469) on both builds, where CPython prints `'\u2469'`; long literals also lacked
CPython's 200-character repr cut (`%.200R`). The live general-path helper copied each UTF-16
unit of `repr(s)` into a `char`, so it now composes the message from the repr string itself
and views only its first 200 code points. The typed path's `ail__int_base_fail` already kept
the full characters but printed the whole repr, so it now applies the same 200-code-point
cut. Valid Unicode decimal digits and the existing quote/escape handling are unchanged.
Probes in `/tmp/probes` covered BMP printable characters in the argument, a list item, an
attribute and a dict value, bases 0/2/10/16/36, prefix/underscore/quote/control cases, short
and 300-character literals, and the typed `str`/`int` path; all match CPython on both
`cmp.sh` builds. `test_ail_pre180.py` keeps the general and typed cases.
## 2026-10-25 - bytes padding names the fillchar type (job-pre182-10251541)

The fuzz51 review item was documentation-only (the `None` fillchar is already fixed),
but the same `_ail_b_fill` guard still differed for every other non-bytes fillchar:
`b"abc".ljust(5, "x")`, `b"abc".rjust(5, 1)` and a user-class value raised the generic
`a bytes-like object is required, not '<type>'` because `_ail_bs` converted before the
method-specific check. CPython says `ljust() argument 2 must be a byte string of length
1, not str` (and likewise for rjust/center, with the value's type name). The guard now
checks bytes/bytearray membership first; length errors on a bytes/bytearray fillchar
still name bytes/bytearray, and `None` keeps fuzz51's `not None`. `test_ail_pre182.py`
covers direct values, arguments, list items, attributes, dict values, valid single-byte
fills, empty and multi-byte fills, widths around the text length, and both builds.
`test_ail_fuzz51.py` still passes.
## 2026-10-25 - range slicing (job-pre185-10251543)

The first still-differing item from the fuzz48 review was range slicing: `range(10)[2:5]`,
`range(10)[::-1]` and every other slice of a range raised `TypeError: 'range' object is not
subscriptable` on both builds. `ail_op_getslice` now handles `AIL_T_RANGE`: it adjusts the
slice against the range's count (CPython's PySlice_AdjustIndices rules, including negative
steps and empty results), maps the adjusted ordinals back through the range's own start/step,
and returns a new range. The arithmetic is done in 128 bits because a range's count can exceed
INT64_MAX; a result whose start/stop/step would fall outside int64 is the AIL int limit and is
recorded in DIFFERENCES. Added `test_ail_pre185.py` (literal, empty, negative, bool-index,
int64-boundary and argument/list-item/attribute/dict routes on both builds). Probes p8 in
`/tmp/probes` matched CPython on both builds; an earlier probe showed the out-of-int64 reverse
case stops with `integer overflow`.
## 2026-10-25 - pre188: abs() of negative zero (job-pre188-10251545)

The first still-differing item from the task's list was `abs(-0.0)` printing `-0.0` (CPython `0.0`) on the
default/typed path. Both typed lowerings wrote `x < 0 ? -x : x`, and that comparison is false for negative
zero, so the sign survived: the legacy emitter in `pyfunc.py`, and the IR lowering in `ir/lower.py` (which
emitted `fneg` + `select`). Floats now use a sign-clearing absolute value (`__builtin_fabs`) in both places;
the new IR `fabs` op is verified, emitted and treated as pure. The integer lowerings are untouched, so the
declared `abs(-2**63)` integer-overflow stop (`p8`) remains as before.

Probes in `/tmp/probes` (`p_abs`, `p_abs_fn`, `p_abs_typed`, `p_abs_routes`, `p_absfull`) covered literals,
a float parameter (IR), a plain function argument, an alias, a list item, an attribute, a dict value,
`-0.0` from arithmetic, subnormals, infinities, NaN, booleans, signed zero comparisons and the int64
boundary on both `cmp.sh` builds. All matched CPython. `test_ail_pre188.py` runs the same routes on both
builds.
## 2026-10-25 - pre103 re-apply: a single NUL byte is a format code

`format(1, '\x00')`, `format('a', '\x00')` and the same spec after a width, sign
or grouping flag returned the value on both builds; CPython raises `ValueError:
Unknown format code '\x0' for object of type 'int'` (or `'str'`).  The general
formatter's spec parser recorded the NUL only as `type == 0`, which is also how
it spells "no type"; it now tracks the presence of a type separately, so a NUL
reaches the unknown-code error.  A float keeps CPython's quirk of accepting the
NUL as no type, and None/instance keep the TypeError naming the class.  Unknown
control codes now use CPython's `\x<hex>` spelling in the message.
`test_ail_pre103.py` covers int/bool/str/float/None/instance values, width and
flag boundaries, and a spec arriving through an argument, a list item, an
attribute and a dict value on both builds.  NUL followed by another character
still uses the pre-existing generic `Invalid format specifier` text.

## 2026-10-25 - re-apply pre117: mutable literal defaults of nested defs

Re-applied job `pre117` on top of the current export. The tree already refused a nested `def` with a
mutable literal default from the fuzz87 fix, so both sides were kept: the one helper now also covers
a `bytearray` in a literal (as the accepted change did) and its message names a "mutable literal
default", which keeps the new `test_ail_pre117.py` and the existing `test_ail_fuzz87.py` refusal
checks satisfied. `test_ail_pre117.py` is registered in `ail_check.MODULES`, the DIFFERENCES row is
restored, and immutable defaults still match CPython on both builds. Probes and required tests are
listed in the job report.
## 2026-10-25 -- statically known unary int64 overflow (job-rbpre172-10251601)

The first pre-existing difference left by job-pre108 was pure unary overflow: `-MIN`, both on a
module constant and as `-(-9223372036854775808)`, compiled on the default build and then stopped at
run time with `integer overflow`, while CPython printed a bignum; the general path refused the
`MIN` literal with a different message. A new front-end check evaluates unary `+`/`-` over integer
literals and module-level int constants and refuses an out-of-int64 result by name (`int64 constant
expression out of range: ...`) on both builds. A module constant shadowed by a parameter is not
folded, and values that only reach the unary operation as variables keep the fixed-width trap.
Added `test_ail_pre172.py` and registered it in `ail_check.MODULES`.
## 2026-10-25 - contextlib re-raises a sent StopIteration (job-pre181-10251538)

The first still-differing item from the task list was `p_stopiter`: a `StopIteration` raised
inside a `with` body reaches the `@contextmanager` generator through `send()`, which re-raises it,
and the generator runtime's PEP 479 conversion turned it into
`RuntimeError: generator raised StopIteration` on both builds. CPython also makes that RuntimeError,
but it sets `__cause__` to the escaping StopIteration and `contextlib.__exit__` recognises the
cause, returns false, and lets the `with` re-raise the original StopIteration. The conversion in
`safetyrt.py` now stores that exact object in a private attribute id (`AIL_ATTR_GEN_CAUSE`), and
`_AilGenCM.__exit__` in `prelude_with.py` checks it through a small internal primitive, matching
CPython's `isinstance(value, StopIteration) and exc.__cause__ is value` branch. Ordinary
`getattr(e, "__cause__")`/`__context__` reads still refuse chaining (test_ail_pre179 passes), and a
generator that catches the sent value and raises a *different* StopIteration still gives
RuntimeError.

Probes in `/tmp/probes` (`p_si1`-`p_si10`, `p_stopiter_k`, `p_cause_hidden`) covered builtin and
user-subclass StopIteration, a replacement StopIteration after catching the sent one, replacement
ValueError, a contextmanager method, nested managers, sources through an argument / list item /
attribute / dict value, clean and suppressing exits, raw PEP 479, and both builds; all match CPython
or keep the existing named refusal. `p_tb` still differs (`tb is None`), as recorded in
DIFFERENCES (`C?-job-pre181-10251538-2`) and not touched here. Added `test_ail_pre181.py` (3
programs, two builds each, 20s). Required modules on the final commit: test_ail_pre181,
test_ail_pre179, test_ail_fuzz56, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3
all pass (6 modules, 371s, `-j 2`).
## 2026-10-25 - re-apply pre137: negative r in the itertools choosers (job-rbpre137-10251548)

Re-applied the accepted pre137 change on the current tree. `permutations`, `combinations` and
`combinations_with_replacement` with `r < 0` returned `[]` on the general path; CPython raises
`ValueError: r must be non-negative`. The shared chooser runtime now raises that catchable error
after the pool is materialized, so a non-iterable argument still raises TypeError first, as in
CPython. Coverage: `r` reaching the call as a literal, a local, an argument, a list item, an
attribute and a dict value, plus r = 0, r > n, an empty pool and booleans. Added
`AIL_CURRENT/test_ail_pre137.py` and registered it in `ail_check.MODULES`. Other observed, not
fixed (identical on the base): a float, str or explicit None `r` still disagrees with CPython
(`permutations(xs, 1.5)` prints `[]` instead of TypeError, `combinations_with_replacement(xs, None)`
prints `[()]`), and explicit `permutations(xs, None)` is treated as 0 instead of the omitted
default. The default build also cannot compile a top-level `print(list(itertools.permutations(...)))`
(a pre-existing typed-list error, the same with a non-negative `r`).
## 2026-10-25 - pre170 review follow-up: class-name rebinding before the definition (job-rbpre170-10251554)

Review fix. The module slot for a class name was bound in the hoisted `setup`, before any module
statement, so a module-level assignment before the class definition (`C = None; class C: pass`)
replayed afterwards and the class never rebound it: `C is None` printed True where CPython says
False. The binding is now emitted at the class-definition point in the module body (and in the
array-entry shape's class-init sequence), so assignment order decides the value in both directions.
`test_ail_pre170.py` gained `test_assignment_before_the_class_definition`.

## 2026-10-25 - pre170 re-applied: last duplicate class-body attribute through a class value (job-rbpre170-10251554)

Re-applied the accepted pre170 change on top of the current tree. A class body with a duplicate
assignment (`class C: x = 1; x = 2`) read through an alias, an argument, a list/dict item, an
instance attribute or `getattr()` returned the first value (or raised `AttributeError` for an
aliased class), where CPython keeps the last. The general path now registers every class-body
entry in source order on the class object and the runtime lookup scans each class backwards, so
the last definition wins; a module-level rebinding of the class name is bound at definition time,
the array-entry shape evaluates the class bodies before the entry call, and reading a
method/property through a directly known class value is refused by name. Added
`test_ail_pre170.py` (4 tests, both builds); probes `p_dup`, `p_dup2`, `p_sources`, `p_missing`,
`p_array`, `p_shadow` and `p_attr` match CPython.

## 2026-10-25 - pre87 review: callback exceptions cross back to boxed try

The default build still aborted on `% 0` (and `// 0`) raised through a lambda or a
helper passed as a value. `pymix.py` selected a typed clone for the helper, and the
clone's `ail_die` trap only unwinds the typed `try` stack; the boxed caller's `try`
lives on `ail_ctx` and never saw it. An escape analysis already rejects clones whose
exceptions reach a boxed `try`, but it only followed direct `Call(Name)` edges, so a
lambda body or a function passed as a value looked like an uncaught module-level path.
`_protected` now treats both as possibly-protected: names referenced as values and
call sites inside a lambda are not mixed, so the call stays boxed and returns its
error through `cx`. Added `CALLBACK_ZERO` to `test_ail_pre87.py` (lambda, named
callback, list item, dict value, alias, `//`, `divmod`, negative, INT64_MIN, bool,
IntEnum, IntFlag).

## 2026-10-25 - pre87: integer modulo by zero names CPython's message

The general path and the default build's fallback reported
`ZeroDivisionError: integer division or modulo by zero` for integer `% 0`.
CPython reserves that text for `//` and `divmod`; `%` raises
`integer modulo by zero`.  Both emitters now pass the shorter text from
`ail_obj_mod` and `ail_op_mod`, while the floor-division helpers keep
CPython's wording.  `test_ail_pre87.py` compares both builds with CPython for
a plain helper, a typed helper, a lambda, a list item, an attribute, a dict
value, negative and INT64_MIN dividends, bools, an IntEnum and an IntFlag; a
second program keeps the neighbouring `//`, `divmod` and float zero messages
unchanged.
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
## 2026-10-24 - build time in the AIL/C/Rust comparison (job-bench2-10241946)

`bench/compare.py` now records build wall time in the existing post-timing build-disk pass: the median
of three cold builds (fresh build directory, `AIL_CACHE` and TMPDIR) and three incremental builds after
appending one harmless comment line to the app's AIL, C or Rust source with the caches warm. The JSON
has `build_time_ms` and the table has `cold build s ail/c/rust` and `incremental build s ail/c/rust`
beside the unchanged columns. The full run is in `bench/results/2026-10-24-buildtime.md`: AIL cold
builds took 2.02-7.12 s versus C 0.07-0.34 s and Rust 2.40-2.61 s; AIL incremental builds took
0.17-0.40 s. Timestamped cold compiles (LD_PRELOAD exec/exit log) spend 55-65% in the AIL front end,
31-44% in the C compiler and 2-3% linking. No language behaviour changed, so no DIFFERENCES row.
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
## 2026-10-24 - pre101: `itertools.permutations(xs, None)` (job-pre101-10242138)

CPython treats an explicit `r=None` as "not given" and yields every full-length permutation.
The general path (`pyboxed2._lib_permutations`) passed the None through as r=0 and returned
`[()]`. It now treats a literal/keyword None as omitted and, for a value known only at run
time, passes `has_r = (r.tag != AIL_T_NONE)` so a None argument/attribute/list item/dict value
is handled the same way. The typed path already handled the literal None; a None-typed
variable is refused by name there (no null value), so the default build falls back to the
general path. `AIL_CURRENT/test_ail_pre101.py` covers both builds.
## 2026-10-24 - pre102: format() of None / an instance without __format__

The general runtime parsed the format spec before it dispatched on the value, so `format(None, ' +8')`
and `format(Box(1), ' +8')` raised `ValueError: Invalid format specifier` where CPython's
`object.__format__` rejects any non-empty spec with
`TypeError: unsupported format string passed to NoneType.__format__` (resp. `Box.__format__`).
`safetyrt.py` now does that rejection before `ail2f_parse`; str/int/bool/float keep parsing, and an
instance that defines `__format__` is still dispatched first by dunderrt. Added
`test_ail_pre102.py` (one program, both builds, values through an argument, list item, dict value,
attribute, f-string and str.format, plus an empty spec and a custom `__format__`).
The NUL / non-ASCII unknown-code difference (a NUL spec still formats as if empty) is pre-existing
and not touched by this job. Verified with `test_ail_pre102`, `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3`: 26 tests, all OK.

## 2026-10-24 - pre104: round() of nan/inf raises CPython's exception

The pre54 review recorded the default build's one-argument `round()` of nan/inf as a
pre-existing difference: it stopped through `ail_die` with `round() of nan` or
`round() result does not fit in this language's int64`, so a `try` could not catch it and an
uncaught program printed the trap message instead of CPython's exception line.  `ail_round0`
now raises `ValueError("cannot convert float NaN to integer")` and
`OverflowError("cannot convert float infinity to integer")` through the normal exception path
on both builds.  Finite values, including the int64-boundary trap, are unchanged.  Added
`AIL_CURRENT/test_ail_pre104.py` and registered it in `ail_check.MODULES`.
## 2026-10-24 - pre105: a multi-name import refusal names the unmodelled module

The exact errmsg3 case `import math, html` (with `html` used, so the general path refuses too)
reached the typed path's module scan, which joined every alias into one name and printed
`import of 'math, html' is not available` at the import's line.  That denied the supported
`math` and did not say which module was missing.  The scan now picks the first name outside the
modelled set (`html`, or `html.parser`) and names it alone; an unused `html` import still builds
on both paths.  Added `AIL_CURRENT/test_ail_pre105.py` (eight refusals, both builds, plus the
accepted unused case).
## 2026-10-24 - pre107: random.expovariate's default rate

Job cov8 recorded `gauss(mu)` / `expovariate()` without defaults as pre-existing. On this
tree `random.gauss(2.5)` already matches CPython on both builds; `random.expovariate()` and
`Random.expovariate()` were still refused because the two Random preludes declared
`expovariate(lambd)` without CPython 3.12's `lambd=1.0`. Both now default to 1.0.
The module-level function and a `Random` object match CPython after `random.seed(<int>)`,
including explicit int/float/negative/infinite rates, keyword calls, a zero rate's
`ZeroDivisionError`, and rates passed through an argument, a list item, an attribute and a
dict value. On this tree the default build reaches the general path for these programs:
the typed path still refuses `Random` for its plain-positional `randrange` requirement (an
unrelated pre-existing gap). Added `AIL_CURRENT/test_ail_pre107.py`.
## 2026-10-24 - pre112: a frozenset of tuples as a dict key (job-pre112-10242224)

The tuple pass (`tuplib.py`) lowers `frozenset({(1, 'a'), (2, 'b')})` to its `_AilS_Pi_sQ` table class. The
table refuses a set as a key, so a dict keyed by that frozenset stays a plain object, but the same expression
used as the *lookup* key was still lowered: `D[frozenset({(1, 'a'), (2, 'b')})]` raised `KeyError`,
`frozenset(...) in D` was False and `D.get(...)` was None, while the dictionary itself printed correctly (the
reviewer's `t4h`, also on base). The pass now refuses a set / frozenset of tuples used as the key of a
container that is not a table dict (`tupexpr.ex_Subscript`, `tupstmt.assign_one`) and bails on a module-level
constant whose type cannot be told and that mentions a tuple (`tuplib.module_assign`), so the whole program is
left as written and the general path keeps the dict and the key boxed. Added `test_ail_pre112.py` (4 programs,
two builds each). Verified with 15 differential probes (`cmp.sh`, both builds) plus `test_ail_tuples`,
`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_collections`,
`test_ail_sets_general` and `test_ail_modconst`.
## 2026-10-24 - pre113: fold all-int constant expressions exactly

`(1 << 63) - 1` and `2**65 - 2**65` are exact in Python even though an intermediate is outside
int64; both builds used to emit checked operations for the intermediate and stopped with
`integer overflow`.  `pyfront.int_constant` now evaluates an all-int constant expression with
Python ints (with a size limit for giant intermediates), and the typed IR, legacy typed emitter,
unified general path and boxed emitters emit the one int64 result.  Added `test_ail_pre113.py`
(one program, four build modes); the second listed case, a module constant exponent, is still a
separate difference.
## 2026-10-24 - pre114: bytes/bytearray membership type-error text

`x in b`, `b.__contains__(x)` and the bytearray forms now raise CPython 3.12's
`TypeError: a bytes-like object is required, not 'T'` for a non-index, non-bytes-like
item (str, float, None, list, user class). Both builds used the shared substring
helper, whose wording belongs to find/index/count/replace ("argument should be integer
or bytes-like object"); membership now has its own conversion. Ints 0..255, bools,
bytes and bytearray membership are unchanged. Added `test_ail_pre114.py`, which covers
items reaching the code through an argument, a list item, an attribute and a dict
value on both builds. Non-index start/stop bounds for bytes search remain a separate
open difference and are not changed here.
## 2026-10-24 - Counter(mapping) keeps its values (job-pre120-10242313)

CPython 3.12's `Counter.update(mapping)` uses `dict.update` when the counter is empty and only
adds `count + self.get(elem, 0)` when it is not. Every constructor starts empty, so
`Counter({"a": "x"})` keeps `"x"`; the general path added `0 + "x"` for each entry and raised
`TypeError`, and `Counter().update({"a": "x"})` did the same. `ail_counter_update_map` now takes
CPython's empty-counter branch (copy the values), while a non-empty update still adds counts and
keeps CPython's operand order in the TypeError it can raise. The same change sorts string counts in
Counter's `repr` in most_common order and makes the operators' comparison with 0 name the operator
CPython names. Added `AIL_CURRENT/test_ail_pre120.py` (five programs, both builds) and registered it
in `ail_check.MODULES`.
## 2026-10-24 - pre124: module-scope annotations are evaluated

A module-level `target: annotation` without a value dropped the whole statement on both builds:
`touch(b).x: ann()` never called `ann` and `xs[touch(i)]: ann()` never evaluated `xs` or `i`
(CPython evaluates the target parts and then the annotation). An annotated assignment with a value
also never evaluated its annotation. `ail_syntax` now keeps those evaluations in one expression or
semicolon statement, in CPython order, for every target form (name, attribute, subscript, slice and
extended slice). Under `from __future__ import annotations` only the target is evaluated, as in
CPython, and static type expressions (`int`, `list[int]`, `A | None`) stay unevaluated. Added
`AIL_CURRENT/test_ail_pre124.py`.
## 2026-10-24 - pre127 review fix: a shadowing binding also wins at a call site (job-pre127-10242351)

The review found two defects in the r6 fix.  `expr_Name` read a parameter, local, cell or
closure binding instead of the class, but `_call_name` still checked `self.classes` first, so
`U()` in the same activation called the class constructor regardless.  A self-referential
`U = U()` in a function therefore constructed the class and silently succeeded instead of
raising `UnboundLocalError` (also for `U: object = U()` and `U, x = U(), 5`), and a loop target
`for U in items:` left `U()` after the loop calling the class instead of raising `TypeError` on
the instance.  `_call_name` now applies the same shadowing test as `expr_Name` before taking
the class-constructor path.  `test_ail_pre127.py` gains both shapes; the probes also cover an
unshadowed constructor, `global U`, a parameter holding the class itself, local/cell bindings
of an instance, list/attribute/dict sources of a class value, an empty loop and a use before
the assignment.  Module-level `U = U()` (already different on the base tree) is unchanged.

## 2026-10-24 - pre127: a parameter or local shadows a class name (job-pre127-10242351)

The first still-differing item from the pre96 list is `r6`: the general emitter's
`expr_Name` returned the module-lifetime class value for every name that matched a class
definition, even when the current function had a local slot for that name.  In
`class U: ...; def f(U): return U.m()` the argument was ignored: both builds read the class
object and raised `AttributeError: 'type' object has no attribute 'm'` where CPython returns
42 from the instance's class attribute or method.  A class name now becomes a class value
only when the activation has no parameter, local, cell or closure binding for it; a
shadowing binding is loaded from its own slot.  The probes cover a nested parameter, a method
parameter, a local, a cell, a `nonlocal` closure, an annotated parameter, and values arriving
through a list item, an attribute and a dict value.  `r7` (`cls.__name__`), `r8`
(`K = "abc"; f = K.upper`) and `r9` (class through a list item, `[U][0].m`) still differ on
this tree and were not changed.  `test_ail_pre127.py` keeps the r6 probes; emitted C is
unchanged for a program that does not shadow a class name.

## 2026-10-24 - pre117: mutable literal defaults of nested defs

A nested `def` with a literal list/dict/set default (or a tuple holding one) rebuilt the default
at every call site. `def f(x, acc=[]); f(1); f(2)` printed `[1] [2]` where CPython shares the
object built when the `def` ran and prints `[1] [1, 2]`; an empty default was wrong by identity
even when one call hid it. The general path now refuses the construct by name on both builds,
matching the fuzz94 fix. An immutable-default program (negative/int-boundary, empty tuple, tuple,
values through an argument, a list item, a dict value and an attribute) still matches CPython.
Added `AIL_CURRENT/test_ail_pre117.py` and registered it in `ail_check.MODULES`.
## 2026-10-25 - pre116 review fixes: unsafe constructors stay refused

The saved-generator screen no longer trusts a class merely because `__new__`/`__init__` exist.
A class is kept on the eager lowering only when it is plain (no bases other than `object`, no
decorators/metaclass, no `__new__`, `__slots__`, `__setattr__`/`__getattr__`/`__getattribute__`/
`__delattr__`) and its `__init__` only assigns its parameters or constants to `self`; inherited
constructors, non-division `BinOp` bodies (`1 + "a"`), custom attribute hooks, `__slots__`, free
names, a rebound or deleted class name and a shadowed/deleted `next` are refused by name.  Defect
probes (`Bad.__init__` with `1 + "a"`, inherited raising `__init__`, `C = boom`, plus slots,
custom `__setattr__`, free name, `del C`, arity, alias/attribute rebinding) are refused on both
builds; safe `next`/parameter-constructor saved generators match CPython on the simulated
integration tree.  `test_ail_pre116.py` has the new controls.  On the simulated integration tree
(`origin/integ` ffeb623 + this diff) `test_ail_pre116`, `test_ail_pre166` and
`test_ail_typed_tuples` pass together (20 tests); on this branch `test_ail_pre116`,
`test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` pass (`-j 2`).

## 2026-10-25 - pre116: keep pre166's saved-generator shapes compiling

The pre116 refusal was too broad for the integration branch's pre166 cursor-list
generators: it refused a saved generator whose body called `next(...)` or a class
constructor, so `test_ail_pre166` failed.  Those two shapes now stay on the existing
eager lowering when the class's `__new__`/`__init__` cannot raise (`self.v = v`), so
pre166's `nested` and `membership_dunder` cases pass.  The refusal still fires for a
user-function call, `int(...)`, a risky method, a subscript and a division/modulo by
a non-literal divisor, including a class whose constructor body divides.
`test_ail_pre116.py` gains controls for the safe `next`/constructor shapes and for a
refused raising constructor.  Simulated on origin/integ (ffeb623), test_ail_pre116,
test_ail_pre166 and test_ail_typed_tuples pass together (17 tests).

## 2026-10-24 - pre116: a saved generator expression that can raise is refused

The first pre-existing difference the pre87 reviewer recorded was `% 0` through a generator
expression: `g = (helper(5, 0) for _ in range(1)); next(g)` inside a `try` aborted on both builds.
The general path materialised every generator expression eagerly, so the error was raised at the
assignment rather than at `next()`, before the handler was live (the typed path already refused
the construct by name).  `pyboxed2.Compiler` now refuses a generator expression used as a value
when its lazy body contains a division/modulo by a non-literal divisor, a subscript, or a call
that can raise (`int`, `input`, `next`, a method outside the builtin value-type whitelist, or a
user function).  Immediate consumers
(`sum`, `any`, `all`, `list`, `tuple`, `sorted`, `for`, `*`, `join`/`extend`/`update`) and tuple
unpacking keep the existing eager lowering, so the common forms still match CPython.
`test_ail_pre116.py` covers assignment, argument, list item, attribute and dict value, plus `//`,
negative, bool, IntEnum and empty sources; it also keeps the immediate-consumer and
safe-returned-generator controls compared with CPython on both builds.

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
