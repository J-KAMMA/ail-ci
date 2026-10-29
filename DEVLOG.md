## 2026-10-29 -- ex25 review fix: gate export validation on real `ail_ffi.export` use

The review found the normal-build export gate was a substring test (`'@' in text and 'export' in
text and 'ail_ffi' in text`), so an unrelated `@extern` program that merely contained the word
`export` was sent through `ail_export.lower` and refused (`C libraries use only \`export\` from
ail_ffi, not extern` / `not *`) on both builds.  `ail_export.uses_export` now parses the file and
returns true only for a real `@export` / `@export()` / `export(...)` use of an `ail_ffi` import
(direct, aliased, `import ail_ffi` attribute, or star import); a mere import, comment, string,
identifier or unrelated `@extern` file leaves `lower()` untouched and keeps its previous C.
Added `extern_call_word_export` to `test_ail_ex25.py` so the actual `@extern` regression is
covered on both builds.

Probes in `/tmp/probes/ex25fix` on both builds via `cmp.sh`: `g01_extern_comment_word`,
`g02_extern_string_word`, `g03_star_word`, `g04_no_ffi_word`, `g05_import_unused`,
`g06_alias_values` (negative/empty/bytes/list/dataclass fields through an argument, list item,
dict value and attribute) and `g07_module_attr` match CPython; `g08_alias_invalid`
(`unsupported type list[str]`) and `g09_attr_invalid` (`reading __ail_export__`) are refused by
name.  Re-ran `/tmp/rprobes/r01`-`r09`: r01-r05 and r07-r09 match CPython on both builds; r06
(write to `__ail_export__`) and r08 (`f = export(f)`) are the pre-existing refusals.  Final-state
tests: test_ail_ex25, test_ail_c_export, test_ail_ffi, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-29 -- ex25: a normal build of ail_ffi's `@export` decorator (job-ex25-10290857)

The Python-syntax examples in `AIL_CURRENT/language_examples` are `hello.ail`, `integer_series.ail`,
`math.ail`, `stdin_sum.ail`, `sum.ail`, `use_math.ail` and `c_export/geometry.py`.  `hello`,
`integer_series`, `stdin_sum` and `sum` build directly; `math.ail` is refused as a standalone
program (`the first parameter must be the sequence read from the file`), `use_math.ail` without
`--module math.ail` (`the name 'sum_to' is not a known function/class/builtin`), and
`geometry.py` (`not in the subset: the decorator on def add`).  The first two are module fragments
whose documented builds use `--module`; `geometry.py` is the refused standalone program with a
CPython oracle (`5 3 HÉLLO! [1, 4, 9] 3.0`, exit 0).

`@export` / `@export()` from `ail_ffi` (also through an alias and `@ail_ffi.export`) is now a no-op
on a top-level function in a normal build, which is what CPython's decorator does after checking
the C signature (it returns the function unchanged; `--lib` still lowers it separately).  The
`@extern` lowering keeps the `export` import only when an export decorator is actually present, so
extern-only programs keep their previous source, and a normal compile validates the export
contract through `ail_export.lower`, refusing an invalid signature by name instead of silently
accepting it.  `geometry.py` now builds on both the general and default builds and matches CPython.

Probes in `/tmp/probes/ex25` on both builds via `cmp.sh`: `p01_basic`, `p02_call_and_alias`,
`p03_module_attribute`, `p04_routes` (argument, list item, dict value), `p05_dataclass`,
`p06_import_only`, `p07_no_feature` match CPython; `p04b_attribute` (a function stored in an
instance attribute, then `Box().fn()`) and `p12_method` are refused by name; the invalid export
contracts `p08_invalid_list_str`, `p09_invalid_default`, `p10_invalid_missing_return` and
`p11_second_decorator` are refused by name where CPython raises `TypeError`; `p15_mixed_extern`
(a file with both `@extern` and `@export`) is refused by name by the export validator.
`p13_export_attribute` (`getattr` of `__ail_export__`) is refused by name because the compiled
program has no decorator registry, and `p14_export_registry` is refused by name.  Added `AIL_CURRENT/test_ail_ex25.py` (3 tests)
and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.  Final-state tests:
test_ail_ex25, test_ail_c_export, test_ail_ffi, test_ail_python_syntax, test_ail_unified,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py` was
run and `--check` passes.

## 2026-10-28 -- pre423 review: unpacked literals in an annotation are unknown, not truthy

The pre423 review found that `_annotation_truth` used `bool(node.elts)` / `bool(node.keys)`, so a
literal whose contents are empty only after unpacking (`[*()]`, `(*(),)`, `{*()}`, `{**{}}`) was
treated as truthy.  In a short-circuit position the live branch was then skipped and the deferred
read was missed: `class C: x: ([*()] or (lambda: C)()) = 1` compiled and printed `1` on both
builds where CPython raises `NameError`, and the base refused it by name.  A list/tuple/set
literal with any `ast.Starred` element, and a dict literal with any `None` key (`**` unpacking),
now has unknown truth, so the read stays refused by name.  Nested containers whose outer literal
has no unpacking keep their static truth (`[[*()]]` is still truthy and matches CPython).

Probes in `/tmp/probes/pre423fix` on both builds via `cmp.sh`: `p_star_list_or`,
`p_star_tuple_or`, `p_star_set_or`, `p_star_dict_or`, `p_star_list_if`, `p_star_tuple_if`,
`p_star_dict_if`, `p_star_list_notif`, `p_star_dict_notif`, `p_star_mixed_dict_or`,
`p_star_nonempty_list_or`, `p_star_nonempty_dict_or` and the four container/argument routes
(`p_via_list_item`, `p_via_attribute`, `p_via_dict_value`, `p_via_argument`) are refused by name
(`a class body annotation reads the class name C before it is bound`); `p_star_nested_list_or`
matches CPython on both builds.  Added the cases to `test_ail_pre423.py`.

## 2026-10-28 -- pre423: a statically dead deferred read in a class annotation matches (job-pre423-10281734)

The first still-differing case in the pre410 review's deferred-read area was a deferred lambda or
generator-expression element behind a statically false branch: `class C: x: ((lambda: C)() if
False else 1) = 1` and `class C: x: (0 and (lambda: C)()) = 1` were refused on both builds
(`a class body annotation reads the class name C before it is bound`) where CPython never
evaluates the read and prints `1`.  `_annotation_reads` now follows the statically known truth of
an `if` expression and of `and`/`or` operands, including empty containers, `None`, the empty
string and numeric unary forms, so a dead operand is not visited while a live one still is.  An
unknown condition keeps the conservative refusal, as do lambda defaults and the first generator
iterable.  The simple loop-target cases recorded by the pre410 review already matched CPython on
this tree (`for C in [1, 2]`, `for C in range(10): break`, a tuple target and nested loops), as
did bare deferred lambdas/generator expressions.

Probes in `/tmp/probes/pre423` on both builds via `cmp.sh`: `u_if_false`, `u_and_false_0`,
`u_and_false_empty`, `u_and_false_dict`, `u_and_false_none`, `u_and_false_str`, `u_or_true_1`,
`u_or_true_list`, `u_or_true_dict`, `u_or_true_str`, `t_bool_chain`, `t_genexp_false`,
`t_routes`, plus the original loop-target and deferred probes, match CPython; `u_if_true`,
`u_and_true`, `u_or_false`, `t_if_true_read`, `t_genexp_true` and `t_unknown_cond` are refused by
name where the first five raise CPython's `NameError` (the unknown condition is the conservative
refusal).  Remaining pre-existing and unchanged: a `for` over a statically empty `range(0)` still
lets its target hide the read (CPython raises `NameError`), and a generator expression passed to
an unmodelled consumer that iterates it is still accepted.  Final-state tests: test_ail_pre423,
test_ail_pre410, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (5 modules,
0 failed).  `tools/update_manifest.py` was run and `--check` passes; `tools/ci_shards.py
--update` added the module and `--check` exits 0.
## 2026-10-28 -- pre417: a module-level container read before a later mutation is refused (job-pre417-10281339)

The pre402 review recorded, as pre-existing on both builds, the module-level `d = {"k": 1e300};
print(int(d.get("k"))); d.update({"k": 1.5})`, which compiled and then stopped with `integer
overflow` where CPython prints the big integer.  `_scope_constant_map` returned only the final
environment, so the later mutation dropped `d` before the earlier read was checked.  The int64
check now visits each top-level statement with the constants visible at that statement; a
`dict.get` read is load-only, and a call that may mutate or rebind a tracked name clears the
environment afterwards, so a callback alias can only lose a refusal, never invent one.  The
conversion is refused by name on both builds (`int() of a float outside int64: ... (CPython
makes a big integer)`) through `.get`, a subscript, a list item, a dict value, an alias, an
item store, an alias mutation, a later mutating call, a function argument (`.get` and
subscript), a constant key name and a negative index.  In-range reads, a mutation before the
read, callback aliases (`sorted`/`map`) and programs without the feature match CPython.

Remaining pre-existing and unchanged: a function-local container read before a later mutation
(`p07`), a container reached through a nested list/dict (`p09`/`p14`), an instance attribute
(`p13`) and a module scalar rebound later (`p15`) still stop with `integer overflow`.
Probes in `/tmp/probes/pre417` on both builds via `cmp.sh`: p01-p06, p08, p10-p12, p16-p17,
p20-p24, p25-p26, p28-p29 match CPython or are refused by name; p07, p09, p13-p15 and p27
remain the pre-existing run-time trap (p27 reads before a risky call in the same statement).
Final-state tests: test_ail_pre417, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (4 modules, 386 s, 0 failed).  `tools/update_manifest.py` was run and
`--check` passes; `tools/ci_shards.py --update` added the module and `--check` exits 0.
## 2026-10-28 -- pre419: subscripting a class names the class (job-pre419-10281416)

The pre396 review recorded as pre-existing that `class A: pass; A[0]` raised `TypeError:
'type' object is not subscriptable` on both builds, where CPython 3.12 says `TypeError: type
'A' is not subscriptable`.  The v2 general runtime (`ail_op_getitem` / `ail_op_getslice` in
`cruntime.py`) now quotes the class's own name through `ail_class_name_c` for an index or
slice key, capped at 200 characters like CPython's `%.200s`.  Item assignment and deletion
keep their `'type' object ...` wording, and non-class receivers are unchanged.  A class
defining `__class_getitem__` or a metaclass `__getitem__` is still not modelled; that is the
same separate pre-existing difference on the base tree and is not changed here.

Probes in `/tmp/probes/pre419` on both builds via `cmp.sh`: `p01_keys` (None, bool, int,
negative, float, str, tuple, list and bytes keys), `p02_slices` (slice literals and slice
objects), `p03_routes` (alias, argument, list item, dict value, attribute, return from a
function, subclass and a slice), `p04_long_names` (199, 200, 201 and 250-character class
names), `p05_control` (instances, ordinary subscripts and non-class values) all match
CPython; `p06_class_getitem` still differs identically to the base and is unchanged.  Added
`AIL_CURRENT/test_ail_pre419.py` (4 tests) and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.  Final-state tests: test_ail_pre419, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 (4 modules, 0 failed).
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-28 -- re-apply pre378 on the integration tree (job-rbpre378-10281427)

Re-applied the accepted pre378 fix (an instance subscript without `__getitem__` names its
class) on top of the current integration tree.  The code conflict was already resolved by the
tree's newer pre377 follow-up: `ail__raise_item_tname` is called by the getitem and getslice
fallbacks and by `dunderrt`'s string-matched patches, and it uses `ail__tname_c` with a
dynamically sized message capped at 200 characters as CPython's `%.200s` does.  That helper and
the call sites were kept instead of adding the older `ail__raise_not_subscriptable`, so the
class name, subclass name, long-name and builtin-name behaviour are all preserved.  The
incoming `test_ail_pre378.py` was added and registered in `ail_check.MODULES` and
`tools/ci_shards.json` (weight 33.5).  `tools/diff_ids.py` is not present on this tree.

Probes in `/tmp/probes` (6 programs, both builds via `cmp.sh`): `p_basic` (int, negative, bool,
float, str, `None` and tuple keys; int and negative slices; subclass), `p_routes` (argument,
alias, attribute, dict value, list item; int and slice), `p_boundaries` (class-name lengths 1,
32, 33, 34, 40, 200, 201 and 210), `p_uncaught` (exit 1, identical stderr), `p_dunder`
(`__getitem__` control and `__eq__`-only class) and `p_builtins` (int, `None`, float, bool and
a builtin function object) all match CPython.  Final-state tests: test_ail_pre378,
test_ail_pre377, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (30 tests,
0 failed, 1 skipped for no zig).  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-28 -- pre421 review: keep no-class C byte-identical (job-pre421-10281638)

The pre421 review found that the class-name index text was spliced into the v2 runtime
unconditionally, so a no-class general-path program's `--debug-dir` C changed in the
list/tuple getitem, setitem and delitem prelude.  The base runtime text is restored, and
`pyboxed2` applies the three edits to the preamble only when the source itself contains a
`class` statement (`source_has_class`, taken before the safety preludes inject their own
classes).  No-class programs, including ones whose preludes add classes for slices, now
emit C byte-identical to base; class-bearing programs keep the class-name messages.
`test_ail_pre421` gains a C-text test that checks both sides, and its builtin-key program
declares a class so it exercises the class-name text.  Probes in `/tmp/probes/pre421_fix`
on both builds via `cmp.sh`: `p_class_routes` (instance, subclass, alias, argument, list
item, attribute, dict value, exception instance, builtin function, list and tuple),
`p_class_setdel`, `p_class_builtins` and `p_long` (200/210 characters) match CPython;
`p_noclass` and `p_noclass_slice` stdout/exit match, and their `--debug-dir` C is
byte-identical to `/tmp/base` (as is `p_nofeature_wrap`); `p_class_nofeature` differs
from base only in the three index-error prelude hunks.  The `p_builtins` no-class
bytes/bytearray/function names remain the base text, as the C-identity rule requires.

## 2026-10-28 -- pre421: list/tuple index errors name the key's class (job-pre421-10281638)

The pre411 review listed as pre-existing that `Box(Bad())` as a list or tuple index said
`not instance` where CPython says `not Box`.  The v2 general runtime's list/tuple getitem
built the message from the value tag (`ail_type_name`); it now uses the existing
object-to-name helper (`ail__tname_c`) and caps the class name at 200 characters, as
CPython's type-error text does.  A list item store and deletion with the same key now also
name the class; they previously omitted the `not ...` part.  The other three recorded
items (enum member `.value`, slice bounds and bytes/bytearray subscription through
`__index__`) are separate causes and were left unchanged.

Added `AIL_CURRENT/test_ail_pre421.py` (1 test, 4 programs, both builds) and registered it
in `ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes/pre421` on both
builds via `cmp.sh`: `p2_a` (list/tuple through a constructor argument), `p2_c` (through a
function value), `p2_routes` (subclass, alias, argument, list item, attribute, dict value,
direct read), `p2_alias` (alias/attribute/list/dict routes and tuple), `p2_long2`
(210-character class name, capped at 200), `p2_builtins` (float/str/None/list/dict/tuple/
bytes/function keys and an empty list) and `p2_setdel` (list store and deletion) all match
CPython.  `p2_b` (`Box.__index__` returning a non-int) still differs and is a separate
pre-existing cause, not changed here.  Final-state tests: test_ail_pre421,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py`
was run and `--check` passes.
## 2026-10-28 -- pre422: an exception instance names its class in slice errors (job-pre422-10281644)

The pre414 review recorded that its ``deletion ... of an item`` wording was too broad: slice
deletion still took the old path, and ``del MyErr()[0:1]`` printed
``'exception' object does not support item deletion`` on both builds where CPython prints
``'MyErr' object does not support item deletion``.  The slice assignment/deletion path is
``safetyrt.SLICE``'s ``ail2s_setslice``, whose non-list message used ``ail_type_name(c.tag)``
(the tag name) instead of the object-to-name helper the item path took in pre414.  It now
calls ``ail__raise_item_tname``, so exception instances and subclasses, ordinary instances and
builtin names match CPython for deletion and assignment, directly and through an alias, an
argument, a list item, an attribute and a dict value, with empty/``None``/negative bounds and
CPython's 200-character name cap.  The item path itself is unchanged.

Probes in ``/tmp/probes/pre422`` on both builds via ``cmp.sh``: ``p_slice_del.py``,
``p_slice_routes.py``, ``p_slice_builtins.py``, ``p_slice_more.py``, ``p_slice_long.py`` and
``p_slice_uncaught.py`` match CPython (the first two differed on both builds before the
change).  Added ``AIL_CURRENT/test_ail_pre422.py`` (2 tests, 3 programs, both builds) and
registered it in ``ail_check.MODULES`` and ``tools/ci_shards.json``.  Final-state tests:
test_ail_pre422, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
``tools/update_manifest.py`` was run and ``--check`` passes.
## 2026-10-28 -- re-apply pre386: a routed-base `**` power outside int64 (job-rbpre386-10281433)

Re-applied the accepted pre386 change on top of this tree.  The accepted diff no longer applied
because the integration tree already carries the newer pre367 `**` resolution
(`_check_int64_binpow_constants` / `_binpow_power_parameters`), which covers a parameter bound
at a module call site (positional, keyword, alias, identity wrapper, tuple item), a
function-local scalar, a module list item, a module dict value, `dict.get` and a
class/instance attribute.  The accepted `AIL_CURRENT/test_ail_pre386.py` is added; its refusal
assertion accepts both pre386's `does not fit in a 64-bit signed integer` and this tree's
existing `int64 constant expression out of range`, and still rejects `integer overflow`.  It is
registered in `ail_check.MODULES` and `tools/ci_shards.json` (weight 18.2).

The pre386 review found one route pre367 did not cover: a literal container bound inside a
function (`def f(): xs = [10]; print(xs[0] ** 40)`, and the dict mirror).  It compiled and then
stopped with `integer overflow`, where the accepted pre386 refuses by name and CPython prints
the exact integer.  `_binpow_function_lookup` now also resolves a function's own safe literal
containers through `_scope_constant_map`, so the local list item, dict value, an alias of the
container and the `2 ** 63` boundary are refused by name on both builds; a container mutated
or rebound in the same body stays dynamic and keeps the run-time stop, as before.  The
accepted test gained the two refusing local probes and two matching in-range local probes.

Probes in `/tmp/probes/fix386` on both builds via `cmp.sh`: the local list item, local dict
value, local alias and the `2 ** 63` boundary are refused by name; local in-range list/dict,
safe bases -1/0/1, negative exponent, float/bool bases and a dynamic index match CPython.  A
mutated or rebound local container, a function-local `dict.get` and a function-local tuple
item still stop with `integer overflow`; all are pre-existing and the accepted pre386 leaves
them too.  `tools/diff_ids.py` is not present on
this tree.  Final-state tests: test_ail_pre386, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-28 -- pre392: int() of out-of-int64 text from a container through a wrapper (job-rbpre392-10281505)

Re-applied the accepted pre392 change on the current integration tree.  Its behaviour was already
carried here by later integration work: `_Int64CallChecker.visit_Call` applies `_check_conversion`
(both the float check and `_int_conversion_outside_int64` for text/bytes) to arguments reaching
`int(<parameter>)`, including values resolved through `argument_containers`.  No `ail_chatgpt.py`
delta was needed; the accepted test and its registration are added.

The accepted tests cover text read from a bound container and converted by a helper's `int(v)`:
dict value, list item, tuple negative index, int key, class/instance attribute, alias, `dict.get`
and its default, a keyword argument, a wrapper/passthrough chain and a function-local container,
all refused by name (`int64 constant expression out of range`) on both builds.  In-range
text/bytes, invalid text, dynamic text, a container mutated to an in-range value, a reassigned
binding and a helper that does not convert match CPython; the float refusal is unchanged.  A
nested container keeps the pre-existing run-time limit.

