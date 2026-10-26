## 2026-10-26 -- re-apply fuzz58: non-ASCII repr in int()/float() errors (job-rbfuzz58-10261656)

Re-applying the accepted fuzz58 change on the current integration tree.  The runtime fix is
already present here: `ail__raise_head_str` builds the ValueError text from an ASCII head plus
the repr's UTF-16 units, so `int("\u2469", 10)` keeps the circled digit (and `ail__repr_limited`
keeps CPython's `%.200R` cut for int()), while `float()` keeps the full repr as CPython does.
No cruntime change was needed; this reapply adds the accepted `AIL_CURRENT/test_ail_fuzz58.py`
and registers it in `ail_check.MODULES`.  Probes in `/tmp/probes`: `f58_int`, `f58_float`
(bases 0/2/8/10/16/36, empty, signs, long input, astral literals refused by name on both builds,
and values through an argument, list item, attribute, dict value and aliases) match CPython on
both builds.  Tests on the final tree: `test_ail_fuzz58`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (4 modules, 320 s, 0 failed; 1 skipped, no zig for Windows).
`python3 tools/diff_ids.py` is not present in this tree.
## 2026-10-26 -- re-apply pre2: out-of-int64 constant power is refused by name (job-rbpre2-10261658)

Re-applying the accepted pre2 change on the current integration tree.  The refusal is already
present here: pre121/pre177's generic constant-expression rule refuses `2 ** 63`, `(-2) ** 64`,
`2 ** 100000000` and the assignment/argument/list-item/attribute/dict routes by name, while
pre113's exact fold keeps `2 ** 63 - 1`, `(2 ** 63) >> 1` and `2 ** 63 - 2 ** 63` in range and
matching CPython.  The conflict resolution keeps that newer rule and does not add pre2's second,
power-specific refusal path.  Added the accepted `AIL_CURRENT/test_ail_pre2.py`, adapted to
accept the current tree's named wording and to check the now-in-range subtraction against
CPython, and registered it in `ail_check.MODULES` and `ci_shards.json`.
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and `--check`
passes.  Probes `pre2_*` in `/tmp/probes` on both builds: `pre2_inrange`, `pre2_bounds`,
`pre2_float` and `pre2_after` match CPython; `pre2_direct`, `pre2_assign`, `pre2_neg`,
`pre2_huge`, `pre2_arg`, `pre2_list`, `pre2_attr`, `pre2_dict`, `pre2_local` and `pre2_ail` are
refused by name.  Tests on the final tree: `test_ail_pre2`, `test_ail_pre113`,
`test_ail_pre121`, `test_ail_pre177`, `test_ail_pre97`, `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3` (8 modules, 379 s, 0 failed).

## 2026-10-26 -- re-apply pre29: invalid format specifier names spec and type (job-rbpre29-10261659)

Re-applied the accepted pre29 change on the current tree. Its `safetyrt.py` behaviour is already
present from the pre206/pre243 format work: `ail2f_bad_spec` builds the full 16-bit
`Invalid format specifier '<spec>' for object of type '<type>'` text (spec, controls, NUL and
non-ASCII units intact) for str, int, bool and float, `ail2f_unsupported` rejects object types
before the spec is parsed, and a lone non-ASCII type gives `Unknown format code '\x..'`.
No runtime edit was needed, keeping both sides' fixes. Added the accepted
`AIL_CURRENT/test_ail_pre29.py` (5 tests, both builds) and registered it in `ail_check.MODULES`;
DIFFERENCES row `C?-job-rbpre29-10261659-1`. `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes.

Probes in `/tmp/probes/pre29`: `pre29_invalid`, `pre29_sources`, `pre29_objects`,
`pre29_valid`, `pre29_unicode`, and `pre29_boundaries` (empty, sign/width/precision edges,
negative/zero, NUL/control/quote, long and non-ASCII specs, alias/argument/list/attribute/dict
routes, bool/int/float/str and None/list/tuple/dict/instance values) match CPython on both builds.
Final-state tests: pre29, safetynet, files and corpus_findings3.
## 2026-10-26 -- pre263 follow-up: inline tuple source (job-pre263-10261654)

The reviewer found the new row claimed a literal tuple source was covered, while
`int(("9999999999999999999",)[0])` still compiled and stopped with `integer overflow`.
`python_surface` rewrites that tuple to `_AilT_s(...).f0`, which `_constant_text` did not read.
It now follows the generated `_AilT_*` constructor and field chain, so the one-argument parse
sees the same constant text and refuses the out-of-range value by name; nested tuple sources
and `[-1]` work as well, and an unselected out-of-range sibling is not refused.  Added
`tuple_source` and `tuple_source_negative_index` to `test_ail_pre263.py`.  Probes
`/tmp/probes/pre263fix/t01`-`t20` cover direct/multi/negative/bytes/nested/whitespace, both
int64 boundaries, two-argument and explicit-base forms, argument/list-item/dict-value/class
attribute/module-alias routes, in-range values, invalid and empty text; every one matches
CPython or is refused by name on both builds.

## 2026-10-26 -- pre263: constant single-argument int(text) beyond int64 (job-pre263-10261654)

The task named a pre-existing difference from the bigint-fix05 review, but its list was empty in
the task text.  The first still-differing bignum item I could reproduce from the records was
`int("9999999999999999999")`: both builds compiled it and then stopped with `integer overflow`,
while CPython prints the bignum.  The two-argument `int(<text>, <base>)` form was already refused
by pre253, but a call with no explicit base (CPython's base 10) was not folded.

`_check_int64_int_base_constants` now also reads the one-argument form: when the text is a
constant str or bytes, it is parsed with CPython's default base and a value outside int64 is
refused by name at compile time (`int64 constant expression out of range`).  Constant module
names and aliases, literal list/tuple/dict sources, arguments, list items, class attributes and
dict values are covered; in-range constants, invalid literals, dynamic text and a rebound `int`
keep their previous behaviour.  Dynamic text above int64 still stops with `integer overflow`
(the existing open row `C?-job-rbrbrbrbmemsafe2-10261346-7`).

Added `AIL_CURRENT/test_ail_pre263.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.  Probes `/tmp/probes/pre263/p01`-`p12` cover direct/negative/bytes,
int64 boundaries, 19/100/4300-digit widths, module constants and aliases, argument/list item/
class attribute/dict value routes, list/tuple/dict sources, in-range values, invalid literals,
an explicit base and a dynamic helper; every probe matches CPython or is refused by name on both
builds.  Final-state tests: test_ail_pre263, test_ail_safetynet, test_ail_files,
test_ail_corpus_findings3.
## 2026-10-26 -- re-apply pre19: refuse `del` bounds a constant cannot evaluate in int64 (job-rbpre19-10261657)

Re-applied the accepted pre19 change on the current tree.  `pyfront.refuse_unrepresentable_delete_bounds`
evaluates a constant `del` index or slice bound exactly, keeping the intermediate-overflow flag (so
`del a[2**63 - 1]`, `del a[-2**63]`, `2**100000` and `2**100:2**101` are all caught), and refuses the
`del` by name on both the typed path (`pyfunc._stmt_inner`) and the general path
(`pyboxed2.Compiler.stmt_Delete`).  This tree's earlier checks already refuse compound constant
indexes and powers by name (`int64 index out of range` / `int64 constant out of range`), so the
accepted test accepts either named refusal; the new wording is exercised by the unary-int64 and
slice cases that reach the added helper.  In-range constants (`del a[1 + 1]`, `del a[-2:-1]`,
bool indexes) and the same expression outside a `del` are unchanged.

Follow-up for the full suite: the helper now treats the literal spelling `-9223372036854775808`
(unary minus on the Constant `2**63`) as INT64_MIN without an overflow, matching the compiler's
unary branch, so `del box.values[::-9223372036854775808]` in `test_ail_string_field_mutation`
still builds.  A computed `del a[-2**63]` (unary minus on a power) is still refused.

Added `AIL_CURRENT/test_ail_pre19.py` (3 tests, both builds), registered it in
`ail_check.MODULES` and `ci_shards.json`.  Probes `pre19_*` in `/tmp/probes` cover index, INT64_MIN,
huge power, huge slice/step, nested subscript, attribute, list item and dict value routes, a
function argument, representable bounds, bool indexes and the non-`del` expression: every one
matches CPython or is refused by name on both builds.  Final-state modules: test_ail_pre19,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (28 tests, 1 skipped, 0 failed);
`update_manifest.py --check` rc 0.  `tools/diff_ids.py` is not present on this tree.
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
## 2026-10-26 - re-apply pre31: int() of a float outside int64 (job-rbpre31-10261700)

Re-applied the accepted pre31 change on the current tree. The same scope-aware, value-exact refusal
is now part of `_check_int64_literals`, alongside the later int64 constant checks that this tree
already had; both sides' fixes are kept. Added `test_ail_pre31.py` and registered it in
`ail_check.MODULES`.
## 2026-10-26 -- re-apply pre36: fold constant chr() arguments before the non-BMP refusal (job-rbpre36-10261703)