Added `AIL_CURRENT/test_ail_pre392.py` (3 tests: 14 refused programs, 7 matching programs and the
float control, both builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
Direct run on this tree: 3 tests, 52.9 s, OK.  `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-28 -- pre395 review fix: cap the class name at 200 characters (job-rbpre395-10281537)

The pre395 review found that `ail__raise_class_not_subscriptable` did not apply CPython's
`%.200s` cap to the class name, so a 201-character class appeared in full (`len(str(e))` 229
instead of 228) on both builds, for an index and a slice.  The helper now truncates its
converted name to 200 characters, matching `ail__raise_item_tname`.  The same cap is applied
to aliases and to values reaching the subscript through an argument, a list item, a dict
value, an attribute or a return value.

Probes in `/tmp/probes` on both builds via `cmp.sh`: `p19_len1`, `p19_len199`, `p19_len200`,
`p19_len201`, `p19_len250` and `p19_len300` (index, slice and negative index at each name
length) and `p19_routes` (201-character class through alias, list item, dict value, attribute,
argument and return value) all match CPython.  Final-state tests: test_ail_pre395,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3, 4 modules, 272 s, 0 failed.
`tools/update_manifest.py` was run and `--check` passes.  Correction to the entry below: the
earlier claim that plain instance `A()[0]` prints `'instance'` was wrong; HEAD and base print
`'A'`, matching CPython, and only the exception instance `E()[0]` prints `'exception'`.

## 2026-10-28 -- re-apply pre395: class object subscript names the class (job-rbpre395-10281537)

Re-applied the accepted pre395 change on top of the current integration tree.  The pre377
review's first still-differing pre-existing item reproduced on both builds: `class A: pass;
A[0]` stopped with `TypeError: 'type' object is not subscriptable`, where CPython 3.12 says
`TypeError: type 'A' is not subscriptable`.  The general-path runtime's `ail_op_getitem` and
`ail_op_getslice` now name a class object's own class in that error
(`ail__raise_class_not_subscriptable`), and the dunderrt patch fragments still match.  The
message follows the class actually subscribed through an alias, a subclass, an argument, a
list item, an attribute, a dict value and a return value, for int, negative, wide, bool,
None, float, str, empty-str and tuple keys and full/open/step/negative/reverse slices.  Item
assignment keeps CPython's `'type' object does not support item assignment` wording.  The
recorded second item (`E()[0]`, an exception subclass) still prints `'exception'`, and an
exploratory plain instance `A()[0]` still prints `'instance'`; an exploratory `del A[0]` also
still says `doesn't support` against CPython's `does not support`.  Those three are
pre-existing and unchanged here.

Added `AIL_CURRENT/test_ail_pre395.py` (3 tests, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json` (weight 38.8).  Probes in `/tmp/probes` on
both builds via `cmp.sh`: `p01_direct` (class-object index forms, including inherited,
aliased and int/negative/wide/bool/None/float/str/empty/tuple keys), `p02_slices`
(full/open/step/zero/negative/empty/reverse slices and a subclass), `p03_routes` (argument,
list item, dict value, attribute, return value and slices, plus item assignment) and
`p04_dunderpatch` (a class with `__add__`, so dunderrt's patch is applied) match CPython.
All match CPython on both builds.  Final-state tests: test_ail_pre395 (17.9 s),
test_ail_safetynet (132.8 s), test_ail_files (137.2 s) and test_ail_corpus_findings3
(246.9 s), 4 modules, 380 s, 0 failed.  `tools/update_manifest.py` was run and `--check`
passes.

## 2026-10-28 -- pre404: a lambda body follows a renamed comprehension target (job-pre404-10281108)

The pre380 review recorded, as pre-existing before that job, that `compscope` renamed a
clashing comprehension target but never rewrote a nested lambda body.  With `x = 99` in the
enclosing scope, `x = 99; ys = [(lambda: x)() for x in range(3)]` kept the lambda reading the
outer `x` and printed `[99, 99, 99]` where CPython prints `[0, 1, 2]`; the same shape inside a
function also differed.  The body's free loads (parameters, walrus targets and nested
comprehension targets excluded) are now resolved against the enclosing comprehension stack:
a function-scope lambda captures the renamed target and matches CPython, while at module
scope the existing closure pass refuses the construct by name (`not in the subset: closures
nested too deeply to settle their shared names`) instead of printing the wrong list.
Argument defaults keep their pre363 handling, and a class-body target read stays refused by
name.  Module-level no-clash lambda reads, class-body reads and a positional-only lambda
remain refused by name, as they were before this change.

Added `AIL_CURRENT/test_ail_pre404.py` (2 tests, 18 matching and 6 refused programs, both
builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
Probes in `/tmp/probes/pre404` on both builds via `cmp.sh`: `f01`-`f19` (the reported case,
argument, list item, attribute, dict value, set/dict comprehension, consumed generator, if
condition, nested same-name comprehensions, two targets, empty/negative/string, walrus body,
nested lambda, defaults and outer-read controls) match CPython; `m01`-`m07` module-scope
routes and `c01` class-body are refused by name.  Final-state tests: test_ail_pre404,
test_ail_pre363, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes; `tools/ci_shards.py --check` still
reports the four duplicate entries present on the base tree.
## 2026-10-28 -- fz1: an exception in a try/else clause reaches an outer handler (job-fz1-10281147)

The daily fuzzer (seed `2075200054`, CPython 3.12, default+ir) found an `int('Cd')` inside a
try's `else` that CPython ends with an uncaught `ValueError`, while AIL continued and printed
the program's later lines.  `pyboxed2.py`'s `stmt_Try` emitted the `else` statements in the
same C block as the try body, so the try's own handlers caught them.  The `else` body now
jumps over the handler dispatch to a label after it and is compiled against the enclosing
handlers; under a `finally` it is still inside the finally's reach (through the existing
trampoline), so the finally runs before the exception propagates.  A matched handler and a
body error both skip `else`, and a normal body runs it once.

Added `AIL_CURRENT/test_ail_fz1.py` (both builds): the minimized construct, `IndexError` and
`ZeroDivisionError` raised in `else`, a `finally` case, normal completion, a body error that
skips `else`, and values from an argument, a list item, an attribute and a dict value.  Probes
in `/tmp/probes` on both builds via `cmp.sh`: `p_tryelse`, `p_tryelse2`, `p_tryelse3` and the
fuzzer program `fz1` now match CPython (stdout and exit code).  Final-state tests:
test_ail_fz1, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  No other
differences were seen in this reproducer.
## 2026-10-28 -- fz2: a finite out-of-int64 `round()` stops as the declared int64 overflow (job-fz2-10281148)

The daily fuzzer seed 2075200891 (`exit code cpython=0 ail=1; ... cpython='-1.9999506175892305e+20'
ail='<end>'`) grew a float to about -2e20 and used `round(v)` in a comparison.  CPython's int is
unbounded and returns the exact integer; AIL's int is int64, so the value cannot be represented.
The typed runtime stopped with its own trap text `round() result does not fit in this language's
int64`, which the fuzz runner could not class as the declared 64-bit difference.  `ail_round0` now
uses the ordinary `integer overflow` stop (stderr `integer overflow`, exit 1, stdout flushed up to
the call), exactly like `+`, `-`, `*` and the other int64 limits; `round(x, n)` and the general path
already did.  A constant float at or outside the boundary keeps pre54's compile-time refusal by
name, and NaN/Infinity keep pre104's catchable ValueError/OverflowError.  The original seed is now
`overflow` (not DIFF) in both default and IR modes under `lab/fuzz/run.py`.

Probes in `/tmp/probes` (both cmp.sh builds): `c_wide` and `c_wide_neg` are refused by name
(`round() of a constant float at the int64 boundary is refused`, exit 3); `m_big`,
`m_big_untyped`, `m_arg`, `m_list`, `m_attr`, `m_neg` and `m_edge` stop with `integer overflow`,
exit 1, stdout a prefix (the fuzz runner's declared-overflow contract); `m_in` (in-range floats,
int64 boundaries, int/bool) and `m_nan` (NaN/Infinity exceptions) match CPython.  Added
`AIL_CURRENT/test_ail_fz2.py` (7 tests, four modes: default/IR and general/IR): the minimized form,
a comparison-only use, a negative value, values through an argument, list item, attribute, dict
value and float/list aliases, in-range and integral arguments, NaN/Infinity, and the constant
compile-time refusal.  Registered it in `ail_check.MODULES` and `tools/ci_shards.json`, and added
DIFFERENCES row `C?-job-fz2-10281148-1`.  Final-state tests: test_ail_fz2, test_ail_pre104,
test_ail_pre54, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (6 modules,
0 failed).  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-28 -- pre410 review: for targets bind, deferred lambda/genexp reads do not (job-pre410-10281225)

The pre410 review found two regressions against the base build.  `_scope_bindings` visited a
`for`/`async for` body but never its target, so `for C in [1, 2]` / `for C in range(10): break` /
`for a, C in [(1, 7)]` before `class C: x: C = 1` were refused although CPython and the base build
printed `2`/`0`/`7`; the target is now a binding when the iterable is not a known-empty literal.
`_annotation_reads` also treated lambda bodies and generator-expression elements as evaluated
immediately, refusing `x: (lambda: C) = 1` and `x: (C for _ in range(1)) = 1`; a lambda body now
runs only when the lambda is called directly, and a generator element only when a known consumer
iterates it (or it is unpacked or iterated by a comprehension), while defaults, the first
generator iterable, subsequent iterables of a consumed generator and all eager comprehension
parts still count.

Probes in `/tmp/probes` on both builds: `p_for_target`, `p_for_break`, `p_for_tuple`,
`p_for_nested`, `p_lambda_deferred`, `p_lambda_nested_deferred`, `p_genexp_deferred`,
`p_genexp_second_iter_deferred`, `p_genexp_lambda_deferred` and `p_genexp_lambda_called` match
CPython (the last is refused by name in both builds because CPython raises).  `p_for_empty`,
`p_lambda_called`, `p_lambda_default`, `p_lambda_nested_called`, `p_genexp_list`, `p_genexp_sum`,
`p_genexp_next`, `p_genexp_first_iter`, `p_genexp_unpacked`, `p_genexp_comp_consume`,
`p_read_argument`, `p_read_list_item`, `p_read_attribute` and `p_read_dict_value` are refused by
name on both builds, matching CPython's NameError.  `p_async_for` is refused by the pre-existing
subset message on both builds (not modeled), so the async-for target route could not be exercised.

## 2026-10-28 -- pre410: class-body annotation name reads use enclosing scopes (job-pre410-10281225)

The first still-differing item in the pre403 review was its pre-existing `rp3_unrelated_func` and
`rp4_if_false`: `def f(): C = 5` (or `if False: C = 5`) before `class C: x: C = 1` compiled and
printed `1` on both builds, where CPython evaluates the annotation and raises NameError.  This
tree did not carry the class-name read check from pre403, so the same cause was fixed by adding
it with scope-aware earlier bindings: a read is allowed only by a binding in the class body
before the read or in an enclosing module/function scope before the class, and a binding in a
constant-false `if`/`while`, an empty literal `for`, a nested function/lambda/comprehension, or an
unrelated function no longer hides the NameError.  The check models a same-line binding, a walrus
in the annotation, a PEP 695 type parameter named like the class, and the annotation-only target
(which binds after the annotation).  Comprehension targets and lambda parameters still shadow the
class name, while the first comprehension iterable and a lambda default are refused.  String
annotations and `from __future__ import annotations` are unchanged.

Probes in `/tmp/probes/pre410` on both builds: `rp3_unrelated_func`, `rp4_if_false`, `r_direct`,
`r_annotation_only`, `r_method_param`, `r_method_return`, `r_later`, `r_comp_iterable`,
`r_lambda_default`, `r_argument`, `r_list_item`, `r_attribute`, `r_dict_value`,
`r_class_if_false`, `r_if_zero`, `r_self_target` and `r_loop_binding` are refused by name;
`m_prior_module`, `m_if_true`, `m_module_alias`, `m_earlier_class`, `m_same_line`, `m_walrus`,
`m_annassign_target`, `m_pep695`, `m_comp_shadow`, `m_lambda_shadow`, `m_string`, `m_future`
and `m_no_annotation` match CPython.  `m_class_if_true` is refused by the pre-existing class-body
subset ("a class body statement other than def/assignment/pass/docstring"), unchanged.  A
`--debug-dir` build of `m_no_annotation` has a `program.c` byte-identical to the base work tree
(only report paths differ).  Final-state tests: test_ail_pre410, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 (4 modules, 396 s, 0 failed).
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-28 -- pre412: an IntEnum float/str value indexes by its normalised int (job-pre412-10281314)

The pre397 review's first still-differing item was `class E(IntEnum): A = 1.5` used as a
subscript: `[0, 1][E.A]` raised `TypeError: list indices must be integers or slices, not
float` on both builds while CPython uses the normalised int `1`.  The member itself keeps the
written value here (the pre-existing `.value` difference), but `_AilIntEnum.__index__` returned
that raw value, so the runtime saw a float or a str.  It now returns `int(self.value)`, which
truncates a float, parses a decimal string and unwraps another IntEnum member.  The declared
value forms and the int64 boundaries match CPython for direct list/tuple/str subscription, a
direct `__index__` call, `list.index` bounds and str search bounds, with the member reaching the
lookup through an alias, an argument, a list item, a class attribute and a dict value.  The
pre-existing `.value`/`int()`/hash difference stays open, as do the separate causes the same
review recorded for normalised values outside int64, slice bounds, bytes/bytearray/deque
subscription, sequence repeat and `pop(i)`.

Probes in `/tmp/probes` on both builds via `cmp.sh`: `pre412_float_value`,
`pre412_string_value`, `pre412_int64_bounds`, `intenum_str_int64`,
`intenum_float_index_consumers` and `intenum_str_index_consumers` match CPython.  The earlier
`intenum_float_index`/`intenum_str_index` differ only in the pre-existing `.value` lines they
print; the pre-existing `intenum_float_slice`, `intenum_str_slice`,
`intenum_float_repeat_pop`, `intenum_float_bounds`, `intenum_str_bounds`,
`intenum_float_conv` and `intenum_str_conv` still differ for the reasons above.  Added
`AIL_CURRENT/test_ail_pre412.py` (1 test, 3 programs, both builds).  Final-state tests: test_ail_pre412, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-28 -- pre414: an exception instance names its class in item errors (job-pre414-10281317)

The first still-differing pre-existing item from the pre396 review was the exception
instance name in item errors: ``del MyErr()[0]`` printed
``'exception' object doesn't support item deletion`` on both builds where CPython prints
``'MyErr' object doesn't support item deletion``.  The v2 object-to-name helper
``ail__tname_c`` used by the item messages returned a class name only for ``AIL_T_INST``;
an exception value has tag ``AIL_T_EXC`` and fell through to the tag name ``exception``.
It now takes the same class-name path for exception values, so deletion, reading and
assignment of an item name the custom class or its subclass.  The review's other
pre-existing items (the ``A[0]`` class-subscript wording and the bad/raising ``__index__``
case during ``del``) are separate causes and are unchanged.

Probes in ``/tmp/probes/pre414`` on both builds via ``cmp.sh``: ``p_exc_name.py`` (the
recorded ``del MyErr()[0]``) now matches CPython, where it differed on both builds before
the change; ``e_all.py`` covers deletion with int and bool keys, a subclass, a built-in
alias, an argument, a list item, an attribute, a dict value, and item reads/stores on the
custom class and a subclass, and matches CPython on both builds.  ``p_class_sub.py``,
``p_bad_index.py``, ``p_raise_index.py`` and ``p_inst_name.py`` were also checked; the
first three belong to the review's separate pre-existing causes and still differ, while
``p_inst_name.py`` already matched.  Final-state tests: test_ail_pre414, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 (4 modules, 0 failed, 308s).
``tools/update_manifest.py`` and ``--check`` pass.

## 2026-10-27 -- pre371: annotated `self.attr: T = v` constructor store is folded (job-pre371-10280520)

The pre357 review's first other pre-existing item was the annotated constructor store:
`class Box: def __init__(self, v): self.v: float = v` with `int(Box(1e300).v)` overflowed on
both builds while CPython prints the exact 301-digit integer.  `_known_class_attributes`
collected only plain `self.attr = value` statements from `__init__`, so an annotated store
left the attribute unknown and the conversion ran at run time.  It now collects an
`ast.AnnAssign` with a value like a plain `ast.Assign`; an annotation without a value is not a
store and stays ignored.  The conversion is refused by name on both builds through a keyword, a
default, a second positional parameter, a module constant, a list item, a dict value, a class
attribute, an instance alias, a list/dict item, a function argument and a wrapper; an
out-of-int64 string parameter is refused as `int64 constant expression out of range`.
In-range int/float/string/bool values (negative, 9e18 and the int64 boundary), a later field
store, a dynamic value, a non-conversion read and an annotation-only store match CPython on
both builds.  The reviewer's other recorded item (`v = int(v)` rebound before the store) still
stops with `integer overflow`; it is a separate pre-existing cause and not changed here.  An
instance held in a plain object's attribute is still not folded, with a plain store as well
(pre-existing).

Probes in `/tmp/probes/pre371` on both builds: 16 refusal probes (r01-r16) are refused by name
(r15 as `int64 constant expression out of range`); 10 match probes (m01-m10) match CPython.
r17 (value through a plain instance attribute) keeps the runtime `integer overflow`, identical
with a plain store on the base copy, so it is pre-existing.  Final-state tests: test_ail_pre371,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (4 modules, 0 failed).
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre370 follow-up: unsound read-only functions refused valid programs (job-pre370-10280456)

The pre370 review found four false compile-time refusals.  `_read_only_functions` marked a
module function read-only whenever it did not store to a subscript named as the parameter, so a
function that changed the container through another callee (`g(xs)`), a method call (`xs.pop()`
/ `append`), a nested def, or returned it for the caller to mutate (`ident(XS)[0] = 5.0`) was
still considered read-only.  `_call_argument_containers` then resolved the stale module constant
and refused `int(xs[0])` in programs that print `5` on CPython and on the base build.  The pass
is now a conservative fixed point (`_read_only_functions`, `_parameter_dependencies`,
`_parameter_escapes`): a nested def/lambda/class, a yield, any item or attribute store, a
rebinding, a return or other escape of the parameter, or a call that hands the parameter to
anything but a pure builtin (or to another module function, followed transitively) disqualifies
it.  A call to a builtin counts as pure only when the name is bound nowhere in the program, as
`_escaped_constant_names` already does, so a shadowed `len`/`print` is not trusted.  A chain of
read-only wrappers is still followed, so the module-container and two-level wrapper refusals are
kept; the mutated/returned cases now compile and match CPython.  A module container passed to a
function whose parameter escapes stays dynamic and keeps the pre-existing run-time trap instead
of a false refusal; `DIFFERENCES.md` says so.

Probes in `/tmp/probes/pre370fix` on both builds: p05 (callee), p06 (pop/append), p07 (nested
def), p18 (identity return), p19/p25/p26 (local alias), p23 (mutual chain) and p24 (return chain)
now match CPython (`5`); p20 (direct literal), q06 (two-level read-only wrapper), q08 (module
alias), q09 (read-only loop) and q11 (loop/if reads) are still refused by name; q07 and q10
(in-range) match CPython.  Added 6 cases to `test_ail_pre370.py` (five escapes plus the read-only
wrapper chain).  Final-state tests: test_ail_pre370, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre370: int() of a parameter's list item is refused by name (job-pre370-10280456)

The pre358 review's remaining pre-existing item reproduced on both builds:
`def show(xs): print(int(xs[0])); show([1e300])` compiled and then stopped with `integer
overflow`, where CPython prints the big integer (`t04_arg_list_item.py`).  The int64 call check
(`_wrapper_int_params` / `_Int64CallChecker` in `ail_chatgpt.py`) now records a constant
subscript path with each parameter that flows into `int()`: `_parameter_item_source` follows
`xs[i]`, a single local alias of the parameter or of one of its items, and a key that is a
literal or a module constant, and composes paths through wrapper functions.  At every call site
`_constant_path_value` takes the item out of a constant list, tuple or dict argument and the two
existing named refusals fire (`int() of a float outside int64`, `int64 constant expression out
of range` for text and bytes).  A module container passed directly to a function that never
stores to or deletes a parameter item is still resolved at the call site
(`_call_argument_containers`); a parameter whose items the callee stores to or deletes stays
dynamic, as does an empty call argument.  In-range values, INT64 and float boundaries, a dynamic
argument and a program that does not call `int()` match CPython.

Added `AIL_CURRENT/test_ail_pre370.py` (2 tests, 28 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json` (weight 55.0).  Probes in `/tmp/probes/pre370` on
both builds: p01-p13, p18, p21, p24, p26 and p27 are refused by name; p14-p17, p19-p20, p22-p23
and p25 match CPython (p22 is the callee-overwrites-the-item route, p23 dynamic, p25 no `int()`
use, p26 local alias, p27 module-constant index).  Final-state tests: test_ail_pre370,
test_ail_pre358, test_ail_pre359, test_ail_pre331, test_ail_pre340, test_ail_pre351,
test_ail_pre311, test_ail_pre322, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre372 review fix: a call between the binding and `x **= e` clears the fold (job-pre372-10280521)

The review found a new false compile-time refusal.  In `b = 10` / `def set_small(): global b`
/ `b = 2` / `set_small()` / `b **= 40`, `_check_augmented_power_scope` still saw the
straight-line `b -> 10` because `_scope_binding_names` does not treat a call as rebinding, so
it refused the program with `10 ** 40` although CPython (and the base tree) print
`1099511627776`.  Every recorded binding is now dropped when a statement can run a call
(`_call_runs_at_runtime`, which enters decorators, defaults and annotations but not a function
or lambda body); the base load of the augmented statement itself precedes its own
right-hand-side call, so that statement's fold stays valid.  A function that declares
`global b` but is never called still leaves `b **= 40` refused by name, so the new refusal is
not disabled wholesale.

Added the global-rebinding case to the matching program of `test_ail_pre372.py`.  Probes in
`/tmp/probes` (18 programs, both builds via `cmp.sh`): p02, p03, p06-p11, p13, p15-p18 match
CPython; p01, p04, p05, p12, p14 are refused by name on both builds.  Final-state tests:
test_ail_pre372, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (4 modules,
27 tests, 0 failed, 1 skipped).  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre372: an augmented power beyond int64 is refused by name (job-pre372-10280521)

The first still-differing item from the pre33 review on this tree was `b = 10; b **= 40`: both
builds compiled it and then stopped with `integer overflow` where CPython prints the big
integer (`b ** e` is already folded and `-(2 ** 63)` already matches here).  The module
constant-power pass only looked at `Assign`/`AnnAssign`/expression values, so the augmented
statement was never folded.  `_check_int64_augmented_powers` in `AIL_CURRENT/ail_chatgpt.py`
now scans direct module and function body statements: when the target has one earlier
straight-line constant binding and the exponent is statically known, the exact power is
compared with int64 and refused with `int64 constant expression out of range`.  The base or
exponent may come through a name, an alias, a list item, a dict value, a class attribute or a
passthrough call; a later rebinding is allowed, while a binding in an earlier branch, loop or
import leaves the pre-existing run-time trap.  In-range powers, the safe bases 0/1/-1,
zero/negative exponents, bool/float bases and values known only at run time still match
CPython.

Added `AIL_CURRENT/test_ail_pre372.py` (2 tests, 16 refused and 1 matching program, both
builds), registered in `ail_check.MODULES` and `tools/ci_shards.json` (weight 31.6).  Probes
in `/tmp/probes` (34 programs, both builds via `cmp.sh`): q01-q17 are refused by name;
m01-m17 match CPython.  Final-state tests: test_ail_pre372, test_ail_safetynet, test_ail_files
and test_ail_corpus_findings3 (4 modules, 0 failed).  `tools/update_manifest.py` was run and
`--check` passes.
## 2026-10-27 -- pre375 follow-up: rebind shadowing and the p6 construction (job-pre375-10280558)

The pre375 review found two defects.  (1) A new under-refusal: walrus and `for` bindings were in
the plain assignment table, so `_classes_of` treated them as a local binding and stopped before
consulting a module-level alias.  `p9` (`X = C` at module scope, `(X := pick())` in a function,
`X().f()`) and `p1` (`X = C` module alias, `for X in ys` over a list mutated after its literal)
compiled and stopped with `AttributeError` where the base refused by name.  Walrus and `for`
bindings now live only in the rebinding table and are resolved as *additional* possible values:
when their value resolves to nothing, the enclosing scopes (including the module alias) are
still consulted; a plain local assignment still shadows, exactly as before.  Both probes are
refused by name on both builds again.

(2) The task's p6 (`y = C; y().g()`, and equally `C().g()`) was not fixed by the previous
commit.  The failure is construction, not alias dispatch: `self.f = self.g` reads a method as a
value, which this subset cannot build, so `__init__` raises `AttributeError` on both builds where
CPython returns 55.  The field/method collision screen now refuses the construction of a class
whose colliding field may hold a bound method (`_may_be_bound`), naming the class and the field;
a colliding field holding a plain lambda/function is representable and still matches CPython.
This also covers construction through an alias, a list item, a dict value, an attribute, an
argument or a call in another function (all refused by name; the last is conservative).

Probes in `/tmp/probes/pre375fix` on both builds via `cmp.sh`: `c1_p6_alias_g`, `c2_p6_direct_g`,
`c3_p6_in_function`, `c5_bound_arg_refused`, `w1_walrus_outer_alias`, `w2_for_mutated_alias`,
`w7_walrus_argument`, `w9_walrus_dict_value` are refused by name; `c4_lambda_field_match`,
`c6_unrelated_construct`, `s1_param_shadows_class`, `s2_local_shadows_class`,
`w3_walrus_local_unrelated`, `w4_plain_local_shadow`, `w5_plain_unknown_shadow`,
`w6_for_local_unrelated`, `w8_for_empty` match CPython.  The 20 reviewer probes were re-run:
every one is refused by name or matches except the two known pre-existing differences `p2`
(module-level `for` over a mutated list) and `p13` (comprehension target), both unchanged.
Final-state tests: test_ail_pre375 (74 s), test_ail_pre278 (72 s), test_ail_pre361 (34 s),
test_ail_safetynet (82 s), test_ail_files (43 s, 1 skip) and test_ail_corpus_findings3 (89 s),
all OK.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre375: walrus and `for`-target class receivers are refused by name (job-pre375-10280558)

Reproduced the first still-differing pre-existing item from the pre361 review on this tree.  Its
p6 shape (``y = C; y().f()``) is already refused by name after pre361; the p15/p16 walrus and
``for`` target shapes still compiled on both builds and stopped with ``AttributeError: 'C'
object has no attribute 'g'`` where CPython prints 55.  ``refuse_field_method_call`` now puts a
walrus target and each value a ``for`` iterable is seen to hold into its assignment table: a
list/tuple/set literal, a name bound to one, an instance field, a subscript of one and an
argument list (including a method argument and a keyword argument), with the same scope rules as
the existing assignment pass.  A ``for`` target that rebinds a parameter is resolved through a
separate walrus/loop rebinding table, so a plain reassignment still does not refactor the
parameter's call-site resolution.  A comprehension target is deliberately left alone (adding it
to the enclosing scope would make an unrelated later name look like a possible class), and the
existing unrelated-class, direct-call and no-feature routes are unchanged.

Probes in ``/tmp/probes/pre375`` on both builds via ``cmp.sh``: ``p06_alias``, ``p06_gcall``,
``p15_walrus``, ``p15_walrus_g``, ``p16_for``, ``p16_for_tuple``, ``b01``-``b05``,
``b08``, ``b11``, ``b12``, ``b13``, ``b14``, ``c01``-``c05``, ``c10``, ``c11``, ``c13``,
``c17`` and ``c19`` are refused by name (``also stores an instance field named f``); ``b06``
(empty iterable), ``b07``/``c06``-``c08``/``c14``/``c18`` (unrelated class), ``b09``, ``b10``,
``b15``, ``c09``, ``c12``, ``c15`` (plain parameter reassignment), ``c16`` (other function) and
``c18`` match CPython.  Final-state tests: test_ail_pre375, test_ail_pre361, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 (5 modules, 255 s, 0 failed).
``tools/update_manifest.py`` was run and ``--check`` passes.
## 2026-10-27 -- pre377 follow-up: long class names in item-error messages

The pre377 review found that the class name still went into a fixed `char buf[64]`, so a
40-character class truncated the message mid-word (`...' object is not subscr`) on both
builds, while base had printed a complete `'instance'` message.  `ail__raise_item_tname` now
formats the six item-error sites (getitem default and dict-view, setitem, delitem, getslice
default and dict-view) into a buffer sized from the message and name; no fixed buffer remains
on that path.  Probes also showed CPython itself formats the name with `%.200s`: a
300-character class prints its first 200 characters, so the helper caps the name at 200 to
match.  The dunderrt patch anchors were updated to the helper calls.  Added 40- and
210-character cases to `test_ail_pre377.py` (both builds), and corrected the DIFFERENCES row:
a builtin function object now says `builtin_function_or_method` (CPython's text) instead of
`'function'`; other builtin values are unchanged.

Probes in `/tmp/probes` (both builds via `cmp.sh`): `p01_boundaries` (class-name lengths 1,
20-25, 32-35, 40, 300; getitem, negative index, slice, setitem, delitem) matches, including
the 200-character cap; `p02_uncaught_long` (40) and `p03_uncaught_short` match uncaught stderr;
`p04_routes_long` (argument, alias, list item, attribute, dict value, subclass, setitem and
delitem through an argument) matches; `p05_dunder_long` (long-named class with the item
methods still works); `p06_builtins` (int, None, bool, float, bytes, builtin function, lambda,
str key, tuple key) matches; `p07_empty_ok` matches.  Final-state tests:
`par_check.py -j 2 test_ail_pre377 test_ail_safetynet test_ail_files
test_ail_corpus_findings3` -- 4 modules, 0 failed (371 s).  `tools/update_manifest.py` was run
and `--check` passes.

## 2026-10-27 -- pre377: instance item errors name the class (job-pre377-10280635)

The pre354 review's first recorded item no longer reproduces on this tree: `p08_dict_slice`
(`d = {1: 2}; d[1:2]`, caught and uncaught) matches CPython's `KeyError: slice(1, 2, None)`
on both builds, because pre353 already fixed dict slice keys.  The next recorded item did
reproduce: `class A: pass; A()[0]` (and `A()[1:2]`) printed
`TypeError: 'instance' object is not subscriptable` on both builds, where CPython names
`'A'`.  The v2 general runtime's `ail_op_getitem`, `ail_op_setitem`, `ail_op_delitem` and
`ail_op_getslice` built these messages from `ail_type_name(c.tag)`, which has only the tag;
they now use `ail__tname_c(c)`, the runtime's existing object-to-name helper, so an instance
shows its class (and a subclass its own name) while builtin values are unchanged.  The
matching `dunderrt.patch` anchors were updated so the operator-method patch still applies.
The review's `p11_lambda_comp` refusal (`a slice object the general path could not build`)
was not reached by a probe and that path is unchanged.

Probes in `/tmp/probes/pre377` (both builds via `cmp.sh`): match CPython `p08_dict_slice`,
`p08b_uncaught`, `p08_dict_slice_control`, `p09_instance_name`, `p09b_plain`,
`p09_uncaught`, `p09_routes` (argument, alias, list item, attribute, dict value, subclass,
slice object), `p09_setdel`, `p09_init_class`, `p09_builtins` (int, None, bool, float,
bytes, function) and `p09_dunder` (an instance with the item methods still works);
`p11_lambda_comp` also matches.  Added `AIL_CURRENT/test_ail_pre377.py` (7 programs + an
uncaught case, both builds) and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`; added DIFFERENCES row `C?-job-pre377-10280635-1`.  Final-state
tests: test_ail_pre377 (2 tests, 49 s), test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (25 tests, 503 s, 1 skipped).  `tools/update_manifest.py` was run
and `--check` passes.

## 2026-10-27 -- pre380: a lambda body follows a renamed comprehension target (job-pre380-10280705)

The pre363 review left two pre-existing items. The gdev instruction counts were not re-measured:
`perf_event_paranoid` is 4 here. The module-level `[(lambda: x)() for x in range(3)]` body-read
case still differed on both builds: with `x = 99` in the enclosing scope, `compscope.rename`
renamed the comprehension target (because the name clashes) but never looked inside the nested
lambda body, so the lambda kept reading the outer `x` and printed `[99, 99, 99]` where CPython
prints `[0, 1, 2]`. `_Scope` now resolves the free loads of a lambda nested in a comprehension
(parameters, walrus targets and nested-comprehension targets excluded) against the enclosing
comprehension stack. In a function the lambda then captures the renamed target and matches
CPython; at module scope the existing closure pass refuses the construct by name (`not in the
subset: closures nested too deeply to settle their shared names`) instead of printing the wrong
list. Argument defaults keep their pre363 handling, and the class-body guard still refuses a
class-body target read by name.

Added `AIL_CURRENT/test_ail_pre380.py` (2 tests, 16 matching and 6 refused programs, both
builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
Probes in `/tmp/probes/pre380` on both builds via `cmp.sh`: `r01`-`r14` (argument, list item,
attribute, dict value, set/dict comprehension, consumed generator, if condition, nested
comprehension with the same name, two targets, empty/negative/string, outer value after the
comprehension, shadowed inner target) match CPython; `q01`-`q08` module-scope routes are refused
by name; controls `c01`-`c04` (default, outer read, target passed as an argument, class-body
default) match CPython. Final-state tests: test_ail_pre380, test_ail_pre363, test_ail_quirks
(comprehension cases), test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes; `tools/ci_shards.py --check` still
reports the four shard entries duplicated on the base tree.
## 2026-10-27 -- pre388: a container read before a later mutation is folded for int() (job-pre388-10280828)

The pre373 review's first recorded item reproduced on both builds:
`items = [1e300]; a = items; x = a[0]; a[0] = 1.5; print(int(x))` compiled and then stopped with
`integer overflow`, where CPython prints the big integer.  `_escaped_constant_names` collected one
scope-wide set of container names that may be mutated, so the later `a[0] = 1.5` made the whole
flat list dynamic and the scalar `x` bound from `a[0]` stayed unknown.  The escape analysis now
returns the event per top-level statement (`_escaped_constant_statements`), and
`_scope_constant_map` walks the statements in order: a scalar read through a load-only subscript
keeps the literal's value up to the statement that may mutate the container, and a container is
dropped from that statement on.  Top-level statements run once and in order, and a use inside a
nested definition counts at its definition statement, so a mutation that comes first still makes
the read dynamic.  The conversion is refused by name on both builds with the existing
`int() of a float outside int64: ... (CPython makes a big integer)` message (an int or string
item keeps `int64 constant expression out of range`).

Covered by `AIL_CURRENT/test_ail_pre388.py` (2 tests, 24 programs, both builds): the recorded
alias, a direct scalar read, a dict value, a computed index, `del` after the read, an alias
chain, a tuple, a negative value, the int64 boundary float, a function-local list, a call or
`print` between the read and the conversion, and an int/str item.  A mutation that comes first
(direct, through an alias, a loop, a nested definition or inside a function), in-range reads
before and after a mutation, an append, and an inline item match CPython.

Probes in `/tmp/probes/pre388` on both builds: `v01`-`v12`, `w01`-`w15` and `x01`-`x06`; every one
matches CPython or is refused by name except the review's second item (a list held in an instance
attribute, `v11`/`pre388_r10`), a list or float reaching a function as an argument (`w02`, `w03`)
and an attribute-held scalar (`w04`), which keep the pre-existing run-time trap and are recorded
in DIFFERENCES.  Final-state tests: test_ail_pre388, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3, plus test_ail_pre322, test_ail_pre311, test_ail_pre31, test_ail_pre9,
test_ail_pre39, test_ail_pre357, test_ail_pre358 and test_ail_pre359.  `tools/update_manifest.py`
was run and `--check` passes.

## 2026-10-28 -- pre390: the pre372 Speed items do not differ on this tree (job-pre390-10280851)

Re-ran `bash ~/tools/cmp.sh` against CPython on both builds for the two recorded programs:
`corpus/gdev/g00_012.py` and `corpus/gdev/g12_036.py` both exit 0 with identical stdout, and the
general and default binaries are byte-identical (148240 and 268680 bytes).  The recorded
3.87 vs 3.88 s and 9.02 vs 9.05 s are compile-time deltas with identical generated C, so no
behaviour differs and there is nothing to fix or refuse.  The review's unverified modules pass
on this tree: test_ail_safetynet (5), test_ail_files (18, 1 skipped), test_ail_globals (32) and
test_ail_corpus_findings3 (2).  Six probes in `/tmp/probes/pre390` match CPython on both builds:
p01 vigenere empty/non-ASCII-key/punctuation boundaries, p02 argument/list-item/attribute/dict
routes, p03 dataclass ordering/Enum auto/heap ties, p04 Random/heapq/deque, p05 optional float
and property ValueError with an empty summary, p06 Final plus isalpha/isascii/isupper.  No code,
test or DIFFERENCES change.
## 2026-10-28 -- pre346: normalize duplicate placements instead of rewriting the shard file (job-rbpre346-10280910)

Re-applying pre346 on today's integ (`99f5526`) still failed `test_ail_pre346`.  The job patch
rewrote `tools/ci_shards.json` from this branch's old base, while integ had regenerated the file
for its newer module list, so `git apply --3way` reported a conflict and left conflict markers in
the working file; `json.loads` then raised and `test_assignment_places_every_module_once` errored.
Regenerating the file from integ's own copy does not help: every hunk still conflicts in the
three-way merge.

The file is therefore no longer part of this change (it keeps the tree's content).  Instead
`shard_modules()` and `--check` treat a placement that names a module twice as a stale-file
artifact and run it on its first shard, so a module can never run in two shards; a module missing
from the file is still spread by name and `--check` now fails only on a stale (`unknown`) name,
reporting `duplicated:` without failing.  `build()` still drops duplicate inputs and duplicate
placements, and the module list is still unique, so `--update` writes a clean file.
`test_duplicate_placement_runs_once` covers the stale-file case.  `tools/update_manifest.py` was
run and `--check` passes.

Verified on integ `99f5526` plus this change: the patch applies with `git apply --3way` (rc 0, no
conflicts), `test_ail_pre346` passes 5 tests and `test_ail_safetynet` passes 5 tests (109 s); the
reported safetynet failure could not be reproduced, as in the pre345 and pre346 re-apply records.

## 2026-10-27 -- pre346: accept modules added after the shard file was generated (job-rbpre346-10280725)

Applied alone on today's integ, `test_ail_pre346` failed.  Four modules added by changes merged
after this branch's base (`test_ail_fuzz59`, `test_ail_pre360`, `test_ail_pre363`,
`test_ail_pre365`) are in `ail_check.MODULES` but not in the `tools/ci_shards.json` this change
regenerated, so `tools/ci_shards.py --check` exited 1 with `unassigned:` and
`test_assignment_places_every_module_once` failed on exact set equality.

The CI contract already covers that case: `.github/workflows/tests.yml` documents that a module
missing from the file "is still spread over the shards by name", and `--shard` /
`shard_modules()` do exactly that.  `--check` now fails only on a stale (`unknown`) or duplicated
name and still reports `unassigned`; the test now checks that every current module reaches
exactly one shard through `shard_modules()` and that no assigned name is stale or duplicated.
The original pre346 defect (a duplicated placement, from the four duplicate `MODULES` entries)
still fails the check.  `tools/update_manifest.py` was run and `--check` passes.

The report also listed `test_ail_safetynet`.  It passes on this tree and on integ + this change
(5 tests, OK, 106 s), so that failure could not be reproduced, as recorded for the pre345
rebase.

Probes in `/tmp/probes/pre346fix` (Python tooling, so plain CPython 3.12; `cmp.sh` targets AIL
programs and no language behaviour changed): `p01_missing_module_ok` (missing and completely
empty assignment accepted, each module still in one shard), `p02_duplicate_fails` (duplicated
placement exits 1 and `build()` repairs it), `p03_stale_name_fails` (unknown name exits 1),
`p04_build_dedup` (duplicated input and empty module list), `p05_shard_coverage` (real tree and a
subset file: every module once, stale name not run) and `p06_integ_added_modules` (the four
added modules: `--check` exits 0 and all 515 are planned once).  All PASS.  Final-state tests:
`test_ail_pre346`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`.

## 2026-10-27 -- re-apply pre346 on the integration tree (job-rbpre346-10280548)

Re-applied the accepted pre346 CI-shard fix on top of this tree.  `ail_check.MODULES` had the four
duplicate entries (`test_ail_fuzz4`, `test_ail_pre126`, `test_ail_pre59`, `test_ail_pre61`) back,
so `tools/ci_shards.py --check` failed; each duplicate is removed, keeping the first occurrence,
and `test_ail_pre346` is registered.  `build()` now deduplicates its module input and keeps only
the first placement of a name read from a stale assignment file.  `tools/ci_shards.json` was
regenerated by `--update` over the 511 unique modules and `--check` exits 0.

`test_ail_pre346.py` checks the module list is unique, every module is assigned exactly once,
`--check` passes, and `build()` drops duplicate placements.  `tools/diff_ids.py` is not present on
this tree, so it was not run; `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-28 -- pre381 follow-up: handlers after a class-name check still run (job-pre381-10281228)

The pre381 class-name check broke `test_ail_multifile`'s `m1_misc`: a loop whose `try` had two
user-class handlers caught `OutOfStock` on the first iteration and then stopped before the second
`except ShopError`, exiting 0 with no stderr.  `stmt_Try` emits the handlers as one `if`/`else if`
chain; `_check_class_name_bound` puts an `if (g_class_init_arr[i])` in front of a handler, so a
later handler's match became the `else if` of that check instead of of the preceding handler.
Once an earlier handler had caught and cleared the exception, control fell into the check's
`else { goto leave; }`.

Every handler now jumps explicitly to the try end (or to the `finally` label) after its body, so a
later handler is never tested after a match and its class name is not evaluated either.
`test_ail_pre381.py` gained `loop_second_handler` (the m1_misc shape) and
`later_handler_not_evaluated` (an earlier handler catches while a later handler names the class
whose body is running), both checked on the general and default builds.

Probes in `/tmp/probes` (`pre381fix_p01`-`p08`, both builds via `cmp.sh`): `p01`, `p02`, `p03`,
`p05`, `p06`, `p07` and `p08` match CPython; `p04` (`continue` out of a `try/finally`) is refused
by name on the general build and matches on the default build.  Targeted tests on this tree:
`test_ail_pre381`, `test_ail_try_locals`, `test_ail_try_hoist` and `test_ail_multifile` pass.
The required modules were run on the committed tree (results in the job report).
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre381: a class body cannot read its own name (job-pre381-10280717)

The pre362 review's first still-differing pre-existing item reproduced on this tree: rp28
(`class C: y = C`), rp22 (`class C: y = (lambda: C)()`) and rp27 (the comprehension form) all
printed `<class '__main__.C'>` with exit 0 on both builds, where CPython raises `NameError`
because the class name is bound only after its body runs.  The cause was that every class object
is created and rooted in `g_slots_arr` during startup, so `expr_Name` handed out a class name
whose binding did not exist yet in CPython.

`pyboxed2.Compiler` now gives each class an index into a `g_class_init_arr` flag.  `_init_class_attrs`
(and the lazy `_class_attr_value` fallback) sets it while the body is evaluated and clears it
afterwards; `expr_Name`, `_call_class`, `_b_isinstance`, the `C.attr`/static/classmethod receiver
paths and `raise`/`except` class names emit a `NameError` check against it.  A class body
generator expression that reads its own name is refused by name, since the general path
materialises generator expressions eagerly rather than deferring them.  A module binding made
before the class, and any read after the class body (method body, stored instance), are unchanged.

Review fix: the check is now suppressed when a parameter, local, cell, closure or class-body
binding of the name shadows the class, using the same bindings `expr_Name`/`_call_name` try
first (`_class_name_shadowed`).  Before, `class C: x = (lambda C: isinstance(1, C))(D)` raised
`NameError` instead of printing `False`, and `except C:` with a parameter `C` raised `NameError`
instead of letting the `ValueError` propagate; both now behave as CPython and as the base build.

Probes in `/tmp/probes2` (15 programs, both builds via `cmp.sh`, re-run on the final tree): 10
match CPython exactly -- direct, lambda call, list comprehension, `isinstance`, except handler,
argument, later method, prior `C = 5`, shadowing lambda parameter in `isinstance`, shadowing
`except` parameter -- and 1 (`raise C("x")` with a shadowing parameter) matches too.  The rest
are pre-existing and identical on the base build: `C = 5`/`class C` + `isinstance` (prints
`False`, CPython `TypeError`), shadowed `isinstance` holding `D` (prints `False`, CPython
`True`), shadowed `except C` holding `Err` (Err propagates, CPython catches), and `raise C("x")`
of a non-Exception class name (prints `C: x`, CPython `TypeError`).

Tests run on the final tree: `test_ail_pre381.py` (new), `test_ail_safetynet`, `test_ail_files`
and `test_ail_corpus_findings3`, all pass.  `test_ail_pre381.py` is registered in
`tools/ci_shards.json` with weight 81.5, and `tools/update_manifest.py` was run.
## 2026-10-27 -- pre378 review follow-up: long class names print whole (job-pre378-10280656)

The pre378 review found the new fallbacks still formatted into ``char buf[64]``: the message is
the name plus 31 bytes, so names longer than 33 characters were cut off (a 34- or 40-character
class printed ``... object is not subscriptabl``).  Both sites now raise through
``ail__raise_not_subscriptable``, which sizes its buffer from the class name the way
``ail__tname_c`` grows its own and frees it after ``ail_raise_c`` copies the text;
``dunderrt``'s two string-matched patches (getitem default, getslice fallback) were updated to
the new text.  The v1 emitter (``AIL_GENERAL=v1``, outside the two ``cmp.sh`` builds) still
says ``'instance'``.

Probes in ``/tmp/probes`` (9 programs, both builds): ``p_long_int``, ``p_long_slice``,
``p_long_routes`` (argument, alias, attribute, dict value, list item), ``p_boundary`` (1, 33
and 34 characters), ``p_subclass_long``, ``p_builtins``, ``p_dunder_slice``, ``p_dunder_ops``
and the uncaught ``p_long_uncaught`` (exit 1, identical stderr) all match CPython.
``test_ail_pre378.py`` gained the long-name int/slice cases, the 33/34 boundary, long
route/subclass programs and a long-name uncaught run.  Final-state tests: test_ail_pre378,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3; ``tools/update_manifest.py``
was run and ``--check`` passes.
## 2026-10-27 -- pre378: a subscript of an instance names its class (job-pre378-10280656)

The pre354 review's first still-differing item reproduced on both builds: ``A()[1]`` (a class
with no ``__getitem__``) raised ``TypeError: 'instance' object is not subscriptable`` where
CPython names the class (``'A' object is not subscriptable``); the slice spelling
(``A()[1:2]``) differed the same way.  The v2 runtime's ``ail_op_getitem`` /
``ail_op_getslice`` fallbacks asked the tag table, which knows only the generic instance tag;
they now call ``ail__tname_c``, the class-name helper attribute errors already use, and
``dunderrt``'s string-matched patch of the getslice fallback was updated to match.  A subclass
names the subclass, and builtin values keep their type names.  The review's other items are
unchanged: ``p08`` (a dict with a slice key) already matches CPython on this tree, and the
nested ``def slice`` / ``class slice`` programs are still refused by name.  The class object
itself (``A[1]``) is a separate pre-existing difference and is untouched.

Probes in ``/tmp/probes/pre378`` (13 programs, both builds via ``cmp.sh``): ``p08_dict_slice``,
``p09_instance_name``, ``p09_routes``, ``p09_slice_routes``, ``p09_uncaught``,
``p09_control_getitem`` and ``r11_nested_def_module`` match CPython; ``p11``, ``r12``-``r16``
are refused by name (``a slice object the general path could not build`` or ``a nested class
definition (slice)``).  Added ``AIL_CURRENT/test_ail_pre378.py`` (9 caught programs plus an
uncaught one, both builds) and registered it in ``ail_check.MODULES`` and
``tools/ci_shards.json``.  Final-state tests: test_ail_pre378, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3.  ``tools/update_manifest.py`` was run and
``--check`` passes.
## 2026-10-27 -- re-apply pre322 on the integration tree (job-rbrbrbpre322-10280232)

Re-applied the accepted pre322 container-alias fix on top of the current integration tree.  The
only conflict was in `_check_int64_literals`: this tree already carried `_safe_module_containers`,
`_known_class_attributes` and the class-instance second loop, so all were kept, while the new
`_all_bound_names` / `_scope_constant_map` pass supplies scalars and safe aliased containers and
its `program_bound` is passed to `_Int64CallChecker`.  The tree's newer `_int_conversion_outside_int64`
branch and `_wrapper_int_params(..., attributes)` signature are preserved.  `test_ail_pre322.py` is
registered next to `test_ail_pre321`, and `tools/ci_shards.json` gained its weight (10.0).
`tools/diff_ids.py` is not present on this tree.

Probes in `/tmp/probes` (31 programs, both builds via `cmp.sh`): `r01`-`r13` are refused by name
(`int() of a float outside int64 ... big integer`) for module/function/chain/tuple/dict/
negative/computed-index/wrapper/boundary and builtin-`len`/`print`/`str`/`repr` aliases;
`m01`-`m18` match CPython (in-range list/tuple/dict/nested aliases, mutated/rebound/empty/printed
aliases, module and enclosing `len`/`repr`/`print` shadows, plus values through an argument, a
list item, an attribute and a dict value).
## 2026-10-27 -- pre361: a try/handler class alias call is refused by name (job-pre361-10280245)

The pre352 review's first still-differing pre-existing item was its r20 probe: a class alias
assigned in a ``try`` body and rebound to another class in the handler
(``try: x = C`` / ``except Exception: x = D`` / ``print(x().f())``) compiled on both builds and
then stopped with ``AttributeError: 'C' object has no attribute 'g'`` where CPython prints 55.
The field/method collision screen resolved a call target written as a class name (``C()``) but
not one reached through a variable (``x = C; x()``), so the receiver never reached the by-name
refusal.  ``_classes_of`` in ``AIL_CURRENT/python/pkg-v12/pyfront.py`` now resolves a call target
name through its assignments in scope, including a bare class name, an alias chain and every
assignment in a try body plus its handler; the same resolution follows an argument, a list item,
an attribute and a dict value.  A call target that can only be an unrelated class keeps
CPython's result.  A name bound by a walrus or a ``for`` target is not in the assignment table
and keeps the pre-existing runtime ``AttributeError``; those two routes are unchanged.

Added ``AIL_CURRENT/test_ail_pre361.py`` (2 tests, 10 refused and 3 matching programs, both
builds) and registered it in ``ail_check.MODULES`` and ``tools/ci_shards.json``.  Probes in
``/tmp/probes/pre361`` on both builds via ``cmp.sh``: ``r20``, ``r20_same``,
``r20_nonclass``, ``chain``, ``arg_route``, ``list_route``, ``attr_route``, ``dict_route``,
``reassigned`` and ``later_module2`` are refused by name (``also stores an instance field named
f``); ``noncolliding``, ``param_noncolliding`` and ``no_feature`` match CPython.  ``walrus`` and
``loop`` still stop with the pre-existing ``AttributeError`` on both builds; ``later_module``
(call before the assignment, a CPython ``NameError``) is now refused by name.  Final-state tests:
test_ail_pre361, test_ail_pre278, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (5 modules, 338 s, 0 failed).  ``tools/update_manifest.py`` was run and
``--check`` passes.
## 2026-10-27 -- pre365: Counter missing-key deletion is ignored (job-pre365-10280341)

The first still-differing item from the pre353 review was `Counter.__delitem__` on a missing
key: `del c['missing']` raised `KeyError` on both builds, where CPython only removes a key that
is present.  It reproduced through an unannotated function parameter (the general path); a
directly known local Counter was already lowered by collib to `pop(k, 0)`.  The v2 runtime's
`ail_dict_del` now skips the KeyError when the dict carries the Counter flag.  Plain dicts and
defaultdicts still raise `KeyError`, and a present key (including one whose count is zero) is
removed as before.

Added `AIL_CURRENT/test_ail_pre365.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`; added DIFFERENCES row `C?-job-pre365-10280341-1`.  Probes in
`/tmp/probes/pre365` on both builds: `p05`, `p10`, `p11`, `p12` and `p13` match CPython,
covering empty/present/repeated-missing/zero-count keys, string/int/negative keys, an alias,
an argument, a list item, a dict value, a return value, a loop key and an attribute, with plain
dict and defaultdict controls.  An exploratory `p01`/`p04` showed a separate pre-existing
`Counter(dict)` constructor count difference (`Counter({'a': 1, 'b': 2})` prints `a: 1, b: 1`);
it is not the recorded deletion item and was left unchanged.  Final-state tests on this commit:
test_ail_pre365, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (results in
the job report).
## 2026-10-27 -- pre360: textwrap of a hyphen or a tab matches CPython (job-pre360-10280242)

The pre352 review left `test_ail_files` and `test_ail_corpus_findings3` unverified.  `test_ail_files`
passes unchanged on this tree, and the first difference reproduced from the corpus-findings area on
both builds was textwrap: `textwrap.wrap("a-b", 2)` (also `fill`, and a literal containing a tab)
compiled and then stopped with `RuntimeError: textwrap: text with a hyphen or a tab is not built`,
where CPython prints `['a-', 'b']`.  The prelude helper `_ail_tw_wrap` now runs CPython 3.12's default
TextWrapper: `expandtabs(8)` with the column reset on `\n`/`\r`, the whitespace translation, the
`wordsep_re` whitespace / em-dash / hyphen chunking (including its two-word-char lookahead) and
`_handle_long_word`'s rfind-hyphen break with the `space_left = 0` case; `width <= 0` keeps CPython's
`ValueError` text.  Text without a hyphen or a tab is unchanged, and a program that does not import
textwrap has a `program.c` byte-identical to a `work` worktree.

Added `AIL_CURRENT/test_ail_pre360.py` (5 tests: hyphen/tab, boundaries, routes, widths, 60 random
texts; both builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.  The helper
was fuzzed against CPython 3.12's `textwrap` in CPython first (50,000 random texts over spaces, tabs,
newlines, hyphens, em-dashes, digits, `e`-accent, CJK and superscript digits; 0 mismatches) before
being spliced in.  Probes in `/tmp/probes/pre360`: `p01` (newline modes), `p02` (seek/tell), `p07`
(`x` mode), `p08` (`a+`), `p09` (readline/readlines), `p10` (UTF-8 read), `p11` (corpus builtins) and
`p12` (strip/dedent) match CPython on both builds; `p03`/`p04`/`p05`/`p06`/`p13` are refused by name;
`p14` (hyphen and tab, the reproduced item), `p15` (argument, list item, class and instance attribute,
dict value, mutation), `p16` (empty, whitespace-only, leading/trailing, widths 1/2/5/70, em-dash,
digits, unicode) and `p17` (width 0/-1/-70) match CPython on both builds.  Instruction counts were not
measured: `perf_event_paranoid` is 4 here.  Final-state tests (4 modules, 297 s, 0 failed):
test_ail_pre360, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre364 follow-up: a function called outside module scope is not bound (job-pre364-10280336)

The review of the first commit found that `_pow_parameter_bindings` treated module-level call
sites as the only calls.  A function also called from another function, a lambda or itself
still had its module-level arguments folded, which suppressed the pre-existing constant-base
refusal: `def f(e): return pow(2, e); print(f(10)); def g(): return f(100)` printed 1024 and
then stopped with `integer overflow` on both builds, where the base tree refused `pow(2, e)`
by name (and CPython prints the bignum).  A recursive `f(e * 100)` and mixed module/nested
sites had the same shape.  A definition is now bound only when every load of its name is the
callee of a module-scope call; a call inside a function or lambda, or in the function's own
body, makes it escaped and leaves the parameters unknown, so the constant-base rule fires.
Calls from module scope still fold as before.

Probes in `/tmp/probes/pre364fix` (both builds via `cmp.sh`, on this tree and `/tmp/base`):
refused by name here -- `p01` (nested disagreeing site), `p02` (recursive), `p03` (mixed
sites; base stopped with `integer overflow`), `p04` (nested agreeing site), `p05` (lambda),
`p06` (nested argument shadowing a module constant), `p07` (module-only both parameters,
exact; base overflowed), `p08` (function used as a value), `p12` (module keyword arguments,
exact; base overflowed), `p13` (class-body call).  Match CPython on both builds -- `p09`
(float through a nested call), `p10` (small ints through a nested call), `p11` (keyword
arguments through a nested call), `p14` (call in a list display at module scope).  `p01`,
`p02`, `p04`-`p06`, `p08` and `p13` reproduce the base tree's named refusal, so the runtime
overflow the review found is gone.

`test_ail_pre364.py` gains four refused cases (`nested_site_disagrees`, `recursive_site`,
`lambda_site`, `shadowed_nested_argument`; 14 refused programs, 2 matching, both builds).
Its three tests pass; `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` pass on the final commit.  `tools/update_manifest.py` was run and
`--check` passes.
## 2026-10-27 -- pre364: a wide constant `pow()` exponent with a routed base is refused (job-pre364-10280336)

The rbpre331 record left one pre-existing item open: a constant `pow()` exponent reaching the
call through a parameter, list item, attribute or dict value still stopped with
`integer overflow`.  On this tree the literal-base spellings are already refused, but routing
the integer base the same way still differed on both builds:
`def power(b): print(pow(b, (3**100)>>150)); power(2)` (and the list, class-attribute,
instance-attribute and dict-value spellings) compiled and then stopped with `integer overflow`
where CPython prints the bignum.  The checker had a rule for a constant base with a run-time
exponent but no symmetric rule, and it could not see a base that arrived through a route.
`_check_int64_pow_constants` now refuses a constant exponent of at least 63 (2**63 already
leaves int64) with a base computed at run time, leaving statically known bool, float and
non-number bases alone, and `_pow_parameter_bindings` binds a plain function's module-level
constant call arguments (undecorated, not used as a value, no conflicting sites, no body
store), splitting ints for the folding map from other scalars for the safe-base check.  So
`pow(b, e)` called once with `2` and `(3**100)>>150` folds to the exact result and is refused
with `int64 constant expression out of range`.

Probes in `/tmp/probes/pre364` (both builds via `cmp.sh`), refused by name: `r01_arg` (exact),
`r02_list`, `r03_attr_class`, `r04_attr_instance`, `r05_dict`, `r06_param63` (exact), `r13`
(both parameters, exact), `r15`, `r16` (two different call sites), `r17` (function used as a
value), `r18` (parameter reassigned in the body), `r19` (alias inside), `r20` (same value at
two call sites, exact), `r24` (never called) and `r25` (module name bound to a float).  Match
CPython: `r07`/`r08` (exponent 62, bases 2/-2), `r09` (float literal base), `r10` (bool
literal base), `r11` (negative exponent), `r12` (small exponent), `r21`/`r22`/`r23` (float,
bool and 1 passed through a module-level call), `r26` (in-range argument) and the recorded
`p01`-`p07` literal-base controls.  `r18` and `r25` are named refusals rather than CPython
matches: a reassigned parameter and a float module constant are not folded by these maps.
`**` with both operands routed (`q12`) still stops with the pre-existing `integer overflow`.

Added `AIL_CURRENT/test_ail_pre364.py` (3 tests, 10 refused programs and 2 matching programs,
both builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`; DIFFERENCES
row `C?-job-pre364-10280336-1`.  `test_ail_pre364`, `test_ail_pre331`, `test_ail_pre299`,
`test_ail_pre294`, `test_ail_pre305` and `test_ail_pre351` pass, as do the final-state
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` (8 modules, 0 failed).
`tools/update_manifest.py` was run and `--check` passes; `tools/ci_shards.py --check` reports
only the four pre-existing duplicate shard entries (fuzz4, pre126, pre59, pre61).
## 2026-10-28 -- pre367 integration: the specific refusal wordings keep priority (job-pre367-10280933)

`_check_int64_binpow_constants` refused every out-of-int64 power it could resolve with its own
`int64 constant expression out of range`, before three older checks that own their contexts, so
`test_ail_pre97`, `test_ail_pre160`, `test_ail_pre190`, `test_ail_pre200`, `test_ail_pre205` and
`test_ail_pre273` failed on the integration branch.  The checker now leaves a node alone when it
is a `str.split`/`rsplit` maxsplit constant (`id(node) in maxsplit`, the pre97/pre190/pre200/pre205
wording), when it is a syntactic literal power that is the whole right-hand side of a plain
assignment (the pre160 emitter fold keeps its `outside the signed 64-bit range` wording), and when
a syntactically constant base of magnitude at least 2 is raised to an exponent the front end does
not see as constant (`pyfront.refuse_variable_int_pow` keeps its `constant base N ... computed at
run time` wording, pre273).  A power whose base reaches the checker through a name, list item,
attribute, dict value or a constant argument is still refused by name here, and a literal power in
a class body or default still is too.

Probes in `/tmp/probes` on both builds: `p1_saturate_assign` is refused by the emitter's wording,
`p2_maxsplit_pow` and `p9_assign_name_pow`/`p10_list_dict_attr`/`p5_name_base_refused` are refused
by name, `p3_variable_pow_local` and `p4_variable_pow_inrange` are refused by the front end,
`p6_inrange_local`, `p7_closure_shadow` and `p8_maxsplit_inrange` match CPython.  Tests on the
final commit: the six restored modules plus `test_ail_pre367`, `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre113`, `test_ail_pre33`,
`test_ail_pre331`, `test_ail_pre334`, `test_ail_pre335`, `test_ail_pre338` and
`test_ail_pre351` all pass.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre367 follow-up: closure free names resolve to the enclosing function (job-pre367-10280424)

The pre367 review found a false refusal: a nested function's free name was looked up only
against module constants, so `x = 10; def outer(): x = 2; def inner(): return x ** 62` was
refused as `10 ** 62` instead of computing `2 ** 62`.  `_binpow_function_lookup` now takes the
names bound by enclosing function scopes (parameters, stores, nested def/class names, imports
and exception targets; a global/nonlocal declaration is not a local binding and stays with the
outer map) and prefers the enclosing scope's single-assignment int constant to a same-named
module value.  `_binpow_enclosing_scope` builds that map as the checker descends into nested
functions; methods of a class nested in a function inherit the function's bindings the same
way.  Module-level functions are unchanged.

Probes in `/tmp/probes/pre367_fix` on both builds: `c1`, `c2`, `c11` and `f01`-`f04`,
`f07`-`f10`, `f13`, `f14` (value or exponent bound by an enclosing local, parameter, method,
two-level nesting, default argument) match CPython; `f05`, `f06`, `f15` (an out-of-range value
or exponent bound in the enclosing scope) are refused by name; `f12` (enclosing name bound to a
nested def) matches base and CPython (runtime TypeError, no false refusal); `f11` (class nested
in a function) is the unchanged "not in the subset" on both builds.  Added these cases to
`test_ail_pre367.py` (2 tests, 45 programs, both builds).  Required tests: test_ail_pre367,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py`
was run and `--check` passes.

## 2026-10-27 -- pre367: a constant power behind a name is refused by name (job-pre367-10280424)

The pre351 reviewer's unverified items were re-run first: `test_ail_files` and
`test_ail_corpus_findings3` both pass on this tree, so the remaining recorded pre-existing
difference is the one pre351 itself left: `x = 10; print(x ** 40)` at module level was already
refused by name, but the same value reaching `**` inside a function body, through an argument,
a list item, a class/instance attribute or a dict value compiled and then stopped with
`integer overflow` on both builds, where CPython prints the exact bignum.

`_check_int64_binpow_constants` (called from `_check_int64_literals`) now resolves the power's
operands while compiling: the module's rich constant environment (`_constant_value`, so safe
literal containers read by subscript, class attributes and instances), a function's own int
locals, a parameter the function unconditionally rebinds to a constant, and a constant argument
to a module function whose parameter is the base of a constant-exponent power.  An exact result
outside int64 is refused with `int64 constant expression out of range` on both builds, as the
task allows.  The existing enclosing-expression allowance is kept, so `(2 ** 63 - 1) // 1` and
`10 ** 40 - 10 ** 40` still fold and match CPython.  In-range powers, negative and float
exponents, bool bases, bases 0/1/-1, shadowed locals/containers, a parameter rebound in range,
empty containers and run-time-only operands are unchanged.  Not covered (pre-existing, still the
run-time `integer overflow` stop): a literal container bound inside a function, a default
argument, an instance created inside a function, and a value known only at run time.

Added `AIL_CURRENT/test_ail_pre367.py` (2 tests, 31 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes/pre367` on both builds:
`p01`-`p08`, `r01`-`r21` (argument, keyword argument, local, local alias, local exponent, list
item, list alias, class attribute, instance attribute, dict value, tuple and floor-div nesting,
negative base, method, rebound parameter, base boundary, int alias, argument from a list item /
dict value / attribute, named cancellation) are refused by name; `p07`, `m01`-`m12` (in-range
argument calls, module routes, int64 boundaries including `(-2) ** 63`, literal cancellation,
negative/float exponents, bools, dynamic operands and arguments, shadowed local and container,
rebound parameter, local exponent, empty containers) match CPython.  The unchanged pre-existing
variants `x01`-`x03` still stop at run time.  Final-state tests: test_ail_pre367,
test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, test_ail_pre351 and
test_ail_pre33.  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre351: local constant power is already refused by name (job-pre351-10280022)
## 2026-10-27 -- pre363: a lambda called in a class-body comprehension no longer recurses (job-pre363-10280258)

The pre347 review's first pre-existing item was an uncaught `RecursionError` for a
class-body comprehension whose lambda uses a default (`[(lambda v=x: v)() for x in
range(3)]`) or a shadowing parameter (`[(lambda x: x)(i) for i in range(3)]`), where
CPython runs the program and both builds crashed.  `call_value` expanded the
construct-a-class branch for every call through a value; compiling that branch
(`_call_class` -> `_class_attr_value`) evaluated the class attribute whose value was
still being compiled, so `_init_class_attrs` recursed.  A lambda literal is never a
class object, so while a class-attribute value is being compiled `expr_Call` now skips
that branch for an `ast.Lambda` callee (elsewhere the emitted C is unchanged), and
`_class_attr_value` refuses a re-entrant read of a slot that is still being compiled
by name instead of recursing.  Once the crash was gone, `[(lambda v=x: v)() ...]`
still clobbered the enclosing `x` because `compscope`'s class-body guard suppressed the
target rename for any lambda load.  The guard now counts a lambda body's names that the
lambda does not bind itself and ignores argument defaults, which are evaluated in the
comprehension scope and are renamed with the target, so the default and shadowing-
parameter forms match CPython.

Probes in `/tmp/probes/pre363` on both builds (`cmp.sh`): match CPython `p02`-`p08`,
`p14`, `p15`, `p17`-`p21`; refused by name `p09`-`p12` (`not in the subset: closures
nested too deeply to settle their shared names`) and `p13` (`not in the subset: name 'x'
is not defined`).  `p01` (module-level `[(lambda: x)() ...]`) is the separate pre-existing
body-read difference and is unchanged.  Final-state tests: test_ail_pre363,
test_ail_pre347, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.



The rbrbrbrbrbpre33 review's first pre-existing difference was `x = 10; print(x**40)`, a
runtime `integer overflow` on both builds where CPython prints the unbounded value.  On this
tree the module-level local form is already folded by the constant-power pass and refused at
compile time with `int64 constant expression out of range` on both builds, which is the
allowed named refusal, so no compiler change was needed.  The alias, computed-exponent,
negative-base, wide-exponent and nested-expression spellings are refused too; the four other
recorded items (`2**63 / 2**63`, `(2**63)/2`, `2**63*1.0`, `2**63+0.0`) are refused by name
(`int64 constant out of range`).  In-range powers, safe bases, negative and float exponents,
a mutated local and the argument/list-item/attribute/dict-value routes for safe values match
CPython.  A power known only at run time, or inside a function body, keeps the pre-existing
runtime `integer overflow` stop; those routes are unchanged here.

Added `AIL_CURRENT/test_ail_pre351.py` (4 tests, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes/pre351`: `p01`-`p05`
(the recorded items) and `c_mod`, `c_both`, `c_neg`, `c_big_exp`, `c_safe_bound`, `d_nested`,
`d_right`, `d_cond`, `r_alias`, `r_both`, `r_neg` are refused by name; `e_inrange` (in-range
powers, safe bases, negative/float exponents, mutation, argument/list/attribute/dict routes)
matches CPython, on both builds.  The route probes `r_arg`, `r_list`, `r_attr`, `r_dict`,
`c_func`, `c_class`, `c_both_func`, `c_mut_arg`, `d_fdiv` and `d_tuple` still stop with
`integer overflow` on both builds; that is the pre-existing run-time-only limitation noted
above, not changed by this job.  Final-state tests (4 modules, 0 failed): test_ail_pre351,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py`
was run and `--check` passes.
## 2026-10-27 -- pre353: a dict subscription by a slice uses the slice as the key (job-pre353-10280033)

The first still-differing item recorded by the pre328 reviewer was `p2_noninstance`: in CPython
3.12 a slice is hashable, so `d[1:2]` is a dict lookup with `slice(1, 2, None)` and a missing key
raises `KeyError: slice(1, 2, None)`; both AIL builds instead said `'dict' object is not
subscriptable` (the set half already matched CPython's own TypeError).  The general path's
`pyboxed2.expr_Subscript` now builds a slice object for a dict (also `Counter`/`defaultdict`)
target and uses it as the key; its unknown-kind branch checks `AIL_T_DICT` as well as
`AIL_T_INST`; `_store_slice` does the same for item assignment and deletion.  `safetyrt`'s
`ail2s_getitem`/`ail2s_setitem` treat a dict as keyed by the slice object rather than slicing
it, and `SLICE_PRELUDE` now defines `__hash__` over the three fields so equal slices find each
other.  The second recorded item (a local or parameter named `slice` shadowing the injected
prelude) is unchanged.  List/str/tuple/range slices and set subscriptions keep their behaviour.

Added `AIL_CURRENT/test_ail_pre353.py` (3 tests, 13 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`; added DIFFERENCES row
`C?-job-pre353-10280033-1`.  Probes in `/tmp/probes/pre353` on both builds: `p01`-`p15`, `p20`
and `p22` match CPython, including missing/present keys, an empty dict, caught and uncaught
`KeyError`, equal slice objects, argument/list-item/attribute/dict-value/alias routes,
dynamic/None/negative/bool bounds, literal and variable assignment and deletion, membership,
list/str/tuple controls and the set `TypeError` control.  `test_ail_pre353` (3 tests, 50 s)
passes; `test_ail_silent5` and `test_ail_pre327` also pass on this change (2 modules, 118 s).
Final-state tests: test_ail_pre353, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.  `tools/update_manifest.py --check` passes.
## 2026-10-27 -- pre354: a local named `slice` no longer shadows the slice class (job-pre354-10280045)

The first pre-existing item from the pre327 review still reproduced on this tree: a function
whose parameter or local is named `slice`, followed by a slice of a user-class instance
(`def cut(slice, x): return x[1:2]`), built on both builds and then stopped with
`TypeError: 'int' object is not callable`, where CPython passes its builtin slice object to
`__getitem__`.  The general path's `_slice_obj` built the object with a call to the
user-visible name `slice`, which the local shadowed.  `_slice_obj` now calls the prelude's
class through the compiler's own class reference (`_call_class('slice', ...)`), so neither
`slice` nor any helper name can shadow it; user code that binds `slice` still sees its own
binding, and an ordinary `slice(...)` call is unchanged.  (The first fix used an
`_ail_slice_type` alias; the review showed a user binding of that name shadowed it too, so
the alias is gone.)

Probes in `/tmp/probes/pre354` (both builds via `cmp.sh`): `p01_shadow_param`,
`p02_shadow_local`, `p03_shadow_method`, `p04_shadow_module`, `p05_shadow_global_func`,
`p06_user_slice`, `p07_shadow_loop` and `p10_routes_shadow` (alias, attribute, dict value,
list item, slice assignment/deletion) all match CPython, as do the review's `r01`-`r07`
(including `r02_alias_local` and `r03_alias_global`, where a user `_ail_slice_type`
binding previously shadowed the alias).  The review's other pre-existing items still differ
and were not changed: `p08_dict_slice` (`TypeError` instead of `KeyError slice(...)`) and
`p09_instance_name` (`'instance'` instead of `'A'`); `p11_lambda_comp` is still refused by
name.

Added `AIL_CURRENT/test_ail_pre354.py` (11 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Final-state tests: test_ail_pre354,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py`
was run and `--check` passes.
## 2026-10-27 -- reapply pre33: constant integer `**` beyond int64 (job-rbrbrbrbpre33-10271808)

Re-applied the accepted pre33 change on this tree, including its compiler fix: a constant integer
power whose exact result leaves int64 is refused at compile time by name
(`the integer power 10 ** 40 does not fit in a 64-bit signed integer (DIFFERENCES
C?-job-rbrbrbrbpre33-10271808-1)`) on both builds and in the IR lowerer. The accepted
`refuse_int_pow_overflow` helper is added to `pyfront.py` and called from `pyboxed.py`,
`pyboxed2.py`, `pyfunc.py` and `ir/lower.py`; this closes the v1 general-emitter gap where an
assigned `x = 10**40` or `b.v = 10**40` compiled and then stopped at run time with
`integer overflow`. The reapply also adds the accepted `AIL_CURRENT/test_ail_pre33.py` (8 refused
placements, 2 matching programs, both builds) and registers it in `ail_check.MODULES`.
Probes: assigned, plain, tuple, argument, list, attribute and dict placements are refused by name
on both builds; fit, float, negative-exponent and bases -1/0/1 programs match CPython. Tests on the
final tree: `test_ail_pre33`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`.
## 2026-10-27 -- pre357: int() of a float outside int64 through a `*args` constructor is refused (job-pre357-10280153)

The pre340 reviewer's first pre-existing item was `p04_starargs.py`:
`class Box: def __init__(self, v, *rest): self.v = v` with `int(Box(1e300, 2).v)` overflowed on both
builds while CPython prints the exact 301-digit integer.  `_bind_constructor_arguments` returned
`None` whenever a call had more positional arguments than named parameters, so a constructor with
`*args` never bound its named parameters.  It now discards the surplus positional arguments when
`__init__` has `*args`, and refuses to bind a keyword that would duplicate an already bound
positional parameter (that call is a Python `TypeError`, so no fold).  The conversion is refused by
name on both builds through a keyword, a default, a second positional parameter, six surplus
arguments of mixed types, a module constant, a list item, a dict value, a class attribute, an
instance, an alias, a list/dict item, a function argument and a wrapper; an out-of-int64 string
parameter is refused as `int64 constant expression out of range`.  In-range int/float/string
values (also negative and at 9e18), a starred in-range call, surplus argument types read back, a
later field store, a dynamic value, no surplus arguments and a keyword-only parameter match
CPython on both builds.  A duplicate-keyword call (`Box(1e300, 2, v=3)`) still fails at compile
time as `not in the subset: ...` on both the base copy and this tree (unchanged).  The reviewer's
other recorded items (the `self.v: float = v` annassign, `v = int(v)` rebound before the store)
still stop with `integer overflow`; they are pre-existing and not changed here.

Probes in `/tmp/probes/pre357` on both builds: 17 refusal probes (v01-v17) are refused by name;
12 match probes (m01-m12) match CPython; m13 (duplicate keyword) fails at compile time on both the
base copy and this tree.  A `/tmp` copy with the original binder shows v01 stopping with
`integer overflow` on both builds, confirming the change.  Final-state tests: test_ail_pre357,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py` was
run and `--check` passes.
## 2026-10-27 -- pre358: int() of a statically known dict.get() result is refused (job-pre358-10280158)

The pre338 reviewer's first pre-existing item reproduced on both builds:
`d = {"k": "9223372036854775808"}; print(int(d.get("k")))` compiled and then stopped with
`integer overflow`, where CPython prints the big integer (`t02_dict_get.py`).  The int64 constant
fold now reads `dict.get(key)` and `dict.get(key, default)` when the key is constant, and a
module-level dict literal (or alias) whose only uses are subscript reads or `.get` calls stays
foldable; the conversion is then refused by name with `int64 constant expression out of range`
on both builds.  Covered: an inline literal, a negative value, bytes, whitespace/underscore/plus
text, a missing key with a big default, an empty dict, an alias, and the key arriving from a list
item, a dict value or a class attribute; a float value or default keeps the `int() of a float
outside int64` refusal.  In-range values and INT64 boundaries, a big default that a present key
overrides, dicts mutated in place (subscript or `update`) to an in-range value, a dynamic value
and invalid text match CPython.  A dict held in a class or instance attribute is not folded, so a
dict mutated through `c.d[...]` keeps CPython's output.  The reviewer's other item, a function
parameter's list item (`t04_arg_list_item.py`), still stops with `integer overflow` on both
builds; it is a separate pre-existing cause and not changed here.

Added `AIL_CURRENT/test_ail_pre358.py` (2 tests, 22 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes/pre358` on both builds:
`t02`, `t02_alias`, `t02_bytes`, `t02_empty_default`, `t02_get_default_big`, `t02_inline_get`,
`t02_key_from_attr`, `t02_key_from_dict`, `t02_key_from_list`, `t02_negative` and
`t02_whitespace` are refused by name; `t02_boundaries`, `t02_dynamic_ok`, `t02_in_range`,
`t02_mutated_class_d` and `t02_mutated_in_range` match CPython; `t02_direct_subscript` was
already refused by name.  Final-state tests: test_ail_pre358, test_ail_safetynet, test_ail_files
and test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre359: int() of an inherited class attribute outside int64 is refused by name (job-pre359-10280222)

The pre337 review recorded two pre-existing items.  The first, `bump = lambda xs:
xs.__setitem__(0, 1.5)` followed by `int(items[0])`, is already refused on both builds by name
(`not in the subset: the method .__setitem__() (on a value of unknown static kind)`), which the
task allows, so it needed no compiler change and is only pinned in the new test module.

The second (`p3`, subclass class-attribute lookup) still differed: both builds compiled
`class Box: text = 1e300; class Sub(Box): pass; print(int(Sub().text))` and then stopped with
`integer overflow`, where CPython prints the big integer.  `_known_class_attributes` skipped
every class with a base, so `Sub` was unknown and the inherited value never reached the static
int() check.  It now accepts a class whose single base is a plain name bound once to an earlier
known class (also through a base alias) and copies the base's class attributes, class/instance
constructor state and `__init__` parameter map; a name bound in the subclass body shadows an
inherited class attribute.  The conversion is now refused by name with the existing
`int() of a float outside int64: ... (CPython makes a big integer)` message on both builds, also
through a three-level chain, an inherited `__init__` parameter, the negative value, a module
constant, a list item, a dict value, a function argument and a local; an inherited string keeps
the `int64 constant expression out of range` refusal.  Overridden in-range values, a subclass
with its own `__init__`, an unrelated base and plain classes match CPython.  Multiple
inheritance and later class-attribute stores were already refused by name on both builds.

Probes in `/tmp/probes/pre359` on both builds: `p_lambda`, `p_lambda_direct`, `p_subclass`,
`p_subclass_cls`, `p_alias`, `p_base` and `s01`-`s19`; every one matches CPython or is refused by
name (`s11_base_mutated` and `s12_two_bases` are existing named refusals).  Added
`AIL_CURRENT/test_ail_pre359.py` (2 tests, 21 programs, both builds) and registered it in
`ail_check.MODULES`; `tools/ci_shards.py --update` added it to `tools/ci_shards.json` (its
`--check` still reports the four duplicate assignments that are already in the committed file).
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre338: int() of an out-of-int64 class attribute read through an instance is refused (job-pre338-10272141)

The pre315 reviewer's first pre-existing item was `t01_class_attr_instance.py`:
`class Box: text = "9223372036854775808"; b = Box(); print(int(b.text))` compiled on both
builds and then stopped with `integer overflow`, where CPython prints the big integer.  The
static int() checker in `ail_chatgpt.py` now also refuses a statically known str, bytes or int
whose conversion leaves int64, so this route is refused by name at compile time with
`int64 constant expression out of range` on both builds.  In-range text (INT64 boundaries,
whitespace/underscore, a plus sign), invalid and empty text, a mutated instance or alias, an
`__init__` value that shadows the class attribute, and the existing list-item, dict-value,
class-alias and identity-argument routes keep CPython's output; the class-attribute float route
keeps its existing `int() of a float outside int64` refusal.  The reviewer's other two routes
(`t02_dict_get.py` through `dict.get` and `t04_arg_list_item.py` through a function parameter's
list item) still stop with `integer overflow` on both builds; they are pre-existing and not
changed here.

Added `AIL_CURRENT/test_ail_pre338.py` (2 tests, 17 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.  Probes in `/tmp/probes/pre338`: `t01` is refused
by name; `p03`, `p08`, `p09`, `p12`, `p13`, `p14`, `p21` and `p20` are refused by name; `p02`,
`p04`, `p05`, `p06`, `p07`, `p10`, `p11`, `p17`, `p18`, `p19`, `p23` and `p24` match CPython, all
on both builds.  Final-state tests (8 modules, 448 s, 0 failed): test_ail_pre338,
test_ail_pre263, test_ail_pre290, test_ail_pre306, test_ail_pre311, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py` was run and `--check`
passes.
## 2026-10-27 -- pre340: int() of a constructor-parameter float outside int64 is refused (job-pre340-10272149)

The pre333 reviewer's first pre-existing item was its p16 `int(Box(1e300).v)`, where
`__init__(self, v)` stores the parameter directly: both builds compiled and then stopped with
`integer overflow`, where CPython prints the exact 301-digit integer.  The class-attribute fold
now binds a constructor call to its `__init__` parameters, so a direct `self.attr = param` store
can be read at a call site.  That route is refused by name with the existing
`int() of a float outside int64: ... (CPython makes a big integer)` message on both builds, also
through a keyword argument, a default, a second positional parameter, a module constant or list
item passed as the argument, an instance name, an alias, a list/dict item and a function argument
or wrapper.  In-range values, dynamic constructor values, literal class attributes, a later field
store and a non-conversion read still match CPython.

The second recorded pre-existing item (the default build's dict item-overwrite failure, p12/p15)
is unchanged; only the first still-differing item was fixed.

Probes in `/tmp/probes/pre340` on both builds: `p16`, `p16b`, `p16d`-`p16m` and `p16r` are
refused by name; `p16c`, `p16n`-`p16q`, `p16s` and `p16t` match CPython.  The baseline `p12`
matches on the general build and keeps the pre-existing default-build failure; `p15` matches on
both.  Final-state tests: test_ail_pre340, test_ail_pre306, test_ail_pre302, test_ail_pre311,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (7 modules, 0 failed).
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre341: a mutated module-level list of number tuples keeps the list (job-pre341-10272226)

The pre329 review's first pre-existing item reproduced on both builds: `ps = [(1, 2), (3, 4)]` at
module level followed by `del ps[-1]` printed the unchanged list.  The tuple pass kept a module-level
list of number tuples as two number columns and rebuilt a fresh list (`_ail_rc_ps()`) for every value
use, so the delete (and `append`, `pop`, an item store, or a mutation through an alias or a function
argument) changed the temporary instead of the list CPython shares.

`tupcommon.rowconst_module_in_place` now checks the module-level statements too, ignoring only the
defining assignment: anything but a for/comprehension walk, an indexed read, an `in` test or a
read-only builtin keeps the list as written, and the normal compiler handles the mutation.  In-place
reads still lower to columns.  Deletions of lists of int, float, bool, string, mixed and nested
tuples, empty lists, out-of-range and uncaught indexes, indexes arriving through a list item,
attribute or dict value, aliases and function arguments match CPython on both builds.

Only the first reported item was in scope and is fixed.  Spot-check probes for the others were not
exhaustive: a no-try typed int-list delete (`del xs[9]`, also `-9`) already printed the `IndexError:`
prefix on this tree, the typed nested shapes did not build on the default path in the probe shape,
and the uncaught trap wordings (`KeyError`, `ZeroDivisionError`, bytes `IndexError`) still differ on
the default build.  None of them was changed here.
Probes in `/tmp/probes/pre341` (46 programs): all 33 i2 module-tuple probes match CPython on both
builds; the i3/i4/i5 probes cover the other items.  Added `AIL_CURRENT/test_ail_pre341.py` (13
programs, both builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
Final-state tests:
test_ail_pre341, test_ail_safetynet, test_ail_tuples, test_ail_files and test_ail_corpus_findings3
(5 modules, 434 s, 0 failed).  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre331: wide constant `pow()` exponent refused by name (job-rbpre331-10272258)

The pre331 reviewer's first still-differing item was `pow(2, (3**100)>>150)`: both builds
compiled it and then stopped with `integer overflow`, where CPython prints the bignum.  The
`pow` constant check already refused `pow(2, 63)`, but its exponent folder (`_const_expr_int`)
returned `None` for a power whose exponent is above 64, so the `>>150` result (361) was never
static.  `_pow_static_int` now prefers the shared exact-int folder (`_const_fold_int`) and keeps
the tree's shift-aware `_constant_int`/`_const_expr_int` fallbacks, and the module/local
constant collectors do the same, so the direct call, a module or local name bound to the
expression, and an alias of `pow` are refused at compile time with `int64 constant expression
out of range`.  In-range bases/exponents, the safe bases 0/1/-1, bool and float bases, a
negative exponent, the three-argument modular form and a program that binds its own `pow` still
match CPython.  An exponent that reaches the call only through a list/attribute/dict item or a
function parameter keeps the old runtime `integer overflow`; that container/parameter
propagation gap predates this fix and is unchanged.

Probes in `/tmp/probes/pre331` on both builds via `cmp.sh`: refused by name `p01_direct`,
`p02_shift_beyond`, `p07_neg_base`, `p12_module_const`, `p13_local`, `p14_argument_call`,
`p19_alias`, `p21_result_list`, `p22_result_attribute`, `p23_result_dict`, `p27_exp_one`,
`p28_local_alias` and `p29_int64_min`; match CPython `p03_inrange_base`, `p04_zero_exp`,
`p05_one_base`, `p06_negone_base`, `p08_bool_base`, `p09_float_base`, `p10_modulo`,
`p11_negative_exp`, `p24_shadowed`, `p25_inrange_ordinary` and `p26_base_expr_zero`.  Added
`AIL_CURRENT/test_ail_pre331.py` (3 tests, 11 refused programs and 2 matching programs, both
builds) and registered it in `ail_check.MODULES`, `tools/ci_shards.json` and `MANIFEST.json`.
## 2026-10-27 -- pre347 follow-up: a lambda reading a renamed class-body target (job-pre347-10272320)

The review of this job found that `x = 99; class C: ys = [(lambda: x)() for x in range(3)];
print(x, C.ys)` compiled on the base with the named refusal `closures nested too deeply to settle
their shared names`, but the new class-body analysis renamed the target to `x__c1`, removing the
shared name the closure pass saw, and both builds then stopped with an uncaught `RecursionError`
from the class-attribute path.  `compscope` now leaves a class-body comprehension target
unrenamed when a lambda nested anywhere in that comprehension reads it (body, nested lambda,
condition or list item), so the construct keeps the base tree's named refusal.  Comprehensions
without such a lambda are renamed as before.  Added four refusal programs to
`test_ail_pre347.py`; `DIFFERENCES.md` records the refusal.

Probes in `/tmp/probes` on both builds: p23 (the review case), p31 (nested lambda), p35 (lambda
in a condition) and p32 (lambda as a list item) are refused by name with exit 1 and no
`RecursionError`; pre347 p01 (the original class-body target case), p10 (all comprehension
kinds), p17 (class attribute and global of the same name), p18 (conditions), p19 (multiple
classes) and p20 (module/function controls) still match CPython.  Final-state tests:
test_ail_pre347, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre347: a class-body comprehension target stays local (job-pre347-10272320)

The reviewer of job rbpre304 recorded `x = 99; class C: ys = [x for x in range(3)];
print(x, C.ys)`: both builds printed `2 [0, 1, 2]` where CPython prints `99 [0, 1, 2]`.  The
comprehension-scope pass (`compscope.py`) analysed module and function bodies but not class
bodies, so a class-body comprehension target kept the enclosing module's name slot and overwrote
the global.  `visit_ClassDef` now records each class body, and the analysis runs it separately
with the enclosing scope's names, so a target that can clash with an enclosing or class-body
name gets the existing fresh identifier.  Module and function comprehensions keep their previous
C.  This covers list, set, dict and generator comprehensions, nested and multiple-generator
forms, a target equal to a class attribute, the class name or a builtin name, empty or negative
ranges, other value types and aliases.

Probes in `/tmp/probes/pre347` on both builds: `p01`-`p05` and `p07`-`p12` match CPython; `p06`
(a nested class) and `p13` (a destructuring target over a module list, also refused on the base)
are refused by name; `p14`-`p23` match CPython.  Final-state tests: test_ail_pre347 (1 test, 15
programs, both builds), test_ail_pre304, test_ail_quirks Q2, test_ail_fuzz23,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.  `tools/update_manifest.py`
was run and `--check` passes.
## 2026-10-27 -- pre328: user-class slicing after a compound rebinding (job-pre328-10271926)

The pre323 reviewer recorded as pre-existing that slicing a user-class instance through
`__getitem__` after a `for`, `with` or tuple-unpacking rebinding (and through an argument, a
list item, an attribute or a dict value) compiles and then stops with
`NotImplementedError: slicing an instance through __getitem__ is not supported: this path has
no slice objects`, while CPython passes a real slice object.  The general path's slice branch
for an unknown kind already knew how to dispatch on the runtime tag, but it was entered only
when a previous `NeedSlice` retry had set `want_slice`; a program whose only instance slice was
one of these routes therefore took the ordinary `ail2s_getslice` path.

That branch is now requested whenever the target is not a known `str`/`list`/`tuple` and any
class defines `__getitem__`, so the generated code asks the value's tag: an instance gets a
slice object through `ail_op_getitem`, everything else keeps `ail2s_getslice`.  The bounds are
evaluated inside the two branches, once in whichever runs, which also removes the double
evaluation the old unknown-kind branch did for an instance.  Direct instances, `if` rebinding,
`for`/`with`/tuple rebinding, the argument/list-item/attribute/dict-value routes, empty,
negative and dynamic/`None` bounds and bounds with side effects match CPython on both builds;
a constant index or step outside int64 is still refused by name.  Added
`AIL_CURRENT/test_ail_pre328.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.

Probes in `/tmp/probes/pre328` on both builds: `p_direct_in`, `p_assign_in`, `p_if_in`,
`p_for_in_only`, `p_with_in`, `p_tuple_in`, `p_routes_in`, `p_str_list_in`,
`p_dynamic_bounds`, `p_negative`, `p_empty`, `p_side_effect` and `p_set_del_routes_in` match
CPython; `p_direct`, `p_for`, `p_for_in` and the out-of-int64 routes are refused by name.
`p_errors` (dict/unknown TypeError text) is identical on the base and this tree, so it is a
pre-existing difference not caused by this change.  Final-state tests: `test_ail_pre328` (2
tests, OK, 55 s), `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`.
`tools/update_manifest.py --check` passes.

Re-applied on job-rbpre328-10272341 over a tree that already carried the same general-path tag
dispatch (from pre327): resolving the conflicts kept both sides' fixes, so the compiler and
`test_ail_silent5` were already at the fixed behaviour and only `test_ail_pre328.py`, its
`ail_check.MODULES` registration and the records are new.  `tools/diff_ids.py` is not present on
this tree, so it was not run.  Probes re-run for this job in `/tmp/probes/pre328` on both builds:
`p_alias`, `p_direct_if`, `p_dynamic_bounds`, `p_empty_negative`, `p_for`, `p_routes`,
`p_self_bounds`, `p_side_effect`, `p_tuple` and `p_with` match CPython; `p_huge_attr`,
`p_huge_index`, `p_huge_slice` and `p_huge_step_route` are refused by name (`int64 ... out of
range`).  Final-state tests on this commit: `test_ail_pre328`, `test_ail_silent5`,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` (48 tests, OK, 696 s,
1 skipped); `tools/update_manifest.py --check` passes.

## 2026-10-27 -- pre345 fix: accept the re-applied pre9 infinity refusal wording (job-pre345-10280059)

Applied alone on today's integ, `test_ail_pre345` failed.  The integ "re-apply pre9" change
(`job-rbrbrbrbpre9-10272112`) gave the infinity-literal refusal its own named wording,
`the float literal inf converted with int() does not fit in a 64-bit signed integer ...`, where
this branch still says `not in the subset: a nan/inf float literal`.  The test's `REFUSALS`
list had no marker for the new text, so its first affected slug (`infinity_literal`) failed on
both builds and, because the per-slug mode check sits outside the subTest, the assertion ended
the loop and skipped the remaining slugs.

`REFUSALS` now also accepts `does not fit in a 64-bit signed integer` (the wording integ's own
`test_ail_pre9` accepts), keeping the previous markers so the test passes on both this branch
and integ.  No compiler code changed.  `test_ail_safetynet` is byte-identical on this branch
and integ; it passes on the integ worktree with the patched test and on this branch, so its
recorded failure could not be reproduced (not observed under `par_check.py -j 2`).

Probes in `/tmp/probes/pre345fix` with `cmp.sh` on both builds: `p01_inf`, `p02_ninf` are
refused by name (`a nan/inf float literal` here); `p03_finite_pos`, `p04_boundary_hi`,
`p07_list_item`, `p08_dict_value`, `p09_attr`, `p10_arg`, `p11_alias` are refused by name
(`int() of a float outside int64`); `p05_boundary_inrange`, `p06_rounding` and
`p12_inrange_flows` (argument, list item, dict value, attribute) match CPython.  Final-state
tests: test_ail_pre345, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre345: pre9's int() float-literal and int-shadow cases are already refused by name (job-pre345-10272303)

The pre9 reviewer recorded as pre-existing the pre290 finite float-literal refusals, the
infinity literal refusal and the int-shadowing refusal.  Reproduced the first on this tree with
`bash ~/tools/cmp.sh` on both builds: a finite out-of-int64 float literal passed directly,
negatively, through a unary paren, a constant conditional, a module constant, a list/tuple/dict
item, an alias, or a positional/keyword/positional-only wrapper already stops at compile time
with the named `int() of a float outside int64` message; `int(1e400)` and `int(-1e400)` stop
with `not in the subset: a nan/inf float literal`.  The int-shadow cases are also resolved: a
local lambda or a parameter named `int` matches CPython, while `def int` and a module `int`
constant are refused by name.  No compiler change was needed.  Added
`AIL_CURRENT/test_ail_pre345.py` (22 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.

Probes in `/tmp/probes/pre345` on both builds: `p1`-`p3`, `p5`-`p7`, `p9`, `p10`, `p14`-`p16`,
`p19`, `p20` and `p22`-`p28` are refused by name (`p9`/`p10` as `a nan/inf float literal`, the
rest as `int() of a float outside int64` or the int-shadow message); `p13`, `p17`, `p18` and
`p30` match CPython.  Shapes outside the recorded literal refusals still stop at run time on both
builds and were not changed: `p4` (non-constant conditional), `p8`/`p21` (instance attribute),
`p11` (`2.0**63`), `p12` (`float(1e300)`) and `p29` (power through a wrapper).  Final-state
tests: test_ail_pre345, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre326: a nested class inside a function is already refused by name (job-pre326-10271918)

The pre324 reviewer's first pre-existing item was a nested class inside a function
(`def make(): class C: ...`, including an attribute, an `__init__`, an unexecuted class, a
conditional class, a nested function and a method body), which CPython runs.  Reproduced it on
both builds: this tree already refuses the construct at compile time with the named
`a nested class definition (C)` message, which the task allows, so no compiler change was
needed.  The review's other pre-existing items are also already refused by name on both builds
(`a class body statement other than def/assignment/pass/docstring in C`): an async method and a
class-body `for`, `with`, `try` or `global`.  A top-level class control still matches CPython.
Added `AIL_CURRENT/test_ail_pre326.py` (13 programs, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`.

Probes in `/tmp/probes/pre326` on both builds: `p01`-`p05` (nested class) and `p06`-`p10`
(async method, class-body `for`/`with`/`try`/`global`) are refused by name.  Final-state tests:
test_ail_pre326, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre307: out-of-range list deletion uses CPython's assignment message (job-pre307-10271311)

The one pre-existing difference recorded by the rbrbpre19 review was
`del a[-9223372036854775808]`: both builds exited 1 with matching stdout, but stderr said
`IndexError: list index out of range` (the current tree) or `pop index out of range` (the typed
path) where CPython says `IndexError: list assignment index out of range`.  The base tree
(`eedf548`) shows the same, so the difference predates this job.

`ail_list_delitem` in cruntime.py now normalizes the index and raises the assignment wording,
both for the unified/context entry point and for the object-level helper used by the typed path;
the index-kind mapping learned the new text and exctext.py's redundant DIE edit is gone.  Typed
`del` of an int list emits an explicit `_dk >= n || _dk < -n` check before `ail_list_pop`, so it
no longer borrows `.pop()`'s message.  `.pop()` itself is unchanged (`pop index out of range` /
`pop from empty list`).

Probes in `/tmp/probes` (`pre307_*`) match CPython on both builds for ordinary, negative,
INT64_MIN/MAX, empty, float and str lists; the argument/list-item/attribute/dict-value routes and
aliases; caught `IndexError` with and without `str(e)`; valid negative and slice deletes; dict
deletes; and unchanged `.pop()`/reads.  An uncaught typed trap still prints the bare message text
without the `IndexError: ` prefix, a pre-existing limitation already recorded for typed traps.

Added `AIL_CURRENT/test_ail_pre307.py` (3 tests, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`; `tools/update_manifest.py --check` passes.
Final-state tests: test_ail_pre307, test_ail_pre269, test_ail_pre246, test_ail_pre298,
test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 (7 modules, 290 s, 0 failed).
## 2026-10-27 -- re-apply pre57: CPython dict key-table shape after delete/reinsert (job-rbpre57-10271816)

Re-applied the accepted pre57 change on the current integration tree, keeping both sides'
fixes: the tree's newer `ail_map_set_hashed`, `ail_map_merge_dict`, `ail_map_clone_shape` and
`ail_map_clone` paths are reconciled with the accepted CPython perturbed probe sequence and the
new `nentries`/`tail_dead`/`usable`/`dirty` dummy-slot tracking, direct instance `__hash__`
results, and the `test_ail_pre57` module. Probes are listed in the report; final-state tests are
test_ail_pre57, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-24 - pre57 follow-up: CPython probing and dk_usable

The review of the first pre57 fix found two regressions against the base tree. The dummy index
slots were placed by AIL's linear probe, while CPython probes with `perturb >>= 5` and
`i = i*5 + perturb + 1`; for a user `__hash__` returning 32 the old code also fed the value
through the private int table mix instead of using it directly. Dict lookup, insertion, delete,
rehash and resize now use CPython's probe sequence, `find_empty_slot` reuses the first dummy,
and an instance `__hash__` result is the table hash itself (`-1` becomes `-2`). A separate
`usable` field now models `dk_usable`: `popitem` lowers `nentries` without restoring it, so the
next insert still resizes when CPython does. Copies clone the index including dummy slots.
`test_ail_pre57.py` adds the reviewer's equality-order and popitem/usable probes.

## 2026-10-24 - pre57: dict key-table shape after delete/reinsert

The pre43 reviewer recorded as pre-existing that `update` / `dict()` after a delete+reinsert
called a user `__eq__` a different number of times from CPython 3.12 (p14 omitted `E 20 11`), and
that source dict construction after delete+insert could print the same calls in a different
order. The cause was `ail_map_del` rebuilding the whole index: CPython leaves a dummy index slot
and keeps `dk_nentries`. The runtime now tracks `nentries`, trailing dummies and dummy slots, uses
stored hashes for dict-to-dict merge/copy, and dict equality skips `-2` slots (the pre43 fix read
`index[-2]` there). `test_ail_pre57.py` covers p10/p14-style update/dict/copy/popitem shapes,
dict equality with tombstones, source order, arguments/list items/attributes/dict values, and
empty/negative/plain boundaries on both builds.
## 2026-10-27 -- re-applied fuzz68: mixed-type container displays (job-rbfuzz68-10271833)

Re-applied the accepted fuzz68 change on this tree.  The tree already refused a list / set /
dict display whose known element types differ, so the general path keeps CPython's mixed text;
that refusal and its message are unchanged.  `Exprs.seq_type` in
`AIL_CURRENT/python/pkg-v12/tupexpr.py` now also remembers a `None` element and refuses a
display that mixes `None` with another known type, instead of skipping the `None` and lowering
the display with the other type (which mattered when an annotation supplied `want_elem`).  The
tree's int + bool widening and the general-path fallback for the remaining numeric mixes are
kept; int + float widens in either order.  Added `AIL_CURRENT/test_ail_fuzz68.py` and registered
it in `ail_check.MODULES`; it covers the value through an argument, a list item, an attribute
and a dict value on both builds.  `tools/diff_ids.py` is not present in this tree, so it was not
run.  Probes in `/tmp/probes` (`p_none`, `p_numeric`, `p_mixed`, `p_homogeneous`) match CPython
on both builds.  Final-state tests: `test_ail_fuzz68`, `test_ail_fuzz32`, `test_ail_tuples`,
`test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

## 2026-10-27 -- pre329: an uncaught nested-list deletion keeps its IndexError text (job-pre329-10271938)

The pre307 reviewer's first pre-existing item reproduced on the default build: with an open `try`
that does not catch it, `del rows[i][j]` into a nested list (a list literal, an argument, a class
attribute, a dict value, an alias and an empty inner list) prints just `IndexError` where CPython
says `IndexError: list assignment index out of range`.  `ail_die()`'s conversion to a catchable
exception stored an empty payload, so the re-raised exception had no text; it now stores the trap
message, and `exctext` still swaps in CPython's wording when the program reads exception text.
The general path already matched.  Added `test_ail_pre329.py` (7 uncaught routes plus a
caught/`finally` route, both builds) and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.

Probes in `/tmp/probes/pre329` via `cmp.sh` on both builds: `p09`, `p11` and `p12` reproduce and
now match CPython; `p13` and `p14` (caught and bare re-raise, which read the text) still match.
Unchanged pre-existing: the second item (`del ps[-1]` on a list of tuples does not remove the
element, both builds) and the third (an uncaught typed list delete without an open `try` omits
the `IndexError:` prefix).  The full-C pins in `test_ail_numeric_bindings` and
`test_ail_record_initializers` were regenerated for the changed DIE block.  Final-state tests:
test_ail_pre329, test_ail_pre272, test_ail_numeric_bindings, test_ail_record_initializers,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre327 review fix: slice bounds evaluated once (job-pre327-10271919)

The reviewer found that the unknown-kind slice branch evaluated the non-`None` bounds with
`_slice_bounds` before the instance tag test and then again inside `_slice_obj`. An instance
reached through an unknown value therefore ran `f():g():h()` twice (and `x[data.pop():data.pop()]`
popped once per bound before the tag test, giving an `IndexError` instead of CPython's
`(2, 1, None)`). `_slice_bounds` now emits only inside the non-instance `else` arm, so each
runtime path evaluates the bounds exactly once; the instance arm keeps `_slice_obj`.

Probes in `/tmp/probes/pre327fix` (both builds via `cmp.sh`): `p_eval_once` (instance through an
argument, an attribute, a list item, a dict value and an alias; list and str non-instances),
`p_mutating` (two and three `list.pop()` bounds on an instance, a list, a tuple and a str),
`p_types` (empty, negative, `None`, bool and step bounds on instance, list, tuple, str, bytes,
bytearray and range), `p_routes` (inherited `__getitem__` through argument, alias, attribute,
dict value, list item, `for`, `with` and tuple unpacking) all match CPython. `p_literal_bounds`
is refused by name (`int64 literal out of range`). Required tests on this final state:
test_ail_pre327, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (4 modules,
0 failed). `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre327: a slice of an instance reached through an unknown value (job-pre327-10271919)

The pre323 reviewer's second pre-existing item reproduced on this tree: a user-class slice
through a parameter, a `for` / `with` target or a tuple-unpacked item built and then stopped with
`NotImplementedError: slicing an instance through __getitem__ is not supported: this path has no
slice objects`, where CPython calls `__getitem__` with `slice(1, 2, None)`. The general path's
unknown-kind branch in `expr_Subscript` was gated on `want_slice`, so when no statically known
instance slice appeared earlier in the program the prelude was never requested. The branch now
raises `NeedSlice` on the first attempt and, after the retry, tests the instance tag and passes a
slice object; built-ins keep `ail2s_getslice`. Slices whose value is not an instance still match
CPython. The first recorded item, a direct out-of-int64 literal including as a slice bound, is
already refused by name (`int64 literal out of range`) on both builds, so it was not changed.

Probes in `/tmp/probes/pre327` (both builds via `cmp.sh`): `p1_literal`, `p19_huge` and
`p20_huge_neg` are refused by name; `p2_for_inrange` through `p15_assign`, `p17_incode` and
`p18_nofeature` match CPython. `p16_other` / `p16b_other_only` still print `'instance' object is
not subscriptable` where CPython names `'A'`, identical on the base (pre-existing). A program
whose only executed slices are built-ins compiles to different C only when it also defines a
class with `__getitem__` (the branch's gate); with no such class the C is unchanged. Its output
matches CPython either way. Added `AIL_CURRENT/test_ail_pre327.py` (8 programs, both builds; each
matches CPython or is refused by name) and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.

## 2026-10-27 -- pre334: a store into an outer e.args[i] from a nested handler is refused by name (job-pre334-10272100)

The first pre-existing item from the pre317 review still reproduced on this tree: a store into the
outer caught exception's `e.args[i]` from a nested handler (`except ... as inner: e.args[0] = 5`)
ran on both builds and matched CPython's stdout, exit status and last stderr line, but AIL's
stderr traceback was only one line where CPython prints the full chain.  `_scope_nodes` treated an
`ExceptHandler` as a scope boundary, so the outer handler's scan never reached the nested handler
body; `ast.ExceptHandler` is no longer in `_SCOPES`, and the walk now enters the nested body in
source order, forgetting the nested handler's own name through the existing `_forget_binding` (so
a same-named inner `e` still refers to the inner exception, and a nested handler with its own name
is still refused by that handler's own scan).  The construct is therefore refused by name at
compile time on both builds for a literal, negative or computed index, `+=`, an annotated store,
`del`, a destructuring target, a `for` or `with` target, a value reaching it through an argument, a
list item, an attribute or a dict value, an alias of the outer exception through a name, list item,
attribute or dict value, a deeper nested handler, and an empty `args`; rebinding the outer name
inside the nested handler, an unrelated object's `args` list and reads of `e.args[i]`/`e.args` are
unchanged.  Added `AIL_CURRENT/test_ail_pre334.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`; added DIFFERENCES row `C?-job-pre334-10272100-1`.

Probes in `/tmp/probes/pre334` on both builds (27 programs): the 23 stores are refused by name
(`p6`, `p6_neg`, `p6_comp`, `p6_aug`, `p6_del`, `p6_ann`, `p6_dest`, `p6_for`, `p6_with`,
`p6_value_arg`, `p6_value_list`, `p6_value_attr`, `p6_value_dict`, `p6_alias_name`,
`p6_alias_list`, `p6_alias_attr`, `p6_alias_dict`, `p6_alias_after`, `p6_shadow`,
`p6_inner_name`, `p6_nested2`, `p6_empty`, `p6_typed`); `p6_read`, `p6_read_typed`, `p6_rebind`
and `p6_unrelated` match CPython on both builds.  `test_ail_pre334` (6 tests, 49 s) passes; the
final-state required modules are run on the commit.
## 2026-10-27 -- re-apply pre9: `int(<float literal>)` outside int64 refused (job-rbrbrbrbpre9-10272112)

Re-applied the accepted pre9 change on this tree. CPython's int is unbounded, so `int(1e300)`
returns an exact big integer; AIL's int is 64-bit (SEMANTICS section 1). The current tree's
pre290 front-end pass already refuses a finite direct `int(<float literal>)` outside int64 by
name, so the accepted helper is added to all three emitters (`pyfunc.py`, `pyboxed2.py`,
`pyboxed.py`, through `pyfront.refuse_int_float_literal`) and also covers the infinity literal
(`int(1e400)`), which pre290's finite-only check skipped. In-range float literals, including
`-9223372036854775808.0`, and values arriving through arguments, lists, attributes, dicts,
aliases or variables keep the ordinary conversion.

`test_ail_pre9.py` accepts either refusal wording and covers the refused literals (1e300,
-1e300, 2**63 as a float, an infinity literal) in default/general builds on AIL_IR=0/1, and
compares in-range literal and flow results with CPython. Probes in `/tmp/probes`
(`pre9_inrange`, `pre9_flows`) match CPython on both builds; `pre9_refuse_pos`, `pre9_refuse_neg`,
`pre9_refuse_two63`, `pre9_refuse_inf`, `pre9_refuse_ninf`, `pre9_refuse_unary`,
`pre9_refuse_list`, `pre9_refuse_dict` and `pre9_refuse_attr` are refused by name on both builds.
`tools/diff_ids.py` is absent on this tree; `tools/update_manifest.py --check` passes.
## 2026-10-27 -- pre335: the rbrbrbrbpre33 review's first pre-existing difference is already refused (job-pre335-10272125)

The review recorded `99999999999999999999 ** 0` as a pre-existing difference: CPython's
unbounded int makes the exact result 1, while AIL refuses the 20-digit base literal.  Reproduced
it on both builds: this tree already refuses the construct by name at compile time
(`int64 literal out of range: 99999999999999999999`), which the task allows, so no compiler
change was needed.  The module-assignment spelling `VALUE = 99999999999999999999 ** 0` folds
the whole expression to 1 and matches CPython, as do `(10 ** 20) ** 0`, the int64 boundaries
and the existing wide-intermediate bases `(1 << 5000) ** 0`, `0 ** (1 << 5000)`,
`1 ** (1 << 5000)` and `(-1) ** (1 << 5000)`.  The other two recorded items stay named
refusals on both builds: `float(10 ** 400)` (CPython raises OverflowError at run time) and
huge literal powers in an f-string or a `str.split` maxsplit.  Added
`AIL_CURRENT/test_ail_pre335.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.

Probes in `/tmp/probes/pre335` on both builds: `p02_pow_zero_expr`, `p12_bounds` and
`p14_route_pow` match CPython; `p01_pow_zero`, `p02_absorbing`, `p03_zero_bases`, `p04_negative`,
`p05_routes`, `p06_huge_local`, `p07_fstring`, `p08_maxsplit`, `p09_float400`, `p10_huge_literal`,
`p11_nested`, `p13_pow_one` and the route probes `p15_route_arg`, `p16_route_list`,
`p17_route_attr`, `p18_route_dict`, `p19_route_return` are refused by name.  The earlier
`p03_pow_zero_routes`, `p04_float400`, `p05_fstring` and `p06_maxsplit` probes also stay
refused by name.  Final-state tests: `test_ail_pre335`, `test_ail_safetynet`, `test_ail_files`
and `test_ail_corpus_findings3`.  `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- fuzz59 suite fix: CPython 3.12.15 changed the step-1 slice TypeError text (job-rbrbfuzz59-10280352)

`test_ail_fuzz59` failed on the integration runner because CI's setup-python 3.12 is now
3.12.15, and CPython 3.12.15 (like 3.13) raises `TypeError: must assign iterable to extended
slice` for a non-iterable value on a step-1 slice (`b[1:2] = 5`), where 3.12.3 says `can only
assign an iterable`.  AIL still emits the 3.12.3 text (`safetyrt.py` picks it by `step == 1`),
so the `ERRORS` program's exact-output comparison failed only on the newer interpreter.
`test_ail_fuzz59` now normalizes those two known spellings before comparing stdout, so it
passes on both; the exception type and every other message are still compared verbatim.  No
compiler change: `test_ail_fuzz59` passes under system CPython 3.12.3, 3.12.15 and 3.13.16 on
the general and default builds (AIL keeps 3.12.3's wording, which the normalization accepts
when the host is newer).  `test_ail_safetynet`, the other module named by the task, passes
its 5 tests on 3.12.3, 3.12.15 and 3.13.16, on integ `0ece0a9` plus this branch's diff and on
this tree; its failure in the batch suite was not reproducible.  Probes
`/tmp/probes/p1_slot_foreign.py`, `p2_routes.py`, `p3_noniter_slices.py`,
`p4_valid_slices.py` and `p5_srepr.py` match CPython on both builds.  Final-state tests:
test_ail_fuzz59, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3;
`tools/update_manifest.py --check` passes.

## 2026-10-27 -- rbrbfuzz59 repair re-check: branch is green on the batch bases (job-rbrbfuzz59-10280140)

The repair task reported `test_ail_fuzz59` and `test_ail_safetynet` failing when this branch is
applied alone on the integration tree.  The culprit job (`culprit rbrbfuzz59`, run 40542121839,
16:33Z) ran while the repair branch it names was still the export that predates the fix from
job-rbrbfuzz59-10272331 (the `_ail_srepr` non-str fallback and the `list[str]` route), so the
report describes that earlier tree, not this one.  Re-ran the exact culprit steps here: this
branch is a snapshot of integ `753c709` plus a 7-file change (352 insertions: `tuplegen.lrepr`
scalars through `%r`, `_ail_srepr` falling back to `%r` for a non-str, `%r` lowered through
`_repr_conv` in `pyfunc._build_percent_value`, the new `test_ail_fuzz59`, registration, the two
DIFFERENCES rows and this log).  `git diff 753c709 b8c01c7 -- . ':!.agent' ':!corpus'
':!AIL_CURRENT/MANIFEST.json'` piped into `git apply --3way` on integ `5dff385` and on the batch
candidate base `cf63372` conflicts only in `DEVLOG.md` (union merge, as before); no source hunk
conflicts.  On both bases `test_ail_fuzz59` passed 7 tests in 37.7 s and `test_ail_safetynet`
passed 5 tests in 134-136 s; on this branch itself they pass in 37.6 s and 131.6 s.  The same
check on the pre-fix snapshot (branch job-rbrbfuzz59-10272028, `7cd2ef1`) also passes (37.7 s,
134.3 s), so nothing in the branch's semantics depends on the older export.  Probes
`p1_slot_foreign` (int/bool/float/None left in a `list[str]` by a failed `heappush`, plus a str
in a `list[int]` slot), `p2_slot_routes` (item, dict value, attribute, argument), `p3_srepr_escapes`
(quotes, backslash, newline/tab/CR, control and non-ASCII characters, empty string),
`p4_percent_r` (int, negative, bool, float, str, None, tuple, list, dict, and a program-defined
`repr`) and `p5_refused_width` (`%5r`, `%.2r`) match CPython on the general and default builds.
No source change was needed; this entry records the re-verification.  `tools/update_manifest.py
--check` passes.

## 2026-10-27 -- fuzz59 apply on an integ that already has the first change (job-rbrbfuzz59-10272331)

The culprit gate applied this job alone on an integ tree that already contained the first fuzz59
change (its `lrepr` used `repr_expr` for a `list[str]` slot), so the second change's hunk in
`tuplegen.lrepr` conflicted; `git apply --3way` left conflict markers in the source and both
`test_ail_fuzz59` and `test_ail_safetynet` failed to compile.  The branch's diff now keeps that
`lrepr` hunk byte-for-byte identical to the first change, so it merges cleanly there, and puts the
later half in `_ail_srepr`: a value whose runtime type is not a str (an int, bool, float or None
that a failed `heappush` left in a `list[str]`) falls back to `"%r"` and shows its own repr, while
a real str keeps the existing quoting/escaping.  Simulated the culprit steps on integ `894a446`
with the first change already applied, then this diff: only `DEVLOG.md` needed the union merge,
`update_manifest.py --check` passed, and `test_ail_fuzz59`, `test_ail_fuzz65` and
`test_ail_safetynet` all passed (132 s, 0 failed).  Probes `f59_slot_foreign` (int/negative/bool/
float/None through an argument, empty list), `f59_slot_routes` (through a list item, a dict value
and an attribute) and `f59_str_repr` (quotes, escapes, non-ASCII, empty, nested lists and tuples)
match CPython on the general and default builds.

## 2026-10-27 -- fuzz59 regression: a `list[str]` repr uses the value's `%r` (job-rbrbfuzz59-10272028)

The re-applied fuzz59 change gave a `list[str]` slot the generated str-repr helper
(`repr_expr`), which calls `_ail_srepr(x)` and iterates its argument as a string.  fuzz65 pushes
an int into a `list[str]` (CPython appends before its comparison raises, so the int stays there)
and then prints the list: both builds stopped with `TypeError: argument of type 'int' is not
iterable` where CPython prints the list with `1`.  `tuplegen.Gen.lrepr` now formats every scalar
element with `%r`, str included; the typed path lowers `%r` of a str through `_repr_conv`, so a
real str keeps `_ail_srepr`'s quoting and a value of another type in a `list[str]` slot shows its
own repr.  fuzz59's `list[int]`/`repr`-shadowing cases and fuzz65 both pass on the general and
default builds; probes over quotes, escapes, non-ASCII and int/bool/float/None elements match
CPython.  `tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- rbrbfuzz59 re-check: current integ already passes both target modules (job-rbrbfuzz59-10272028)

The repair task reported `test_ail_fuzz59` and `test_ail_safetynet` failing when this job was
applied alone to the integration tree.  Re-ran the exact culprit patch (`git diff 753c709
4212b36 -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`) on current `origin/integ`
(`82a3ead`, the PR #160 merge), including the culprit workflow's conflict handling and manifest
refresh: `test_ail_fuzz59` passed in 22.3 s and `test_ail_safetynet` in 76.5 s.  Also checked the
earlier integration candidates `60d5cb6`, `6789dfa`, `a74a15f` and `a949741`; both modules pass
on each.  No source change was needed; this entry records the re-verification.

## 2026-10-27 -- re-apply fuzz59: keep list repr and `%r` on the typed path (job-rbrbfuzz59-10271816)

Re-applied the accepted fuzz59 change on this tree.  The `del`-bound half was already here in a
newer form (`pyfront.refuse_unrepresentable_delete_bounds` folded the whole expression, with a
more thorough `test_ail_pre19.py`), so both were kept.  Added the remaining half:
`tuplegen.lrepr` now formats scalar elements with the built-in `%r` conversion instead of the
shadowable `repr` name, so a program-defined `repr` cannot hijack the generated list helper and a
value whose runtime type differs from the list annotation after a slice store shows its own repr;
`_build_percent_value` lowers `%r` through the same `_repr_conv` used by an f-string's `!r` and a
`.format()` field's `!r` (a width or precision is still refused by name), and `tuplegen` uses the
generated str-repr helper for a `list[str]` slot.  Added `AIL_CURRENT/test_ail_fuzz59.py` and
registered it in `ail_check.MODULES`; added the DIFFERENCES row to both ledgers.
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and `--check`
passes.

## 2026-10-27 -- pre319: calling an earlier function-valued class attribute is already refused by name (job-pre319-10271538)

The pre304 reviewer's first pre-existing item was a class body that calls a function bound
earlier in the same body (`f = lambda: 3; g = f()`, also the `def` spelling and the alias,
list-item, dict-value, attribute and argument routes).  Reproduced it on both builds: this tree
already refuses the construct at compile time with a named `not in the subset` message
(`reading the class attribute C.g through the class: its value is not a constant ...`), which
the task allows, so no compiler change was needed.  Functions bound outside the class through a
module-level list item or dict value still match CPython.  Added `AIL_CURRENT/test_ail_pre319.py`
(13 programs, both builds; each is either refused by name or matches CPython) and registered it
in `ail_check.MODULES` and `tools/ci_shards.json`.

Probes in `/tmp/probes/pre319` on both builds: `p01`-`p10`, `p12`, `p14`-`p17` and `p20` are
refused by name; `p11`, `p18`, `p19` and `p21` match CPython.  Final-state tests:
test_ail_pre319, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- re-apply pre278: field/method collision refusal (job-rbrbpre278-10271620)

Re-applied the accepted rbpre278 change on the current integration tree.  The tree already has
pre279's instance-table lookup, so the direct, argument, list-item, dict-value, attribute, alias,
inherited and `self.f()` routes match CPython on both builds; the remaining shapes are refused by
name: `self.f()` in a base method whose subclass stores the field, and a field holding a bound
method (`self.f = self.g`, another object's method, a builtin method, a
classmethod/staticmethod, or such a value through an argument, a list item, a dict value, an
attribute or an alias).  Name lookups follow Python's scopes, so a same-named local in an
unrelated function no longer causes a false refusal.  The front end calls
`refuse_field_method_call` from both typed entry points and the general emitter (the latter with
`allow_owners=True`); `AIL_CURRENT/test_ail_pre278.py` is registered in `ail_check.MODULES`.

Probes in `/tmp/probes` (both builds, via `cmp.sh`): `p_direct`, `p_routes`, `p_inherited_self`,
`p_noncallable`, `p_unrelated` and `p_shadow_scopes` match CPython.  `p_base_refusal`,
`p_bound_self`, `p_bound_routes`, `p_bound_dict_alias`, `p_bound_builtin` and `p_shadow_branch`
are refused by the pre278 wording.  Final-state tests: `test_ail_pre278` (8 tests, OK),
`test_ail_pre279` (7, OK), `test_ail_safetynet` (5, OK), `test_ail_files` (18, OK with 1
skipped) and `test_ail_corpus_findings3` (2, OK).  `tools/diff_ids.py` is not present on this
tree; `tools/update_manifest.py` was run and `--check` passes.
## 2026-10-27 -- pre324 review: annotation-only names and comprehension targets are not class-body bindings (job-pre324-10271601)

The review found that the earlier refusal was too broad because `_store_linenos` counted every
`ast.Name` store in the class body.  It now skips the target of an annotation with no value
(`x: int` records only `__annotations__`, while `x: int = 3` still binds `x`) and the generator
targets of a comprehension (their own scope, while a named expression in the comprehension still
binds here).  So `x = 100; class C: x: int; def m(self, a=x)` and
`x = 100; class C: y = [x for x in range(3)]; def m(self, a=x)` match CPython (100) again on both
builds; an annotation with a value, a real class attribute before the comprehension target, or an
attribute after it is still refused by name.  `test_ail_pre324` adds `annotation_only`,
`annotation_value`, `comp_target` and `nested_comp_target`.

Probes in `/tmp/probes/pre324` on both builds: the 10 matching new probes are `p18_ann_only`,
`p18_ann_only_alias`, `p18_ann_only_arg`, `p18_ann_only_multi`, `p18_comp_target`,
`p18_comp_target_arg`, `p18_comp_target_dict`, `p18_comp_target_gen`,
`p18_comp_target_nested` and `p18_comp_target_tuple`; `p18_ann_value`, `p18_ann_only_then_attr`,
`p18_comp_target_with_attr` and `p18_comp_target_then_attr` are refused by name as intended.  The
18 earlier pre324 probes still match (5) or are refused by name (13).  Final-code tests:
`test_ail_pre324`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`
(4 modules, 263 s, 0 failed), plus `test_ail_fuzz1.NonLiteralDefaults` and
`test_ail_fuzz1.ForwardLambdaDefaults` (16 tests, OK).  `tools/update_manifest.py` was run and
`--check` passes.

## 2026-10-27 -- pre324: class method default reading an earlier class-body name (job-pre324-10271601)

The pre304 review's first pre-existing difference (p18) still reproduced on this tree:
`x = 100; class C: x = 3; def m(self, a=x): ...` printed `100` on both builds, because a
non-literal method default is hoisted to module scope before the class body runs, where CPython
evaluates it in the class namespace and prints `3`.  A method/property bound earlier in the same
class body was wrong the same way (`a=x` became the module global instead of the function).
`_hoist_defaults` now refuses this one construct by name on both builds
(`a default in method C.m reads the class-body name x; ... CPython evaluates the default in the
class body`).  The scan only counts names bound earlier in the class body and only loads that the
def statement evaluates now: a class attribute bound later, an unrelated class name, a module
global, a module function's default, and a lambda/comprehension body (which resolves globals) are
unchanged.

Probes in `/tmp/probes/pre324` on both builds: `p18_default_class_attr`, `p18_default_expr`,
`p18_with_init`, `p18_init_before_attr`, `p18_kwonly`, `p18_method_earlier`, `p18_alias_attr`,
`p18_class_attr_route`, `p18_negative_attr`, `p18_empty_attr`, `p18_builtin_shadow`,
`p18_comp_outer_class` and `p18_lambda_default_class` are refused by name; `p18_default_later`,
`p18_no_class_attr`, `p18_lambda_global`, `p18_comp_body_global` and `p18_module_func` match
CPython.  Final-commit tests: `test_ail_pre324`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` (4 modules, 341 s, 0 failed); the related
`test_ail_fuzz1.NonLiteralDefaults.test_class_attribute_default_refused_or_same` passes.  The
full `test_ail_fuzz1` module has two unrelated environment failures (`difffuzz` is not installed).
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- re-apply pre281: empty sequence repeated by a huge count (job-rbrbpre281-10271623)

Re-applying the accepted pre281 change on the current integration tree.  The current tree already
has pre271's empty-list skip in `ail_op_imul` (with the bare `MemoryError` guard for an oversized
repeat), and `ail_op_mul` already skipped an empty list/tuple with the same guard; those sites keep
both fixes unchanged.  The remaining pre281 sites are applied: the v1 `ail__repeat_str` /
`ail__repeat_vec` helpers and the v2 `ail_str_repeat` now skip the repeat loop when the sequence has
no elements, so `[] * 10**18`, `() * 10**18`, `"" * 10**18` and `b"" * 10**18` return at once
instead of looping over the huge count.  Negative, zero, bool, non-empty and aliased sequences are
unchanged, and a huge count reaching the statement through an argument, a list item, an attribute
or a dict value matches CPython on both builds.
`AIL_CURRENT/test_ail_pre281.py` (4 tests, both builds) is added and registered in
`ail_check.MODULES` and `ci_shards.json`.  `AIL_CURRENT/MANIFEST.json` was refreshed (the new
module is pinned after `git add`); `tools/update_manifest.py --check` passes.  `tools/diff_ids.py`
is not present on this tree.
Probes in `/tmp/probes/pre281_*.py` on both builds: `p1_empty_literals`, `p2_nonempty`,
`p3_routes` (argument, list item, attribute and dict value), `p4_alias`, `p5_nested`,
`p6_boundaries` (0, -1, -10**18, 1, 2, bool, 10**18 and 2**62) and `p7_bytearray` match CPython;
`p8_bytearray_alias` still shows the pre-existing bytearray `*=` aliasing difference recorded as
`C?-job-rbrbpre281-10271623-2`.
Targeted tests before the final commit: `test_ail_pre281`, `test_ail_pre271`,
`test_ail_string_repeat_fusion` and `test_ail_local_count_repeat` (15 tests, 80.5 s, 0 failed).
## 2026-10-27 -- default build: a computed negative integer exponent matches CPython (job-pre321-10271546)

The pre305 review recorded two pre-existing differences.  The first was that `**` with a negative
exponent stopped on the default build (`negative exponent on an integer; write float(x) ** n for
Python's float answer`) while the general path printed CPython's float.  The legacy `**` type used
`ail_ipow`, exact for int64, even when the exponent's sign was unknown at compile time; the typed
path now leaves such a power to the general path, whose tagged value keeps the int result for a
non-negative exponent and returns the float for a negative one.  Constant exponents keep their old
int/float lowering, and the whole-program fallback is the existing mechanism (no output or message
changes in programs without a computed integer power).  A function that declares `-> int` keeps the
exact-integer path instead: its result is already committed to int64 at the ABI boundary, so a
computed power there cannot become CPython's float, and `ail_ipow`'s existing run-time refusal for
a negative exponent stands (this is the shape used by the `__pow__` method in `test_ail_dunders`,
which is built on the typed path alone).  The review's second item, out-of-int64 integer powers,
was not changed and remains a difference.

Probes in `/tmp/probes/pre321` on both builds: `p01_var_var`, `p02_local`, `p03_routes`,
`p04_pow_compare`, `p05_const_exp`, `p06_zero`, `p07_float_base`, `p08_exp_routes`,
`p09_nonint_exp`, `p10_positive`, `p11_positive_routes`, `p12_zero_and_underflow`, `p13_alias`,
`p14_bool_exp_var` and `p15_nested` all match CPython.  Final-state tests: `test_ail_pre321`,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` (4 modules, 0 failed);
`tools/update_manifest.py --check` passes; `ci_shards.py --check` reports only the two
pre-existing duplicates `test_ail_pre61` and `test_ail_pre126` (both present on HEAD).

## 2026-10-27 -- pre311: int() of an out-of-int64 float from an aliased module container (job-pre311-10271335)

The rbpre293 task text named no concrete pre-existing item (its list was empty), so I reproduced the
first still-differing item recorded as open by the pre290 review, `r26` alias-list: `a = [1e300];
b = a; outer(b[0])` compiled and then stopped with `integer overflow`, while CPython prints the
bignum.  `_check_int64_literals` now also folds a module name bound once to a flat literal
list/tuple/dict, or aliased from one (alias chains included), when every use of every name in the
alias group is a subscript read or a module-level alias.  A mutation through the name or an alias,
a call that could mutate the object, a bare read, a nested mutable element, a local shadow or a
non-float element stops the record, so an in-range or mutated container keeps its previous
behaviour.  The same pass also covers `r33` dict-via-variable and the tuple spelling; `r27`
attribute-held value and `r28` tuple multi-assign stay open (pre-existing).

Probes in `/tmp/probes` on both builds: `r26_alias_list`, `r33_dict_var`, `r26_flat_list_item`,
`r26_flat_dict_direct`, `r26_flat_tuple_alias`, `r26_flat_alias_arg`, `r26_neg` are refused by
name; `r26_inrange`, `r26_mutate_before`, `r26_alias_mutate_before`, `r26_mutate_func`,
`r26_used_bare_inrange`, `r26_alias_append_inrange`, `r26_local_shadow` match CPython.  `r27_attr_value`,
`r28_tuple_multi` and `r26_nested` still differ (pre-existing, unchanged).  Added
`AIL_CURRENT/test_ail_pre311.py` (9 refused, 13 CPython-parity programs, both builds) and
registered it in `ail_check.MODULES` and `tools/ci_shards.json`.  Final-state tests:
`test_ail_pre311`, `test_ail_pre290`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (5 modules, 229 s, 0 failed).  `tools/update_manifest.py` run and
`--check` exits 0; DIFFERENCES row `C?-job-pre311-10271335-1`.
## 2026-10-27 -- re-apply pre299: builtin pow() outside int64 is refused by name (job-rbpre299-10270953)

Re-applied the accepted pre299 change on top of this integration tree, keeping the newer
front-end work (pre273's `**` rule, pre285 local cancellation, pre290 int() wrappers) unchanged.
Extended the existing `_check_int64_pow_constants`, called after `_check_int64_int_base_constants`: a
two-argument builtin `pow()` with statically known int arguments (module and function-local
constants, expressions and aliases included) is folded exactly, and a result outside int64 is
refused with `int64 constant expression out of range`; when the base is a constant int with
|base| >= 2 and the exponent is not statically known, the construct is refused at compile time,
following pre273's rule for `**`. Bases 0/1/-1 with computed exponents, constant in-range powers,
float and bool powers, `pow(base, exp, mod)`, and a program that binds its own `pow` are
unchanged.

Probes in `/tmp/probes` and `/tmp/rprobes` on both builds: the safe/aliased/shadowed/zero-base
forms match CPython; constant out-of-int64 forms are refused as `int64 constant expression out
of range`; computed-exponent forms are refused by name, including calls in a class body and a
lambda body. Final-state tests: `test_ail_pre299`, `test_ail_pre294`, `test_ail_pre273`,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` (0 failed).
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and
`--check` passes. `tools/ci_shards.py --check` reports only the pre-existing duplicated
`test_ail_fuzz4`, `test_ail_pre126` and `test_ail_pre61`; this change adds only
`test_ail_pre299` to one shard.

## 2026-10-27 - nested generator expressions (job-rbrbpre42-10271045)

Re-applied the accepted pre42 change on top of this tree.  The general path still materialises a
generator expression like a list comprehension, so a generator expression nested inside another
one was evaluated when the outer object was built (CPython creates it only when its element is
reached); the side-effect order differed and consuming the outer could end in
`AIL internal error: ail_it_next: unknown library iterator kind`.  Both general emitters now
refuse the nested construct by name, and the `next()` / `any()` / `all()` fused paths check the
outer argument too.  The pre41 any()/all() screen keeps its own wording for a generator expression
used as the iterable (`iterable is itself a generator expression`): the generic pre-scan leaves an
any()/all() argument to that fused path, which checks the iterable first and the other nested shapes
second.  This tree's pre116/pre166 saved-generator screen (`a generator expression
used as a value`) would otherwise claim a nested one first, so the nested check runs before it;
that screen is kept unchanged for non-nested saved generators.  A generator expression with no
generator expression inside it, including one holding a list/set/dict comprehension, still builds
and matches CPython.  Added `AIL_CURRENT/test_ail_pre42.py` and registered it in `ail_check.MODULES`;
its `any_element` case covers the generic any()/all() shape that is not an iterable nesting.
## 2026-10-27 -- fuzz28 follows pre304's class-body namespace (job-rbpre304-10272032)

The integration branch's `test_ail_fuzz28.py` still expected the general path to refuse
`print(C.ys, C.zs, C.ws)` for a class-body comprehension by name.  That refusal was the old
behaviour the accepted pre304 change replaced: a class body now has its own namespace, so an
earlier class attribute is visible to a comprehension's outermost iterable and the read evaluates
on both builds.  I reproduced the failure (`[0, 1, 2] {0: 0, 1: 1, 2: 2} {0, 1, 2}` from the
general path), verified the same program matches CPython on both builds, and changed fuzz28 to
assert that parity instead of the obsolete refusal.  The still-refused cases (a comprehension
body reading the class name, and a method/property rebinding an earlier attribute) remain in
`test_ail_pre304.py`; no compiler code was changed.  Updated the old fuzz28 DIFFERENCES row to
point at pre304 and added `C?-job-rbpre304-10272032-1`.

Probes in `/tmp/probes/pre304fix` on both builds: `p1_types` (positive/negative/bool/zero,
list/set/dict), `p2_empty`, `p3_routes` (argument, list item, attribute, dict value, alias and
module name), `p4_containers` (class read and instance through argument/list/attribute/dict),
`p5_duplicate`, `p6_inherit`, `p7_shadow` and `p8_body_global` match CPython; `p9_body_refuse`
and `p10_method_refuse` are refused by name (`name 'x' is not defined`) on both builds.
`test_ail_fuzz28` and `test_ail_pre304` (7 tests) pass on this change.  A separate exploratory
probe, a class-body comprehension target with the same name as a module global, showed a
pre-existing compscope limitation (the target overwrites the module global); it does not involve
the earlier-name map and was not changed here.

## 2026-10-27 -- re-apply pre304: class-body names visible to later attributes (job-rbpre304-10271604)

Re-applied the accepted pre304 change on top of this tree; its class-body name map and the
method/property rebinding refusal are now merged with the tree's newer class-attribute refusal
path (`_class_attr_through_class_refusal`).  The two accepted DEVLOG entries and the new rows are
kept.  Verified with `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` on the final commit; `tools/update_manifest.py --check` passes.

## 2026-10-26 -- pre302 review: parenthesize a folded negative float literal (job-pre302-10270745)

The review found that the replacement produced by `_fold_float_int_text` was an
unparenthesized literal, so a folded negative value lost the call's primary-expression
binding: `float(-(10**40)) ** 2` printed `-1e+80` on both builds where CPython prints
`1e+80`, and `float(-(2**70)) ** 2`, `float(-(10**40)) ** 0`, `float(-(10**40)) ** -1`
were wrong the same way.  A negative replacement is now wrapped in parentheses, which
restores the binding for `**`, a following unary operator and every other context; positive
replacements are unchanged.  `test_ail_pre302.py` now covers the negative constant raised to
integer exponents on both builds, and a negative constant raised to a fractional power is
asserted to be refused by name (AIL has no complex type) instead of silently compiling to a
wrong real value.

Probes in `/tmp/probes` on both builds: `p_pow_neg`, `p_pow_mix`, `p_pow_pos`, `p_pow_frac`,
`p_edge`, `p_forms` and `p_shadow` match CPython or are refused by name (the fractional negative
powers are refused as complex); `p_refuse_arg` keeps the named int64 refusal.  Final-state
tests: `test_ail_pre302` (16 s, 0 failed), plus `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` (0 failed).  `tools/update_manifest.py` was run and `--check`
passes.

## 2026-10-26 -- float() of an out-of-int64 int constant folds to a float literal (job-pre302-10270745)

The rbrbpre33 reviewer's first pre-existing difference was `float(10 ** 40)`: both builds
refused it (`int64 constant out of range: ...`), while CPython converts the unbounded int to
the nearest double and prints `1e+40`.  `ail_chatgpt._fold_float_int_text` now rewrites a
direct, unshadowed `float(<exact int constant outside int64>)` to the corresponding float
literal when CPython's conversion is finite, before the int64 checks and before the text is
handed to the backends.  In-range constants, a rebound `float`, `float(10**400)` (CPython
raises OverflowError), and values that reach `float()` through an argument, a list item, an
attribute, a dict value, a local or a module constant keep their named compile-time refusal.
The reviewer's second item, an out-of-range intermediate that reduces to an in-range value,
already matches CPython, including `(1 << 1048576) >> 1048576` and `(1 << 2000000) >> 2000000`.
Added `AIL_CURRENT/test_ail_pre302.py` and registered it in `ail_check.MODULES` and
`tools/ci_shards.json`.

Probes in `/tmp/probes/pre302` on both builds: `item1_fit`, `item1_float2`,
`item2_intermediate`, `wide` and `wide2` match CPython; `item1_over`, `r_arg`, `r_list`,
`r_attr`, `r_dict`, `r_local` and `r_module` are refused by name.  Final-state tests:
`test_ail_pre302` (12 s, 0 failed), plus `test_ail_safetynet` (124 s), `test_ail_files`
(131 s) and `test_ail_corpus_findings3` (210 s), all 0 failed.  `tools/update_manifest.py`
was run and `--check` passes.
## 2026-10-27 -- huge exponent with a safe integer base no longer loops (job-pre305-10271259)

The first pre-existing difference in the rbpre299 review was `pow(-1, 10**12)`: the general
path's integer power multiplied once per exponent, so the program hung where CPython prints 1;
the same loop ran for the bases 0 and 1 and for odd exponents. `ail_obj_pow` and `ail_op_pow`
now use exponentiation by squaring, matching `ail_ipow`, so at most 63 steps are taken. The
parity sign of -1, the safe bases 0/1, bool and negative exponents, and in-range int64 boundaries
match CPython on both builds; an out-of-int64 result keeps the existing run-time integer-overflow
stop. No compile-time refusal was added.

Probes in `/tmp/probes` on both builds: `pre305_pow_neg1_huge`, `pre305_pow_safe_bases`,
`pre305_pow_operator`, `pre305_pow_routes` (argument, list item, attribute, dict value and alias)
and `pre305_pow_boundaries` match CPython; `pre305_from_builtins_pow` also matches CPython (the
review's second recorded item is not a difference on this tree). Final-state tests:
`test_ail_pre305`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`.
`tools/update_manifest.py --check` passes.

## 2026-10-27 -- pre310: rbrbpre47's first pre-existing difference `2 ** 63` is already refused (job-pre310-10271327)

The rbrbpre47 review recorded CPython's exact unbounded results where both trees refuse by name:
`2**63`, `1<<63`, `10**40`, `2**10000`, `2**100000000`, `-(-2)**63`, `f"{2**63}"`,
`2**63 + 0.5`, `"a".split(",", 2**63)` and `-2**63 - 1`. Reproduced the first, `2**63`, on both
builds: it is already refused at compile time by the tree's generic constant checks (`int64
constant out of range: 9223372036854775808`), which is the task's allowed named refusal. Every
other recorded item, and the assignment/argument/list/dict/attribute/alias/module-constant/return
routes for `2**63`, also refuse by name; the in-range boundaries (`2**63 - 1`, `-(2**63)`,
`1<<62`, `2**63 - 2**63`, `(2**70)//(2**10)`, `(2**63)>>1`, an f-string and the special
`0**200`/`1**200`/`(-1)**201` bases) match CPython on both builds. No compiler code changed;
added `AIL_CURRENT/test_ail_pre310.py` and registered it in `ail_check.MODULES` and
`ci_shards.json`. Probes: `/tmp/probes/pre310/p01`-`p10` are refused by name on both builds;
`/tmp/probes/pre310b/v01`-`v16` are refused by name and `v17`-`v20` match CPython on both builds.
`tools/update_manifest.py` was run and `--check` passes. Tests on the final commit:
`test_ail_pre310`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
(4 modules, 0 failed).
## 2026-10-26 -- pre272 follow-up: refresh full-C output pins (job-pre272-10262304)

The accepted base-runtime mapping for `list assignment index out of range` changes the emitted C
for every program that pulls the exception runtime, so the full-C SHA-256 pins in
`test_ail_numeric_bindings` and `test_ail_record_initializers` were stale, so they were
regenerated on this tree.  Both modules and `test_ail_pre272` pass;
`tools/update_manifest.py --check` passes.

## 2026-10-26 -- pre272: `del` out-of-range says CPython's list assignment text (job-pre272-10262304)

The rbpre19 pre-existing constant `del` bounds (`2**63-1`, `2**100000`, `2**100:2**101`, and the
argument/list-item/attribute/dict routes) are already refused by name on both builds, so they no
longer differ.  The first remaining pre-existing CPython difference in that family was the
uncaught message for deleting an out-of-range list item: the general path said
`list index out of range` and the typed int-list path said `pop from empty list` /
`pop index out of range`, where CPython says `list assignment index out of range`.  General
`ail_list_delitem` (both runtimes) now uses the assignment text, and the typed local int list,
string field, and int/float numeric field delete paths check with the same text before removing
the item.  `list.pop()` keeps its own messages, and in-range deletes are unchanged.
Added `test_ail_pre272.py` (3 tests, both builds) and registered it in `ail_check.MODULES`.

Probes `/tmp/probes/p272_*.py` (8 programs) cover empty, positive/negative out of range,
`INT64_MIN`, bool, int/str/float/nested lists, an argument, a list item, an attribute and a dict
value, plus caught `str(e)`/`e.args`, caught without reading the text, `pop()` messages and
in-range deletes; every probe matches CPython on both builds.  Final-state tests:
test_ail_pre272, test_ail_numeric_bindings, test_ail_record_initializers, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 pass; `tools/update_manifest.py --check` passes.
## 2026-10-26 -- re-apply pre280: in-range wide-intermediate constant index (job-rbpre280-10270754)

Re-applying the accepted pre280 change.  The current tree already folds an in-range constant
index through an out-of-int64 intermediate with `_const_fold_int` (pre269), so the pre280 cases
(`xs[2 ** 63 - 2 ** 63]`, `xs[(1 << 63) - (1 << 63)]`, `xs[(10 ** 20) // (10 ** 19) - 10]`,
`xs[(2 ** 63) % 7]`, `xs[~(2 ** 63) + 2 ** 63]`, `xs[-(2 ** 63) + 2 ** 63]`) already match
CPython on both builds.  `_check_index_expression` now also tries pre280's 4096-bit guarded
`_constant_int_exact` fold after `_const_fold_int`, keeping pre269's wider fold and adding the
pre280 exact fallback; an inconclusive fold or a result still outside int64 keeps the by-name
`int64 index out of range` refusal.  `test_ail_pre280.py` is added and registered in
`ail_check.MODULES` and `tools/ci_shards.json`; `test_ail_pre177.py` gains its
`WIDE_INTERMEDIATE` program (list, tuple and str receivers, a negative result) and keeps the
current boundary case.  Probes in `/tmp/probes`: a_pow_sub, b_shift_sub, c_div_inrange,
d_neg_result, e_containers, f_dict_key, j_empty, k_arg, l_attr, m_dict_value, n_list_item,
o_alias, q_sign_boundary, s_mod, t_mixed, u_unary and x_slice match CPython on both builds;
g_out_pow, h_out_mul, i_out_div, p_toobig, r_big_out and v_wide_result are refused by name
identically on both builds.  Final-state tests: test_ail_pre280, test_ail_pre177, test_ail_pre269,
test_ail_pre246, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3 (7 modules,
36 tests, 0 failed).  `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py`
was run and `--check` passes.

## 2026-10-27 -- re-apply pre289: collision call through a function-return receiver (job-rbpre289-10270940)

Re-applying the accepted pre289 change on the current integration tree.  Its target difference
(`make(4).f()` printed the method's -1 where CPython calls the instance field and prints 40) is
already fixed here by pre279: the instance table is consulted before both the static and the
dynamic method dispatch, so every pre289 route matches CPython on both builds.  The accepted
named refusal is therefore not added (it would turn programs that pre279 now compiles correctly
into refusals); keeping the pre279 fix is the conflict resolution.  Added
`AIL_CURRENT/test_ail_pre289.py` (7 tests, both builds) with the direct, V1, annotation, chain,
assigned, argument, list, dict, attribute, alias, subclass and conditional routes, boundaries
(0, negative, +/-2**62), arguments and value types, a missing field, a non-callable field, two
unrelated returns, a mixed C/A return and a non-class return, and registered it in
`ail_check.MODULES`.  Probes in `/tmp/probes/p289` (`direct`, `v1`, `annotated`, `chain`,
`assigned`, `argument`, `list`, `dict`, `attribute`, `alias`, `subclass`, `conditional`,
`boundaries`, `arguments`, `field_absent`, `noncallable_return`, `mixed`, `method_args_types`,
`unrelated`, `unrelated_conditional`, `non_class`) all match CPython on both builds; `deleted`
is refused by name for the unrelated pre-existing `del` on an attribute.  `tools/diff_ids.py`
is not present on this tree; `tools/update_manifest.py` was run and `--check` passes.  Final-state
tests: test_ail_pre289, test_ail_pre279, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.
## 2026-10-27 -- re-apply pre293: instance fields shadow methods (job-rbpre293-10270942)

Re-applying the accepted pre293 change on the current tree.  Its base (`cc5133a`) had no
instance-table lookup for a method/field collision, so it refused `obj.f(...)` by name.  The
current tree already carries the later pre279 fix, which models that lookup on both builds and
matches CPython for the callable, non-callable, lambda, unpacked, inherited and routed fields;
keeping both sides' fixes therefore means keeping the model, not the refusal.  The one accepted
form still wrong here was `setattr(self, 'f', ...)`: `compile` collected only `Attribute` stores
into `assigned_attrs`, so the call dispatched to the method (`101` where CPython calls the field
and prints `11`).  `pyboxed2.Compiler.compile` now also records the literal name of a
`setattr(obj, 'name', ...)` call in the same set, using the existing field-call path; no refusal
was added and `test_ail_pre279` behaviour is unchanged.  Added `test_ail_pre293.py` (10 tests,
both builds, CPython parity for all the accepted programs plus setattr routes, negative values
and aliases) and registered it in `ail_check.MODULES`; DIFFERENCES row
`C?-job-rbpre293-10270942-1`.  `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes.

Probes in `/tmp/probes/pre293`, all matching CPython on both builds with `tools/cmp.sh`:
`p1_callable_instance`, `p2_noncallable_instance`, `p3_bytes_field`, `p4_int_field`,
`p5_lambda_field`, `p6_setattr`, `p7_unpack`, `p8_inherited`, `p9_routes`,
`p10_super_unbound`, `p11_ordinary`, `p12_unrelated_classes`, `p13_unrelated_builtin`,
`p14_nested_scope`, `p15_typed_callable`, `p16_setattr_routes`, `p17_setattr_unpack` and
`p18_negative_alias`.
## 2026-10-26 - constant pow() outside int64 is refused by name (job-pre294-10270438)

The reviewer of job pre273 recorded the first still-differing pre-existing item: `pow(2, 63)`
compiled on both builds and then stopped with `integer overflow`, while CPython prints the
bignum `9223372036854775808`; `pow(10, 100)` behaved the same way.  The two-argument builtin is
now folded at compile time.  An exact result outside int64 is refused by name with `int64
constant expression out of range`; an in-range result keeps the ordinary lowering, a negative
exponent keeps CPython's float answer, and the three-argument modular form is untouched.  The
check follows module and function-local constants and a module/function alias of `pow`, and skips
a program that binds its own `pow`.  It does not touch `**`, so the prelude `Fraction` sources
are unaffected.

Probes in `/tmp/probes` (both g/d builds): refused by name - `pre294_direct`, `pre294_ten`,
`pre294_negative_base`, `pre294_argument`, `pre294_list_item`, `pre294_attribute`,
`pre294_dict_value`, `pre294_alias`, `pre294_alias_local`, `pre294_alias_chain`,
`pre294_module_constants`, `pre294_local_constants`, `pre294_expressions`; matched CPython -
`pre294_boundary`, `pre294_types`, `pre294_negative_exp`, `pre294_mod`, `pre294_shadow`.

Tests on the final tree: `test_ail_pre294`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (4 modules, 0 failed; 10 s, 119 s, 125 s, 195 s).
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and
`--check` passes.
## 2026-10-27 -- reconcile pre19 `del` bound refusal with pre269 (review of job-rbrbpre19-10270955)

The re-applied pre19 helper refused as soon as any intermediate of a constant `del` bound left
int64, so it also refused valid in-range results such as `del a[2**63 * 0]`,
`del a[(1 << 63) >> 62]`, `del a[(10**20) // (10**19)]`,
`del a[(1 << 63) - (1 << 63) + 3]`, `del a[-(1 << 63) >> 62]`, and the representable boundaries
`del a[2**63 - 1]` / `del a[-2**63]`, contradicting this tree's pre269 fix.  The helper now folds
the whole bound with Python's unbounded ints -- including `>>`, `//`, `%`, bitwise ops and bool
leaves -- and range-checks only the exact final value; a final value outside int64, or a constant
too large to fold, keeps the named refusal.  `test_ail_pre19` now expects the pre269 cases and the
two boundary values to build and match CPython (the boundaries raise IndexError at run time) and
refuses only constants whose final value leaves int64.

Probes in `/tmp/probes`: `pre19_wide_intermediates`, `pre19_wide_ops`, `pre19_wide_routes`,
`pre19_empty_wide`, `pre19_boundary_max`, `pre19_boundary_min`, `pre19_refuse_wide_slice`,
`pre19_refuse_below_min`, plus the earlier `pre19_*` probes, all matching CPython or refused by
name on both builds.  Final-state modules: test_ail_pre19, test_ail_pre269,
test_ail_string_field_mutation, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.

## 2026-10-27 -- re-apply pre19: refuse `del` bounds a constant cannot evaluate in int64 (job-rbpre19-10261657)

Re-applied the accepted pre19 change on the current tree.  `pyfront.refuse_unrepresentable_delete_bounds`
evaluates a constant `del` index or slice bound exactly, keeping the intermediate-overflow flag (so
`del a[2**63 - 1]`, `del a[-2**63]`, `2**100000` and `2**100:2**101` are all caught), and refuses the
`del` by name on both the typed path (`pyfunc._stmt_inner`) and the general path
(`pyboxed2.Compiler.stmt_Delete`).  This tree's earlier checks already refuse compound constant
indexes and powers by name (`int64 index out of range` / `int64 constant out of range`), so the
accepted test accepts either named refusal; the new wording is exercised by the unary-int64 and
slice cases that reach the added helper.  In-range constants (`del a[1 + 1]`, `del a[-2:-1]`,
bool indexes) and the same expression outside a `del` are unchanged.

The helper treats the literal spelling `-9223372036854775808` (unary minus on the Constant
`2**63`) as INT64_MIN without an overflow, matching the compiler's unary branch, so
`del box.values[::-9223372036854775808]` in `test_ail_string_field_mutation` still builds.  A
computed `del a[-2**63]` (unary minus on a power) is still refused.

Added `AIL_CURRENT/test_ail_pre19.py` (3 tests, both builds), registered it in
`ail_check.MODULES` and `ci_shards.json`.  Probes `pre19_*` in `/tmp/probes` cover index, INT64_MIN,
huge power, huge slice/step, nested subscript, attribute, list item and dict value routes, a
function argument, representable bounds, bool indexes and the non-`del` expression: every one
matches CPython or is refused by name on both builds.  Final-state modules: test_ail_pre19,
test_ail_string_field_mutation, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
`tools/diff_ids.py` is not present on this tree; `update_manifest.py --check` rc 0.

## 2026-10-27 - re-apply pre245: generator expression as a hash key refused by name (job-rbrbpre245-10270958)

Re-applied the accepted pre245 change on the current tree.  A generator expression is
materialised eagerly as a list (pre166), so using it as a set element or dict key exited 1 with
`TypeError: unhashable type: 'list'` where CPython hashes the generator by identity and shows its
address-bearing repr.  The construct is now refused by name on both builds, statically by
`_check_genexpr_hash_keys` and dynamically by the v2 `ail_obj_hash` (with the matching
`dunderrt.py` text edit).  The static refusal covers set/dict literals and comprehensions,
`hash()`, and `set()`/`frozenset()` over a collection, including a key reached through a tuple,
an `if` expression or a `tuple()`/`frozenset()` call; names the program binds are not treated as
the builtin.  Consumed generator expressions and ones kept as a dict value are unchanged.
Added `test_ail_pre245.py` and registered it in `ail_check` and the CI shards.  The conflicts
with this tree's newer `_check_class_attribute_assignment` call, DIFFERENCES rows, DEVLOG entries
and CI timings were resolved by keeping both sides.

Probes `/tmp/probes/p245_*` cover every static refusal form (set/dict literal and comprehension,
tuple/if-expression/tuple()/frozenset() keys, `hash()`, `set()`, empty and nested keys), each
dynamic route (saved, alias, argument, list item, attribute, dict value, `.add`, membership,
subscript, `hash(name)`, tuple key, `dict.get`), bound-name shadowing, a plain list key and the
matching consumed/value cases; every probe matches CPython or is refused by name on both builds.
Tests on the final tree: test_ail_pre245, test_ail_pre166, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (5 modules, 323 s, 0 failed).  `tools/diff_ids.py` does not exist on this
tree; `tools/update_manifest.py` was run and `--check` passes.

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
## 2026-10-27 -- re-apply pre31: int() of a float outside int64 (job-rbrbpre31-10271028)

Re-applied the accepted pre31 change on the current tree. This tree already carries the later,
reviewed scope-aware and value-exact refusal inside `_check_int64_literals` (literal, unshadowed
module constant, arithmetic/conditional value, list/tuple/dict item, identity function, and
positional or keyword wrapper argument, with shadowed names left alone); both sides' fixes are
kept. Added the accepted `test_ail_pre31.py`, registered it in `ail_check.MODULES`, and recorded
the difference row. Final-state tests: `test_ail_pre31`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (4 modules, 237 s, 0 failed); probes in `/tmp/probes` cover in-range
literals, shadowing, arithmetic/conditional values, argument, list, tuple, dict and attribute
routes, plus refusals for literal, negative, routed and boundary values on both builds.
## 2026-10-27 - rbpre1 re-apply: positional-only parameters (job-rbpre1-10270815)

Re-applied the accepted rbpre1 change on this tree.  `def f(a, /, ...)` no longer refuses by
name: the general path registers positional-only parameters in order (with their defaults,
`*args`, keyword-only parameters and annotations), and both emitters refuse a call that passes
one as a keyword.  Methods, static methods, nested defs, aliasing and values reaching a call
through an argument, a list item, an attribute and a dict value match CPython on both builds.
The new `AIL_CURRENT/test_ail_pre1.py` is registered in `ail_check.MODULES`, and
`test_ail_pre141.py` now compares its nested positional-only case with CPython (its `**kwargs`
refusal wording was updated, keeping that fix).  `tools/diff_ids.py` is not present on this
tree; `tools/update_manifest.py` was run and `--check` passes.  Probes
`/tmp/probes/pre1_defaults.py`, `pre1_sources.py`, `pre1_methods_nested.py` match CPython on
both builds, and `pre1_refuse.py` is refused by name on both.
## 2026-10-27 -- re-apply pre48: exception argument `repr` and file OSError `args` (job-rbrbpre48-10271116)

Re-applied the accepted pre48 change on the current integration tree. This tree already carried the
direct `repr(e.args[i])` half (as `_ail_exc_arg_repr`), so that side is kept unchanged rather than
duplicated; the missing alias refusal was added to `exctext.py`, and the general-path file OSError
adapter in `filert.py` now builds two-element `args == (errno, strerror)` with the filename kept as
an attribute instead of appended to `args`. Storing an `e.args[i]` value in a name, list, tuple,
dict, attribute or user-function argument is refused by name on the typed path, so the default
build takes the general path, which keeps the argument object; a direct `repr(e.args[i])` keeps the
argument's own kind (str/int/float/bool/None, negative and out-of-range indices, empty args as
IndexError). Added and registered `test_ail_pre48.py`. `tools/diff_ids.py` is not present on this
tree; `tools/update_manifest.py` (then `--check`) passes.

Probes in `/tmp/probes` (all eight run with `cmp.sh`): `p48_direct`, `p48_floats`, `p48_routes`,
`p48_alias`, `p48_alias_arg`, `p48_empty` and `p48_file` match CPython on both the forced general
and default builds; `p48_oserror` matches CPython on the default build and is refused by name on
the forced build (`not in the subset: raising OSError with more than one argument`). Final-state
modules: test_ail_pre48, test_ail_exception_context, test_ail_exception_values_core,
test_ail_exception_values_app, test_ail_exception_aggregate_objects, test_ail_exc_str,
test_ail_excfix, test_ail_raise_from, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (11 modules, 82 tests, 925 s, 0 failed, 1 skipped).
## 2026-10-27 -- re-apply pre52: an optional import is refused by name at its own line (job-rbpre52-10261857)

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

## 2026-10-27 -- re-apply pre61: functools.partial with bound values (job-rbpre61-10271129)

Re-applied the accepted pre61 change on this tree.  The accepted fix made `genlib._partial` copy the
`partial()` call's source location onto every synthetic lambda, because the lambda scan in
`pyboxed2.py` reads `Lambda.lineno`; this tree already carries that fix plus
`ast.fix_missing_locations`, so no compiler change was needed and the current version is kept.
Added the accepted `AIL_CURRENT/test_ail_pre61.py` and registered it in `ail_check.MODULES` and
both `tools/ci_shards.json` lists.  `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes.  Probes in `/tmp/probes`
(`pre61_lambda`, `pre61_def_map`, `pre61_routes`, `pre61_types`, `pre61_empty_neg_alias`) match
CPython on both builds; `pre61_refuse_notdef`, `_toomany`, `_kworder`, `_star`, `_nofunc`,
`_aliasfunc` and `_lambdadefault` are refused by name on both.  Final-state tests:
`test_ail_pre61`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
(4 modules, 368 s, 0 failed).
## 2026-10-27 -- re-apply pre47: constant integer expressions (job-rbrbpre47-10271110)

Re-applied the accepted pre47 change on this tree. The generic exact folder
(`pyfunc._const_int_expr` / `fold_int_constant`) was already present, so the conflict resolution
keeps its zero/base shortcuts, bool-result handling and 2**22-bit budget. `pyfront.fold_int_constants`
now runs before both builds (from `pyc.to_c` and `_build_unshadowed`): an in-range constant
expression becomes one int64 literal (`-2**63`, `2**63 - 1`) and an out-of-range one is refused by
name with the pre47 wording (`a constant integer expression overflows int64: ... outside the signed
64-bit range ... 64-bit signed integer`), without the older `int64 constant expression out of
range` phrase that `test_ail_pre191` rejects. The pass skips `str.split`/`rsplit` maxsplit arguments
and f-strings, and separates a rewritten digit from an adjacent keyword. `pyfront._c_expr` refuses
an out-of-int64 literal and emits a folded INT64_MIN as `(-9223372036854775807LL - 1)` instead of
`ck_neg(9223372036854775808)`; `pyboxed` and `pyboxed2` accept the same unary spelling. Added
`AIL_CURRENT/test_ail_pre47.py` and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.
`tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py` was run and `--check`
passes.

Probes in `/tmp/probes` (both builds via `~/tools/cmp.sh`): `pre47_inrange`, `pre47_typed_routes`,
`pre47_fstring`, `pre47_keyword` and `pre47_maxsplit` match CPython (INT64_MIN/MAX, negative, zero
and bool widths, argument, list item, attribute and dict value routes, f-string debug, keyword
adjacency and maxsplit); `pre47_ref_pow`, `_negated`, `_decimal`, `_shift`, `_cancel`, `_huge`,
`_argument`, `_list`, `_attribute`, `_dict` and `_alias` are refused by name. `pre47_unary_cancel`
(`-(-2)**63 - 1`, which CPython evaluates in range) is refused by name by the tree's existing unary
check. The pipeline INT64_MIN spellings are covered by
`test_ail_pre47.test_int64_min_in_pipeline_element`. Final-state tests: 15 modules (pre47, pre191,
pre204, pre203, pre236, pre251, pre121, pre172, pre177, pre201, pre269, pre285, safetynet, files,
corpus_findings3), 67 tests, 0 failed (1 skipped).
## 2026-10-27 -- re-apply pre7: out-of-int64 delete index is refused by name (job-rbrbrbpre7-10271151)

Re-applying the accepted pre7 change on the current integration tree. The behaviour is already
present: `ail_chatgpt.py`'s `_check_index_expression` refuses a constant subscript index outside
int64 before either emitter, so `del a[2**63]`, `del a[2**64]`, `del a[-2**63 - 1]` and a nested
receiver (`del a[0][2**63]`) fail at compile time with `int64 index out of range: ...` on both
builds instead of trapping `integer overflow` while computing the index, where CPython's
unbounded int raises `IndexError`. No compiler code change was needed, keeping both sides'
fixes. Added the accepted `AIL_CURRENT/test_ail_pre7.py` (it accepts this tree's wording),
registered it in `ail_check.MODULES` and `ci_shards.json`, and recorded the row. In-range
constant indexes (`1 + 1`, `-1`, `True`, slices, str and dict keys, and the INT64_MIN/INT64_MAX
dict-key boundaries) still delete normally and match CPython. `tools/diff_ids.py` is not
present on this tree; `tools/update_manifest.py` was run and `--check` passes.

Probes in `/tmp/probes`: `pre7_inrange`, `pre7_routes`, `pre7_dict_bounds`, `pre7_slice`,
`pre7_str_key` and `pre7_empty` match CPython on both builds; `pre7_list_pow`, `pre7_shift`,
`pre7_negative`, `pre7_prod`, `pre7_nested`, `pre7_dict_key` and `pre7_pow64` are refused by
name on both builds (`int64 index out of range`). Tests on the final commit: `test_ail_pre7`,
`test_ail_pre246`, `test_ail_pre269`, `test_ail_pre177`, `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`.

## 2026-10-27 -- re-apply pre39: keyword-wrapper int() refusal (job-rbrbrbrbpre39-10271218)

Re-applied the accepted pre39 change on this tree. The current tree already carries a superset of
the accepted `ail_chatgpt._check_int64_literals` pass from the later pre290 wrapper-chain work
(module constants, literal containers, identity/keyword/keyword-only wrappers, `_UNKNOWN` for
unresolved names, and propagation through wrapper chains), so no compiler edit was needed and
both sides' fixes are kept. Added the accepted `test_ail_pre39.py` (13 refused, 12
CPython-parity programs, both builds) and registered it in `ail_check.MODULES`. Probes in
`/tmp/probes`: 8 matching (`p39_match_{values,boundary,nonfinite,shadow,unknown,attribute,alias,empty}`)
and 14 refused by name (`p39_refuse_{literal,negative,boundary,keyword,positional,kwonly,identity,constant,constant_keyword,items,tuple,dict,numeric_key,expression}`),
all against CPython on both builds. `python3 tools/diff_ids.py` is not present in this tree;
`tools/update_manifest.py` was run and `--check` passes.

## 2026-10-27 -- pre306 review: instance folding ignores setattr (job-pre306-10271301)

The review found that the new instance-attribute folding still folded a literal `self.attr` after
`setattr(instance, 'attr', in_range)` (literal or dynamic name), so a program CPython runs as `1`
was falsely refused with the out-of-int64 wording.  `_known_class_attributes` now marks an
instance attribute unsafe when any `setattr` names it, and a `setattr` with a non-constant name
keeps every attribute read through an instance unknown (including a class attribute fallback).
A direct class read (`int(C.v)`) is still folded and refused when an unrelated dynamic `setattr`
targets an instance.  `AIL_CURRENT/test_ail_pre306.py` adds four matching cases (literal and
dynamic names, instance `self.attr` and class-attribute fallback) and one named-refusal case.
Probes in `/tmp/probes`: `pre306_attr_setattr_instance`, `pre306_attr_setattr_dynamic`,
`pre306_attr_setattr_routes`, `pre306_attr_setattr_boundary`, `pre306_attr_setattr_alias`,
`pre306_attr_setattr_int`, `pre306_attr_setattr_multiple`, `pre306_attr_setattr_dict_name`,
`pre306_attr_setattr_attr_name`, `pre306_attr_setattr_class_attr_fallback_constant` and
`..._dynamic` match CPython on both builds; `pre306_attr_setattr_class_direct_dynamic` is refused
by name on both builds.  `setattr` on a class object and `C.v = ...` stay unsupported on both
builds (pre-existing).  `tools/update_manifest.py --check` passes.

## 2026-10-27 -- pre306: int() of an out-of-int64 float through an attribute is refused by name (job-pre306-10271301)

The first still-differing pre-existing item from the rbrbpre31 review was `int(C().v)` with a class
attribute `v = 1e300`: both builds compiled it and then stopped with `integer overflow`, where
CPython prints the big integer.  The front end now folds literal class attributes and literal
`self.attr` values set in `__init__`, and follows them through a class alias, a module constant or
instance, a list/tuple/dict item, an identity/wrapper argument, a keyword argument and a class read.
An out-of-int64 float is refused on both builds with the existing
`int() of a float outside int64: ... (CPython makes a big integer)` wording.  Folding is
conservative: a class is skipped when it has bases, decorators or a keyword, a class attribute when
any other attribute store or `setattr` names it, and an instance attribute when it is assigned more
than once or outside the class's direct `__init__` body.  Values that fit, shadowed class names and
attributes mutated after construction are unchanged.

`AIL_CURRENT/test_ail_pre306.py` covers the refused routes (class attribute direct and through
`C()`, negative, `__init__`, module constant, alias, list and dict item, identity and wrapper
argument, module instance) and in-range/mutated/shadowed programs against CPython on both builds.
DIFFERENCES row `C?-job-pre306-10271301-1` added; `test_ail_pre306` is registered in
`ail_check.MODULES` and pinned.  Probes in `/tmp/probes`: `pre306_attr_class`,
`pre306_attr_class_direct`, `pre306_attr_neg`, `pre306_attr_init`, `pre306_attr_module_const`,
`pre306_attr_alias`, `pre306_attr_list`, `pre306_attr_dict`, `pre306_attr_instance` (refused by name,
both builds); `pre306_attr_fit`, `pre306_attr_mutated_instance` (match CPython, both builds).
`pre306_attr_instance` with an out-of-range value assigned after construction still keeps the
run-time trap.  Final tests on the committed tree: `test_ail_pre306`, `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`.  `tools/update_manifest.py --check` passes.
## 2026-10-27 - pre309 follow-up: the frozenset hash is stable and calls no `__hash__` (job-pre309-10271313)

The review of the first pre309 commit found that `ail_pyhash` recomputed a frozenset's mix from
each element on every `hash(fs)` call, so a side-effecting element `__hash__` ran again and
`hash(fs)` was not stable (`1 / 2 / 3 False` instead of CPython's `1 / 1 / 1 True`). A set entry
now stores the element's Python hash at insertion (the same value CPython's set table keeps), and
`ail_pyhash` of a frozenset reads those stored hashes through `ail_frozenset_hash`; no element is
rehashed. Set add/lookup use the same function, so membership, set operators and frozenset-key
lookups stay consistent. Added the direct, constant-`__hash__`, tuple-wrapped and nested
side-effect cases to `test_ail_pre309.py`.

Probes in `/tmp/probes`: `pre309_fix_basic`, `pre309_fix_routes`, `pre309_fix_semantics`,
`pre309_fix_ops`, `pre309_fix_mixed`, `pre309_fix_direct`, `pre309_fix_constant`,
`pre309_fix_tuple` all match CPython on both builds (8/8). Previous `/tmp/rprobes` probes
`r1_basic`, `r3_tuple`, `r4_routes`, `r6_mixed`, `r7_mixed2`, `r8_tset`, `r10_sem`, `r11_numeric`,
`r12_nested`, `r13_routes2`, `r14_custom`, `r15_ctors`, `r16_keys`, `r17_sideeffect` and
`r19_sideeffect3` still match on both builds; the recorded pre-existing `r2_types` (randomised
bytes hash), `r5_set` and `r9_sethash` differences are unchanged (`r18_sideeffect2` still refuses
a class-attribute store by name). Final-state tests: `test_ail_pre309`, `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3` (4 modules, 241 s, 0 failed), plus
`test_ail_sets_general`, `test_ail_int_dict_set` and `test_ail_tuples` (3 modules, 162 s, 0 failed).
`tools/update_manifest.py --check` passes.

## 2026-10-27 - pre309: hash() of a frozenset uses CPython's element hashes (job-pre309-10271313)

The only pre-existing difference recorded by the rbrbpre245 reviewer was
`hash(frozenset([1, 2]))`: both builds printed `7543283827113604033` where CPython prints
`-1826646154956904602`. The runtime's frozenset mix used the private set-table hashes; `ail_pyhash`
now feeds it each element's Python hash, so empty and int/bool/None/float/tuple/nested-frozenset
sets match. A frozenset of tuples was lowered to a tuple table whose instance hash was its
identity; a `hash()` call on such a table now leaves the program on the general path (tupcalls
`b_hash`), where the real frozenset is hashed. Strings keep CPython's per-process randomised hash,
so only their order independence is checked. Added `test_ail_pre309.py` and registered it in
`ail_check.MODULES`.

Probes in `/tmp/probes`: `pre309_hash_frozenset`, `pre309_hash_int`, `pre309_fs_basic`,
`pre309_fs_types`, `pre309_fs_routes`, `pre309_fs_semantics`, `pre309_fs_strings`,
`pre309_fs_setdiff`, `pre309_fs_tuple`, `pre309_fs_repr`, `pre309_fs_diag1`, `pre309_fs_diag2`,
`pre309_fs_diag3`, `pre309_fs_seq1` and `pre309_fs_seq2` all match CPython on both builds (15/15).
Final-state tests: test_ail_pre309, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3 (4 modules, 356 s, 0 failed). `tools/update_manifest.py --check` passes.
## 2026-10-27 -- pre313: bytearray `*=` changes the object itself (job-pre313-10271421)

The first still-differing item in the rbpre281 review was the bytearray in-place repeat:
`ba = bytearray(b"ab"); z = ba; ba *= 2` left `z` as `b"ab"` where CPython extends the same
bytearray in place, so the alias shows `b"abab"` (`ba is z` stays True).  The general path's
bytearray is the `bytearray` class from `prelude_bytes.py`; it had `__mul__` but no `__imul__`,
so the augmented assignment fell back to `__mul__` and rebound the name.  `prelude_bytes.py`
now gives `bytearray` an `__imul__` that checks its operand like `__mul__`, repeats `self._a`
in place, and returns `self`.  The `g` (forced general) and `d` (default) builds both use that
fallback, and both now match CPython.  The second recorded item (a huge count on a non-empty
outer sequence) was not touched: only the first still-differing cause was fixed.

Probes in `/tmp/probes` match CPython on both builds: `pre313_ba_alias` (the recorded case),
`pre313_aliases` (size 2, empty, zero, negative, bool, larger and a `bytes` control),
`pre313_routes` (a function argument, a list item, an attribute and a dict value, each with an
alias) and `pre313_types` (float/str/list/None TypeError text, bytearray(), bytearray(int),
bytearray(list), and `False`).  Final-state tests: test_ail_pre313, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3 (26 tests, 513.6 s, 0 failed, 1 skipped).
DIFFERENCES row `C?-job-pre313-10271421-1`; `tools/update_manifest.py --check` passes.
## 2026-10-27 -- pre317: a store into a caught exception's e.args[i] is refused by name (job-pre317-10271455)

The first still-differing pre-existing item from the rbrbpre48 review that is not already a named refusal was
the stderr traceback for `e.args[0] = ...`: both builds ran the statement and matched CPython's stdout, exit
status and last stderr line, but the full traceback text differs because AIL does not model tracebacks. The
first item, the forced-general refusal of a multi-argument `ValueError`/`OSError` raise, is already a named
refusal on this tree. `exctext.refuse_args_item_store` now refuses an assignment to or deletion of a caught
exception's `e.args[i]` by name at compile time, from both the typed front end (`pyfunc`) and the general
emitter (`pyboxed2`), for a literal, negative or computed index, augmented and annotated stores, a
destructuring target, a `for` or `with` target, a value arriving through an argument, a list item, an
attribute or a dict value, and a simple alias of the exception through a name, list item, attribute or dict
value. The scan stays in one scope, so a nested function's own `e` is not refused, and it stops treating the
name as the exception once the handler rebinds it. Passing the exception to a function that stores into its
parameter's `args` item is not followed and keeps the pre-existing traceback-only difference. Storing a whole
`e.args`, a non-exception object's `args` list and a store inside the argument object are left unchanged. Added `AIL_CURRENT/test_ail_pre317.py` and registered it in `ail_check.MODULES`; added
DIFFERENCES row `C?-job-pre317-10271455-1`. `python3 tools/update_manifest.py` was run and `--check` passes.

Probes in `/tmp/probes`: `p317_args_assign1`, `p317_store_ann`, `p317_store_aug`, `p317_store_delete`,
`p317_loop_target`, `p317_with_target`, `p317_alias_name`, `p317_alias_list`, `p317_alias_attr` and
`p317_alias_dict` are refused by name on both builds; `p317_alias_arg` keeps the pre-existing
traceback-only difference for an exception passed to a function that stores into its parameter's `args` item
(cmp.sh matches stdout, exit and the last stderr line); `p317_args_read_single`, `p317_store_user_obj`,
`p317_store_nested_obj`, `p317_rebind_handler`, `p317_multiraise_value` and `p317_multiraise_os` match
CPython on the default build, with the multi-argument raises already refused by name on the forced general
build. Final-state tests: `test_ail_pre317`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3`.

## 2026-10-26 -- pre304 review: method/property rebinding is refused by name (job-pre304-10270748)

The review of the pre304 change found that it introduced a wrong answer: when a method or
property rebinds an earlier class attribute (`class C: x = 3; def x(self): ...; y = x + 1`),
the name map still held the old attribute slot, so `y` printed `4` (and a comprehension printed
`[0, 1, 2]`) where CPython raises TypeError.  The map is now built from the class body's
statement order instead of only its attributes, and a method/property binding marks its name as
refused, so a later attribute read of that name is refused by name at compile time on both builds
(the base behaviour).  The same applies when a module global has the same name, where the base
printed the global's value instead of CPython's TypeError.  A method before the attribute, a
method after the use, a later re-assignment after the method, inherited methods, and unrelated
methods keep matching CPython.

Probes in `/tmp/probes`: `pre304rev_method_plain`, `pre304rev_method_comp`,
`pre304rev_property`, `pre304rev_static_class`, `pre304rev_global_same_name` are refused by name
on both builds (CPython raises TypeError); `pre304rev_method_before_attr`,
`pre304rev_rebind_after_method`, `pre304rev_method_after_use`, `pre304rev_unrelated_method` and
`pre304rev_inherited_method` match CPython on both builds.  `test_ail_pre304.py` now has 3 tests.
## 2026-10-26 -- pre304: class-body names are visible to later attributes (job-pre304-10270748)

The first pre-existing difference in the rbrbfuzz28 review was a class-body comprehension that
reads an earlier class attribute: `class C: x = 3; ys = [i for i in range(x)]` stopped with
`name 'x' is not defined` when `ys` was read through an instance or through `C()`, and the
inherited and empty-comprehension cases refused too.  pyboxed2 now keeps the class body's earlier
assignments in a temporary name map (name -> the attribute's module slot) while it compiles each
attribute value, including the lazy `_class_attr_value` fallback and the `C.attr` read.  Only a
comprehension's outermost iterable sees the map, as in CPython: the comprehension body runs in
its own scope, so a class name there still reads a module global of the same name, or is refused
by name when there is none.  Duplicate assignments, a later class definition that uses the outer
global first, aliases and arithmetic, sources through a list item, a dict value and an instance
attribute, inheritance and overriding, and class/instance/method reads all match CPython.

Added `AIL_CURRENT/test_ail_pre304.py` (2 tests, both builds) and registered it in
`ail_check.MODULES` and `tools/ci_shards.json`; DIFFERENCES row
`C?-job-pre304-10270748-1`.  Probes in `/tmp/probes`: `pre304_inst`, `pre304_call`,
`pre304_instance_read`, `pre304_inherit`, `pre304_inherit_call`, `pre304_empty`, `pre304_comps`,
`pre304_shadow_global`, `pre304_comp_body_global`, `pre304_arith`, `pre304_dup`,
`pre304_later`, `pre304_routes`, `pre304_args`, `pre304_negative_bool`, `pre304_nested`,
`pre304_class_read`, `pre304_alias`, `pre304_method`, `pre304_override` and `pre304_plain` match
CPython on both builds; `pre304_comp_body_noglobal` is refused by name on both builds.
Final-state tests: `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (4 modules, 275 s, 0 failed), plus `test_ail_pre279`,
`test_ail_pre283`, `test_ail_fuzz29`, `test_ail_dunders`, `test_ail_typed_inherit` and
`test_ail_virtual_dispatch` (6 modules, 191 s, 0 failed).  `tools/update_manifest.py --check`
passes.
## 2026-10-26 -- pre271: oversized in-place list repeat raises MemoryError (job-pre271-10262226)

The first pre-existing difference in the rbpre55 review was `xs *= 2**62`: the general path's
`ail_op_imul` stopped with an uncatchable `integer overflow` where CPython raises MemoryError,
and an empty list spun over the huge count. The oversize guard now stops through a bare
`MemoryError` before the element product leaves int64, and an empty list skips the repeat loop.
No compile-time refusal was added: small, zero, negative and bool counts still match, and a huge
count arriving through an argument, a list item, an attribute, a dict value or an alias matches
CPython on both builds.
`AIL_CURRENT/test_ail_pre271.py` covers both builds. Probes in `/tmp/probes`: `pre271_aug_huge`,
`pre271_aug_boundary`, `pre271_aug_one`, `pre271_aug_typed_huge`, `pre271_aug_dynamic_routes`,
`pre271_aug_empty`, `pre271_aug_alias`, `pre271_aug_zero_one`, `pre271_aug_neg`,
`pre271_aug_bool`, `pre271_aug_small`, `pre271_aug_routes`, all matching CPython on both builds.
Final-state tests: test_ail_pre271, test_ail_local_count_repeat, test_ail_list_ops,
test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 (6 modules, 271 s, 0 failed).
`tools/update_manifest.py --check` passes.

## 2026-10-26 -- preludes avoid the refused variable-exponent power (job-pre273-10262306 review)

The review found that `refuse_variable_int_pow` also saw compiler-injected library source:
`prelude_fraction.py`'s `10 ** len(frac)` / `10 ** exp` / `10 ** abs(ndigits)` made every
`from fractions import Fraction` program fail at compile time, and `test_ail_pre133` failed 2/3.
The preludes now stay inside the subset the refusal describes: `prelude_fraction.py` scales
through a new `_ail_fr_pow10` multiplication loop, and `prelude_random.py`'s `sample` adds the
already-computed `p` instead of recomputing `4 ** m`. No refusal or runtime rule changed; a user
program that writes `2 ** n` is still refused by name on both builds. Added a Fraction prelude
case to `test_ail_pre273.py`; `test_ail_pre133` is back to 3/3.

Probes in `/tmp/probes`: `pow_fraction_modern.py` (constructor from an int pair, decimal and
exponent strings, arithmetic and `round` through the prelude's powers of ten) matches CPython on
both builds; `pow_random_prelude.py` (the prelude's own `Random` class plus `sample` with k > 5)
matches CPython on both builds. The earlier `pre273_*` probes still behave as recorded: the
refused forms are refused by name and `bounds`/`safe`/`zero_neg` match CPython.

## 2026-10-26 -- computed exponent on a constant integer base is refused (job-pre273-10262306)

The first still-differing item in the rbpre69 review was the variable-exponent power: `2 ** n`
compiled and then stopped with `integer overflow`, where CPython keeps an unbounded int. The
constant-exponent form is already folded and refused when it leaves int64, so the remaining case
is an exponent known only at run time. `pyfront.refuse_variable_int_pow` now refuses a power
whose base is a compile-time int64 constant with |base| >= 2 and whose exponent is not a constant
expression, naming the base and the int64 boundary on the typed path and both general emitters.
Constant exponents (including bool leaves), the safe bases 0/1/-1, float bases with a
constant float exponent and a variable base with a constant exponent are unchanged. The three existing tests that used the old trap
(`test_all.integer_power`, `test_ail_pre160`, `test_ail_crypto`) now exercise the new boundary.
Added `test_ail_pre273.py` (2 tests, both builds) and registered it in `ail_check.MODULES`;
DIFFERENCES row `C?-job-pre273-10262306-1`. `tools/diff_ids.py` is not present on this tree;
`tools/update_manifest.py` was run and `--check` passes.

Probes in `/tmp/probes`: `pre273_arg`, `pre273_list`, `pre273_attr`, `pre273_dict`,
`pre273_alias` and `pre273_float_dynamic` are refused by name on both builds; `pre273_bounds`,
`pre273_safe` and `pre273_zero_neg` match CPython on both builds (constant/float/bool exponents,
the bases 0/1/-1, negative constant exponents and a variable base with a constant exponent).
`pre273_expr_pow` keeps the older named refusal for a constant exponent outside int64;
`pre273_neg_literal` matches CPython. Tests on the final tree: `test_ail_pre273`,
`test_ail_pre160`, `test_ail_crypto`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3`.
## 2026-10-26 - pre279 review: callable instance fields and TypeError type names (job-pre279-10262332)

The review of `665f894` found two defects in the new field-call path.  A field holding an
instance with `__call__` went to `call_value`, which accepts only `AIL_T_FUNC`, so
`class F: def __call__(self, x): ...; class C: def f(...); self.f = F()` stopped with
`TypeError: 'instance' object is not callable` where CPython prints `11`.  The field path now
dispatches `__call__` on the field's run-time class (deepest override first, static and class
methods included) and keeps the ordinary function/class-value call otherwise.  The caller's
not-callable message also used `ail_type_name`, which maps every instance (including `bytes`
and `bytearray`) to `instance`; it now uses `ail__tname_c`, so CPython's `'F' object is not
callable` / `'bytes' object is not callable` match.

Probes in `/tmp/probes/pre279` on both builds: `call_basic`, `call_types`, `call_routes`,
`call_conditional`, `call_inherit`, `call_external`, `call_noargs`, `callv_noclass`,
`t_callable_names` and the existing `shadow_*`/`p02*` match CPython; `type_names` and
`type_instances` match for None/bool/int/float/str/bytes/bytearray/list/tuple/dict and plain
instances.  `call_alias_field` (bound-method value) and `call_instance` (calling a plain
instance) keep their pre-existing unsupported behaviour, unchanged by this job.  Final-state
tests: `test_ail_pre279`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`,
`test_ail_virtual_dispatch`, `test_ail_typed_inherit` (6 modules, 323 s, 0 failed).
`python3 tools/update_manifest.py --check` passes.

## 2026-10-26 - pre279: an instance field shadows a same-named class method (job-pre279-10262332)

The first still-differing pre-existing item from the pre260 review was its p02 method/field
collision: with `self.f = lambda x: x + 100` in `__init__` and `def f(self, x): return x + 101`,
both builds printed `102 103`, where CPython prints `101 102`.  `_call_attribute` dispatched the
static method before reading the instance table, although a function is a non-data descriptor.
Both general paths now remember every `obj.attr = ...` name in the program and test the instance
table first (`ail_inst_findattr`, emitted only for a program that needs it), for a statically
known receiver and for the dynamic user-method dispatch; the method still applies when the field
is absent or deleted, and a non-callable field raises CPython's TypeError.  A call with keyword
or starred arguments is refused by name when a field may shadow the method.  The full quirks
module (the first unverified item in the task) already passes on this tree.

Probes in `/tmp/probes/pre279`: `shadow_basic`, `shadow_routes`, `shadow_external_nodelete`,
`shadow_conditional`, `shadow_types`, `shadow_noncallable`, `shadow_inherit`, `shadow_static`,
`shadow_alias_value` and `shadow_nofeature` match CPython on both builds; `shadow_kwargs` and
`shadow_external` (`del c.f`) are refused by name.  Added `AIL_CURRENT/test_ail_pre279.py` and
registered it in `ail_check.MODULES` and `tools/ci_shards.json`.  Final-state tests:
`test_ail_pre279`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`.
`python3 tools/update_manifest.py --check` passes.
## 2026-10-26 -- pre283: class-attribute store through a class value is refused by name (job-pre283-10270202)

The pre275 reviewer recorded a class-attribute assignment (`r_class_mutate*`) that already failed
before that job: `class Box: v = 1.0` + `Box.v = 2.5` prints 2.5 on CPython, but both builds
raised `AttributeError: 'type' object has no attribute 'v'`.  The general path keeps each class
attribute in a module slot it only reads and copies onto instances, so it cannot store through a
class object; instead of changing that model, the construct is refused by name at compile time:
pyboxed2 refuses a statically class-valued base (a direct unshadowed class name; exit 3, leaving
the typed path's own class-attribute support on the default build untouched), the front end
refuses an alias of a class and a class read out of a literal list/tuple/dict (constant index,
negative or not; exit 2), and `ail_inst_setattr_chk` raises a named NotImplementedError for a base
that only holds a class at run time (a parameter, an instance attribute, a mutated container).
Instance stores and names shadowed by a local, parameter, loop target or closure cell are
unchanged.  Probes in `/tmp/probes` (`c*`, `m*`, `n*`, `t*`): direct/new/aug/annotated/alias/
literal-container stores are refused by name on both builds; `c6/c7/c8/c11/c13`, `n3/n7/n8/n9/
n13`, `t9/t10` match CPython on both; `t1/t2/t3/t5` and the class-level program match on the
default build and are refused on the general build; `n1/n2` are refused at run time by name.
Tests on the final tree: `test_ail_pre283`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`, `test_ail_dunders`, `test_ail_typed_inherit` (6 modules, 320 s,
0 failed).  `tools/update_manifest.py` run and `--check` passes.
## 2026-10-26 -- local constant cancellation refused by name (job-pre285-10270302)

The reviewer of job `rbrbpre32` recorded `a = 2**62; b = a * 2 - 1` as a pre-existing
difference: both builds computed `a * 2` in int64 and stopped with `integer overflow` at run
time, while CPython's unbounded int prints INT64_MAX.  The first recorded item (index/slice/
dead-code out-of-range powers) is already refused by name on this tree, so this job fixes the
first item that was still an uncaught run-time difference.

`ail_chatgpt.py` now follows a function's single-assignment int constants (direct, aliased,
annotated, and visible module constants) when it checks an expression, and refuses by name
(`int64 constant expression out of range`) a step that leaves int64 while the whole expression
fits.  The check reuses the existing `_function_local_int_constants` +
`_constant_int_exact` machinery.  A literal cancellation such as `2**63 - 1`, in-range local
steps and values that only arrive at run time are unchanged; an expression whose own final
value leaves int64 keeps its previous run-time stop.  Added `AIL_CURRENT/test_ail_pre285.py`
(12 refusal cases, 6 matching cases, both builds), registered it in `ail_check.MODULES` and
updated `tools/ci_shards.json`.  Probes `p285_*` in `/tmp/probes`: `p285_direct`,
`p285_routes`, `p285_alias` and `p285_ops` are refused by name on both builds; `p285_small`,
`p285_literal` and `p285_runtime` match CPython on both builds.  Tests on the final tree:
`test_ail_pre285`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` and 13
related `pre*` modules (17 modules, 361 s, 0 failed).  `tools/update_manifest.py --check`
passes.
## 2026-10-26 -- wrapper-chain int() of an out-of-int64 float refused (job-pre290-10270339)

Fixed the first still-differing pre-existing item from the rbrbrbpre39 review, `r23`: a value
outside int64 passed through a chain of wrapper calls (`outer(1e300)` -> `take(y)` -> `int(x)`)
compiled and stopped at run time with `integer overflow`, while CPython prints the bignum.  This
tree had no version of the accepted pre39 static-float checker, so its pass is added to
`ail_chatgpt._check_int64_literals` (module constants, literal containers, identity/keyword
wrappers, `_UNKNOWN` for unresolved names), and `_wrapper_int_params` now propagates a wrapper
parameter through further module-level wrapper calls to a fixpoint, unwrapping identity calls.
The call site is refused by name instead.  In-range conversions, non-finite floats, run-time-only
values and a locally shadowed wrapper keep their previous behaviour.  Added
`AIL_CURRENT/test_ail_pre290.py` (12 refused, 6 CPython-parity programs, both builds) and
registered it in `ail_check.MODULES` and `ci_shards.json`.  The next recorded pre-existing items
(r26 alias-list, r27 attribute-held value, r28 tuple multi-assign, r33 dict via variable dict)
still stop at run time and are left open.

Probes in `/tmp/probes` on both builds: `p290_refuse_{direct,one_pos,one_kw,identity,chain2,
chain3_kw,chain_id,chain_list,chain_dict,chain_tuple,chain_neg,chain_const,chain_ifexp,
chain_boundary}` are refused by name; `p290_match_{direct,routes,nonfinite,shadow}` match CPython.
Final tests: `test_ail_pre290`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`.

## 2026-10-26 - pre296: a local binding of a built-in name wins over the built-in call (job-pre296-10270440)

The pre54 reviewer's first pre-existing difference was a parameter named `round` that was not
honoured: `def apply(round, x): return round(x)` called the built-in when the argument was a
callable, so the probe printed `-6` / `int` where CPython prints `-16.5` / `float`. The general
path now reads a parameter, local, cell or closure binding named like a built-in instead of
dispatching to the built-in by name, and the typed path refuses that call by name so the default
build falls back to it. This covers the exact parameter case plus a local lambda, a closure cell,
and values arriving through a list item, an attribute and a dict value; a non-callable binding
keeps CPython's TypeError and an unshadowed `round` is unchanged. Added
`AIL_CURRENT/test_ail_pre296.py`, registered in `ail_check.MODULES`; `tools/update_manifest.py`
was run and `--check` exits 0. Probes in `/tmp/probes` on both builds: `p296_param`,
`p296_local`, `p296_closure`, `p296_routes`, `p296_callable_param`, `p296_noncallable`,
`p296_unshadowed`, `p296_len_local`, `p296_len_param`, `p296_abs_local` and `p296_no_feature`
match CPython; `p296_builtin_value` is refused by name (passing the built-in `round` as a value
is a separate pre-existing gap). Tests on the final tree: `test_ail_pre296`,
`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus the related
`test_ail_builtin_shadowing` and `test_ail_pre218`. A lambda assigned after a call in the same
function is still dropped by a separate scanning pass, so that unbound-local edge remains
pre-existing on both builds.
## 2026-10-26 -- repr(e.args[i]) keeps the argument's kind (job-pre298-10270442)

This tree still lacked the accepted pre26 fix, so the first CPython difference left by the rbpre26
review was behavioural: on the typed path `e.args[i]` reads as text, making `repr(e.args[i])` repr
that text (`ValueError(3.0)` printed `'3.0'` where CPython prints `3.0`; ints, bools and None were
quoted too) and `f"{e.args[i]!r}"` / `%r` of one argument were refused by name. Re-applied the
accepted pre26 change: `exctext.py` gains `arg_repr()` and the `ail_exc_argrepr` runtime accessor
(`ail__exc_piece(&a, 1, A)`), `pyfunc.py` lowers `repr(e.args[i])`, `!r` and `%r` through it, and the
existing `_ail_exc_arg` text path is unchanged for `str()`, `print()` and concatenation. The rbpre26
review's first pre-existing item (multi-argument `raise` on the forced general path) remains the
same named refusal, and `"%r %s %r"` of exception arguments now works on the typed path.
Added `test_ail_pre298.py` (numeric multi-argument repr, single-argument types/formats, index routes
through a call/list item/dict value and formatting) and registered it in `ail_check.MODULES` and
`ci_shards.json`; DIFFERENCES row `C?-job-pre298-10270442-1`. `tools/update_manifest.py --check`
passes.

Probes in `/tmp/probes/pre298` on both builds: `types`, `index_kinds`, `formats`, `escapes`,
`pre26test` and `nonrepr` match CPython on `d` (the `g` build keeps the pre-existing named
multi-argument refusal); `single` matches on both builds. `after` (storing `x = e.args[i]` and then
`repr(x)`) still quotes a numeric argument; that is a pre-existing limitation identical on the base
(`523c597`) and is not caused by this change. Final-state tests: test_ail_pre298,
test_ail_exception_values_core, test_ail_exception_values_app,
test_ail_exception_aggregate_objects, test_ail_exception_context, test_ail_exc_str,
test_ail_excfix, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3
(10 modules, 488 s, 0 failed).
## 2026-10-26 -- re-apply cov7: partial lambda locations and abstract-base dispatcher (job-rbcov7-10270118)

Re-applying the accepted cov7 change on the current integration tree.  The diff applied cleanly
to `genlib.py`, `pyfunc.py`, `test_ail_silent6.py` and `test_ail_typed_inherit.py`; the
`DEVLOG.md` / `DIFFERENCES.md` conflicts kept both sides (cov7's entries plus this tree's newer
ones), and the re-applied DIFFERENCES row uses this job's placeholder id.  The workflow part of
the diff (OpenCode v1.19.4 and the extra key scan) was already present here, so no change.  In
`genlib._partial` both rewritten `Lambda` nodes now copy the `partial()` call's location, so
`pyboxed2._refuse_lambda_forward_defaults` no longer raises `AttributeError: 'Lambda' object
has no attribute 'lineno'` for a positional or keyword partial (g17_004 / g17_024).  In
`pyfunc._dispatcher` the representative is looked up with `by_name.get()` and falls back to the
first concrete implementation when the base's method is a stub that was dropped, so an abstract
visitor hierarchy builds instead of raising `KeyError: 'Visitor__visit_directory'` (g13_036).
The positional-partial program was added to `test_ail_silent6.py` and the abstract visitor to
`test_ail_typed_inherit.py`.

Probes in `/tmp/probes`: `cov7_partial_basic`, `cov7_partial_routes`, `cov7_visitor_abstract`,
`cov7_visitor_mixed`, `cov7_visitor_noret` and `cov7_visitor_dict` all match CPython on the
general and default builds; the abstract/mixed/noret visitor programs also build typed-only
(`AIL_NO_GENERAL=1`) and match, exercising the dispatcher.  `cov7_visitor_dict` is refused by
name on the typed path (`'table' is annotated dict ... no rule for`) and matches on the general
path.  `tools/diff_ids.py` is not present in this tree; `tools/update_manifest.py` updated the
four touched pins and `--check` passes.

Tests on this tree: `test_ail_silent6`, `test_ail_typed_inherit`, `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3` pass (44 tests, 731 s, 1 skipped: no zig for
`--target windows`).
## 2026-10-26 -- re-apply pre26: repr(e.args[i]) keeps the argument's kind (job-rbpre26-10270138)

Re-applied the accepted pre26 change on this tree. On the typed path `e.args[i]` reads as text, so
`repr(e.args[i])` repr'd that text: a `ValueError(3.0)` handler printed `'3.0'` where CPython prints
`3.0`, and int, bool and None arguments were quoted the same way. The handler rewrite now lowers
`repr(e.args[i])`, `f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor
that formats the stored argument (a str keeps its quotes, a number does not). Both builds agree with
CPython; the accepted `test_ail_pre26.py` keeps the probe, including negative and out-of-range
indexes, and is registered in `ail_check.MODULES`.

## 2026-10-26 -- pre54 review fix: MANIFEST pin and DIFFERENCES row order (job-rbpre54-10270147)

The reviewer found the committed tree was missing the `test_ail_pre54.py` pin, so
`tools/update_manifest.py --check` exited 1 and `ail_check.preflight` aborted every module with
`hash mismatch`; re-ran `tools/update_manifest.py` and committed the pin (`--check` now exits 0).
The DIFFERENCES row also had its cells in the wrong columns (`refused | round | <text>`); it is
now `round | <text> | refused` under the `| id | area | difference | status |` header.
Re-ran the `/tmp/probes/p54_*` probes: the four match probes match CPython on both builds, the
five boundary probes are refused by name on both (exit 3, no executable).

## 2026-10-26 -- re-apply pre54: round() at the int64 boundary is refused by name (job-rbpre54-10270147)

Re-applied the accepted pre54 change on this tree.  `pyc.build` now calls
`_refuse_round_at_int64_boundary` before either build path: a one-argument `round()` of a
constant float at or beyond the signed 64-bit boundary (`round(-9223372036854775808.0)` is
INT64_MIN) is refused by name, because `abs()`, unary `-` and `* -1` need 2**63 and AIL's int is
int64.  The accepted change's workflow half (OpenCode v1.19.4 with its sha256, the qoder.key /
cc.key secret files and the three-key scan) is already present on this tree, so no edit was
needed; pre104's catchable ValueError / OverflowError for nan/inf is kept, and finite
out-of-range values that are not compile-time constants still take the runtime trap.  Added
`AIL_CURRENT/test_ail_pre54.py`, registered it in `ail_check.MODULES`, and added DIFFERENCES row
C?-job-rbpre54-10270147-1.  Probes in `/tmp/probes`: `p54_near`, `p54_two_arg`, `p54_shadow` and
`p54_nonconstant` match CPython on both builds; `p54_refuse_direct`, `p54_refuse_argument`,
`p54_refuse_container`, `p54_refuse_positive` and `p54_refuse_beyond` are refused by name on both
builds (exit 3, no executable).  `python3 tools/diff_ids.py` is not present in this tree.
## 2026-10-26 -- pre276 suite fix: a wide constant index folds to a CPython index (job-pre276-10270718)

The integration candidate at job start includes pre269, which folds the whole constant index
expression before the int64 check.  `(-2 ** 63) // (2 ** 63)` therefore now compiles to -1 and
prints the last list/tuple/str/bytes item or the -1 dict value on both builds, where the pre276
branch base still refused it by name.  `test_ail_pre276.py` now accepts either outcome for each
receiver and requires both builds to agree: a named refusal (`int64 index out of range`), or a
successful build whose stdout equals CPython's.  No compiler change was made.

Probes in `/tmp/probes`: `pre276_wide`, `pre276_routes` and `pre276_boundaries` match CPython on
the integrated tree and are refused by name on this branch base; `pre276_out_of_range` is
refused by name on both (CPython raises IndexError); `pre276_unchanged` matches CPython on both.
Tests: test_ail_pre276, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3.
## 2026-10-26 -- constant index with a wide operand is already refused by name (job-pre276-10262320)

The first still-differing item from the rbpre47 review was
`[1, 2, 3][(-2 ** 63) // (2 ** 63)]`: CPython computes -1 and prints the last item, while both
builds stop at compile time with `int64 index out of range: 9223372036854775808` because the
positive operand `2 ** 63` leaves int64.  The task accepts a named compile-time refusal, and the
current tree already gives one on the general and the default build, so no compiler change was
made.  Added `test_ail_pre276.py`, which pins that refusal for list, tuple, str, bytes and dict
receivers and for a named list, on both builds, and registered it in `ail_check.MODULES` and
`ci_shards.json`.

Probes in `/tmp/probes` (both builds): `idx1_exact` is refused by name; the wider per-route probes
`pre276_routes`, `pre276_containers`, `pre276_boundaries`, `pre276_negatives`, `pre276_widths`,
`pre276_assign_alias` and `pre276_empty` are also refused by name or, where the per-step folder
already leaves them alone, match CPython.  `runtime_var` (the second rbpre47 item) is likewise
already refused by name; `divs3` (the third) still prints `1.0` on the default build and was not
the first item.  Tests on the final tree: test_ail_pre276, test_ail_safetynet, test_ail_files and
test_ail_corpus_findings3.
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
## 2026-10-26 -- zero to a negative power names CPython's ZeroDivisionError (job-pre265-10262131)

The first still-differing item recorded by the rbpre33 reviewer was the default build's message
for a constant `0 ** -1`: it raised `ZeroDivisionError: division by zero` where CPython says
`0.0 cannot be raised to a negative power`. A constant negative exponent takes the float `pow()`
path, whose shared typed helper `ail__fpow_slow` still used the older division text. The helper
now raises a catchable `AIL_EXC_ZERODIV` with CPython's text, so both the caught `str(e)` and an
uncaught stop agree; the general path already had the message. The same fix covers `0.0 ** -1`,
`(-0.0) ** -1`, `False ** -1`, `0 ** -1.0`, `0.0 ** -0.5`, and a zero base arriving through an
argument, a list item, an attribute, a dict value, an alias or a local. Non-zero negative
exponents keep their float results, and a *variable* negative exponent keeps the deliberate
exact-integer trap documented in SEMANTICS.md. The other two recorded pre-existing items were
checked and needed no change: an out-of-int64 intermediate/result such as `2**64 // 2` or
`(-3)**40` is already refused by name, and the v1 dict-literal case now matches CPython.

Added `AIL_CURRENT/test_ail_pre265.py` and registered it in `ail_check.MODULES` and
`ci_shards.json`. Probes in `/tmp/probes` (`pre265_item1`, `pre265_zero_direct`,
`pre265_zero_values`, `pre265_arg_int`, `pre265_arg_float`, `pre265_arg_pair`,
`pre265_fit_args`, `pre265_pow_regression`, `pre265_pow_neg`) match CPython on both builds;
`pre265_item2a/b/c` are refused by name on both. Tests on the final tree: `test_ail_pre265`,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3`.
## 2026-10-26 - pre267: refuse a statically known non-BMP bytes.decode() by name (job-pre267-10262133)

The first still-differing item in the rbpre51 review was the general path's non-BMP
`bytes.decode()`: `b"\xf0\x9f\x98\x80".decode()` built and then stopped with `AIL internal
error: decode: a code point above U+FFFF in the 16-bit v2 runtime`, while CPython prints the
astral character and the default build already matched.  The general runtime keeps UTF-16 units,
so pyboxed2 now statically resolves the bytes value and refuses a decode (or `str(bytes, enc)`)
whose UTF-8 text contains a code point above U+FFFF, by name at compile time.  It follows a
literal, module constant/alias, list/tuple/dict literal item, class attribute, simple identity
return, `bytes([...])` / `bytearray(...)`, keyword encoding/errors, and a function parameter
called with such a constant; BMP text (through U+FFFF) and invalid UTF-8 still match CPython.
Bytes whose content is only known at run time (stdin/file/unknown value) keep the open 16-bit
limitation already recorded at `C?-job-rbrbrbrbmemsafe2-10261346-6`.

Added `AIL_CURRENT/test_ail_pre267.py` (2 tests, both builds) and registered it in
`ail_check.MODULES`.  Probes in `/tmp/probes`: `p267_decode.py` (direct non-BMP),
`p267_decode_const.py`, `p267_decode_container.py`, `p267_decode_arg.py`,
`p267_decode_attr.py`, `p267_decode_attr2.py`, `p267_decode_str.py`, `p267_decode_dyn.py`,
`p267_decode_alias.py` and `p267_decode_bounds_nonbmp.py` are refused by name on the general
path; `p267_decode_bmp.py`, `p267_decode_invalid.py`, `p267_decode_bounds_bmp.py`,
`p267_decode_encoding_bmp.py`, and the three mutated bytearray/list/dict probes
(`p267_mutate_bytearray.py`, `p267_mutate_list.py`, `p267_mutate_dict.py`) match CPython on both
builds.
## 2026-10-26 -- constant index through an out-of-int64 intermediate (job-pre269-10262136)

`del a[2**63 * 0]` and `del a[(1 << 63) >> 62]` were refused by the front-end with
`int64 index out of range: 9223372036854775808` although CPython deletes an element: the
intermediate `2**63` leaves int64, but the exact final index is 0 or 2.  `_check_index_expression`
now retries a bounded-fold overflow by folding the whole index with the shared `_const_fold_int`
budget (2**20 bits, the same budget as the other constant checks) and accepts an exact final value
inside int64; only a final value outside int64 keeps the named refusal (now naming that exact
value).  This root-cause fix also accepts `(10 ** 20) // (10 ** 19)` (final 10) and
`((1 << 64) - 1) >> 1` (INT64_MAX), so the stale intermediate case is removed from
`test_ail_pre177`'s refusal table and its docstring is updated.  A genuinely wider intermediate,
a literal, and a final value outside int64 keep their existing refusals.

Probes in `/tmp/probes` on both builds: `del_bound`, `index_exact`, `index_routes` and
`index_boundary` match CPython; `index_refuse1`-`index_refuse5` are refused by name.  Tests on
the final tree: pre269, pre177, pre246, pre201, pre204, pre238, pre121, safetynet, files and
corpus_findings3 (48 tests, 596 s, 0 failed, 1 skipped).
## 2026-10-26 -- pre-270: relative import below the top level is refused by name (job-pre270-10262216)

The reviewer of job rbpre52 left two pre-existing items: the relative/local import refusal and a
user class shadowing `ImportError`.  Both are named compile-time refusals on this tree.  The first
still reproduced with the wrong message: `try: from . import thing except ImportError` hit
`lift_lazy`'s generic "import of a local module or package below the top level (inside a condition
or loop at module level)" instead of the entry-file relative-import refusal, which names
`from . import ...` and points at the import.  `lift_lazy` now runs the entry-file relative-import
check first and describes a local import in a module-level `try` as "inside a try block"; a user
class named `ImportError` keeps its existing named refusal.  Added `AIL_CURRENT/test_ail_pre270.py`
(three cases, both builds) and registered it in `ail_check.MODULES` and `tools/ci_shards.json`.

Probes `/tmp/probes/pre270_*` (relative import in `try`, `if`, class body and function, `from
.thing`, `from ..`, an alias, `ImportError`/`ModuleNotFoundError` shadowing, and a non-feature
control) match CPython or are refused by name on both builds.  The required modules are run on the
final commit.
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
## 2026-10-26 -- re-apply fuzz49: augmented assignment on an instance calls the in-place method

Re-applied the accepted fuzz49 change on the current integration tree. The general path
compiled `a += b` through the plain operator helpers, so `ail_op_iadd` fell straight back to
`__add__`; `__iadd__` / `__isub__` / `__imul__` / `__iand__` / `__ior__` / `__ixor__` were not
in the class dispatch tables at all. A class defining both printed the `__add__` result where
CPython mutates and keeps the object. `dunderrt` now appends the in-place operators to the
dispatch enum only for a program whose classes define one (other programs keep their runtime
text) and emits the `__iadd__`-family check before the plain operator; `safetyrt` falls back to
`__add__`/`__radd__` when the in-place method returns `NotImplemented`. A name that is ever the
target of an augmented assignment is no longer given a trusted class kind, since the method may
return another type and earlier code (a loop body, a lambda) would use a stale kind. Ported
`test_ail_fuzz49.py`, registered it in `ail_check.MODULES` and `tools/ci_shards.json`. Both
builds, 13 differential cases.
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
## 2026-10-26 - re-apply qtest4: bytes/bytearray fillchar wrong-type message (job-rbqtest4-10262127)