Re-applied the accepted pre36 change on this integration tree.  The current general emitter already
refused a literal non-BMP `chr()` argument by name (pre90, with the 16-bit v2 runtime gate and a
separate surrogate literal check), so the conflict resolution keeps those refusals and adds pre36's
integer constant-expression folder (`_const_int`) ahead of them: `chr(+0x1F600)`, `chr(0xFFFF + 1)`,
`chr(0x8000 * 2)` and the shift/floor-div/mod/bitwise spellings fold to their value, and a non-BMP
result in U+10000..U+10FFFF is refused by name on the 16-bit general path instead of reaching
`ail_bi_chr`'s runtime fatal.  BMP results (including 0xFFFF), negative/out-of-range arguments,
bool/type errors, non-constant values and the typed/default build keep their behaviour; a non-BMP
value that is not a compile-time constant still reaches the old runtime fatal (pre-existing,
recorded in DIFFERENCES).  Added `AIL_CURRENT/test_ail_pre36.py`, registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes` (`pre36_literal`,
`pre36_expr_nonbmp`, `pre36_expr_bmp`, `pre36_routes`, `pre36_alias_bmp`) show the general path
refusing the non-BMP constants by name and both builds matching CPython for the BMP, boundary,
route, bool and error cases.
## 2026-10-26 -- re-apply pre41: nested generator expression as an any()/all() iterable (job-rbpre41-10261713)

Re-applied the accepted pre41 change on this tree. The current fused `any()`/`all()` path
short-circuits the outer generator, but an inner `GeneratorExp` used as that generator's
iterable still goes through `_open_iter_loop` -> `expr_GeneratorExp`, which materialises it as
an eager list. So `any(x for x in (mark(i) for i in [0, 1, 2]))` still ran the side effects
after the deciding element (`inner 0`, `inner 1`, `inner 2` where CPython stops after
`inner 1`). The named refusal is therefore kept, placed just before the fused path, and covers
the iterable reached directly, through an argument, a list item, an attribute, a dict value and
a second `for` clause on both builds. Eager iterables (list, tuple, str, dict, set, range, an
argument, a list comprehension) still build unchanged. Added the accepted
`AIL_CURRENT/test_ail_pre41.py` (8 refused shapes, one CPython-compared eager program) and
registered it in `ail_check.MODULES`. Probes `/tmp/probes/pre41_nested.py`,
`pre41_routes.py` and `pre41_eager.py`: the first two are refused by name on both builds; the
last matches CPython on both.
## 2026-10-26 - nested generator expressions (job-rbpre42-10261853)

Re-applied the accepted pre42 change on top of this tree.  The general path still materialises a
generator expression like a list comprehension, so a generator expression nested inside another
one was evaluated when the outer object was built (CPython creates it only when its element is
reached); the side-effect order differed and consuming the outer could end in
`AIL internal error: ail_it_next: unknown library iterator kind`.  Both general emitters now
refuse the nested construct by name, and the `next()` / `any()` / `all()` fused paths check the
outer argument too.  This tree's pre116/pre166 saved-generator screen (`a generator expression
used as a value`) would otherwise claim a nested one first, so the nested check runs before it;
that screen is kept unchanged for non-nested saved generators.  A generator expression with no
generator expression inside it, including one holding a list/set/dict comprehension, still builds
and matches CPython.  Added `AIL_CURRENT/test_ail_pre42.py` and registered it in `ail_check.MODULES`.
## 2026-10-26 -- review fix: pre47 refusal wording (job-rbpre47-10261854)

The pre47 reapply's refusal message carried the tree's older `int64 constant expression out of
range` phrase in its parenthetical, so `test_ail_pre191` failed on both builds: it requires a
function-body constant to be refused with `outside the signed 64-bit range` but not that older
phrase. Dropped the parenthetical phrase from `pyfront.fold_int_constants`'s refusal; the pass
still says `a constant integer expression overflows int64`, `outside the signed 64-bit range`
and `64-bit signed integer`, so `test_ail_pre47` and the integration-tree checks keep their
wording. No other behaviour changed.

Probes `/tmp/probes/review_*.py` on both builds: `review_dead_shift` and `review_unreached_shift`
are refused with the new wording (no older phrase), `review_refuse_argument` is refused by name,
and `review_live_shift`, `review_live_negative`, `review_inrange`, `pre47_inrange` and
`pre47_contexts` match CPython. Tests on the final tree: 12 modules (pre47, pre191, pre172,
pre203, pre214, pre248, pre253, pre215, pre184, safetynet, files, corpus_findings3), 0 failed;
`tools/update_manifest.py --check` passes.

## 2026-10-26 -- re-apply pre47: constant integer expressions (job-rbpre47-10261854)

Re-applied the accepted pre47 change on this tree. The generic exact folder
(`pyfunc._const_int_expr` / `fold_int_constant`) was already present for the general path, so the
conflict resolution keeps its zero/base shortcuts, bool-result handling and 2**22-bit budget
instead of pre47's narrower 4096-bit evaluator. `pyfront.fold_int_constants` now runs before both
builds (from `pyc.to_c` and `_build_unshadowed`): an in-range constant expression becomes one
int64 literal (`-2**63`, `2**63 - 1`, `-(-2)**63` is out of range) and an out-of-range one is
refused by name with the pre47 wording plus the tree's older `outside the signed 64-bit range`
phrase (the review fix above dropped the older `int64 constant expression out of range` phrase).
The pass
skips `str.split`/`rsplit` maxsplit arguments so their specific diagnostics survive, and skips
f-strings so a debug field such as `f"{-(1 << 63)=}"` keeps its source text. A digit starting a
rewritten expression is separated from an adjacent keyword, so `1 and+(1 << 62)` stays valid.
`pyfront._c_expr` now refuses an out-of-int64 literal and emits a folded INT64_MIN as
`(-9223372036854775807LL - 1)` rather than `ck_neg(9223372036854775808)`; `pyboxed` and
`pyboxed2` accept the same unary spelling. Added `AIL_CURRENT/test_ail_pre47.py` and registered it
in `ail_check.MODULES`. `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py`
was run and `--check` passes.

Probes in `/tmp/probes` on both builds: `pre47_inrange` and `pre47_contexts` match CPython
(boundaries INT64_MIN/MAX, negative and zero, power/shift/floor-div, bool shifts, argument, list
item, attribute, dict value, assignment alias, absorbing zero, f-string debug, keyword adjacency,
maxsplit in range); `pre47_refuse_pow`, `_negated`, `_decimal`, `_shift`, `_cancel`, `_huge`,
`_argument`, `_list`, `_attribute`, `_dict`, `_alias` and `_maxsplit` are refused by name on both
builds. Pipeline probes built with `pyc`: `sum((-2**63) ...)`, `x + (-2**63)`, `-1 << 63`, `max`,
guarded `min`, `(2**63 - 1)`, an empty input and the out-of-range refusal all answer CPython or
refuse by name. Tests on the final tree: 14 modules (pre47, pre203, pre204, pre236, pre241,
pre251, pre121, pre184, pre201, pre190, pre246, safetynet, files, corpus_findings3), 66 tests,
0 failed.
## 2026-10-26 -- re-apply pre48: exception argument `repr` and file OSError `args` (job-rbpre48-10261855)

Re-applied the accepted pre48 change on the current integration tree; its compiler edits
(`exctext.py`, `filert.py`, `pyfunc.py`) applied without conflicts, so both sides' fixes are kept.
Direct `repr(e.args[i])` now has the `_ail_exc_argrepr` intrinsic and runtime helper, which reads
the argument's own repr (str/int/float/bool/None, negative and out-of-range indices, empty args as
IndexError); storing an `e.args[i]` value in a name, container, attribute or user function is
refused by name on the typed path so the default build uses the general path, which keeps the
object. The general-path file OSError adapter builds two-element `args == (errno, strerror)` and
keeps the filename as an attribute. Added and registered `test_ail_pre48.py`; `tools/diff_ids.py`
is not present on this tree, and `tools/update_manifest.py` (then `--check`) passes.

Probes in `/tmp/probes` (`p48_direct`, `p48_alias`, `p48_index_routes`, `p48_oserror_ctor`,
`p48_empty`, `p48_file_missing`, `p48_file_dir`) run with `cmp.sh`: every one matches CPython on
the default build, and all but `p48_oserror_ctor` match on the forced build; that probe is
refused by name there (`not in the subset: raising OSError with more than one argument`), as are
multi-argument `raise ValueError(...)` probes. Final-state modules: test_ail_pre48,
test_ail_exception_context, test_ail_exception_values_core, test_ail_exception_values_app,
test_ail_exception_aggregate_objects, test_ail_exc_str, test_ail_excfix, test_ail_raise_from,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (11 modules, 522 s, 0 failed).
## 2026-10-26 - re-apply pre51: format-spec diagnostics and the float z flag (job-rbpre51-10261856)

Re-applied accepted job `job-pre51-10241239` on the current tree. The space-sign-on-str
wording, the whole-spec `Invalid format specifier '<spec>' for object of type '<type>'` text
and the `\xNN` escaping of an unknown format code are already present here from the pre206
parser fix, which also keeps NUL and grouping handling; those newer fixes are kept. From the
accepted change, the parser now decodes a non-BMP type code from a surrogate pair (the spec's
`wide_type` is 32-bit), so a non-BMP code is named as CPython's `\x1f600` instead of being
rejected as a longer spec. Non-BMP and surrogate string literals are still refused by name by
the compiler, so that path is not reachable from source. The float `z` flag already matched.
Added `AIL_CURRENT/test_ail_pre51.py` (2 tests, both builds) and registered it in
`ail_check.MODULES`. `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py`
was run and `--check` passes. Probes `/tmp/probes/pre51_errors.py`, `pre51_codes.py` and
`pre51_z.py` match CPython on both builds; the non-BMP/surrogate literal probes are refused by
name. Tests: pre51, pre206, pre225, pre243, pre103, safetynet, files, corpus_findings3 (0 failed).
## 2026-10-26 -- re-apply pre52: an optional import is refused by name at its own line (job-rbpre52-10261857)

Re-applied the accepted pre52 change on the current tree.  `try: import html ... except
ImportError:` reached the general emitter's try check, which refused `ImportError` as an
unsupported caught exception type without a position.  The check now names the imports in the
try body (`import of 'html' guarded by except ImportError`), points at the first import's line
and column, and says to move it to the top of the file; `ModuleNotFoundError` gets the same
message.  An import only in a handler, `else` or `finally` is not called guarded, so it keeps
the caught-type refusal, now located at the `try`.  Other unsupported caught types are located
at their `try` too.  `except Exception` is unchanged.  Added the accepted
`AIL_CURRENT/test_ail_pre52.py` (fifteen refusals and four accepted programs, both builds) and
registered it in `ail_check.MODULES` and `tools/ci_shards.json`.  `tools/diff_ids.py` is not
present on this tree; `tools/update_manifest.py --check` passes.  Probes `/tmp/probes/pre52_*`
(18 programs: direct/from/two-module/alias/tuple, ModuleNotFoundError, nested def, if, loop,
no-import, other type, handler/else/finally, `except Exception`, ZeroDivisionError, plain
imports) match CPython or are refused by name on both builds.  Tests on the final tree:
`test_ail_pre52`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
## 2026-10-26 -- re-apply pre55: oversized list/tuple repeats (job-rbpre55-10261858)

Re-applied the accepted pre55 change on the current tree. Constant list/tuple repeats whose element
count exceeds 2**60 are refused by name in the general path (`pyboxed2.expr_BinOp`, before the
existing `int_constant` fold). Dynamic repeats are guarded in the boxed `ail_op_mul` (the empty
sequence is skipped and the multiplication is checked), in the typed `_list_repeat_value` (now
reserving `_count * len(elements)` for every element count, including str lists), and in the
one-element `list.repeat` IR; they stop with CPython's `MemoryError`. Empty and negative counts
are unchanged, so `[] * 2**62` is empty as before. Added `AIL_CURRENT/test_ail_pre55.py` and
registered it in `ail_check.MODULES`. The accepted `_constant_int` helper is kept, including its
unary `~` handling.

Probes in `/tmp/probes` match CPython or are refused by name on both builds: `pre55_refuse_pow`,
`pre55_refuse_lit`, `pre55_refuse_tuple`, `pre55_refuse_rev`, `pre55_refuse_invert`,
`pre55_refuse_boundary` (refused on the unified build, `MemoryError` on the default), `pre55_empty`,
`pre55_runtime_arg`, `pre55_runtime_tuple`, `pre55_runtime_routes`, `pre55_runtime_attr`,
`pre55_runtime_dict`, `pre55_small`, `pre55_small_widths`. Tests on the final tree:
`test_ail_pre55`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
(4 modules, 229 s, 0 failed).
## 2026-10-26 - re-apply pre59: itertools choosers reject negative r (job-rbpre59-10261859)

Re-applying the accepted pre59 change. The runtime fix is already present on this tree:
pre137/pre126 route a given `r` through `ail_it_r_index`, which raises
`ValueError: r must be non-negative` before the "r larger than the pool" early exit on both
builds, so the fetched runtime hunk is superseded and no runtime edit was needed. Added the
accepted `AIL_CURRENT/test_ail_pre59.py` and registered it in `ail_check.MODULES`; updated the
fuzz8 DIFFERENCES row to cite it. `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes. Probes `pre59_routes`, `pre59_keyword`
and `pre59_loop` in `/tmp/probes` match CPython on both builds (direct/literal, argument, list
item, attribute, dict value, keyword/expression, empty pool, bool, r=0, r=n, r>n, huge negative,
and the typed for-loop path). Tests on the final commit: pre59, pre137, pre126, safetynet, files,
corpus_findings3.

## 2026-10-26 - pre61: functools.partial with bound values (job-rbpre61-10261900)