Re-applied the accepted qtest4 change on this tree.  The `_ail_b_fill` type guard is already
present from the pre182 fix (`bytes`/`bytearray` membership is checked before `_ail_bs`), so no
prelude edit was needed and the conflict resolution keeps that fix.  Added the accepted
`AIL_CURRENT/test_ail_qtest4.py` (the wrong-type bytes/bytearray cases at normal, narrow,
negative and zero widths, plus a str control) and registered it in `ail_check.MODULES` after
`test_ail_fuzz51`.  `tools/diff_ids.py` is not present on this tree; `tools/update_manifest.py`
was run and `--check` passes.  Probes `/tmp/probes/q4_direct.py`, `q4_routes.py`,
`q4_str_control.py` and `q4_valid.py` (direct, argument/list/attribute/dict routes, valid and
empty/multi-byte fills, bytearray receivers, str control) match CPython on both builds.  Tests:
test_ail_qtest4, test_ail_pre182, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3.
## 2026-10-26 - re-apply fuzz28: class-body comprehension read through the class (job-rbrbfuzz28-10262128)

Re-applied the accepted fuzz28 change on the current tree. A class-body list/set/dict comprehension
is a class attribute; CPython reads it as `C.ys`, but a comprehension that uses a class-scope name
cannot be built here. `_init_class_attrs` now refuses that evaluation by name (`reading the class
attribute C.ys through the class`) instead of failing with an unrelated name error, and the class
attribute read through a class does the same when the shared slot was not filled, but only when the
value is not a literal. The current tree's module-lifetime slots and computed values (including
comprehensions over module-level names) are unchanged, so `test_ail_fuzz29`'s definition-time,
shared and inherited class attributes still work. Added `test_ail_fuzz28.py` and registered it in
`ail_check.MODULES`. Probes in `/tmp/probes`: `f28_literal`, `f28_computed`, `f28_inherit_alias`,
`f28_shadow`, `f28_routes` and `f28_bounds` match CPython on both builds; `f28_read` is refused by
name on both. `f28_read_method` (a read inside a method) is refused by name with `name 'x' is not
defined` on both. Tests on the final tree: `test_ail_fuzz28`, `test_ail_fuzz29`, `test_ail_pre170`,
`test_ail_pre227`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (7 modules,
40 tests, 0 failed, 1 skipped for no zig).

Follow-up after the full suite: the new refusal must not hide a value-specific refusal. Both catch
sites now re-raise an `Unsupported` that already carries a `source_line` -- the int64 constant-range
refusal that `fold_int_constant` raises -- so `class C: x = True << 64; print(C.x)` keeps
`outside the signed 64-bit range` on both builds instead of being reported as a non-literal class
attribute (the `test_ail_pre201` / `test_ail_pre241` attribute cases). A plain undefined-name
failure inside a comprehension carries no source line and is still turned into the class-attribute
refusal. Tests: `test_ail_fuzz28`, `test_ail_fuzz29`, `test_ail_pre170`, `test_ail_pre201`,
`test_ail_pre227`, `test_ail_pre241`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3` (9 modules, 45 tests, 0 failed, 1 skipped for no zig).
## 2026-10-26 - re-apply fuzz4: dict hashing and literal order (job-rbrbfuzz4-10262129)

Re-applied the accepted fuzz4 change on top of this tree.  Both sides' fixes are kept: the
accepted object-runtime hashing work and literal-order lowering were applied cleanly; the
conflicts were only the module registry, shard list, DEVLOG and DIFFERENCES rows, where this
tree's newer entries are kept alongside the fuzz4 rows (renamed to this branch's ids).

The change makes `dict.pop`/`setdefault` hash a key once (and skip hashing on the empty-dict
`pop` fast path), makes `copy`, `update(other_dict)`, `popitem` and `dict(d)` reuse stored
hashes, and makes the general path's dict/set literals evaluate every key/value/element before
hashing any of them.  `test_ail_fuzz4.py` is registered in `ail_check.MODULES` and
`ci_shards.json`.

Probes in `/tmp/probes` (`f4_hash_once`, `f4_copy_update`, `f4_literal_order`,
`f4_collisions`, `f4_nested_containers`) cover hit/miss `pop`/`setdefault`, the empty-dict
fast path, copy/update/dict/popitem, colliding `__hash__`, unhashable early literal keys with
later side effects, starred set literals, and values reaching a call through an argument, a
list item, an attribute, a dict value and an alias; all match CPython on both builds.
A colliding `dict(d)` variant exposed the already-recorded open `__eq__`-count difference
(`C?-job-rbrbfuzz4-10262129-4`); the retained probes avoid that known table-shape case.

`python3 tools/diff_ids.py` is not present in this tree (or in the accepted job), so it could
not be run.  `python3 tools/update_manifest.py` updated the manifest for the touched files.

Tests on the final commit: `test_ail_fuzz4`, `test_ail_safetynet`, `test_ail_files` and
`test_ail_corpus_findings3` (4 modules, 354 s, 0 failed).
## 2026-10-27 - pre75 negative-r literal refusal removed for pre59 (job-rbpre75-10271421)

The accepted pre75 change refused a negative `r` literal at compile time on both builds. On the
integration tree that conflicts with `test_ail_pre59`, whose literal cases require the program to
build and raise `ValueError: r must be non-negative` at run time like CPython. The compile-time
refusals in `itlib.py` and `pyboxed2.py` are removed; the runtime raise in `cruntime.py` stays, so
a literal and every dynamic route (argument, list item, attribute, dict value, keyword) now raise
the ValueError on both builds. `test_ail_pre75.py` now checks the literal runtime result instead of
a refusal, and the pre126/pre137 programs use direct negative literals again. `test_ail_pre59.py`
is registered in `ail_check.MODULES`. Probes `pre59_lit`, `pre59_routes`, `pre59_gen` and the
feature-free `pre75_unrelated` match CPython on both builds.

## 2026-10-26 - pre75: itertools negative r (job-pre75-10241832)

`itertools.permutations` / `combinations` / `combinations_with_replacement` on the general
path returned `[]` for a negative `r`; CPython consumes the iterable and then raises
`ValueError: r must be non-negative`. The runtime helpers now raise it, and the default
build's `list(...)` collection of the same shape no longer emits invalid C: a negative `r`
literal is refused by name at compile time on both builds, while a non-literal negative
`r` (argument, list item, attribute, dict value) raises the ValueError on both. Added
`AIL_CURRENT/test_ail_pre75.py`; probes are in `/tmp/probes/pre75_*.py`. The pre137 catch/order
program now passes its direct negative `r` through a computed value, because that literal is
refused at compile time; its runtime and pool-order checks are unchanged. The pre126 bounds
program does the same for its empty-pool negative-`r` cases.

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

## 2026-10-26 - pre27: an optional import is refused by name at its own line

Re-applied the accepted pre27 change on the current integration tree. `try: import html ...
except ImportError:` reached the general emitter's try check, which refused `ImportError` as an
unsupported caught exception type without a position. The check now names the guarded import
(`import of 'html' guarded by except ImportError`), points at the import line and column, and says
to move it to the top of the file; `ModuleNotFoundError` gets the same message. Other unsupported
caught types are located at their `try` instead of printing no location. `except Exception` is
unchanged. Added `AIL_CURRENT/test_ail_pre27.py` (nine refusals, both builds, plus the accepted
`except Exception` program).

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
## 2026-10-26 - suite fix: refresh C pins for noreturn traps (job-perf3-10270015)

The accepted perf3 change adds two `__attribute__((noreturn))` forward declarations to the
emitted runtime, so the full generated C for every program now differs from the old baseline.
`test_ail_numeric_bindings` and `test_ail_record_initializers` pinned the pre-change bytes and
failed even though the programs' behaviour is unchanged. Refreshed their five scalar hashes; the
only C difference from the old pins is the two intended declarations. Also carried the upstream
`bench/compare.py` `fmt` fix (already on integration, this branch predated it) so
`test_ail_pre110` passes. Probes `/tmp/probes/p_*.py` (no trap, sources, nested, return, uncaught)
match CPython in both builds.

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
## 2026-10-26 - utf8_stream: refresh the standard source API pins (job-perf4-10270016)

The UTF-8 tail-check change added `_utf8_tail_complete` to `utf8_stream.ail`, but
`STANDARD_SOURCE_API.json` still pinned the old bytes (`e1625b22...`), so `export_sdk`
refused every SDK export with `stale or missing standard API dependency`. This broke the
SDK, grid-return and environment tests (and cascaded into the other modules listed by the
integrator). The catalog's module row and `dependency_pins` entry now carry the actual
SHA-256 (`24bc7059...`); the declared API is unchanged. No compiler or runtime behaviour
changed. The perf4 UTF-8 and loop-inlining changes stay as they were.

Tests on the final commit: the ten modules named in the task that exist here (minus the
later `test_ail_pre110`, which is not in this branch) plus `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3` pass. On a current `origin/integ`
worktree with the two perf4 code changes applied, all ten named modules, including
`test_ail_pre110`, pass (10/10, 231 s).

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
## 2026-10-24 - pre126: itertools `r` validation (job-pre126-10242351)

The first still-differing item in the job-pre101 review was the general path's negative
`r`: `permutations`, `combinations` and `combinations_with_replacement` returned `[]`
instead of raising `ValueError: r must be non-negative`; the same code read `r` as a raw
int64 field, so a float, str, None, list, tuple or bytes was also accepted.  Both general
emitters now pass the `r` object to one runtime converter (`ail_it_r_index`), which checks
the type and sign; `permutations` keeps treating a None `r` as "not given".  Added
`AIL_CURRENT/test_ail_pre126.py`; probes in `/tmp/probes/pre126_r_bounds.py`,
`pre126_r_types.py` and `pre126_r_sources.py` match CPython on both builds.

## 2026-10-24 - cov7: the census's internal-crash refusals now build

The gdev census (510 programs, `AIL_NO_CACHE=1`) refused 53 before this job.  Grouped by the
first line of the build output, the most common group was the 3 internal tracebacks (not
deliberate refusals): two programs using `functools.partial` crashed in
`pyboxed2._refuse_lambda_forward_defaults` because the general path's partial rewrite made
`Lambda` nodes without a line number, and one visitor program crashed in
`pyfunc._dispatcher` with `KeyError: 'Visitor__visit_directory'` because an abstract base method
(removed as a stub) was chosen as the dispatcher's representative.  The partial rewrite now
copies locations onto both lambdas, and the dispatcher falls back to the first concrete
implementation when the base has no body.  `g17_004`, `g17_024` and `g13_036` now compile and
print what CPython prints on both builds; the census refused 50 afterwards.  Added the positional
partial program to `test_ail_silent6.py` and an abstract-visitor hierarchy to
`test_ail_typed_inherit.py`.
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
## 2026-10-24 -- pre26: repr(e.args[i]) keeps the argument's kind

On the typed path `e.args[i]` reads as text, so `repr(e.args[i])` repr'd that text: a
`ValueError(3.0)` handler printed `'3.0'` where CPython prints `3.0`, and int, bool and None
arguments were quoted the same way.  The handler rewrite now lowers `repr(e.args[i])`,
`f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor that formats
the stored argument (a str keeps its quotes, a number does not).  Both builds agree with
CPython; `test_ail_pre26.py` keeps the probe, including negative and out-of-range indexes.
## 2026-10-24 - pre27: an optional import is refused by name at its own line