Re-applied the accepted pre61 change on this tree.  The general path lowered `functools.partial`
of a def or lambda to synthetic lambda closures without source locations, so the lambda scan that
looks for a name bound after a lambda stopped with
`AttributeError: 'Lambda' object has no attribute 'lineno'` (pyboxed2.py).  `genlib._partial` now
copies the `partial()` call's location onto every lambda it builds, so partials with positional,
keyword, empty and run-time bound values compile and match CPython on both builds; a bound value
that arrives through an argument, a list item, a dict value or an attribute is covered too.  The
shapes the general path already refused (a non-def/lambda callable, too many bound arguments, a
non-trailing keyword, `*args`, no function) remain refused by name.  Added the accepted
`AIL_CURRENT/test_ail_pre61.py` and registered it in `ail_check.MODULES` and `ci_shards.json`.
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and `--check`
passes.  Probes in `/tmp/probes` (`pre61_lambda`, `pre61_def_map`, `pre61_routes`,
`pre61_runtime`, `pre61_types`) match CPython on both builds; `pre61_refuse_kwlambda` and
`pre61_refuse_notdef`/`_toomany`/`_kworder`/`_star`/`_nofunc` are refused by name on both.  Final-state tests: `test_ail_pre61`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`.
## 2026-10-26 -- pre200 reapply: maxsplit intermediates above 4096 bits fold (job-rbrbpre200-10261625)

Re-applied the accepted pre200 change on this tree.  A maxsplit intermediate above the old
4096-bit cap now folds when the whole expression reduces to an int64 value, so
`"a b c".split(" ", 2**4096 // 2**4050)` (final 2**46), `2**4096 >> 4096` (final 1) and the same
value through an argument, a list item, an attribute, a dict value, a local, a module/class
constant and a default argument match CPython on both builds.  This tree's rbpre190 reapply
already gives the maxsplit folder and `pyfunc` the 2**20-bit width (2**24 for a large exponent)
with exact power sizing, so that larger limit is kept and the accepted 8192-bit raise is
subsumed.

The integration conflict was `ail_chatgpt._constant_int_exact`, used by the module/class/default
constant check, which still had its own 4096-bit cap and refused
`class Box: n = 2**4096 // 2**4050`; its cap now uses the same 2**20-bit width while the
pre190 zero/base shortcuts and special-exponent handling are kept.  The pre200 review fix is
also applied: an exact value that CPython's int-to-str digit limit cannot format now shows
`too large` in the source-positioned refusal instead of escaping as a conversion error.  Added
`test_ail_pre200.py` (folded direct/argument/list/attribute/dict/local cases, over-limit and
out-of-int64 refusals) and registered it in `ail_check.MODULES` and both `tools/ci_shards.json`
lists.

Probes `/tmp/probes/p200_direct.py`, `p200_flows.py`, `p200_boundaries.py`, `p200_types.py` and
`p200_aliasing.py` match CPython on both builds; `p200_giant.py` is refused by name on both with
`int64 constant expression out of range: too large`.  Final-state modules: test_ail_pre200,
test_ail_pre184, test_ail_pre190, test_ail_pre203, test_ail_pre214, test_ail_pre205,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (44 tests, 1 skipped, 0 failed,
274 s).  `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and
`--check` passed.

## 2026-10-26 -- re-apply pre203: unary INT64_MIN constant expression (job-rbpre203-10261301)

Re-applying the accepted pre203 change on the current integration tree.  The behaviour is
already present: the generic all-constant folder (`pyfunc.fold_int_constant`) folds a unary
minus whose exact value is INT64_MIN before the backends parse it, the pre246 unary/index fold
keeps `-(1 << 63)` and `~(-(1 << 63))` in range, and `_CONST_INT_BITS = _MAXSPLIT_BITS`
(2**20 bits) already shares the wide limit, so `-((1 << 5000) >> 4937)` folds rather than being
refused.  No compiler code change was needed; this reapply adds the accepted
`AIL_CURRENT/test_ail_pre203.py`, registers it in `ail_check.MODULES` and `ci_shards.json`, and
records the already-fixed rows.  Probes in `/tmp/probes`: `pre203_min`, `pre203_routes`,
`pre203_adjacent`, `pre203_bounds` match CPython on both builds; `pre203_refuse`
(`-(-9223372036854775808)`) is refused by name on both.  Tests on the final tree:
`test_ail_pre203`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
(4 modules, 346 s, 0 failed).
## 2026-10-26 -- reapply pre201 constant-shift fold budget (job-rbpre201-10261355)

Re-applied the accepted pre201 change on this tree.  The out-of-range shift refusal is already
present here: pre236/pre241's generic constant-expression rule refuses `True << 64`, `1 << 64`
and their argument/list/attribute/dict/assignment routes by name with the `outside the signed
64-bit range` wording, so the conflict resolution keeps that rule and does not add pre201's
second refusal path.  The pre201 fold-budget piece is added to `_check_constant_power`: a
dedicated `_const_fold_int` mirrors the pre190 zero/base shortcuts and its 2**20-bit budget
(2**24 for a 0/1/-1 exponent), so `((10 ** 64) ** 64) >> 100001` folds to 0 like CPython instead
of being refused, while `(1 << 1048576) >> 1048576` and wider intermediates stay refused by name.
`test_ail_pre201.py` covers bool/int shifts, a negative result, argument, list item, class
attribute, dict value and assignment, plus the in-range boundaries; its out-of-range check
accepts either named refusal.  Probes `p201_*` in `/tmp/probes` match CPython or are refused by
name on both builds.  Final-state modules: test_ail_pre201, test_ail_pre190, test_ail_pre195,
test_ail_pre205, test_ail_pre191, test_ail_pre236, test_ail_pre241, test_ail_pre121,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
## 2026-10-26 - pre209 reapply: bytearray defaults of nested defs

The accepted pre209 change proposed naming a nested `def`'s `bytearray(...)` default as a mutable
literal and refusing it by name, because the old surface only matched the generic "nested def with
default parameters" refusal. This tree contains the pre141 fix, which evaluates every non-literal
default once at the `def` statement into a hidden local, including a `bytearray(...)` call and one
inside a tuple/list/set/dict display. That matches CPython (the object is shared between calls, and
a negative count raises at def time), so a refusal would regress it. Both changes are kept: pre141's
evaluation stands, and `test_ail_pre209.py` re-applies pre209's cases as CPython-parity regressions
(empty/bytes/size/list-arg bytearray defaults, tuple/list/dict/nested-tuple containers, an outer
value, keyword-only, class-object and source-keyword defaults, alias bindings through an argument,
a list item, an attribute and a dict value, module-level/returned/doubly-nested/loop-built/lambda/
recursive/immutable defaults, the negative count, and the deeper-nested keyword call still refused
by name). No compiler code change was needed. Probes `p01`-`p24` in `/tmp/probes/pre209` match
CPython or are refused by name on both builds. Tests: pre209, pre141, safetynet, files,
corpus_findings3.
## 2026-10-26 - nested def two levels deep shares the enclosing cell (job-rbpre213-10261303)

Re-applied the accepted pre213 change on top of the current tree.  `_register_nested` now also
takes the free names of deeper defs (`boxclosure.free_names`); when a name is used by such a
deeper scope its enclosing binding is made a cell (`NeedCells`), and the intermediate def
receives that cell rather than a copy, so the deeper def sees the same object and any later
rebinding.  The cell is forwarded through further nested defs and `cell_preamble` leaves an
external cell alone; a closure function declares the def flags of its own nested defs.  The
`by_cell` names are also in the nested context's `free_names`, so an unbound captured scalar
read through the cell raises `NameError` (not `UnboundLocalError`), matching CPython.

`test_ail_pre213.py` covers appends through an argument (empty and non-empty), aliasing, a dict
value/list item/attribute, int and str reads (positive, zero, negative), a default referring to
the captured list, sibling inner defs, a returned inner def called twice, rebinding the outer
name after the intermediate call, three levels, an unbound scalar read before assignment and
after deletion, and a deep `nonlocal` write stays refused by name.  Probes in `/tmp/probes`
match CPython or are refused by name on both builds.
## 2026-10-26 -- reapply pre225: grouping with an unrecognised type code (job-rbpre225-10261321)

Re-applied the accepted pre225 change. Its safetyrt.py fix is already present on this tree from
the pre206 review: `ail2f_parse` checks the grouping against the type before an unknown code (its
whitelist gives the same result as pre225's `bcdeEfFgGnosxX%` once the `n`/`s`/`c` and
`,`+`b/o/x/X` conflicts are applied), and `ail2f_code_text` already escapes a space code as
`\x20` (`c <= 0x20`). The code therefore needed no further edit, keeping both sides' fixes. Added
`AIL_CURRENT/test_ail_pre225.py` (1 test, both builds) and registered it in
`ail_check.MODULES`. Probes `/tmp/probes/pre225_*` (group matrix, value routes, NUL/code points,
boundaries) match CPython on both builds. Tests: pre225, safetynet, files, corpus_findings3.
## 2026-10-26 - reapply pre215: constant abs() outside int64 (job-rbrbpre215-10261331)

Re-applied the accepted pre215 change on this tree. The tree already carried the pre214/pre248
`abs()` work, so the reapply keeps its function-local constant support and adds the accepted
`_known_module_constants` / `_binds_name` helpers: a module constant written as a shift expression
(`M = -(1 << 63)`, including an alias `N = M`) now resolves into `abs()`, and the argument is
folded exactly so a result below `INT64_MIN` or above `INT64_MAX` is refused by name
(`int64 constant expression out of range`) on both builds. The fetched test expected the older
`outside the signed 64-bit range` wording for the three other review cases; the test now accepts
the current tree's named refusal as well, keeping both sides' fix. Added
`AIL_CURRENT/test_ail_pre215.py` and registered it in `ail_check.MODULES`.
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and `--check`
passes. Probes `p1`-`p16` in `/tmp/probes` on both builds: 14 are refused by name (direct,
literal, module shift/alias, below-min, above-max, argument, list, attribute, dict, nested, local,
local alias, power) and `p12`/`p13` match CPython. Tests: pre215, pre214, pre248, pre246, pre253,
pre227, pre236, safetynet, files, corpus_findings3.
## 2026-10-26 - re-apply memsafe2 hostile-input fixes, merged with current format fixes (job-rbrbrbrbmemsafe2-10261346)

Re-applied accepted job `memsafe2` on the current export, keeping the overlapping format()
fixes already on this tree. `safetyrt.py` combined the new whole-unit `wide_type` handling,
group-check-before-value and helper messages with the current tree's duplicate-grouping
"cannot specify ',' with ','" wording and space-as-`\x20` escaping; the remaining files
applied as-is. DIFFERENCES rows use this branch's placeholder ids, and the hostile-input
module is registered before `test_ail_safetynet`.

## 2026-10-25 - re-apply memsafe2 hostile-input fixes on current tree (job-rbrbrbmemsafe2-10260121)

Re-applied accepted job `memsafe2` (branch `job-rbrbmemsafe2-10252051`) on the current export. The
`cruntime.py`, `safetyrt.py`, `exctext.py`, `prelude_bytes.py`, `pyboxed.py` and `pyboxed2.py` edits plus
the new `tools/input_fuzz.py` and `AIL_CURRENT/test_ail_hostile_input.py` applied as-is. Three files
conflicted: `ail_check.MODULES` already had `test_ail_pre141`, so the hostile-input module is registered
just before `test_ail_safetynet`; the DIFFERENCES rows were renumbered to this branch
(`C?-job-rbrbrbmemsafe2-10260121-1..8`) and kept alongside the newer records; and the original memsafe2
DEVLOG entry is placed before the 2026-10-24 codec-name entry. Overlapping fixes already on this tree are
kept on both sides: pre192's `int(bytearray)` text and pre103's NUL format type still hold while the
int()/float() error path now uses the UTF-16 repr helpers and `%.200R`, and the format parser
distinguishes an ASCII type (including NUL) from a whole non-ASCII `wide_type`.
## 2026-10-26 - re-apply pre237: method call sites with colliding names stay boxed (job-rbpre237-10261405)

Re-applied accepted job `job-pre237-10260353` on this tree. The current export already carried
an equivalent `pymix._escapes` fix, but it keyed method bodies by name in a dict and skipped a
method whose name collided with a module function (`bodies.setdefault`), so duplicate method
names across classes collapsed to one body. The re-applied change keeps every method body as a
separate entry (`method_bodies` list) and walks both module functions and methods, recording
`obj.method()` call sites when the attribute names a method. A module function `run` and class
methods `run` (including duplicates) are therefore all visible, so the shift helper `shl`
stays boxed under a caller's `try` on both builds.

Added `test_ail_pre237.py` (2 tests: colliding method call sites with literal/argument/
list-item/attribute/dict-value/alias counts and valid/zero shifts, plus an uncaught method shift
naming `ValueError: negative shift count`) and registered it in `ail_check.MODULES`. Probes
`/tmp/probes/pre237_*` cover the same forms on both builds; results are in the job report.
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
## 2026-10-26 - reapply negative INT64_MIN unary constants (job-rbrbrbpre204-10261336)

Re-applied the accepted job-pre204 fix on the current tree. The tree's pre177/pre190/pre236 work
already folds whole constant expressions exactly through `pyfront.int_constant` and
`pyfunc.fold_int_constant`, so the accepted per-emitter unary checks were already covered on the
typed, typed-legacy and general paths; the one uncovered path was the general legacy
`expr_UnaryOp` in `pyboxed.py`, which now folds the whole unary constant expression too. The exact
constant-folding size limit is raised to `1 << 22` bits in `pyfront._CONST_INT_LIMIT` and in
`pyfunc._CONST_INT_BITS` (including its late assignment that previously shared the 2**20
`_MAXSPLIT_BITS`), so `-(1 << 63)`, `-((1 << 5000) >> 4937)` and the large intermediate
reductions (`0 >> (1 << 5000)`, `2 ** ((1 << 2000000) - (1 << 2000000))`,
`(1 << 2000000) >> 2000000`) fold to their in-range result instead of trapping on the
intermediate. Values that reach a negation as variables keep the fixed-width run-time trap.

The new `test_ail_pre204.py` covers negative INT64_MIN spellings, the four value flows (argument,
list item, attribute, dict value), aliases and returns, in-range boundaries, the large-intermediate
reductions, and dynamic operands, on all four emitter modes. Registered it in `ail_check.MODULES`
and both `tools/ci_shards.json` lists. Conflict resolution with the later pre190/pre236 tests:
pre190 now requires the generic fold limit to cover (not equal) the maxsplit limit and asserts the
new 2**22 value, and pre236's non-special wide-shift refusal moved from the old 2**20 boundary to
the new 2**22 one; both keep their original intent.
## 2026-10-26 - generator expression as a hash key refused by name (job-rbpre245-10261431)

Re-applying pre245 on this tree.  The pre222 review recorded p8c as still differing here:
`print({(x for x in [1, 2])})` exits 1 with `TypeError: unhashable type: 'list'` on both builds,
while CPython stores the generator object and hashes it by identity (its display carries the
address).  The cause is the pre166 representation: a generator expression is materialised
eagerly as a list carrying `from_generator`, so it has neither CPython's identity hash nor its
generator repr.

The construct is now refused by name on both builds.  `_check_genexpr_hash_keys` in
`ail_chatgpt.py` refuses a generator expression that a set literal or comprehension, a dict literal
key or comprehension, `hash()`, or `set()`/`frozenset()` over a collection must hash, including one
reached through a tuple, an `if` expression or a `tuple()`/`frozenset()` call over a collection.
`_bound_names` keeps a program that binds `hash`/`set`/`frozenset`/`tuple` (def, assignment,
parameter, import, `global`/`nonlocal`, match name) on CPython's result; an over-approximated
scope only moves a genuinely builtin call to the run-time refusal.  The v2 `ail_obj_hash` (with
the matching `dunderrt.py` text edit) raises the same named `TypeError` when a saved, aliased,
passed, stored or otherwise dynamic generator expression reaches a hash bucket, so `dict.get`,
membership, `.add`, a subscript and `hash(name)` name the construct instead of the list.  A
consumed generator expression (`sum`, `next`, `list`, `frozenset(genexpr)`, a genexpr passed to
`tuple()`/`frozenset()` as a key) and one kept as a dict value are unchanged.  `print(g)` still
shows the list repr, the separate later item.

Probes `/tmp/probes/p245_*` cover the static forms, every dynamic route above, bound-name
shadowing, a plain list key, `frozenset(genexpr)` and consumption; each matches CPython or is
refused by name on both builds.  Added `test_ail_pre245.py` and registered it in `ail_check` and
the CI shards.

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

## 2026-10-25 - pre227: class constants built from a module name (job-pre227-10260119)

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
## 2026-10-25 - large special exponents before the constant-fold guard (job-pre236-10260352)

The rbpre190 review left two pre-existing items: `test_ail_pre121`'s stale refusal wording and
the `>2**20` / `>16M`-bit constant refusals.  Both still reproduced here.  The generic constant
folders (`pyfunc._const_int_expr`, `ail_chatgpt._constant_int_exact`) evaluated both operands
before their zero/base shortcuts, so `0 * (1 << 2000000)`, `0 ** (1 << 2000000)`,
`1 ** (1 << 2000000)` and `(-1) ** (1 << 2000000)` were refused although every result fits
int64.  They now decide an absorbing zero and the power bases 0/1/-1 before the size guard, as
`pyfront.int_constant` already did, and retry a huge exponent of such a power at the 2**24-bit
special limit so its sign and parity are known.  An absorbing zero also folds with an operand
wider than 2**24 bits (`0 * (1 << 16777216)`); a non-special intermediate beyond 2**20 bits and
a special exponent beyond 2**24 bits are still refused by name.  The two stale `test_ail_pre121`
expectations now also accept pre177's `int64 constant out of range` wording (same named refusal
for the same construct).

Probes `/tmp/probes/p236_*` cover the boundaries, types, negative exponents, module/class/default
positions and argument/list-item/attribute/dict routes on both builds; `/tmp/probes/p236_special_*`,
`p236_zero_*` and `p236_cap_zero.py` match CPython, while the genuinely wide non-special cases and
the `2**24`-bit special boundary are refused by name.  Added `AIL_CURRENT/test_ail_pre236.py`.
## 2026-10-25 - huge constant power diagnostics (job-pre238-10260354)

The first pre-existing difference from the pre159 review was the compiler printing CPython's
int-to-str limit text instead of a named refusal. On this tree the reviewer's
`print(10 ** 4000 * 10 ** 300)` is already refused by name by the front end, and
`tools/ci_shards.py --check` is clean. A related case still failed the same way: a constant `**`
whose exact value has more than 4300 digits (for example a 3000-digit base to the 64th) reached
`str(value)` while `_check_constant_power` built its `int64 constant out of range` message, so both
builds stopped with `Exceeds the limit (4300 digits) for integer string conversion`. The new
`_constant_diagnostic` prints `too large` when the conversion is forbidden, and the index, literal
and unary diagnostics use it too, so those constructs are refused by name at compile time.

Probes `/tmp/probes/p238_*` and `/tmp/probes/p238b_*` cover the reviewer expression, huge bases in
an argument, list item, attribute, dict value, module/class assignment, default and local, unary
and nested powers, index expressions and a huge literal on both `cmp.sh` builds; every one is
refused by name. Added `test_ail_pre238.py` (2 tests, both builds) and registered it in
`ail_check.MODULES` and `ci_shards.json`. Final-state tests: test_ail_pre238, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 pass.
## 2026-10-25 - bool constant shifts fold like ints (job-pre241-10260355)

The pre229 review recorded that a bool shift was still compiled with the fixed-width runtime:
`True << 64`, `True << 4096`, `(True << 100000) >> 100000`, `if False: print(True << 64)` and the
target `(True << 64) >> 64` stopped with `integer overflow` on both builds, where CPython evaluates
the bool as an int subclass and prints the bignum (or 1 for the target).  The general constant
folders only accepted `type(x) is int`, so `True` and `False` never reached exact folding.

Bool constants now fold exactly like int constants in `pyfunc` (the general shift/arithmetic
folder and the maxsplit folder).  `(True << 64) >> 64`, `(True << 100000) >> 100000`, `(True << 63)
>> 63` and `(False | True) << 62` print what CPython prints; a value outside int64 (`True << 64`,
`True << 4096`, `True << 63`, a bool maxsplit) is refused by name with the existing int-constant
wording.  `&`, `|`, `^` of two bools still returns a bool and is left to the runtime, so
`True & False` keeps printing `False`, and a negative shift still raises `ValueError`.  Probes in
`/tmp/probes/pre241/` cover the shift widths 0/1/62/63/64/4096/100000, false operands, negative
counts, bool arithmetic and bitwise, dead code, arguments, list items, attributes, dict values and
module constants on both builds; all match CPython or are refused by name.  Added
`test_ail_pre241.py` and registered it in `ail_check.MODULES`.
## 2026-10-25 - module-level rebinding of a module function (job-pre242-10260356)

The first still-differing item from the pre217 review was `r3_module_shadow.py` /
`p09_module_rebind.py`: a module-level `f = lambda: 102` after `def f` was ignored and `f()`
printed the old `2` on both builds. The general path's `_call_name` always preferred
`self.functions[name]`, and the module body never wrote a top-level function into its module slot.
A module-scope assignment to a top-level function name now marks that name as rebound, the `def`
stores its function value in the module slot, and direct calls/reads of the name go through the
slot. Rebinding a function whose value the general path cannot build (defaults or a keyword call
through the value) is refused by name; a `global f` write inside a function (the separate p32
item) is unchanged.

Probes in `/tmp/probes`: `pre242_basic`, `pre242_order` (before/after), `pre242_signatures`
(0/1/2 params, str/list), `pre242_sources` (another function, list item, attribute, dict value,
function argument), `pre242_conditional`, `pre242_value_read`, `pre242_noncallable` (TypeError),
and `pre242_defaults` / `pre242_kwargs` (refused by name); all match CPython or are refused on both
builds. Added `test_ail_pre242.py` (2 tests, both builds) and registered it in
`ail_check.MODULES`; final-state tests: test_ail_pre242, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.
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
## 2026-10-25 - `abs()` of a local int64 minimum is refused by name (job-pre248-10260359)

The first still-differing item in the pre214 review's pre-existing list was the local variable:
`x = -(2 ** 63)` is an in-range int64, but both builds stopped in `abs(x)` with `integer overflow`
where CPython prints the bignum `9223372036854775808`.  The other items in that list (an `abs`
bound in an unrelated function, an aliased `abs`, `builtins.abs`, and the `complex()` refusal) are
unchanged and still match the base.

`_check_int64_abs_constants` now also follows a function's own top-level single-assignment int
constants into `abs`, resolving module constants unless the function shadows them and skipping
parameters, globals/nonlocals, names stored more than once and nested scopes.  A direct value, a
shift, a module constant, an alias and an annotated assignment are covered, as are calls used as
an argument, a list item, an attribute and a dict value.  In-range locals, an overwrite before the
call, float/bool locals, a local shadowing a module constant and an unused minimum still match
CPython.  `test_ail_pre248.py` is registered in `ail_check.MODULES` and `tools/ci_shards.py`
assigned it a shard.

Probes in `/tmp/probes`: `pre248_direct`, `pre248_shift`, `pre248_module`, `pre248_alias`,
`pre248_annassign`, `pre248_argument`, `pre248_list_item`, `pre248_attribute` and
`pre248_dict_value` are refused by name on both builds; `pre248_in_range`, `pre248_overwrite` and
`pre248_float_bool` match CPython on both builds.  The pre214 probes `r6`, `r7` and `r8` still
behave as before (run-time overflow or a named import refusal).
## 2026-10-25 - review fix: constant `int(<text>, base)` container folding (job-pre253-10260534)

The review found two false refusals introduced by folding text read from literal containers.
A dict literal with a duplicate key now yields the last value, matching Python, instead of the
first.  Escape analysis now records simple `name = name` aliases at every scope rather than only
at module level, so a mutation through a function-local (or nested) alias marks the original
container as escaped and leaves it unfolded.  Both cases keep the in-range run-time parse; an
out-of-range value reached through the last duplicate key is still refused by name.

Probes in `/tmp/probes` (`pre253_dup_*`, `pre253_alias_*`, 12 programs, both builds via
`cmp.sh`): duplicate string/int/three-key dicts and a duplicate-key alias print `1023`; a
function-local, nested, method and module-alias mutation prints `1023`; an unchanged container
still folds and a last duplicate out-of-range value is refused by name.  Added both regressions
to `test_ail_pre253.py`.

## 2026-10-25 - constant `int(<text>, base)` beyond int64 (job-pre253-10260534)

The first listed difference that still differed on this tree was `int("1"*5000, 2)`: both
builds compiled it and then stopped with `integer overflow`, while CPython keeps the bignum.
The earlier out-of-int64 items (`-(1<<63)-1`, `-(1<<64)`, `-(1<<5000)`, `z = 1<<63; z-z`,
`0 ** (-(1<<5000))`) are already refused by name here, so no change was needed for them.

A call whose text and base are both constant is now evaluated during the front-end checks.  A
value outside int64 is refused on both builds as `int64 constant expression out of range`;
in-range constants, invalid literals/bases and dynamic strings keep their previous run-time
behaviour; a text read from a literal list/tuple/dict is folded too, while a container that is
mutated or escapes is left alone.

Probes in `/tmp/probes` (`p1`-`p6`, `v1`-`v7`, `ib1`-`ib37`) compare both builds with
CPython.  The five already-fixed items and `ib1`-`ib12`, `ib17`, `ib20`, `ib22`-`ib28`,
`ib30`-`ib33`, `ib35`, `ib37` are refused by name; `ib13`-`ib16`, `ib18`-`ib19`, `ib21`,
`ib26`, `ib29`, `ib34`, `ib36` match CPython or keep their named compiler refusal.  A list
that is mutated (`ib29`, `ib36`) is left unfolded, while a plain alias or a read through
`len`/`print` is folded (`ib30`-`ib31`, `ib37`).  Added `test_ail_pre253.py`.

## 2026-10-25 - module bare annotation with a starred subscript target (job-pre254-10260535)

The remaining pre-existing difference from the `rbpre125` review was the module-level bare
annotation `xs[*a]: ann()`: CPython rejects it with `SyntaxError: can't use starred expression
here`, while AIL built and ran it on both paths.  The cause was `module_bare_annotation` in
`ail_syntax.py`: `_annotation_slice_parts` returned None for a Starred slice and the rewrite
returned without touching the statement, which the lowerers then dropped because it had no value.
The rewrite now raises a named compile-time refusal (exit 2 on the general and default builds)
and recursively detects a Starred inside nested tuple displays as well.  Starred load positions
(`xs[[*a]]`, `xs[ys[*a]]`, `xs[f(*a)]`, `xs[(*a,) if c else 0]`, `xs[(*a,)+tail]`) and the
annotated assignment with a value keep their old behaviour.

Probes `/tmp/probes/pre254_direct.py`, `pre254_tuple_form.py`, `pre254_mixed.py`,
`pre254_nested.py`, `pre254_future.py` and `/tmp/probes/pre254/valid_*.py` cover direct,
trailing-comma, mixed, double-star, nested-tuple, `__future__`, attribute/list-item/dict-value/
call bases, an empty star, and load-position/value forms on both builds; all are refused by name
or match CPython.  Added `test_ail_pre254.py` (2 tests, both builds) and registered it in
`ail_check.MODULES`.  Final-state tests: test_ail_pre254, test_ail_safetynet, test_ail_files,
test_ail_corpus_findings3, test_ail_pre124 and test_ail_pre125 pass.
## 2026-10-25 -- closure over an outer local callable (job-pre257-10260536)

The first still-differing item in the pre244 review's pre-existing list was a closure over an
outer local callable: `def f(): return 1; def outer(): def inner(): return f(); f = lambda: 101;
return inner()` printed `1` on both builds where CPython prints `101`.  Two causes met here.  The
Python surface's `--syntax python` tuple pass treats `f = lambda: ...` as an alias and removes the
statement, but `stmt_FunctionDef` never enters a nested scope, so a call inside `inner` was left
behind and read the module-level `f`; the assignment is now left as written when its name is loaded
in a nested def or lambda.  The general path's `_call_name` also chose a module function or builtin
before a name captured by value (`ctx.free_names`) or by nonlocal pointer (`ctx.ptr_names`); the
captured value now wins, consistent with `expr_Name`.

Probes in `/tmp/probes` covered the local assigned after and before the nested def, a parameter,
a builtin (`len`), two lambdas closing over each other, a callable with arguments, a local def
replaced by a lambda, the module-function control, the ordinary alias control, and values reaching
the local through an argument, a list item, an attribute and a dict value; all match CPython on both
builds.  A `nonlocal` callable is refused by name ("the method .f() ...").  Added
`AIL_CURRENT/test_ail_pre257.py` and registered it in `ail_check.MODULES`.  Final-state tests:
test_ail_pre257, test_ail_pre165, test_ail_pre127, test_ail_builtin_shadowing, test_ail_tuples,
test_ail_nested_functions, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 pass.
## 2026-10-25 - bytes membership: `__index__` operand (job-pre258-10260537)

The first still-differing item in the job-pre183 review's pre-existing list was an object with
`__index__` used as the left operand of `in` on bytes/bytearray: both builds raised the
bytes-like TypeError, while CPython converts through `__index__` (97 selects the byte, while -1
and 256 raise `ValueError: byte must be in range(0, 256)`) and falls back to the buffer path when
the conversion fails. `_ail_bcontains` now tries `_ail_b_index` first for non-int operands and
keeps the existing bytes-like path as the fallback, so a non-int `__index__` result or a raising
`__index__` gives CPython's bytes-like TypeError rather than the helper's own error.

Probes `/tmp/probes/p1_index_bytes.py` and `p1b_index_edges.py` (values 0/97/255/256/-1, a bool
result, non-int and raising `__index__`, a plain object, through an argument, a list item, a dict
value, an attribute and `__contains__`, both receivers and both builds) match CPython; `p1c` is
refused by name for an out-of-int64 constant. Added `test_ail_pre258.py`. The other three
pre-existing pre183 items (the `type(len).__name__` text, builtin-function names in bytes
errors, and builtin classes in a startswith tuple) are unchanged and not addressed here.

## 2026-10-25 - review fix: short `__exit__` signatures (job-pre197-10252029)

The review found that the traceback rewrite indexed `node.args.args[3]` after a
`len(node.args.args) >= 3` guard, so any `__exit__(self, et, ev)` (three arguments) crashed the
compiler with `IndexError` even when the class was never used.  The guard now requires four
arguments; shorter signatures are left alone.  A short `__exit__` that a `with` actually calls is
then refused by name by the existing argument check ("not in the subset: __exit__() called with too
many positional arguments"), and an unused one compiles where CPython does.

Probes `/tmp/probes/pre197_*` cover 3-argument exits (unused, clean body, raising body, reached via
an attribute/list/dict), 1- and 2-argument unused exits, keyword-only `tb`, `*args`, defaults and the
normal 4-argument path on both builds.  Added both regression cases to `test_ail_pre197.py`.

## 2026-10-25 - `__exit__` third argument when the body raised (job-pre197-10252029)

The first still-differing item left by the pre181 review was the traceback argument:
`__exit__` received None even when the `with` body raised, so `tb is None` printed True where
CPython passes the active traceback object (`C?-job-pre181-10251538-2`).  AIL does not model
traceback objects, so the general path now passes a non-None `_AilTraceback` stand-in in the
exception branch and keeps None on every other exit.  Both paths answer `tb is None` /
`tb is not None` (and `==` / `!=` against None) from whether the body raised; the typed path maps
the test to its exception code instead of folding it to a constant.  Any other use of the `tb`
parameter (`type(tb)`, truthiness, attribute access, passing it to a helper, ...) is refused by
name at compile time on both builds: "__exit__ uses 'tb' other than in `is None` / `is not None`;
traceback objects are not modelled".

Probes in `/tmp/probes` (`p_tb1`-`p_tb12`, `p_final`, `p_stop1`) covered clean and raising bodies,
`is`/`is not`/`==`/`!=` against None, suppression, a returning body, `break`/`continue`, nested
managers, a `@contextmanager` generator (the pre181 StopIteration case still matches), a manager
reaching the `with` through an argument, a list item, an attribute and a dict value, and the
refused `type(tb)` / truthiness / helper / `tb.tb_lineno` uses; all match CPython or are refused by
name on both builds.  Added `test_ail_pre197.py` (2 tests, both builds) and registered it in
`ail_check.MODULES`.  Final-state tests: test_ail_pre197, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 pass.
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
## 2026-10-25 - pre126 reapply: itertools `r` validation (job-rbrbpre126-10252049)

The first still-differing item in the job-pre101 review was the general path's negative
`r`: `permutations`, `combinations` and `combinations_with_replacement` returned `[]`
instead of raising `ValueError: r must be non-negative`; the same code read `r` as a raw
int64 field, so a float, str, None, list, tuple or bytes was also accepted. Both general
emitters now pass the `r` object to one runtime converter (`ail_it_r_index`), which checks
the type and sign; `permutations` keeps treating a None `r` as "not given". The current
tree already rejected a negative `r` (job-pre137), so that fix is kept inside the new
converter. Added `AIL_CURRENT/test_ail_pre126.py`; probes in `/tmp/probes/pre126_r_bounds.py`,
`pre126_r_types.py` and `pre126_r_sources.py` match CPython on both builds.
## 2026-10-25 - pre141 review follow-up: recursive calls see hoisted defaults (job-rbpre141-10251549)

Review defect: a recursive call that omitted a hoisted default resolved the hidden
`_ail_nndefault_N` name in the nested function's own frame, where it was never declared. Without a
module global of that name the general path refused with an internal "name ... is not defined";
with one, it silently read the global (`local` printed as `global`, shared lists got the global's
contents). `_register_nested` now includes the hidden default names in the nested function's free
names, so they are captured by value from the enclosing frame and the recursive call reads the
def-time object. Regression program `recursive_defaults` in `test_ail_pre141.py` covers the module
global collision, shared list/dict/bytearray defaults through recursion, and a keyword-only
recursive default; probes `p9`-`p13` in `/tmp/probes` add scalars/widths, empty/negative values,
aliasing, loop redefinition, values from arguments/list items/attributes/dict values, and both
builds. All match CPython.

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
## 2026-10-25 - pre171 reapply: indirect typed calls and worker trap (job-rbrbpre171-10252050)

Re-applied the accepted pre171 change on top of the current tree.  The tree already carried the
pre87/pre109 partial fix: `_value_referenced` marked names used as values and `_protected` marked
call sites inside a lambda.  Kept those and added the accepted change's transitive walk
(`_indirect_names`), so a function called by an indirectly invoked function is also rejected to the
general path, and `_protected` now short-circuits on an indirect caller scope.  The runtime half is
unchanged from pre171: `ail_raise_value_adopt` on a parallel worker records the exception's code
and message through `ail_par_trap_value`, releases the worker's reference, and unwinds inside the
worker; the join re-raises it on the caller, so a negative shift in a `parallel for` is caught on
both builds instead of longjmp-ing across threads.  Added `AIL_CURRENT/test_ail_pre171.py` and
registered it in `ail_check`.  The earlier `test_ail_pre87` callback case is kept.

## 2026-10-25 - constant abs(INT64_MIN) is refused by name (job-pre214-10252301)

The first still-differing item in the rbpre177 review's pre-existing list was `abs(-(2**63))`:
both builds compiled it and stopped at run time with `integer overflow`, while CPython prints the
bignum `9223372036854775808`.  The earlier items in that list no longer differ on this tree:
`10**100`, `2**65` and `xs[10**100]` are already refused by the general front end, and the local
`x = -(10**20)` is already refused as an int64 constant expression.

`_check_int64_unary_constants` now also refuses a builtin `abs()` whose single argument is a
statically known int64 minimum, with the existing `int64 constant expression out of range` wording
and exit 2.  It sees nested unary forms, shifts and module constants, covers calls used as an
argument, a list item, an attribute and a dict value, and skips the check when `abs` is shadowed.
In-range constant absolutes, float/bool arguments and a value that reaches `abs` only through a
local variable keep their previous behaviour.  `test_ail_pre214.py` is registered in
`ail_check.MODULES`; `tools/ci_shards.py --update` assigned it a shard.

Probes in `/tmp/probes`: `p214_direct_pow`, `p214_direct_shift`, `p214_literal_min`,
`p214_module`, `p214_argument`, `p214_list_item`, `p214_attribute`, `p214_dict_value` are all
refused by name on both builds; `p214_in_range` and `p214_shadow` match CPython on both builds.
`p214_variable` (a local variable holding the minimum) is unchanged and still traps at run time,
the same pre-existing limitation as before this job.
## 2026-10-25 - pre184 review fix: class-body bare `**` with a large exponent (job-rbpre184-10252049)

The reviewer found that the conflict resolution left a hole: a class-body bare `**` value was
always deferred to `_check_constant_power`, but that check folds with `_const_expr_int`, which
returns `None` when the exponent is above 64.  So `class C: M = 2 ** 100` and
`M: int = 2 ** 100` compiled and then stopped at run time with `integer overflow`, where the
accepted tree refuses them by name.  The class-body deferral now applies only when
`_const_expr_int` can fold the value; otherwise `_constant_int_exact` checks it, so both cases
fail at compile time with `int64 constant expression out of range: 1267650600228229401496703205376`.
`class C: M = 2 ** 64` still gets pre177's `int64 constant out of range` wording, and in-range or
special-power results (`2 ** 62`, `0 ** 100000`, `1 ** 100000`, `(-1) ** 100000`, `0 << 100000`,
`(2 ** 100) // (2 ** 99)`) still match CPython on both builds.  Added both class-body cases to
`test_ail_pre184.py`.

## 2026-10-25 - out-of-int64 constant expressions outside function bodies (job-rbpre184-10252049)

Re-applied the accepted pre184 change on top of this tree. A constant integer expression in a
module/class assignment or a default argument that does not fit int64 is now refused by name at
compile time (`int64 constant expression out of range`), instead of compiling and stopping at run
time with `integer overflow`. `corpus/gdev/g22_012.py` (`_MASK: int = (1 << 64) - 1`) and
`def f(x=10**30)` are the motivating cases. The evaluator handles + - * // % ** << >> & | ^ and
unary + - ~ with a 4096-bit guard; Pow bases 0/1/-1 and a zero left shift are decided before the
guard, so `0 ** 100000`, `1 ** 100000`, `(-1) ** 100000` and `0 << 100000` stay in range. An
out-of-int64 expression inside a function body keeps its old run-time stop; a class with a base
(the enum case) keeps its own refusal.

Conflict resolution: this tree already had `_check_int64_literals`, `_check_constant_power`,
`_check_int64_unary_constants` and a two-argument `_constant_int` from pre172/pre177. The new
evaluator is `_constant_int_exact`, and its check runs before the older ones so a default argument
gets the accepted wording; a bare `**` class-body value is left to `_check_constant_power` so
pre177's flow cases keep their existing `int64 constant out of range` wording. Added
`test_ail_pre184.py` (class, module and default refusals plus in-range class/default/module
arithmetic and the power/shift guard boundaries), and registered it in `ail_check.py` and both
`ci_shards.json` lists.
## 2026-10-25 - pre190 reapply: large constant intermediates that reduce to int64 (job-rbpre190-10252302)

Re-applied the accepted pre190 change on top of the current tree. The constant folders now decide
zero absorbing operands and the power bases 0/1/-1 before the size guard, so `0 * (1 << 5000)`,
`(1 << 5000) & 0`, `0 ** (1 << 5000)`, `1 ** (1 << 5000)`, `(-1) ** (1 << 5000)`,
`(1 << 5000) ** 0` and `(1 << 5000) >> 5000` fold instead of stopping with `integer overflow`, and
the same constants used as a `str.split`/`rsplit` maxsplit are not refused. A zero/base shortcut is
taken only when the other operand is itself a constant int, so `1.5 ** 0`, `f() ** 0`,
`0 * "ab"`, `0 * f()`, `0 & 1.5` and `2.0 ** 0` keep normal evaluation. The fold limit moved from
4096 to 2**20 bits (2**24 for a large exponent in such a power), and `_CONST_INT_BITS` now shares
`_MAXSPLIT_BITS` so the generic all-constant folder added by another accepted job does not pre-empt
these reductions on the integration tree. The current tree's exact `_pow_within_maxsplit_bits` guard
is kept alongside the new shortcuts. Added `AIL_CURRENT/test_ail_pre190.py`; probes in `/tmp/probes`
cover boundaries, non-int operands, effectful calls, and argument/list-item/attribute/dict routes on
both builds.

## 2026-10-25 - maxsplit constant through a wider intermediate (reapply, job-rbpre205-10252303)

The first still-differing item from the rbpre121 review was the maxsplit folder's `right >= 64`
power rule: `"a b c".split(" ", 2**100 // 2**80)` was refused by name on both builds although the
final value 2**20 fits in int64 and CPython splits normally.  This tree already carries rbpre121's
follow-up, which bounds the power exactly with `_pow_within_maxsplit_bits` and the existing
`_MAXSPLIT_BITS` (4096) budget, so the accepted pre205 rule is covered by that stronger fix; both
sides are kept.  A final value outside int64 (for example `2**100`, `10**30`, `(2**64) // 2 * 2`)
is still refused with the maxsplit wording.

`test_ail_pre205.py` covers split/rsplit, an explicit and a `None` separator, negative and zero
limits, the empty string, intermediates built from powers, shifts, sums and products, and values
reaching the call through an argument, a list item, an attribute and a dict value, on both builds.
`/tmp/probes/p205_direct.py`, `p205_flows.py`, `p205_types.py` and `p205_features.py` match CPython
on both builds; `p205_out_of_range.py` is refused by name (CPython raises OverflowError at run time).
## 2026-10-25 - pre206 review fixes: complete and non-ASCII format-spec messages

The review of the pre206 job found three defects in the extra whole-spec message rewrite. The
whole-spec message is now built as runtime text instead of a 160-byte C buffer: the complete spec
is included (120/300-character specs, not 159 bytes) and an embedded NUL is kept. Non-ASCII code
units are copied as code units rather than UTF-8 bytes, so `format(1, '__é')` names `'__é'` (no
double encoding). CPython's grouping-vs-type check now runs inside the parser before the non-ASCII
type rejection, so `format(1, ',é')` and `',中'` give `Cannot specify ',' with '\xe9'` /
`'\x4e2d'`; it also covers the previously pre-existing grouping + space/`q`/`i` cases, with
`\x20` escaping. The repeated-grouping behaviour from the earlier commit is unchanged.

Probes `/tmp/probes/p_review_fix.py` and `/tmp/probes/p_review_matrix.py` (non-ASCII and long/NUL
whole specs, grouping with every ASCII/BMP code point, both builds, values through an argument, a
list item, an attribute, a dict value and an alias) match CPython; the reviewer's `p_uni_long`,
`p_uni_group`, `p_uni_plain` and `p_cont` match, and `p_fuzz` is down to the two pre-existing
string `+_`/`+,` sign-vs-grouping differences listed in the review. `test_ail_pre206`,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` pass on both builds.

## 2026-10-25 - format() repeated grouping characters (job-pre206-10252128)

The memsafe2 review listed three pre-existing differences. The first, `int(bytearray(...), base)`
naming `bytearray(b'...')` in the ValueError, is already fixed on this tree (pre192), and
`bash ~/tools/cmp.sh` matches CPython. The first still-differing item is the format-spec parser:
`format(1, '__d')` and `format(1, ',,d')` said `Cannot specify both ',' and '_'.` where CPython
raises `ValueError: Invalid format specifier '__d' for object of type 'int'`.

CPython consumes one grouping character. A different second grouping character keeps
`Cannot specify both ',' and '_'.`; the same character at the end of the spec is read as the type
and gives `Cannot specify 'g' with 'g'.`; the same character followed by anything else rejects the
whole spec with the full `Invalid format specifier '<spec>' for object of type '<type>'` text. The
parser in safetyrt.py now follows those three cases, and its other whole-spec rejections use the
same full text. A single BMP non-ASCII type now reports CPython's
`Unknown format code '\x..' for object of type '...'` instead of the old bare message; a non-BMP
type remains a pre-existing 16-bit-unit limitation and was not changed.

`test_ail_pre206.py` covers int/negative/zero/bool/float/-0.0/str, signs, zero padding, widths,
empty specs, valid grouping, direct literals/f-string/str.format and values through arguments,
list items, attributes, dict values and aliases, on both builds. Probes
`/tmp/probes/p_pre206_group.py`, `p_pre206_generic.py`, `p_fmtgroup.py`, `p_fmtgroup2.py` and
`p_fmtgroup_lit.py` match CPython on both builds.
## 2026-10-25 - class-method call sites keep boxed try handlers (job-pre211-10252259)

The reviewer of rbpre171 recorded two pre-existing differences.  The generator-expression case
(`gen = (shl(1, -1) for _ in range(1))`) is already refused by name on both builds ("a generator
expression used as a value"), so nothing changed there.  The method case still differed on the
default build: `C.run` called `shl(1, -1)` and `c.run()` sat under a module `try`, but pymix's
`_escapes` built its call graph only from module-level `FunctionDef`s and direct `Name` callees.
It therefore saw no protected call site for `shl`, selected a typed clone, and the ValueError
escaped the boxed handler (exit 1, no output).  `_escapes` now includes class method bodies and
attribute call sites (`obj.method()`), so the chain `c.run()` -> `run` -> `shl` reaches the
module `try`, `shl` is rejected as exception-capable, and both builds catch the ValueError.

The new `test_ail_pre211.py` covers literal, argument, list-item, attribute, dict-value and alias
shift counts, zero/large valid shifts, method-to-method and helper chains, and the division,
subscript and dict-key traps on both builds, plus the genexp by-name refusal.  Probes:
`r11_method.py`, `r11_forms.py`, `r11_chain.py`, `r11_uncaught.py`, `r11_traps.py` (all match
CPython on both builds); `r9_genexp.py` is refused by name on both.  `test_ail_pre211.py`,
`test_ail_pre109.py`, `test_ail_safetynet.py`, `test_ail_files.py`,
`test_ail_corpus_findings3.py`, `test_ail_mixed_bounds.py`, `test_ail_flush_exit.py` and
`test_ail_bugs7.py` pass.
## 2026-10-25 - int(bytes-like, base=...) (job-pre212-10252300)

The pre192 review recorded that a keyword `base=` with a bytes-like first argument raised
`TypeError: int() can't convert non-string with explicit base` on both builds, where CPython
parses the bytes: `int(b"10", base=10)` is 10 and `int(bytearray(b"x"), base=10)` raises the
bytes-repr ValueError.  The general-path rewrite into `_ail_int2` only matched the positional
`int(x, base)` form, so the keyword form fell through to the str-only boxed runtime.

The rewrite now also accepts `int(x, base=...)` (exactly one positional argument and one `base`
keyword, no starred argument).  Because that path shares `int(x, base)`, the bytes parser now
validates the base before the literal (CPython checks the base type/range first), and the boxed
runtime checks the base range before the argument type, so `int(b"10", base=1)` and
`int(1.5, base=1)` both raise CPython's `int() base must be >= 2 and <= 36, or 0` instead of a
literal or type error.  The positional bytes form uses the same code and is fixed with it.

`test_ail_pre212.py` covers valid bases 0/2/8/10/16/36, both bytes forms, the direct/argument/
list-item/attribute/dict-value/alias routes for the value and the base, invalid literals and
their b-repr text, empty/signed/whitespace/underscore/prefix/non-ASCII/quote/control inputs,
the 200-character repr cut, invalid base types and ranges, the positional and str baselines, and
evaluation order, on both builds.  Probes: `/tmp/probes/p_intbase_kw.py`,
`p_intbase_kw_routes.py`, `p_intbase_kw_edge.py`, `p_intbase_range.py`; all match CPython on both
builds.

## 2026-10-25 - range.index/count equality and int64 result (job-pre216-10252305)

Review of the pre216 feature found two defects.  `range.index`/`range.count` only consulted
integer arithmetic, so a non-int/float value that compares equal to an element (a user
`__eq__`, Decimal, Fraction) either raised the generic not-found text or counted 0 where
CPython searches the range with `==`; the range branches now walk the range and compare with
`ail_member_eq` for any value that is not int/bool/float, counting every match as CPython's
generic sequence search does.  An index (or count) above `INT64_MAX` used the uncatchable
`ail_hit_limit` stop; it now raises a named, catchable `OverflowError`
(`range.index() index exceeds int64` / `range.count() result exceeds int64`) because AIL ints
are 64-bit.  Probes `/tmp/probes/p6_eq.py`, `/tmp/probes/p6b_listeq.py`,
`/tmp/probes/p7_huge.py` and the boundary probes for types, widths, empty, negative-step and
argument/list/attribute/dict delivery match CPython on both builds except the documented
above-int64 index, which is the named refusal.  `test_ail_pre216.py` covers the equality walk
and checks the above-int64 case is caught, not a hard exit.
## 2026-10-25 - range.index/count (job-pre216-10252305)

The first still-differing item from the memsafe2 review was `range.index()`: the general path's
method dispatch had branches for str/list/tuple only, so `range(2, 20, 3).index(8)` fell through
to `AttributeError: 'range' object has no attribute 'index'` on both builds (CPython: 2).  The
same gap covered `range.count()`.  `pyboxed2` now has a range branch for both methods (and a
range entry in the method type tags); `cruntime` locates an int/bool or an integral float
arithmetically without walking a possibly huge range, raises `<repr> is not in range` for a
missing int and CPython's `sequence.index(x): x not in sequence` for another value, and reports
range's one-argument arity TypeError.  The typed path still names both methods as unsupported, so
the default build falls back to the general path, which matches CPython.

Probes `/tmp/probes/p_range_index.py`, `/tmp/probes/p_range_methods.py` and
`/tmp/probes/p_range_zero_runtime.py` cover values as a literal, loop variable, argument, list
item, attribute, dict value and alias; int/bool/integral-float/non-integral-float/str values;
empty, positive-step, negative-step, huge-step and int64-boundary ranges; not-found messages;
and 2/3-argument arity calls.  Both `-g` and `-d` match CPython on every range method probe (the
zero-step item is a separate pre-existing difference and was not changed).  `test_ail_pre216.py`
is registered in `ail_check.MODULES` and `tools/ci_shards.json`.
## 2026-10-25 - local shadowing a module function, called before assignment (job-pre218-10252343)

The pre141 reviewer recorded `r13_plain_shadow.py`: in a function, `print(side(1)); side = None`
called the module function `side` on both builds, while CPython makes `side` local for the whole
activation and raises `UnboundLocalError` at the call. `r11` reaches the same name-resolution bug
through a default expression (that program is refused by name for its default, so the root cause
reproduces without it). The general path's `_call_name` now checks the activation's own binding
(parameter, assignment, loop/with/except target, import, cell or closure) before resolving a call
to a module function, reading the slot through the ordinary load path; a bound callable is called
and an unbound slot raises CPython's `UnboundLocalError`. The typed path cannot call an arbitrary
local value, so it refuses a call whose name is locally bound (and an optional-local retry for a
same-named module function) by name, and the default build falls back to the general path.
`AIL_CURRENT/test_ail_pre218.py` covers the plain case, a bound lambda, None, parameters, a loop
target, a branch-only binding, list-item / attribute / dict-value aliases, an ordinary call and an
optional local that is not called, plus the default-expression refusal. Probes in `/tmp/probes`
(`shadow_basic`, `shadow_bound_callable`, `shadow_bound_none`, `shadow_param`, `shadow_param_none`,
`shadow_for_target`, `shadow_branch_unbound`, `shadow_alias_list_item`, `shadow_alias_attr`,
`shadow_alias_dict`, `shadow_normal`, `shadow_optional_not_called`, `shadow_default_lambda`) match
CPython or are refused by name on both builds.
## 2026-10-25 - computed `%` format string formats at run time (job-pre220-10252345)

The first still-differing item from the `rbrbmemsafe2` review was runtime `%` with a non-literal
format: `fmt % value` through a name, argument, list item, attribute or dict value raised
`TypeError: unsupported operand type(s) for %` on both builds, where CPython formats it. The
general path only routed a str of unknown kind to the run-time formatter when the right operand
was a tuple/dict (or an enum-like value in a program with classes), so a scalar right operand fell
through to `ail_op_mod`. `pyboxed2.expr_BinOp` now routes every str-or-unknown left operand
through the run-time tag check: a str formats with `ail2f_percent`, anything else keeps
`ail_op_mod` (int/float/bool modulo, zero division and a user `__mod__`/`__rmod__` are unchanged).

`test_ail_pre220.py` covers scalar and tuple right operands, every common directive, values through
an argument, list item, attribute, dict value and alias, the int/float/bool/None boundaries and a
user `__mod__`, on both builds. The probes `p_pct_nonliteral`, `p_pct_more` and `p_mod_regress`
match CPython on g and d; the pre-existing user-object repr address and the `None % int` message
text were kept out of the regression probe.
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
## 2026-10-25 - pre142 withdrawn: saved-genexpr next() already works (job-rbpre142-10251802)

Review follow-up. The re-applied pre142 compile-time refusal was based on a stale premise: on
this tree job pre166 already gives a materialised generator expression a shared cursor, so
`g = (x * 2 for x in xs); next(g)` follows CPython (`2`, `4`, `[6]`) on both builds, and
`test_ail_pre166` passes on the base tree. The new pass therefore removed working behaviour,
and its scope-insensitive taint also refused valid reassignments, shadowed parameters,
branch-returned iterators and user-defined functions named `next`. The refusal, its checker
registration, `test_ail_pre142.py`, and the contradictory `DIFFERENCES.md` row are withdrawn;
`_check_saved_genexpr_next` is gone and the tree keeps pre166's cursor fix. Probes for the
recorded shape, reassignment (local/global/attribute/dict/alias), shadowed parameter, branch
return, direct `next`, and the user-defined `next` all match CPython on both builds.
## 2026-10-25 - pre121: constant int expressions are exact or refused by name

pre97's reviewer recorded that `2**63 - 1` in ordinary arithmetic or a variable, and a user
function called with `10**30`, still stopped at run time with `integer overflow` where CPython
keeps an unbounded int.  The compiler now evaluates an all-constant int expression exactly:
`2**63 - 1`, `-(2**63)`, `-1 << 63`, `~(-2**63)` and an in-range result reached through a wider
intermediate such as `2**100 // 2**80` are emitted as one literal.  A constant whose value does
not fit int64 (for example `10**30`) is refused by name at compile time instead of reaching the
runtime.  This is hooked into the typed `_expr`, the general emitter's `expr`, the unified
unboxed `nexpr` and the IR lowering, because a module-level statement can be lowered by any of
them; the existing maxsplit-specific folder is kept alongside it.  Added `test_ail_pre121.py`
(constant boundaries, dynamic and non-int expressions unchanged, and the recorded p6/p7/p13
shapes refused).  The pre160 module recorded the old run-time `integer overflow` stop for a
constant `10**30` inside `__index__`; its test now checks the compile-time refusal and keeps a
run-time-value variant for the overflow path.  Not fixed here: run-time `sep=None` (pre-existing
p12, a different cause).
## 2026-10-25 - maxsplit power folding (job-pre195-10251916)

The pre97 maxsplit folder rejected any power with an exponent of at least 64 before looking at
the rest of the constant expression, so `"a b c".split(" ", 2**100 // 2**80)` (final value
2**20) was refused on both builds while CPython runs it.  The power branch now uses the same
4096-bit limit as the compiler's other constant folder, so an intermediate may be wider than
int64; the whole expression is folded exactly, and a final value outside int64 is still refused
by name.  Review follow-up: the first guard also overestimated the width of a power
(`bit_length(base) * exponent`), which refused `((2**63 * 4)**63) >> 4095` even though the
4096-bit intermediate reduces to 1 and both CPython and the base tree accept it.  A capped
square-and-multiply test now measures the actual result width, so that expression, `2**2049 //
2**2029` and a 4096-bit intermediate are accepted; only a genuinely wider intermediate (for example
`2**4096 // 2**4050`, final value 2**46) is refused by name, although CPython computes it.
`test_ail_pre195.py` covers literals, a negative result, reduced powers, shifts, both sides of
the fold boundary, the out-of-int64 refusals, and the value through an argument, a list item, an
attribute, a dict value and a local on both builds.  Probes p_regress, p_orig, p_boundary,
p_neg, p_routes and p_types matched CPython on HEAD; p_over_literal, p_over_reduced and
p_over_intermediate were refused by name.
## 2026-10-25 - class repr of a user class value (job-pre196-10252020)

The first pre-existing item recorded by the rbpre170 review was that `repr(C)` for a user
class printed `<object>` where CPython prints `<class '__main__.C'>`; `str()`, `print()`,
containers, f-strings and `%r`/`%s` were the same because they share the writer. The v2
runtime's `ail__write_repr_body` had no `AIL_T_CLASS` case, so class values fell through to
the `<object>` default. It now writes CPython's class repr for top-level user classes; the
builtin-class branch is defensive because no tested construct can obtain a builtin class
value (`type()`, exception constructors and `__class__` are refused). Nested and
function-local classes are already refused by name at compile time, so no qualname is needed.

Probes in `/tmp/probes/pre196` (`p1`, `p9`, `p10`, `p16`, `p18`) covered direct, alias,
argument (including a default), list-item, dict-value, attribute, return, nested-container,
`str`, `print`, f-string and `%` routes on both builds and match CPython; `p6`/`p7`/`p17`
(nested, local and `if`-block classes) and `p14`/`p15` (builtin `type()`/`Exception`) are
refused by name. `p8` rebinds `__name__` and hits the separate unsupported `__module__`
path. A class value passed to the explicit `format()` builtin still hits the older int-default
formatter (`unsupported format string passed to non-int`); that path fails identically on the
base and is not part of this item. Added `AIL_CURRENT/test_ail_pre196.py` and registered it in
`ail_check.MODULES`.
## 2026-10-25 - pre191: accept the integrated rule for list/dict/default-tuple constants (job-pre191-10260206)

`test_ail_pre191` failed in the merged suite on `X = [1 << 64]`, `X = {"k": 1 << 64}` and
`def f(x=(1 << 64,))`: the integration tree's front-end constant-expression rule refuses those
positions first with `not in the subset: an integer constant expression here is outside the
signed 64-bit range`, while the test demanded this pass's own `int64 constant expression out of
range` wording.  The test now accepts either named refusal for every out-of-range position,
matching the tolerance already added for dead function-body unary shifts, and still rejects a
compiled program, `integer overflow`, or a `Traceback`.  Compiler behaviour is unchanged: this
pass still refuses all ten positions by name when its check runs.  Verified with the test on the
branch, on the current integration candidate, and on that candidate without this pass's source
change (the general refusal only).

## 2026-10-25 - pre191: accept the integration tree's function-body constant refusal (job-pre191-10252231)

Rebase follow-up. The integration branch now carries the general constant-expression rule that
refuses an out-of-int64 integer constant anywhere, including an unreached function body, with
`not in the subset: ... outside the signed 64-bit range`. `test_ail_pre191` still expected the
two dead unary-shift cases to print CPython's value, which passed on its older base but failed
once merged with that tree. The test now accepts either that CPython match or the integration
refusal, and still requires the refusal not to be this pass's own `int64 constant expression out
of range` message, so shift folding stays scoped to module/class/default positions. The source
is unchanged; module/class/default out-of-int64 constants remain refused by this pass on both
builds. Re-ran `test_ail_pre191` against a worktree of the current `integ` with this branch's
source applied (3 tests, OK), and against the local tree (3 tests, OK).

## 2026-10-25 - pre191 review follow-up: keep shift folding in the constant-position pass (job-pre191-10251807)

Review fix. Adding `LShift`/`RShift` to the shared `_constant_int` made the pre-existing
whole-tree `_check_int64_unary_constants` start refusing unary shift expressions in function
bodies, so `def f(): return 1; x = -(1 << 64)` and an unreached `return -(1 << 64)` failed to
compile where CPython and the base tree printed `1`. Shift folding is now opt-in
(`_constant_int(..., shifts=True)`) and only `_check_int64_constant_positions` asks for it;
the unary pass and its function-body reach are unchanged. The `DIFFERENCES` row no longer
overstates the fix: `X = 2 ** 65 - 2 ** 64` is a pre-existing clamped-power case that still
runtime-overflows on both builds. `test_ail_pre191.py` now includes the dead/unreached
function-body unary-shift cases on both builds.

## 2026-10-25 - pre191: out-of-int64 constants in module/class/default positions (job-pre191-10251807)

The first still-differing item from the pre184 review notes was the out-of-int64 constant in a
module, class or default position. On this tree the unreachable examples already printed `ok`,
but the reachable forms still compiled and then stopped at run time with `integer overflow`:
`X = 1 << 64`, `class C: X = 1 << 64`, `def f(x=1 << 64)` and `def f(x=2**63)`, where CPython
keeps a bignum. A new front-end pass evaluates only the outermost constant expression of each
module/class value and each function default (including tuple/list/dict values, defaults wrapped
by the mutable-default surface, and the bodies of module/class `if` blocks). An out-of-int64
result is refused on both builds as `int64 constant expression out of range: <value>`, matching
the pre172 wording. Because only whole roots are checked, expressions whose intermediate leaves
int64 but whose answer fits still work (`(1 << 63) - 1`, `2 ** 65 - 2 ** 65`, `0 << 1000`,
`(1 << 64) >> 64`); function-body constants keep the runtime trap, so pre160's `10**30` in an
`__index__` still stops with `integer overflow`. The general path's pre-existing refusal of
`N = -9223372036854775807 - 1` ("not in the subset: an integer literal outside int64 range")
is unchanged; the default build matches CPython for it. Added `test_ail_pre191.py` and registered
it in `ail_check.MODULES`. Probes r1-r15 in `/tmp/probes` cover the boundaries and both builds;
r2's general build keeps the named refusal above.

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
## 2026-10-25 - memsafe2: hostile stdin through parsing and text (job-memsafe2-10251519)

A seeded mutation fuzzer (`tools/input_fuzz.py`) fed empty, 1 MB, NUL, invalid-UTF-8, non-ASCII-digit and
extreme-number inputs to four programs (numbers, text, binary, slices) built with ASan+UBSan on the general
and default builds.  The first sweep found: signed-int64 overflow in slice length/increment at the int64
boundary (UBSan, wrong length, or hang) and `None` bounds held in variables/lists/attributes/dict values
read as 0; `int()`/`float()` error text mangled every non-ASCII unit (the low byte was copied) and ignored
`%.200R`; `format()` treated a non-ASCII (or control) type character as a `char` (wrong unknown-code/grouping
text and a ValueError instead of TypeError for None/list specs); `%`-format printed a non-ASCII/control conversion
character raw instead of `?`; bytearray's repr quote choice and `int(bytearray())` message differed.  All
are fixed in `safetyrt.py`, `cruntime.py`, `exctext.py`, `prelude_bytes.py`, `pyboxed2.py` and `pyboxed.py`.
Two known int64/16-bit-unit limits are recorded in DIFFERENCES (a valid non-BMP UTF-8 decode, and an int
beyond int64), plus one unrelated source-shape inference gap found by an over-broad mixed-type slice probe. `test_ail_hostile_input.py` holds the programs, the regression inputs and a seeded fuzz run.
Probes in `/tmp/probes` (`p_slice_dyn`, `p_slice_dyn2`, `p_slice_none`, `p_repr`, `p_fmt`, `p_convmsg`,
`p_int2`, plus the gen_* fuzz corpus) match CPython with sanitizers on both builds; explicit `None`
slice constants are refused by name on the typed path, so the default build falls back to the general path.

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
## 2026-10-24 - re-apply fuzz3n: str search None bounds (C168)

Re-applied job-fuzz3n-10220658 on this tree. The change itself was already in the export:
`_str_window_bounds` in `AIL_CURRENT/python/pkg-v12/pyboxed2.py` tests each supplied start/end
tag and passes `has_lo = 0` / `has_hi = 0` for a `None`, and `AIL_CURRENT/test_ail_fuzz3n.py`
(registered in `ail_check.MODULES`) covers the literal, variable, argument, list-item, dict-value
and attribute forms on both builds. The job's diff also listed `list.index` / `tuple.index` with
a `None` bound as an open difference, but this tree already closes that case with C169
(`_seq_index_bound` / `_check_seq_index_bound`), so no open row was added.

Tests on this commit: `test_ail_fuzz3n`, `test_ail_c169`, `test_ail_safetynet`, `test_ail_files`
and `test_ail_corpus_findings3` all pass (43 tests, 1 skipped for missing zig). Probes
`/tmp/probes/p_basic.py`, `p_sources.py`, `p_windows.py` and `p_types.py` match CPython on the
general and default builds.
## 2026-10-24 - fuzz42: bool abs()

- fuzz42: the general path's `abs()` kept a bool argument's BOOL tag, so `abs(False)` printed
  `False` and `abs(True)` printed `True` where CPython prints `0` and `1`. The plain call and the
  builtin-as-`key=`/`map()` wrapper now use `ail_bi_abs`, which boxes an intlike argument as an
  int. Added `test_ail_fuzz42.py` and registered it in `ail_check.MODULES`.
## 2026-10-24 - pre31 review: scope-aware, value-exact int() refusal

The first pre31 change read a module constant through a function parameter or local of the same name,
and it scanned every child of the argument, so `int(1e300 * 0)`, `int([1e300, 1.5][1])` and
`int({"a": 1e300, "b": 1.5}["b"])` were refused although the value reaching `int()` fits. The check
now evaluates only the value that reaches the conversion, with function, lambda, class and
comprehension bindings shadowing module constants. It follows unary/binary arithmetic, conditional
expressions, list/tuple/dict literals, constant subscripts, generated tuple fields and simple identity
functions; unknown expressions are not refused. Added the reviewer cases to `test_ail_pre31.py`.

## 2026-10-24 - pre31: int() of a float outside int64 is refused by name

`x = 1e300; int(x)` stopped with `integer overflow` on both builds where CPython prints a 301-digit
integer. This language's ints are int64, so the front end now refuses a conversion the compiler can
see is outside int64 when the float is a literal, a single-binding module constant, or a literal
reached through an argument, a list item, a tuple item or a dict value; the message names
`int() of a float outside int64` and the value. The conversion is unchanged when the result fits
(including the -2**63 edge). Run-time float values still stop at the documented int64 limit.
Added `test_ail_pre31.py` (9 refused programs, 1 matching program, both builds).
## 2026-10-24 - fuzz95: reproduce CPython's Timsort order for NaN

The reviewer rejected the earlier runtime refusal: it rejected valid sorts (a NaN that is never
reached cannot change the order) and failed after valid output. The typed, v1 boxed and v2 boxed
sort engines now all carry a port of CPython 3.12's Timsort and use it only when the sort keys
can contain a NaN; NaN-free keys keep the existing merge/introsort. `reverse=True` follows
CPython's own reverse-input / ascending-sort / reverse-output sequence, and tuple/list key
comparison checks identity first so a shared NaN object compares like CPython's. The typed
keyed/struct sorts carry their reverse flag at runtime instead of negating the key fields.
`test_ail_fuzz95.py` now asserts CPython's NaN order (direct, keyed, nested, reverse, through an
argument, a list item, an attribute and a dict value) in both builds. Six fresh probes
(`/tmp/probes/p200`-`p205`) and the ten reviewer probes match CPython on both builds.

## 2026-10-24 - fuzz95: NaN sorting refused by name

Differential probes for dict/list comprehensions and sorting found that `sorted`/`list.sort`
with a NaN in the values, or in a tuple/list sort key, silently returned a different order from
CPython in both boxed builds: CPython's Timsort gives NaN an input-dependent order that the
stable merge sort does not reproduce. Both boxed sort paths now scan the sort keys (recursively
through tuples/lists) and raise `ValueError: sorting NaN: CPython's Timsort order for NaN cannot
be reproduced`. A key with no NaN is still allowed. `test_ail_fuzz95.py` keeps the case. Other
probes matched CPython; a `10**30` integer overflow and four build refusals were non-silent.
## 2026-10-23 - binary_cursor_records: runtime traps are noreturn (job-perf3-10240012)

`BinaryCursor__remaining` checks `0 <= position <= len(data)` and then calls `ail_raise_named`, but the
runtime declared that trap as an ordinary `void` function. GCC therefore had to keep the fall-through
path alive and could not use the test to prove the subtraction cannot overflow, so `ck_sub` stayed in
the accessor. `ail_exception_uncaught` has the same property (it ends in `_Exit(1)`), so both now have
an explicit `__attribute__((noreturn))` declaration in `cruntime.py`. No app source changed.

Profiling: rdtsc instrumentation of the generated C (40M records, 496 MiB) put the per-record loop at
709,541,927 of 1,193,992,702 cycles (59.5% of the function). The accessor checks are inside that loop;
hand-edited generated C put the `ck_sub` in `remaining()` alone at ~8% overall and all unchecked reads
at ~16%, so the 9.1% below is in line with that ceiling.

`python3 bench/compare.py --app binary_cursor_records`:

| | AIL/C | AIL new/base/C/Rust ms | RSS MiB new/base/C/Rust | binary KiB new/base/C/Rust |
| --- | ---: | ---: | ---: | ---: |
| before | 5.091 [5.041, 5.253] | 50.8/50.8/10.0/9.6 | 1.7/1.7/2.5/2.7 | 39/39/15/1912 |
| after | 4.630 [4.607, 4.674] | 46.0/51.0/9.9/9.6 | 1.7/1.7/2.5/2.7 | 35/39/15/1912 |

Ratio improved 9.1%; `compare.py` checked every timed run byte-for-byte against its Python oracle.
Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`,
`test_ail_exception_values_core`, `test_ail_exception_values_app`, `test_ail_excfix`,
`test_c_api_bridge`, `test_ail_parallel_for`, `test_ail_short_style_traps` all pass. Probes
`/tmp/probes/perf3_*.py` match CPython on both the general and default builds.
## 2026-10-23 - method bounds with annotated returns (job-perf3b-10240813)

The earlier method-field analysis did not fire on the real accessors: the AIL front end writes
`-> int` as the bare name `__ail_checked_int__`, and `inline_candidate` walked the `FunctionDef`
including its return and argument annotations, so that load made every annotated zero-argument
method look impure and `remaining()` was never analysed in place. Annotations are not runtime body
expressions; `rangecheck.py` now collects the id of every annotation node and skips those nodes in
the candidate walk. Nothing else changes: a method with an assignment, loop, try or non-builtin
call is still rejected, and a field store, unknown call or alias still forgets its facts.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 40.8/47.2/9.8/9.5 | 0.866 [0.863, 0.871] faster | 4.145 [4.119, 4.170] slower |

Before (HEAD 4ffe276) the AIL/C ratio was `4.728 [4.701, 4.824] slower`; the ranges do not overlap
(13.4% less AIL time, above the 3% keep threshold). Result:
`bench/results/2026-10-23-12f2492.json`. The new test checks that generated
`Cursor__read_u8`/`read_u32_le` contain no `ail_bytes_get`, while the unguarded method keeps its
check.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`cursor_fields.py` and `bcursor_fields.py` (annotated `remaining`/`read_*` analysed in place,
u8/u16/u32 widths, empty, exact short and long boundaries, negative position, aliasing, values
through an argument, a list item, an attribute and a dict value), `method_side_effects.py`
(annotated methods with a store, a loop and a try are not inlined; out-of-range reads still raise),
`range_guards.py` (plain guarded reads on bytes/list plus unguarded bytes indexing). Tests:
`test_ail_range_checks.py`, `test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`,
`test_ail_files.py`, `test_ail_corpus_findings3.py` all pass.

## 2026-10-23 - range proofs through struct fields and safe method inlining (job-perf3b-10240127)

`binary_cursor_records` was 4.99x slower than C because every `read_*` method rechecked the same
cursor invariants: `remaining()` validated `position`, each byte read paid `ail_bytes_get`'s bounds
check, and the index arithmetic paid `ck_add`. The value-range analysis only reasoned about plain
locals, so it could not connect a guard on a method result to the receiver's fields.

`rangecheck.py` now tracks fields of a single unaliased object parameter (`#fld:o.f`, plus
`#len:#fld:o.f` for bytes/list fields), and records the identity of a subtraction between two exact
symbols. A guard on the difference (`available < 4`) therefore refines its operands
(`position <= len - 4`). Zero-argument methods whose bodies are only guards and a return, with no
assignment, loop, try or non-builtin call, are analysed in place against the caller's field facts,
so `remaining()`'s guard proves `position <= len` inside each `read_*`; `prove_le` now follows a
chain such as `start -> position -> len` that was previously stopped at an already-seen symbol.
Field facts are forgotten on a field store, an unknown method call, an unanalysed construct, or a
field passed to other code, and a function with any parameter besides the receiver is not tracked,
so an aliased argument cannot leave stale facts. `pyfunc.py` wires the class field/method lookups
into `rangecheck.Info` and marks bytes-field subscripts for the same resolver.

`python3 bench/compare.py --app binary_cursor_records`, median of nine windows on this runner:

| app | ms ail/base/c/rust | ail/base | ail/c |
| --- | --- | --- | --- |
| binary_cursor_records | 41.4/51.3/10.5/10.0 | 0.803 [0.801, 0.806] faster | 3.975 [3.943, 4.031] slower |

The base ratio was `4.986 [4.904, 4.997] slower`; the ranges do not overlap (19.3% less AIL time).
Result: `bench/results/2026-10-23-3b21283-dirty.json`. The generated C for `read_u8`, `read_u16_*`
and `read_u32_*` has no `ail_bytes_get`/`ck_add`/`ck_sub` left, and every timed run matched the
Python oracle byte-for-byte.

Probes (`bash ~/tools/cmp.sh /tmp/probes/<name>.py $PWD`, CPython and both compiler paths agree):
`field_remaining_reads.py` (inlined `remaining`, u8/u16/u32, exact boundary, invalid position),
`field_mutation_soundness.py` (field store, bytes-field reassignment, unknown method call, aliased
object argument all keep the out-of-range read checked), `field_guard_bounds.py` (direct
`len(field) - 1` guard and negative index). Tests: `test_ail_range_checks.py`,
`test_ail_binary_cursor_cli.py`, `test_ail_safetynet.py`, `test_ail_files.py`,
`test_ail_corpus_findings3.py` all pass.
## 2026-10-23 - csv_table: inline small leaf loops (job-perf4-10240813)

`field += ch` was already in place and its slow path is about 1% of calls, so this job took
the next cost. Profiling a 132 MB three-million-row input (`gprof -pg`) put
`csv_table_group_scan` at 79% and `parse_int64_decimal` at 2.15% flat. Flat cost understates
it: replacing the parse with a constant saved 7.3% of wall time, while asking gcc to inline
that same nine-statement leaf loop saved 20% (1.24 s -> 0.99 s, user 1.08 s -> 0.84 s). The
extra is the call boundary in the row loop, not the digit loop. The feed/chunk copy was a
larger upper bound (14.5% if the chunk buffer is reused unsafely) but safe per-chunk ownership
saved only 1.6%, so it was rejected.

The compiler now asks for `always_inline` on a function whose body is one `for` loop, no
other loop/try/with/yield, no call to another function or class constructor, a scalar numeric
return, at most 12 statements and 180 AST nodes; recursion, entry points and the existing
straight-line rule are unchanged. In `csv_table` this fires on `parse_int64_decimal` and
`parse_int64_decimal_bytes` only. String/list/object returns are excluded: inlining
`json_quote` as well measured 1.42 s, slower than 1.25 s.

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 14.5/14.5/6.1/6.9 | 0.995 [0.992,1.016] tie | 2.390 [2.341,2.456] slower | 2.093 [2.053,2.252] slower |
| 12.1/14.6/6.1/6.9 | 0.841 [0.814,0.852] faster | 1.979 [1.972,2.031] slower | 1.770 [1.717,1.800] slower |

RSS 5.5/5.5/3.3/3.8 -> 5.5/5.5/3.3/3.6 MiB, binary 107/107/20/1928 -> 111/107/20/1928 KiB,
build disk 400/400/44/1952 -> 412/400/44/1952 KiB. The app's boundary controls and Python
oracle still pass byte-for-byte.

Tests: `test_ail_integer_codec test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_csv_writer test_ail_utf8_stream_fuzz test_csv_column_stats_stream` (24 tests) and
`test_ail_safetynet test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass.
Probes `/tmp/probes/loop_inline.py` and `/tmp/probes/loop_inline_objects.py`
(`bash ~/tools/cmp.sh`) cover negative/empty/invalid parse paths, early return, break/continue,
loops reached through arguments, list items and dict values, and string/list/dict mutations;
both builds match CPython stdout on every case.

## 2026-10-23 - csv_table: one UTF-8 scan per chunk (job-perf4-10240013)

`field += ch` was already in place. The generated code calls `ail_str_cat`, whose first
cases return the existing value or a view when the operands are adjacent, and whose
remaining case appends into the newest arena block with amortized growth
(`AIL_SARENA_TOPS`). The slow path is about 1% of calls; forcing the builder-local path
(`ail_bl_append`, which copies `key = field` per row) measured 3.29 s against 2.48 s on a
263 MB file, so it was rejected.

Profiling the rest (`gprof -O3 -pg`, same file) put `_utf8_complete_length` at 11.2% and
`ail__utf8_validate` at 9.1%: `utf8_decode_feed` scanned `combined` to find the last
character boundary and then `decode("utf-8")` scanned it again to validate. A chunk only
ends mid-character at a chunk boundary, so `_utf8_tail_complete` now checks the final byte
(and at most three continuation bytes) and sends the whole buffer straight to decode. The
full `_utf8_complete_length` scan still runs for the rare split chunk, so the pending bytes,
the feed on which an error is reported, and the decoded text are unchanged. Amdahl bound
about 11%; measured 7.0% on the app (AIL/base 0.930).

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 16.5/16.5/6.9/7.8 | 1.006 tie | 2.387 slower | 2.126 slower |
| 15.5/16.7/7.0/8.0 | 0.930 faster | 2.200 slower | 1.933 slower |

RSS 5.5/5.5/3.2/3.8 -> 5.5/5.5/3.2/3.6 MiB, binary 107/107/20/1928 KiB unchanged, build
disk 400/400/44/1952 KiB unchanged. The app's boundary controls and the Python oracle still
pass byte-for-byte.

Tests: `test_ail_utf8_stream_fuzz test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_splitlines_utf8 test_csv_column_stats_stream` (18 tests) and `test_ail_safetynet
test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass. Probe
`/tmp/probes/utf8_tail.py` (`bash ~/tools/cmp.sh`) compares the old and new boundary logic
on 5,232 curated and random byte strings: same stdout, 0 mismatches, in both builds.
## 2026-10-23 - pre22: `with` around `yield` (job-pre22-10240312)

The p12/p23/p24 case still differs on this tree: a generator with `with` around its `yield`
and then `g.close()` runs no `__exit__` at all, because the general path's generator close finishes
the fiber without running the suspended frames (CPython raises `GeneratorExit` there and passes it
to `__exit__`). Building real `GeneratorExit` close semantics is a runtime change outside this job,
so the construct is refused by name before file-lowering removes the `with`:

* `withlib.refuse_with_yield` (called from `pyboxed2.Compiler.compile`) refuses any `with` whose
  body yields in the same function, for every manager expression and for `with open(...)` too.
* `test_ail_pre22.py` covers the refusal on both builds and checks that a `with` beside (not
  around) a `yield` still runs and matches CPython.
## 2026-10-24 - pre34: literal `%d` accepts a float (profile percentages)

CPython's `%d` converts a real operand with `int()` rules, so a profile line such as
`print("%d%%" % (100.0 * part / total))` prints `60%`; a non-number raises
`TypeError: %d format: a real number is required, not str`. The general path handled only
int/bool in its literal-`%d` fast path (`pyboxed2._percent_format`), so a float percentage
stopped with `TypeError: unsupported format string passed to non-int`. `%i`, `%u` and a computed
template already used `safetyrt.ail2f_percent` and matched CPython. The literal `%d` path now
keeps `ail_obj_format` for int/bool and sends other operands to `ail2f_percent`, which truncates
finite floats toward zero, raises `ValueError` for NaN and `OverflowError` for infinity, and
produces CPython's type-error message. Out-of-int64 finite floats remain the documented int64
limit. Added `test_ail_pre34.py` (4 programs, both builds) and registered it in
`ail_check.MODULES`; DIFFERENCES `C?-job-pre34-10240952-1`.

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