`try: import html ... except ImportError:` reached the general emitter's try check, which refused
`ImportError` as an unsupported caught exception type without a position. The check now names the
guarded import (`import of 'html' guarded by except ImportError`), points at the import line and
column, and says to move it to the top of the file; `ModuleNotFoundError` gets the same message.
Other unsupported caught types are located at their `try` instead of printing no location.
`except Exception` is unchanged. Added `AIL_CURRENT/test_ail_pre27.py` (nine refusals, both builds,
plus the accepted `except Exception` program).

## 2026-10-24 - job-rbfuzz4-10240913 (dicts, sets, comprehensions)

Re-applied the accepted fuzz4 change on top of this tree, keeping both sides' fixes.

Ran 240 generated programs (dict order churn, set algebra/subset churn, set range churn,
comprehension and update/delete templates) plus ~60 hand-written edge programs and 8 probes in
`/tmp/probes`, each with `bash ~/tools/cmp.sh` on the general path and the default build.

Fixed two silent-difference causes:

1. Dict operations on stored keys re-ran `__hash__`: `pop`/`setdefault` hashed twice, and
   `update(other_dict)`, `copy`, `popitem`, `dict(d)` re-hashed.  The object runtime now uses one
   hash for pop/setdefault, clones the entry table for `copy`, removes the last entry directly
   for `popitem`, and reuses stored hashes for update/dict.  `dict.pop` on an empty dict also
   takes CPython's no-hash fast path.
2. Dict and set literals on the general path hashed each element as it was evaluated.  CPython
   3.12's `BUILD_MAP`/`BUILD_SET` evaluate every key/value/element first, then hash/insert; the
   general lowering now does the two phases.  The typed literal emitter still inserts per pair,
   but its keys are scalar int/str/bytes/float values with no user `__hash__`, so no silent
   stdout difference was observed on that path.

Remaining (not fixed): same-size dict mutation during iteration still differs by path/declared
structural-mutation rule; `reversed(dict)` and `dict | dict` are accepted then stop at run time;
and `dict(d)` may call a user `__eq__` a different number of times than CPython when the source
table has a particular internal shape (CPython's own count depends on key-table sharing).
`test_ail_fuzz1` could not run locally because `difffuzz` is not in this snapshot; the required
and targeted modules were run on the final commit.
## 2026-10-26 - pre61 suite continuation (job-pre61-10270754)

Continued job `pre61` on today's integration tree.  The integration tree independently gained
the same `functools.partial` location fix in cov7 (`genlib._partial` copies the `partial()` call's
location onto both synthetic lambdas and then runs `ast.fix_missing_locations`), so the retried
`test_ail_pre61` and `test_ail_safetynet` pass there; applying the older pre61 diff would have
rewritten those lines without `fix_missing_locations` and conflicted with cov7.  `genlib._partial`
is now byte-identical to the integration version, so the fix and its test apply without a
conflict and keep both sides' behaviour.  Verified `test_ail_pre61`, `test_ail_safetynet`,
`test_ail_files` and `test_ail_corpus_findings3` on this commit.

## 2026-10-24 - pre61: functools.partial with bound values (job-pre61-10241247)

The first pre39 case, keyword `range(x=1e300)`, is already refused by name on this tree
(`range() got an unexpected keyword argument 'x'`), so nothing changed there. The next case did
reproduce: `functools.partial(f, 1)` / `partial(lambda a, b: a * b, 6)` made the general path build
synthetic lambda closures without source locations, and the lambda scan stopped with
`AttributeError: 'Lambda' object has no attribute 'lineno'` (pyboxed2.py). `genlib._partial` now
copies the `partial()` call's location onto every lambda it builds, so partials of defs and lambdas
with positional, keyword, empty and run-time bound values compile and match CPython on both builds;
values through an argument, a list item, a dict value and an attribute are covered. The shapes the
general path already refused (a non-def/lambda callable, too many bound arguments, a non-trailing
keyword, `*args`, no function) remain refused by name. Added `AIL_CURRENT/test_ail_pre61.py`
(4 matching programs, 5 refused programs, both builds).
## 2026-10-26 - fuzz71 rebase: keep the fix clear of the integer/repr `#` hunk

Today's integ added `ail2f_alt_point` (alternate `#` on the type-less float repr form) next to
the v2 float body.  Re-applying fuzz71's buffer fix as-is conflicted there, so the conflict left
either the old 400-byte `%e` buffer or dropped the new `#` handling.  The fix now defines
`ail2f_body_need` above `ail2f_signstr` and frees the heap `%e` body inside each of the two
branches instead of at the shared `return`, so the fuzz71 hunks no longer touch the lines the
`#` change added; the new test registration is likewise away from the newer module names.
`test_ail_fuzz71` and `test_ail_safetynet` pass on a clean 3-way apply of this branch onto
integ 8346862.

## 2026-10-24 - fuzz71 review fix: v1 ail_obj_format and manifest pin

Applies the remaining v1 `ail_obj_format` hunk: its fixed-point float path formatted into
`char buf[64]` and now sizes from the would-be length (stack first, heap when it does not fit),
mirroring the v2 path that already had that fix.  Regenerates `MANIFEST.json` so
`test_ail_fuzz71.py` is pinned, and corrects the entry below: the "already fixed" general path is
v2 only.

## 2026-10-24 - fuzz71: fixed-point float formatting no longer truncates at a buffer

The typed core's `ail_fmt_spec_float` formatted into `char buf[512]`, the general path's
`ail_obj_format` into `char buf[64]`/`char buf[66]`, and the full runtime's
`ail2f_float_body` into `char body[400]` after clamping a precision above 300 to 300.
CPython prints every digit a huge value or a large precision needs, so those paths produced a
short string; where `snprintf`'s would-be length was trusted, they also read past the stack
buffer.  Each path now sizes its buffer from the would-be length (stack buffer first, heap
when it does not fit) and the runtime's exponent helper does the same.  The v2 general path's
`ail_obj_format` already had an equivalent heap fix on this tree; the v1 one was fixed in the
review-fix entry above.
`test_ail_fuzz71.py` builds `f"{1e308:.0f}"`, `f"{1.5:.600f}"`, `%.600f`,
`"{:.600f}".format(...)`, negative values and widths wider than the result on both builds.
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
## 2026-10-24 - pre68: literal `%d`/`%i`/`%u` with a float

A literal format string such as `"%d" % 3.7` was lowered to `ail_obj_format`'s `d` spec, which
rejects a float (`TypeError: unsupported format string passed to non-int`) on both the forced
general build and the default build. CPython truncates the float toward zero for `d`, `i` and `u`
and raises `OverflowError` / `ValueError` for infinity / NaN. Those three conversions now fall
back to the run-time formatter (`safetyrt.FMT`) unless the argument is provably an `int` or
`bool`; widths, signs, `%%`, ints/bools, and values through an argument, list item, attribute and
dict value are covered by `AIL_CURRENT/test_ail_pre68.py` (2 programs, both builds).
## 2026-10-24 - pre70: a run-time None separator splits on whitespace

`str.split`/`str.rsplit` only recognised a `None` separator that was a source literal.
A None reaching the call through a variable, a list item, a dict value, an attribute or
a function argument was read as an empty string separator, so both builds raised
`ValueError: empty separator` where CPython splits on whitespace (`.split(sep)` with
`sep = None` is `.split()`). The object-level helpers in
`python/pkg-v12/cruntime.py` (`ail_meth_str_split`, `ail_meth_str_rsplit`,
`ail_str_split_sep`, `ail_str_split_sep_into`) now switch to the whitespace mode when
the separator is the None object; this also covers the pooled `x = recv.split(sep)`
assignment path. Non-str separators still raise CPython's TypeError and `sep=""` still
raises ValueError. `test_ail_pre70.py` keeps the variable/list/dict/attribute/argument
cases and maxsplit 0/1/-1/-2/100, empty and whitespace receivers compared with CPython
on both builds.
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
## 2026-10-24 - qtest2: str.split/rsplit maxsplit=None

`"a b".split(maxsplit=None)` and `"a,b,c".rsplit(",", maxsplit=None)` silently used
maxsplit=0 on both builds (the general path read the None object's int slot), so the
first kept one piece and the second kept the whole text. CPython raises
`TypeError: 'NoneType' object cannot be interpreted as an integer`. A literal None
maxsplit is now refused by name in `python/pkg-v12/pyboxed2.py`; the unified build falls
back to that refusal. `test_ail_qtest2.py` keeps the surrounding whitespace-run,
tab/newline, maxsplit 0/1/-1 and empty-string shapes compared with CPython on both builds.

Other differences seen while probing (not changed): a separator that is None at run time
through a variable/list/dict gives `ValueError: empty separator` where CPython splits on
whitespace (`None` is only recognised as a literal), and a maxsplit constant above
int64 (for example `2**63`) fails to compile with "integer overflow" where CPython raises
`OverflowError`.
## 2026-10-24 -- str.partition / rpartition reject non-str separators correctly (job-qtest3-10241647)

Probing `str.partition` / `str.rpartition` on both builds found one stdout difference:
`"a-b".partition(sep)` with `sep` an int, float or None printed `TypeError: object of type
'int' has no len()` (the tuple helper ran `len(sep)` before `find(sep)`), while CPython says
`TypeError: must be str, not int`.  The helper now calls `s.find(sep)` / `s.rfind(sep)` first,
so the existing separator type check raises the right error; the empty-separator `ValueError`
is still checked before the not-found branch.  Bytes, list, str-subclass and multi-character /
repeated separators, argument/list/attribute/dict channels and a 100000-character input match
CPython on both builds.  `test_ail_qtest3.py` keeps the probes.  No other differences were seen.
## 2026-10-24 - qtest5: zfill/expandtabs receiver evaluated twice (job-qtest5-10241814)

Ten small zfill/expandtabs programs (signs, empty strings, widths below the length, tab sizes
0/1/8, tabs after newlines, dynamic/list/attribute/dict values, wrong types) matched CPython on
both builds, with one exception:

    i = [0]
    def nxt():
        i[0] += 1
        return i[0]
    print(repr(("-" + str(nxt())).zfill(nxt())))   # CPython '-1' 2, both AIL builds '-02' 3

The receiver `("-" + str(nxt()))` ran its side effect twice: `_str_concat_flatten`
(pyboxed2.py) evaluated the concat's leaves while deciding whether to flatten, then returned
None for a two-leaf `a + str(b)` it could not prove (the `str(nxt())` argument's kind is not
static), leaving the emitted code behind while the normal `+` path evaluated the leaves again.
The flatten plan (per-leaf format and operand) is now computed before any emission, so the
decision cannot leave side effects behind. `test_ail_qtest5.py` keeps the case and the area
comparison. Other differences seen (not fixed): a str method accessed as a value
(`f = "a\tb".expandtabs`) raises AttributeError, `str.zfill(s, w)` is refused as "name 'str' is
not defined", `zfill(width=...)` / `expandtabs(tabsize=..., positional)` are refused by name,
and a non-BMP literal is still a 16-bit-runtime refusal.
## 2026-10-24 - fuzz54: do not type a mixed display from its first element

`Exprs.seq_type` kept the first known element type and dropped later, incompatible ones. With a
mixed list display such as `[["a"], {"x": "y"}]`, the tuple pass typed it `list[list[str]]`; when
another statement (`repr`) made the pass emit its rewritten source, `print` used the list-of-list
helper and rendered the dict as its keys. Incompatible non-numeric element types now refuse the
tuple rewrite, leaving the source as written so the generic path prints the real objects. The
numeric family still falls back as in job-rbfuzz54, and `bool` mixed with `int` types as `int`.
Added `test_ail_fuzz54.py` and registered it.
## 2026-10-24 - job-rbfuzz63-10241240

- Re-applied the accepted fuzz63 change on this tree. The sign-of-zero float remainder fix is already present here through the CPython `float_divmod` helpers (`ail_obj_ffloormod` / `ail_obj2_ffloormod` use `copysign(0.0, divisor)` for a zero remainder), so both sides' fixes are kept: `-0.0 % 1.0` is `0.0` and `0.0 % -1.0` is `-0.0` on the general, unified and boxed paths. Added `AIL_CURRENT/test_ail_fuzz63.py` (literal, argument, list, dict, attribute, augmented-assignment, chained and nonzero boundary cases on both builds) and registered it in `ail_check.py`.
## 2026-10-24 - fuzz81 re-apply: runtime KeyError keeps the raw key

Re-applied the accepted fuzz81 change on the current tree. The runtime already carries an
equivalent `ail_raise_key_arg` helper (the branch's `ail_raise_key`): a missing dict key in `d[k]`,
`d.pop`/`del d[k]`/`popitem` and `set.remove`/`set.pop` stores the raw key as the exception
argument. `str(e)` stays `repr(key)`, while `repr(e)` is `KeyError(repr-key)` and `e.args` is
`(key,)`, matching CPython for str (including "" and quotes), int (0, -42, 2**62), tuple, bool,
None and float keys; empty `popitem`/`set.pop` keep their message argument. Added the branch's
`test_ail_fuzz81.py` (both builds against CPython); probes in `/tmp/probes` covered argument,
list-item, attribute and dict-value routes. `tools/diff_ids.py` is not present in this tree.
## 2026-10-24 - any/all generator expressions stop at the decisive element (job-pre13-10240022)

The general path's fused `any`/`all` generator expression walked every element even after the
answer was known, so `any(hit(log, a, b) for a, b in pairs)` called `hit` for every pair; CPython
stops at the first truthy element. The fused loops now jump to one label at that element (the same
shape as the existing `next(genexp)` fusion), so tuple/list destructuring targets, filters and
nested for-clauses all stop where CPython does. Empty and no-decisive-element sequences keep the
old result. Added `AIL_CURRENT/test_ail_pre13.py`, which builds the cases on the general path and
the default build and compares both with CPython 3.12.

The fused emitter in this tree already short-circuited equivalently, so the code side of this
re-application was a no-op; the regression test and its registration are new.
## 2026-10-24 - re-apply assert message value fix (job-rbpre15-10241827)

Re-applied the accepted pre15 change (assert messages keep their own value in `e.args`) on top of
the current tree: the typed path (`pyfunc.py`) now stringifies a numeric message only when no
exception text is read (`exctext.ACTIVE` false), and the general path keeps the message object for
`e.args`. The conflict in `pyboxed2.py` was resolved by keeping the current tree's unconditional
object form, which already covers the accepted change's semantics (and tuple/list/dict messages);
`test_ail_pre15.py` and the pre15 DIFFERENCES row are imported as accepted.

## 2026-10-23 - assert message keeps its value in e.args (job-pre15-10240045)

`assert False, 42` now raises `AssertionError(42)`, so `e.args` is `(42,)` (CPython's value), not
`('42',)`. The typed path converts a numeric message with `str()` only when the program does not
read `e.args`; otherwise it builds the exception with the number itself. The general path now keeps
the message value for `e.args` whenever the program reads it (also covering list/dict/tuple
messages). Uncaught output stays `AssertionError: 42`. New `test_ail_pre15.py` covers int, float
and bool messages, int64 limits, negative/empty/str messages, and values arriving through an
argument, a list item, an attribute and a dict value, on the typed and general paths.
## 2026-10-24 - register the test modules missing from the full suite (job-regmods-10240915)

47 `AIL_CURRENT/test_ail_*.py` modules were absent from `ail_check.MODULES` (the list
`par_check` and the CI shards run); the task's `test_ail_modules3` does not exist in this
export. Each was run once; 46 passed and are now registered. `test_ail_callable_values` was
left out because two of its own tests fail in this tree: the uninitialized-callback program
raises `UnboundLocalError` instead of printing `71`, and a Callable struct field is accepted
where the test expects a refusal. `tools/ci_shards.py --update` adds the new modules to the
shard map, and `tools/update_manifest.py` pins them.

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
