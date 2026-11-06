## 2026-11-06 -- fcclass1: list[X] fields from object literals, empty list fields typed by their appends (job-fcclass1-op1106)

str, list[int], list[float], list[str] and annotated list[X] fields already typed. What sent shtok1's
`Tokenizer` (and the AST ports after it) to the general path was `self.toks = [Tok(...)]` -- a list literal
of objects -- and an unannotated `self.xs = []` filled with str or objects by methods (it defaulted to
list[int]). `_compile_init` now types the first as `(OLIST, X)` (`_object_list_literal_kind`, common base
allowed) and the second from `_field_list_hints`: `self.<f>.append(...)` in the class's own methods, a str
literal / f-string -> list[str], `X(...)` -> list[X], only when those agree; other appends are not read
and every append is still type-checked, so a field given two kinds is refused by name. The old refusal
text (`a field is int64, float or bytes only`) now says what a list field holds. SEMANTICS.md section 25.

Same C: 44 programs (pyproof typed rows that emit program.c, lab/compare/src main.py + typed.py, and the
language_examples that build) byte-identical to origin/integ; 0 differ. Probes: `test_ail_fcclass1.py`
(typed-only and AIL_UNIFIED_FORCE=1, vs CPython). Next blocker for ailtok: `Tokenizer.__init__` has
statements other than `self.<name> = <expr>`; constructor calls to a class defined later in the file.
## 2026-11-05 -- bce s6: field values in the range pass (job-bces6-11060753)

All of it behind `bce_enabled()` (`AIL_BCE=0` emits C byte-identical to the base tree for
ledger_bin):

- (a) `ir/passes/ranges.py` `number_fields()`: each `field.get` is numbered to the earliest earlier
  `field.get` of the same object SSA value and field name when, on every path between them, no
  instruction may write that field -- a `field.set` of the name on **any** object of that struct
  (objects may alias), a call whose effect summary may write the struct's fields or is unknown, or
  a `try` (its outlined body). `if` arms merge only entries both arms keep; loops iterate to a
  fixed point whose entry state keeps a field only when the initial state and every back edge
  agree, so a store anywhere in the loop kills it on the back edge, and nothing survives a loop
  afterwards. The earlier load's facts, including its guard's refinement, then apply to the later
  one.
- (b) every `field.get` of a field listed in `facts['fields']['nonneg']` (bce s4) starts at `lo = 0`.
- (c) `lengths_of` also returns the `bytes.len` of every load in the same numbered class, so a
  `bytes` field's length is one value across two numbered loads.
- (d) probes in `test_ail_bce.py`: `field_cursor_ge` (lengths 0, 1, exactly at the end, one short),
  `field_cursor_gt` (a `>` guard, not proven), `field_cursor_bump` (a call moving `pos`, not
  proven), `field_cursor_alias` (`r2.pos = 99` through an alias, not proven), `field_cursor_negative`
  (the s4 fact retired by a negative store; `r.data[-1]` reads the last byte as CPython does),
  `field_bytes_len`, `field_cursor_bigtext`.

Number: ledger_bin/ail 5,394,586,605 -> 5,233,458,638 instructions (ratio 0.97013, -2.99%);
stripped binary 55,512 -> 55,512 bytes; same stdout and exit. Below the lane's 6% target and its 4%
stop line, so per the stop rule the work stopped instead of changing how `try` functions are
handled: the remaining hand-edited checks are in `main`, which `passes.optimize` skips
(`{"skipped": "try"}`), so no range pass sees line 105; `AIL_BCE_EXPLAIN` on ledger_bin is empty.
tally_lang/ail also changed: one `ail_list_span_get` check and three `ck_add` elided, stripped
71,896 -> 67,800 bytes, same stdout (sha256) and exit. The other compare tasks' C is identical.
Tests: test_ail_bce 10/10, range_checks, ir_s1, ir_s3, ir_s3b, borrowed_owner, boolfield,
safetynet, files, corpus_findings3.

## 2026-11-05 -- rbbces4: two field-fact soundness holes closed, re-applied (job-rbbces4-11052320)

Re-applied the accepted `bces4` change (`876f22ae4e88`..`job-bces4-11051929`). `fieldfacts.py`
built `bytes_fields` from struct names rather than bytes field names, so an attribute whose name
matched a struct that owned a bytes field (an `R.vals` list next to a `struct vals { data: bytes; }`)
was read as a non-negative bytes index. It now collects the unambiguous bytes *field* names, and a
genuine bytes index (`r.data[0]`) still counts.

`_field_still_nonneg` recognised only single-target `Assign`, `AnnAssign` and `AugAssign`, and
silently skipped every other store of the field. It now walks the field's `Store`/`Del` attributes
directly: a tuple/chained target, a `for`/`with`/comprehension target, `del`, an operator other
than `+=`/`-=`, or any other unclassified form retires the fact.

No pass reads `facts['fields']`, so generated C is unchanged. Added regression cases to
`test_ail_bce.py`: the bytes/struct-name collision, a real bytes index, and tuple/chained/`for`
stores. `tools/diff_ids.py` is not present on this tree, so only `update_manifest.py` ran.
## 2026-11-05 -- shseed1: the C-seed estimate comes from the corpus, not the live compiler (job-shseed1-11060533)

`test_ail_selfhost_seed` failed when the shseed1 change was applied to today's integ: `--report-only`
counted the compiler's lines and AST nodes from the working tree, so every merged compiler edit
moved the computed estimates away from the numbers recorded in `lab/selfhost/SEED.md` (the
"estimates" comment no longer matched on integ: binary high 5,730,451,312 vs 5,673,710,177).  `--run` now records the compiler scope (`files`, `lines`, `ast_nodes`,
`top_functions`, `top_classes`) in `lab/selfhost/seed_corpus.json`, and `--report-only` reads that
snapshot; the committed snapshot is the one the SEED.md numbers were measured with, so the file is
unchanged and the test is stable across later compiler edits.  A corpus without the snapshot is
refused by name ("re-run --run to record them").  `test_ail_selfhost_seed` also asserts the
snapshot is present and positive.  `test_ail_selfhost_seed` 2 OK on both this branch and a worktree
of today's integ with the change applied.

## 2026-11-05 -- refuzz95 suite fix: the typed KEYSORT names a NaN tuple key (job-rbprog18_rr1-11051321)

`test_ail_refuzz95` failed on `r_tuple` (default build): after the prog18 typed reach,
`sorted([(1.0, "a"), (nan, "b"), (0.5, "c")])` lowers to the typed KEYSORT path, whose float-column
NaN check raised a bare `ValueError`, while the test requires the "refuzz95" name for that shape.
The KEYSORT check in `python/pkg-v12/cruntime.py` now raises the same named `ValueError` message as
`ail_list_sort`'s boxed check, on both builds. NaN-free tuple sorts keep their stable order and the
typed `ail_flist_sort` stop stays a bare `ValueError` (by name only). The existing DIFFERENCES row
`C?-job-refuzz95-10300605-1` is updated; no new row is needed.

Probes `/tmp/probes/p1_nanfree_tuple.py` (sorts through a local, an argument, a list item, an
attribute and a dict value, empty/negative/-inf/tie/reverse/int tuples), `p2`-`p5` (NaN first and
second field, direct/reverse/key lambda), `p6`-`p9` (NaN tuple list through an argument, list item,
attribute and dict value), `p10` (NaN elsewhere, NaN-free sort unaffected), `p11` (float list NaN)
and `p12` (empty/negative/1-tuple) all match CPython or are refused by name on both builds.
`test_ail_refuzz95`, `test_ail_prog18`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`
and `test_ail_corpus_findings3` pass on the final commit.

## 2026-11-05 -- prog18_rr1 review fixes 3: bool result inference and INT64_MIN width

Two defects from the re-review, both on the default/typed build (the forced-general build already
matched CPython):

- A bool `max`/`min(..., default=...)` reached through unannotated parameters came back as `1`/`0`,
  not `True`/`False`.  `_is_bool_seq_expr` did see the parameters as bool (the call sites settled
  them), but boolkind's result inference ran before those parameters settled and never regrew a
  discarded candidate, so the helper was typed `-> int`.  `_infer` now reconsiders every result
  once the parameter and field facts are final, adding `bool` when all `return`s are bools (to a
  fixed point, since a bool result makes more returns bool).
- A nested width of `INT64_MIN` died with `allocation too large` instead of CPython's
  `ValueError: Too many decimal digits in format string` (which it raises for int, float and str
  before the str sign check, because `abs(INT64_MIN)` does not fit `Py_ssize_t`).  `_fmt_width_c`
  raises that ValueError instead of mapping the value to `INT64_MAX`.

`test_ail_prog18` gains two tests (18 total).  Probes p1-p10 under `/tmp/probes/` match CPython on
both builds.

## 2026-11-04 -- prog18: refresh the stale nested-format-spec refusal case

`test_ail_refusal_messages` still listed `f"{x:{w}.2f}"` as a refusal, but prog18's typed path now
builds a single nested width field (including a precision/type suffix) and matches CPython; the
refusal module's cases track the current refusals, not which programs are accepted.  The case now
uses `f"{x:{w}.{p}f}"` (a runtime width *and* precision, two nested fields), which the typed path
still refuses by name with the `write instead: a literal spec` hint.  `test_ail_refusal_messages`
3 OK and `test_ail_prog18` 16 OK on the final tree.

## 2026-11-04 -- sdkdiag1: text argument type errors report the call site again (job-sdkdiag1-11041645)
## 2026-11-04 -- pyr3fix: the hybrid accelerates unannotated str helpers again (job-pyr3fix-11050045)

`test_ail_cpython_hybrid`, `test_ail_prog2` and `test_ail_prog21` went red when pyreachs3c
(805ce9ba, #371) merged.  The cause was not the new declaration-level annotation/caller refusal
(that one is sdkdiag1's lane; its numeric-only `_explicit_annotation_conflicts` fix is already in
integ, and `test_ail_collections` is green on the base): `_owned_unannotated_str_fns` marks every
unannotated, terminating, str-returning helper as an owned-str function so a caller can adopt the
value.  `to_c`'s entry check then saw that INFERRED ownership and raised "the entry function
cannot return checked str" for each such helper when the hybrid analyses it as a standalone unit,
so pymix dropped `join`, `state_at`, `label` and `fmt` from the mix units entirely.

`to_c` now drops inferred ownership for the entry function only (`returns is None`); the entry
and every call site in that compilation then agree on the legacy out-parameter str ABI, exactly
as before pyreachs3c.  An explicit `-> str` entry (rewritten to `__ail_checked_str__`) is still
refused, because there the source itself asked for the owned ABI.

Counts, module by module (before = 805ce9ba^ 7a3b4522, after = this branch): hybrid 7/7 -> 7/7
(6/7 on integ), prog2 9/9 -> 9/9 (8/9), prog21 8/8 -> 8/8 (5/8), collections 13/13 -> 13/13.
`test_ail_pyreach_infer` 10/10, `test_ail_safetynet` 5/5, `test_ail_files` 18 (1 skip),
`test_ail_corpus_findings3` 2/2, `test_ail_argument_type_details` 16/16, and
`python3 -m compileall -q -j 0 AIL_CURRENT tools` clean.  Nine probes under `/tmp/probes/`
(unannotated str helper through concat, default, list/dict/attribute, argument, `%`, identity,
branches, int widths, script entry) match CPython on both builds.
## 2026-11-04 -- rbdifflib2: bundled `difflib` re-applied on the current tree (job-rbdifflib2-11050254)

Job `difflib2` was accepted against `327abd3`, and its diff no longer applied here. Re-applied
with `git apply`, keeping both sides where they conflicted:

* `AIL_CURRENT/python/pkg-v12/pyfunc.py`: the accepted hunk added `_site_override`, which dropped
  a `str` call-site claim on a parameter whose own annotation says something else. This tree
  already carries the same fix in a newer shape -- `_drop_text_overrides` before the claim is
  recorded, plus the same guard inside `_override_from_site` -- so the hunk was not added and the
  newer code stands unchanged.
* `AIL_CURRENT/manifest.d/*.txt` are generated; they were regenerated with
  `tools/update_manifest.py` instead of patched.

The change itself is the bundled `AIL_CURRENT/stdlib/difflib.py` (SequenceMatcher, Match,
get_close_matches, Differ, ndiff, restore, unified_diff, context_diff, diff_bytes, IS_LINE_JUNK,
IS_CHARACTER_JUNK), the twelve `lab/stdlib/difflib/` programs with their RESULTS.md and bench,
and `test_ail_std_difflib.py` registered through `tests.d/`. Ten of the twelve programs match
CPython 3.12 in the default and `AIL_UNIFIED_FORCE=1` builds; 04 uses a `**kwargs` call argument
and 12 uses `HtmlDiff`, both refused by name. See DIFFERENCES `C?-job-rbdifflib2-11050254-1`.

`test_ail_std_difflib.py` 2/2, `test_ail_safetynet.py` 5/5, `test_ail_files.py` 18/18
(one skip) and `test_ail_corpus_findings3.py` 2/2 pass. Six probes under `/tmp/probes/`
(matched blocks/opcodes/grouped opcodes/ratios, unified/context/ndiff/restore/diff_bytes and a
custom `dfunc`, `get_close_matches` and the junk predicates with values reaching them through
arguments, list items, attributes and dict values, empty/bytes/negative edges): five match
CPython on stdout and exit status in both builds, `HtmlDiff` is refused by name.

## 2026-11-04 -- sdkdiag1: text argument type errors report the call site again (job-sdkdiag1-11041645)

`test_ail_sdk.py::test_relocated_json_source_check_without_c_compiler` was red since ec5e1eda
(#361): `take("wrong")` against `fn take(x:int)` reported `line 2, column 1`,
`location_kind: function_declaration`, `operation: parameter`, `signature_override`, and the
pyfunc message rather than the call-site statement at `line 3, column 17` with an `argument`
record.  The export carries one squashed commit, so `git bisect` was not possible; tracing the
two suspect brace-to-Python conversion jobs instead pointed at propagation: `_claim` now returns
`str` for the literal, `_propagate_signatures_pass` feeds it to `_param_kinds`, and
`_explicit_annotation_conflicts` raised the numeric-style `signature_override` refusal before
`_call_user_func` could refuse the argument at the call.  `_explicit_annotation_conflicts` now
raises only for a NUMERIC caller claim (int/float); text, bytes and list claims are dropped so
the existing per-call guard reports the argument, callee, parameter index, expected/actual and
the original `.ail` statement position through `source_map`.  Numeric override behaviour
(float/int, int/str annotation conflicts) is unchanged.

`test_ail_sdk.py` 30/31 -> 31/31; `test_ail_argument_type_details.py` 11/15 -> 16/16 with the
new source-position regression; 73 tests across test_ail_safetynet, test_ail_files,
test_ail_corpus_findings3, test_ail_type_details, test_ail_source_check,
test_ail_float_argument_widening and test_ail_refusal_messages pass (one skip).
`compileall -j 2` passes with `language_examples/binary_numbers.py` excluded: its line 2 comment
contains `encoding:` and is the separate PEP 263 break PR #376 fixes.  Added DIFFERENCES row
`C?-job-sdkdiag1-11041645-1`.

## 2026-11-04 -- fz226: constant integer subtraction beyond int64 is already refused by name (job-fz226-11041145)

The daily fuzzer (seed 2076102845, modes default+ir) printed `((3 - -9223372036854775807) ** 1)`
and recorded `DIFF|cpython='9223372036854775810' ail='287'`: the int64 run stopped at the
subtraction after the `finally` had printed 287, so stdout was not a prefix of CPython's.

On this tree the constant expression is already refused by name at compile time
(`int64 constant out of range` / `int64 constant expression out of range`), so the silent DIFF
does not reproduce and no compiler change was needed.  In-range neighbours match CPython on the
default and `AIL_IR=1` builds.  A value that reaches the subtraction through an argument, a list
item, an attribute or a dict value cannot be folded: it keeps the declared int64 overflow
contract (exit 1, `integer overflow`, stdout a prefix of CPython's), and `--exact-int` matches
CPython.  Added `test_ail_fz226.py` (6 tests, default and IR, plus exact-int) and registered it
in `tests.d`; added DIFFERENCES row `C?-job-fz226-11041145-1`.  The load-time refusal exits 2,
which `lab/fuzz/run.py` currently classes as `crash` (it only counts exit 3 as `refused`); that
is a fuzzer-classification issue, not a silent language difference.  Final-state tests:
test_ail_fz226, test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.

## 2026-11-03 -- rails3: element-bounded range counters stay int64 (job-rails3-11040144)

`for j in range(a[s], a[s + 1])` used to give `j` a tagged `ail_tint` in the default int64 build,
paying `ail_tint_from_int64`/`ail_tint_add_i64` on every iteration; hoisting the bounds fixed it by
accident.  A range counter always lies between its start and stop, so when every argument's C storage
is int64 the counter is int64 too.  `bigcap._lp_range_value` now asks an emitter-supplied
`int64_oracle` and, when all arguments pass, proves the full int64 bounds; the IR oracle in
`ir/lower.py` accepts int constants, elements of int64 lists/bytes/maps, int fields and arithmetic of
those, and refuses tagged parameters, tagged values, the exact int mode and general-path values.  The
same call site is used by for loops and comprehensions.

`t3.ail` mode 0 falls from 181,761,363 to 101,801,376 instructions (mode 1: 101,821,363 ->
101,801,376, measured with callgrind I refs), and `fd`'s generated C now equals `fe`'s with no
`ail_tint`.  Probes `listbound`, `fieldbound`, `negstep`, `empty` and `bounds` match CPython on the
default and unified builds; the overflow probe stops loudly on both int64 paths and stays exact with
`--exact-int`, and the >2**64 list-element probe stays exact.  Added
`test_ail_range_element_bounds.py` and registered it in `tests.d`; the targeted modules,
`test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` pass on the final commit.

## 2026-11-03 -- fz220: round() of a constant float expression outside int64 is refused by name (job-fz220-11032207)

The daily fuzzer (seed 2076011178) printed `round((1e10 * 1e10))`.  On today's tree the seed already
classifies as the declared `overflow` (fz2 replaced the old uncatchable `round() result does not fit`
text), but `cmp.sh` still showed AIL stopping at the int64 boundary where CPython prints
`100000000000000000000`.  The pre54 refusal (`_refuse_round_at_int64_boundary`) only folded a float
literal with unary signs, so the generated arithmetic expression was not seen as a constant.

The refusal now folds constant numeric expressions (`+ - * / // % **`, unary signs, literals) with a
depth cap, an integer-size cap and no calls or names, and refuses when the rounded value is at or
outside int64.  In-range expressions, NaN/Infinity and zero division keep CPython's answers and
exceptions; runtime values (argument, list item, attribute, dict value) keep the declared overflow
contract.  With `--exact-int` the wide constants match CPython.  The fuzz seed now classifies as
`refused` in both default and IR modes; `/tmp/probes/fz220_min.py`, `fz220_neg.py`, `fz220_div.py`,
`fz220_in.py`, `fz220_bounds.py`, `fz220_edge.py` and `fz220_routes.py` match CPython or are refused
by name.  Added `test_ail_fz220.py` and registered it in `tests.d`.

## 2026-11-02 -- prog29 review 2: typed set/dict sources join the mutation guard (job-prog29-11022055)

Fixed the remaining defect in the set-comprehension guard.  `_setcomp_source_can_change` matched
only the untyped `LIST`/`FLIST`/`SLIST`/`SET`/`DICT` kinds, so a typed `set[int]`/`set[str]` field
(`ISET`/`SSET`) or a typed dict source (`IDICT`/`SDICT`/...) slipped through: the eager lowering
snapshotted it and `len({x for x in box.s if box.side()})` printed `2 3` at exit 0 where CPython
raises `RuntimeError: Set changed size during iteration` at exit 1.  The guard now also matches
every kind in `MAPS`, which covers the typed sets and dicts.  The default build falls back to the
general path for the refused function and matches CPython; `--strict` names the refusal.

`test_ail_prog29` gained typed-set-field mutation and typed-dict-source cases.  Probes
`p_sc_mutate_setfield.py`, `p_sc_mutate_dictfield.py`, `p_sc_mutate_setlocal.py`,
`p_sc_mutate_dictlocal.py` and `p_sc_typed_dict_call.py` match CPython in both builds; the strict
build refuses by name.  The `.keys()`/`.values()`-only limitation noted in the previous entry is
gone: typed set and dict sources are covered too.

## 2026-11-02 -- prog29 review fix: a set comprehension cannot silently walk a changed source (job-prog29-11022055)

Fixed the one defect from the review of the typed reach work.  `len({e for v in seq if c})` lowered
to an eager list comprehension and then walked that list, but a source that the element or a filter
changes (for example a filter that appends to the list field being walked) is snapshotted on the
typed path: CPython's iterator sees the append and yielded `3` where the lowering printed `2`.
Because making that exact would mean changing the field-list snapshot semantics the whole typed
path relies on, the shape is now a named compile-time refusal when the source is a mutable list,
float list or str list, or an untyped set/dict (including a dict `.keys()`/`.values()` snapshot),
and the element or any filter runs code (`Call`, `NamedExpr`, `Lambda`, `Await` or `Yield`).  The
typed set/dict kinds were missed here and are covered by the review 2 entry above.  Immutable
str/bytes sources, and comprehensions without code in the element/filters, still lower as before,
so `g17_026` stays wholly typed.  The default build falls back to the general path for the refused
function and matches the old sequence change (`3 3`); `--strict` names the refusal.

`test_ail_prog29` gained the mutation case.  Probes `p_sc_mutate_attr.py`, `p_lc_mutate_attr.py` and
`p_manual_for_mutate.py` show the default build now matching CPython (`3 3`) and the general build
unchanged; the strict build refuses the set-comprehension probe by name.  `lab/progfix/prog29.md`
now records the actual results for the parameter/local `len` shadows and the annotated-frozenset
parameter probe instead of claiming they were refused.
## 2026-11-02 -- packaging: PyPI distribution name is ailc (job-relpkgname-11030037)

The distribution is now `ailc`; the command stays `ail` and the import package stays `ail_lang`
(`python -m ail_lang` still works). The build backend writes `ailc-<version>-py3-none-any.whl` and
`ailc-<version>.dist-info/` while the wheel payload lives under `ail_lang/`. METADATA gained the
Homepage / Documentation / Issues `Project-URL` lines and classifiers for development status,
console, developers, Linux / macOS / Windows and Python 3.10-3.13 (13 classifiers, up from 2).
Every user-facing `pip install ail-lang` is now `pip install ailc`; INSTALL keeps one sentence
saying the PyPI project `ail-lang` is not AIL. `--version` prints `ailc <version>`. Publish nothing.

`test_ail_packaging` follows the new wheel and dist-info names, asserts the Project-URL lines and
the three Operating System classifiers, and scans `docs/` and `packaging/` for the old install
command. 19 packaging tests pass, `tools/wheel_check.py` passes, and the built wheel is
`ailc-0.1.0.dev0-py3-none-any.whl`.

## 2026-11-02 -- typed reach 12 fix: tuple local store/delete refused (job-prog12-11020843)

Review of 2c28c6a found that the list-compatible-use check counted any `name[...]` as an
indexing read, so a `Store` or `Del` subscript (`last[0] = 9`, `del last[0]`) was accepted:
the typed build mutated a tuple that CPython rejects.  Both `_local_tuple_uses_are_safe`
(`pyfunc.py`) and `itlib.check_nonescaping` now require the subscript itself to be in `Load`
context, so stores and deletes refuse by name and the general path matches CPython.  Probes:
`last[0] = 9`, `del last[0]`, and `a = perm; a[0] = 9` (also through an alias) are refused
typed and match CPython's `TypeError` on the default build; `test_ail_prog12` T5 covers all
three.

## 2026-11-02 -- typed reach 12: an empty tuple local from itertools is a list (job-prog12-11020843)

`t338` was the one hot function of its eight-program batch that this pass could move onto the
typed path: `last: tuple[int, ...] = ()`, assigned each `itertools.permutations` item, was refused
by the tuple pass (and the assignment was treated as an escaping use of `perm`).  A local empty
`tuple[int, ...]` whose uses are all list-compatible (index, loop, `join`, `len`, `sum`, `min`,
`max`, `sorted`, `any`, `all`, `set`, `list`, `index`, `count`, `in`) is now rewritten to
`list[int]`; a print, equality, slice, dict key, return or arbitrary call leaves the old named
refusal.  `itlib.check_nonescaping` follows a plain alias (`last = perm`) and checks the alias
target's uses with the same rules.

`tuple[float, ...]` stays refused on purpose: CPython's `sum(())` is int `0` while the typed
`list[float]` sum is `0.0`.  The other hot functions need the void-`main` hybrid ABI, dict values
that are containers, record/tuple-list parameters and results, or list-valued class fields and
methods; `lab/progfix/prog12.md` records each exact message.  `t338` now builds with
`AIL_NO_GENERAL=1` and matches CPython on all three inputs.

Added `AIL_CURRENT/test_ail_prog12.py`, registered via `tests.d/test_ail_prog12.txt`.  Probes in
`/tmp/probes` cover empty/non-empty permutation tuples, indexing/iteration/len/sum/sorted/any/all/
join, an itertools alias, reassignment from lists and tuple literals, float tuple locals (refused
by name), empty-output cases and unsafe print/equality/slice uses; all match CPython or are
refused by name on both builds.  Tests: test_ail_prog12, test_ail_tuples, test_ail_safetynet,
test_ail_files and test_ail_corpus_findings3.  The generated C of the ten `lab/compare` tasks is
byte-identical.

## 2026-11-02 -- prog19 fix: record t030 as not typed (job-prog19-11021530)

Corrected the `dev/t030.py` row in `lab/progfix/prog19.md`: its hot `main` and `<genexpr>` are not
typed. The default build takes the general path with `(int(x) for x in data[1:1 + n]) cannot be
walked inline here; bind it to a name first...`, and `AIL_NO_GENERAL=1` refuses with the same named
reason. The inline generator expression passed straight to `sorted()` is recorded as a follow-up; no
compiler change was made. Probes: the real program on `in2` matches CPython on the default build and
is refused by name on the strict build; the `random.choice` typed-path probes still match CPython.

## 2026-11-02 -- prog19 typed reach: random.choice of a tuple list unpacks on the typed path

The hot function of `lab/census/programs/gdev/g11_018.py` is `simulate_random_walk`; it was on the
general path because `dx, dy = random.choice(moves)` reached the typed emitter as an opaque
`moves[<index>]` subscript after the random lowering. The tuple pass runs before that lowering and
had no element type for `random.choice`, so it could not turn the unpack into field reads. It now
types `random.choice(seq)` as the element type of a list `seq` (the call itself is still lowered by
stdlib3.py), for `import random` and `from random import choice`. The whole program now builds on
the typed path under both IR settings and prints CPython's output; list parameters, aliases,
`from` imports, empty lists (IndexError), negative coordinates, float tuples and scalar lists were
probed against CPython on the typed and general builds.

`lab/progfix/prog19.md` records the cProfile hot functions of the eight programs and their typed
status. The other general-path programs stay recorded as follow-ups: t030's inline generator
expression passed to `sorted()`, g10's module-level dict of `list[int]` (and its optional list
result), t078's `ord` on a non-proven one-code-point str plus `next(generator, default)`, and
g14's typed `json.loads` with a declared result type.

Files: `python/pkg-v12/tuplib.py`, `python/pkg-v12/tupcalls.py`, `test_ail_prog19.py`.
Tests: `test_ail_prog19`, `test_ail_tuples`, `test_ail_genlib`, `test_ail_safetynet`,
`test_ail_files`, `test_ail_corpus_findings3`.
## 2026-11-02 -- prog7 re-apply verified after a skipped review (job-rbprog7-11022237)

Review 1 was skipped and named no defects. Checked the accepted prog7 change against this tree: the
bool-row typing in `nested_lists.py`, the element-class resolution in `boolkind.py`, the constant-tuple
loop lowering with the domination and rebinding fixes in `tuplib.py`/`tupexpr.py`/`tupstmt.py`, the
host-printability repr table in `tuplegen.py`, `test_ail_prog7`, and the DEVLOG/prog7 record are all
present. No source change was needed.

Probes in `/tmp/probes/` match CPython on both `cmp.sh` builds: `p_tuple_loop_basic`,
`p_tuple_constexpr`, `p_tuple_value`, `p_tuple_conditional`, `p_tuple_rebound`,
`p_tuple_empty_mixed`, `p_tuple_sources`, `p_bool_rows`, `p_bool_rows_param`,
`p_srepr_unprintable` and `p_srepr_bmp` (all non-surrogate BMP code points). Surrogate literals and
non-BMP string literals are refused by name; `chr()` of a surrogate differs identically on base
`8b1e28a8` (pre-existing). `test_ail_prog7`, `test_ail_tuples`, `test_ail_nested_lists`,
`test_ail_boolfield`, `test_ail_safetynet`, `test_ail_files` and `test_ail_corpus_findings3` pass;
`tools/update_manifest.py --check` passes.


## 2026-11-02 -- prog7 review fix: also forget a tuple name that another binding rebinds (job-rbprog7-11021443)

The domination fix restored the tuple-literal bookkeeping around control-flow bodies, but a name whose
one store is a tuple literal can also be rebound without an `ast.Name` store: an `except ... as t`
handler name, or a nested `def` / `class` name. The transform then reused the old literal inside the
handler or after the rebinding. `tupstmt.py` now drops those names (and import aliases, `del` targets,
and any name assigned in a branch once that branch ends) from the tuple-literal map, so only a
straight-line assignment that still holds the tuple is lowered. `test_ail_prog7` gained
TUPLE_EXCEPT_REBOUND and TUPLE_DEF_REBOUND.


## 2026-11-02 -- prog7 review fix: constant-tuple loops only lower a dominating assignment (job-rbprog7-11021443)

The reviewer found that the constant-tuple loop lowering trusted the last tuple literal assigned to a
name even when that assignment was conditional or inside a loop that may run zero times, replacing
CPython's `UnboundLocalError` with a pre-built list. `tupstmt.py` now restores the tuple-literal
bookkeeping around the bodies of `if`, `while`, `for`, `with` and `try` (and around loop `else`), so a
recorded assignment is used only when it dominates the loop in the same straight-line block. The
legitimate cases (assignment before an `if`, inside the same branch, or earlier in a loop body) keep
the lowering.

Probes `/tmp/probes/p_dom_*.py` (conditional, zero-iteration for / while, try before and after the
raise, nested unpack, scalar and tuple displays, both branches, and the legitimate dominating cases)
match CPython on both `cmp.sh` builds. `test_ail_prog7` gained TUPLE_CONDITIONAL.


## 2026-11-02 -- prog7: the hot function of g10_032 reaches the typed path (job-rbprog7-11021443)

Profiled the eight task programs under CPython 3.12 and kept the functions holding 80% of the own
time (`lab/progfix/prog7.md`). Four of them were already wholly typed (`t018`, `g15_018`, `t474`,
`g23_038`). `g12_034`, `g14_038` and `t184` stay general for features that need a new subsystem
(`random.Random` method defaults, `object`/`sys.getsizeof`, an unannotated `json.loads` result and
`Any`); the exact messages are in `lab/progfix/prog7.md` as follow-ups.

`g10_032`'s hot `largest_region` is typed now. Three compiler changes together:

* `nested_lists.py` types a bool row as `_AilRow_bool` (bool is a scalar element) instead of putting
  it in the same `_AilRow_int` as the grid's number rows;
* `boolkind.py` resolves a field store through `row[i]` to the row class named by the list's
  annotation or by a literal list of its constructors, so `_AilRow_bool.v` and `_AilRow_int.v` no
  longer reach each other (they share the field name `v`);
* `tuplib.py`/`tupexpr.py`/`tupstmt.py`/`tupcommon.py` lower `for dr, dc in directions:` over a
  tuple of constant displays to an annotated list built before the loop. It does not force the
  tuple pass when that is the program's only tuple use, so general-path C is unchanged.

Tests: `AIL_CURRENT/test_ail_prog7.py` (registered in `tests.d/`) compiles the exact `g10_032`
program, its empty/single/line/all-ones/diagonal boundaries, constant tuple loops (break, continue,
nested unpacking), tuple-as-value/name/empty/mixed cases and bool+int rows in one function, each
compared with CPython. `test_ail_tuples`, `test_ail_nested_lists` and `test_ail_boolfield` pass. All
ten `lab/compare` tasks keep byte-identical `program.c` on the builds that built before (both
`main.ail` and the `main.py` builds; `berth_sim/main.py` was the sensitive one). Probes in
`/tmp/probes/p_g10_*`, `p_tuple_*`, `p_nested_bool.py`, `p_bool_rows.py` match CPython on both
`cmp.sh` builds.


## 2026-11-01 -- CPython hybrid review 2: concurrent overflow, every-path buffer free, exact metadata (job-cpyhyb1-11012125)

Fixed the four defects from the second review of `ail build --cpython`. The mixed-mode int-overflow
`jmp_buf` and its save pointer are now `__thread` in the hybrid's copy of each unit, so concurrent
calls that overflow no longer share a jump target (the 8x5000 probe now exits 0 with CPython's
answers). Every conversion failure after a list argument now jumps to the `fallback:` label, which
frees each buffer once; a later non-list, wrong scalar, wrong list or failed str result no longer
leaks the earlier list copy (50,000 calls stay at plain-CPython RSS). The wrapper still copies the
original metadata, and now rewrites `__code__` with the original `co_name`, `co_varnames` (including
locals), `co_nlocals`, filename and first line, so functions with locals report CPython's
`co_varnames` and no `__wrapped__`. Helper references in the generated call body use names chosen
against the parameter list, so parameters called `_ail_hybrid_invoke`/`_ail_hybrid_native_ref`/
`_ail_hybrid_original_ref` (or their double-underscore spellings) no longer shadow them.
`test_ail_cpython_hybrid` gained concurrent-overflow, later-argument-fallback and locals/helper-name
metadata cases. Probes in `/tmp/fixprobe*` and `/tmp/fixthr` matched CPython; the standalone paths
are unchanged.

## 2026-11-01 -- CPython hybrid review fixes: fallback buffers, packaged paths, metadata (job-cpyhyb1-11011403)

Fixed the three review defects in `ail build --cpython`. A fallback from the first of several list
parameters no longer frees uninitialised buffers: every list buffer is declared as NULL before the
conversion loops and the fallback label frees all of them (list[int] and list[float]). The packaged
`prog.py` now sets `__file__` and `sys.argv[0]` to the original source and puts its directory first
on `sys.path`, so `__file__`-relative data files and sibling imports work from the output directory.
The accelerated wrapper is generated with the original parameter layout and copies annotations,
defaults, kwdefaults, name/qualname/doc/module/dict, so `__code__.co_argcount`/`co_varnames` and
`inspect.signature` match; keyword calls and default values still behave as CPython. The hybrid
unit's overflow flag is now thread-local because native calls release the GIL; free-threaded CPython
is still not claimed.

Tests: `test_ail_cpython_hybrid` gained regression cases for two- and three-list fallbacks, metadata
and `__file__`/sibling imports. Probes in `/tmp/probes/hyb_*` cover scalar int/float/bool/str
boundaries, int64 and beyond, empty/negative lists, aliasing, mutation, kwargs/defaults, packaging
and concurrent overflow calls; every hybrid run matched CPython. Default and general standalone
paths are unchanged (the same probes still show the pre-existing standalone int64/metadata limits).

## 2026-11-01 -- CPython hybrid prototype: typed helpers in an extension, CPython for the rest (job-cpyhyb1-11011403)

Added an explicit `ail build --cpython prog.py -o DIR` mode. The output is a normal CPython program
with a generated extension module: scalar and list-int/list-float helpers the real typed emitter
accepts are called natively, and every call whose values do not fit the ABI, whose int overflows,
or whose typed clone is absent runs the original Python function. The standalone build is
untouched; the flag, the design (`docs/design/CPYTHON_HYBRID.md` and its `AIL_CURRENT/docs/design`
copy) and the fallback rules are new.

The analysis reuses `pymix.analyze` and `pyboxed2`'s mixed-mode units rather than a second
selection rule. It runs the real CLI general build in a subprocess with a temporary
`sitecustomize.py`, captures the units, and retries a direct `pyboxed2.build` on the original
source when the CLI refuses the program. Annotations only seed parameter kinds (the boundary still
checks the actual value); the CLI's `__ail_checked_*__` return markers are stripped for the unit
emission because `to_c` otherwise refuses a checked `str` helper. Units use the int64 mixed-mode
ABI even when the surround build uses exact ints: the existing overflow flag sends a value that
does not fit back to Python, so no `ail_tint` crosses the extension boundary. Two mixed-mode
details are loosened only in the analysis process: the entry regex has a word boundary so
`ail_unwind_<name>` cannot be taken for the entry, and the str ABI's `uint8_t *_out` is accepted
by the validator. The wrapper defines `ail_mix_drain_out` so a unit's trap path links. A
conservative body gate then keeps any function with a possible typed trap in CPython: indexing,
division/power, a call, `raise`/`assert`, `try`/`with`/import, `global`/`nonlocal`, deletes and
attribute/index stores. A missed speed-up is safe; an IndexError that exits instead of reaching
the caller's handler is not.

Packaging: `prog.py` is the original source plus a preamble and a rebinding after each accelerated
def, `prog.orig.py` is the untouched source, `prog` is the launcher, and
`_ail_<stem>_fast.<ext>.so` plus `build.json` name the native side. A missing extension makes the
preamble return the original functions. Every native call releases the GIL; typed parallel clones
are linked with `-pthread`; free-threaded CPython is explicitly not claimed or tested.

Results: `lab/compare` `berth_sim` and `term_rank` are general today and matched CPython on all
26 and 43 public+hidden cases (hybrid vs CPython: 0.249 s vs 0.246 s and 0.067 s vs 0.065 s on
medium inputs; standalone general 0.528 s / 0.126 s). Five refused corpus programs (`t440`,
`t447`, `t472`, `t437`, `t456`) built and matched CPython on every input; they have no wrappable
unit, so they run as CPython. The accelerated corpus example `t264` (`classify`) was also built
and compared; the other candidates examined (`t081` `is_palindrome`, `t139` `fmt`, `t211`
`evaluate`, `t314` `longest_non_decreasing`) index or call and now stay in CPython under the body
gate. The boundary microbenchmark (`inc(n)=n+1`, 2M calls) is 32.5 ns/call plain,
67.7 ns native-direct and 115.4 ns through the generated wrapper, so the mode pays only when the
function body does enough work; a C callable type is the next step for the closure overhead.

Added `AIL_CURRENT/ail_cpython_hybrid.py`, `AIL_CURRENT/test_ail_cpython_hybrid.py` and
`AIL_CURRENT/tests.d/test_ail_cpython_hybrid.txt`. Final-state tests: test_ail_cpython_hybrid,
test_ail_safetynet, test_ail_files and test_ail_corpus_findings3.
## 2026-11-01 -- bisect(key=) on every sequence: range, bytes and bytearray

The general path's `key=` lowering for `bisect_left/right/bisect/insort*` measured the sequence with a manual
list/tuple/str switch, so `key=` on a `range`, `bytes` or `bytearray` raised the wrong
`TypeError: object of type ... has no len()` (a range/bytes that CPython accepts, and bytes already worked in
the default build). `ail__bisect_len` now asks the runtime's own `ail_op_len`, which covers range counts,
instance `__len__` (bytes/bytearray) and deques; indexing still goes through `ail_op_getitem`. Probes
`/tmp/probes/v_range.py` and `/tmp/probes/v_bytes.py` match CPython on both builds, including lo/hi, hi=None,
negative lo, empty sequences, out-of-range hi, and `insort` AttributeError. `test_ail_std_bisect` gains a
range/bytes/bytearray key program. No non-key bisect codegen changed.

## 2026-11-01 -- int64 constant census: refusals named, safe folds kept

`docs/design/I64_CONSTANTS.md` records the first int64-constant refusal of all 34 modules in the compiler census and
classifies each use: range bounds, all-ones masks, hash multipliers, sentinels, decimal thresholds and test fixtures.
No compiler semantics changed. The safe subset was already the folded one: an out-of-int64 intermediate whose final value
fits builds, as does a mask applied to an int64 constant (`5 & ((1 << 64) - 1)` prints 5); a mask that itself fits int64
works on variables (`x & 0x7FFFFFFFFFFFFFFF`, `x & 0xFFFFFFFF`). Everything else, including `x & ((1 << 64) - 1)` for a
nonnegative-looking argument, `0xcbf29ce484222325`, `1 << 63` and `10 ** 30`, stays refused by name with the
`--exact-int` hint. The new `test_ail_i64_constants.py` locks those refusals on the default and forced general paths,
checks the safe folds/masks against CPython, and checks that exact mode builds the same refused program. Probes in
`/tmp/probes/i64_*.py` cover the values through arguments, list items, attributes and dict values, including negative and
boundary inputs.
## 2026-11-01 -- docs review: FFI u64 arguments above int64 also stop by default (job-docints1-11011229)

The review found that the reference still said an unsigned 64-bit FFI argument may use
`2**63 .. 2**64 - 1` by default, while the default build stops at the call. The Native libraries
paragraph now says an argument above `2**63 - 1` is refused or stops unless `--exact-int` (a literal
at the call is the run-time stop), just like a result; A1 and the current `DIFFERENCES.md` row say
"argument or result". Probes `/tmp/probes/p_ffi_arglit.py`, `p_ffi_argdyn*`, `p_ffi_boundary.py`,
`p_ffi_negative.py` and `p_ffi_result.py` cover literals, a value through an argument/list
item/attribute/dict value, the int64 boundary, negative values and u64 results on the default,
forced-general and exact builds: the default and general builds match CPython at the int64 boundary
and stop with the documented `OverflowError` above it; `--exact-int` matches CPython. No compiler
behaviour changed.

## 2026-11-01 -- docs: integers are int64 by default; exact big ints are opt-in

Documented the rule the compiler already implements (job-docints1-11011229, #284): `int` is signed
64-bit by default and an out-of-range result stops with `OverflowError: integer overflow in <op>
(ints are 64-bit; --exact-int gives exact ints)` (exit 1, stdout kept); a source value that needs a
big int statically is refused at compile time, naming the line and the flag; `--exact-int` /
`AIL_EXACT_INT=1` gives CPython's exact ints. Rewrote the tutorial's integer section and its
examples, the quick reference, the Numbers/FFI/Fraction/Decimal notes, A1/C171 and the related
declared rows, and added the current row to `DIFFERENCES.md`. `test_ail_tutorial.py` now runs
runtime-stop, static-refusal and exact-mode samples as well as the default ones. No compiler
behaviour changed.
## 2026-11-01 -- manifest merge: a regenerated compiler pin keeps its SDK flag

`tools/update_manifest.py` recomputes pins after a manifest.d merge, but a new compiler source whose pin the kept
side did not have was re-added without the `s` flag, so the wheel's `sdk_files` lost it and `test_ail_packaging`
failed on the integration branch (`ccsplit.py` after the cc-split change). The tool now treats every `.py`/`.h`/`.c`
under `python/pkg-v12/` or `stdlib/` as a compiler source: a missing pin is restored as an SDK pin (`s`), and every
compiler source is pinned even when the kept side dropped it. `test_ail_registry` covers the dropped-pin merge, and
`test_ail_packaging` passes after taking either side of the manifest.d conflict.

## 2026-11-01 -- gcc time: one body per identical clone (default), parallel units and one exit cleanup (opt-in)

The typed program's C (runtime, user prototypes, user functions) is one gcc run. OFF BY DEFAULT (they cost up to +0.4%
run icount on some tasks): `AIL_CC_SPLIT=N` (N>=2) or `AIL_CC_JOBS=N` turn the split on, `AIL_EXIT_MERGE=1` the exit
sharing. `python/pkg-v12/ccsplit.py` then cuts it into up to min(4, cores) units compiled in parallel and linked (`pyc._split_build`): the runtime and prototypes
are in every unit, every `static` user function is in every unit, every other user function in exactly one (largest first
onto the lightest unit; the plan depends on the text alone). Run-time state is defined once (`AIL_LINK_STATE` is the
definition in the unit holding `main`, `extern` elsewhere; the object pool's file-scope statics get the same treatment).
It is skipped when the movable user code is under 30000 characters, when one function holds more than 70% of it, on
Windows, with `--debug`, `--static` and a native build report, and falls back to the one-unit build when a unit does not
compile, link, or defines state twice (`nm` check). `AIL_CC_SPLIT_LOG=<file>` records the decision. The legacy `_rewrite_returns` shares one copy of the exit frees among the
returns that lie outside every loop of a function with at least 8 free/release calls (`AIL_EXIT_MERGE=1`, `all` every
return; merging returns inside loops, or in small hot functions, cost run time). A specialisation (`fmt__t0`) whose C is the
base function's with only the name changed is emitted as a call to the base: ON by default (`AIL_NO_CLONE_DEDUPE=1` off); run icount unchanged on all 10 compare-lab tasks.

## 2026-10-31 -- ints are 64-bit by default; exact big ints are opt-in

Owner decision: "strongest" over "identical to CPython". A Python-syntax program now gets int64: an operation that leaves int64
stops the program (exit 1) with `OverflowError: integer overflow in <op> (ints are 64-bit; --exact-int gives exact ints)`, on the
typed path and on the general path alike; a value that fits prints what CPython prints; a program whose source needs a big int
statically (an int literal outside int64, a constant expression such as `1 << 200`) is refused at compile time with the line and
the flag. `compile --exact-int` / `AIL_EXACT_INT=1` is the old behaviour (docs/design/BIGINT.md, section 15 for the wiring). The
switch is `python/pkg-v12/intmode.py`; in the default mode the gate (bigcap marks, tagged ints, big general path) is off, so
nothing leaves the typed path for an int-width reason. The general path runs the `AIL_BIGINT=off` runtime with every piece kept.
`test_ail_int64_default.py` is the boundary matrix (every operation at +-2**63, default and forced general path, against CPython);
the exact-int tests set the variable in `setUpModule`.

## 2026-10-30 -- GPU stage G2: SPIR-V for the G1 kernels, and the Vulkan runtime that is opened at run time

The kernel IR of G1 now has a device twin. `python/pkg-v12/gpu_spirv.py` (a SPIR-V writer of about 800 lines, no shaderc or
spirv-tools at user build time) lowers a kernel to a compute shader; `python/pkg-v12/gpu_vk.py` is the C runtime that goes
into a `--gpu` program: it opens `libvulkan.so.1` with dlopen at run time (never linked), declares the Vulkan structs it
needs itself, picks a device, and runs one pipeline per kernel. The wrapper `ail_gk<k>_run` has the signature of the G1
emulation, tries the device and falls back to the emulation on any missing piece (no loader, no device, no compute queue, a
device without shaderInt64 / shaderFloat64 / round-to-nearest-even / signed-zero-inf-NaN preservation for binary64, a failed
allocation or submit, a static build), so the program prints the same bytes either way. The device sets the same flag bits
as the emulation (a superset is allowed, a subset is not); flag != 0 discards the result and the original loop replays.
Switches: `AIL_GPU=0` (original CPU loop), `AIL_GPU=emu` (the CPU emulation, no Vulkan), `AIL_GPU=force` (device for every
launch), unset (device from `AIL_GPU_MIN_N`=4096 elements; placeholder until the G7 cost model), `AIL_GPU_TRACE=1`,
`AIL_GPU_DEVICE=<name>`; test hooks `AIL_VULKAN_LIB`, `AIL_GPU_DISABLE`. The build prints one note per kernel naming the path it
can take. A bit test on lavapipe found that the device compiler folds `0.0 - x` into `-x` (wrong sign of zero for +0.0), so
the emitter now computes the sign of an exact zero, `-x` and `abs(x)` with integer bit operations. There is no int32 kernel
yet: the typed array module is not in this base, and the G1 kernels are int64 with the overflow flag. Programs without
`--gpu` are byte-identical. `test_ail_gpu_g2.py` runs in its own CI job on lavapipe (`gpu` in tests.yml), not in the shards.

## 2026-10-30 -- FFI F3b: exact unsigned 64-bit results and arguments, `check="allones"`

An `@extern` result of `c_uint64 c_ulong c_ulonglong c_size_t` above 2**63 - 1 used to come back as the negative int
with the same bits; F3a refused a constant argument in `2**63 .. 2**64-1` because the program held int64 only. Both are exact
now, as under the CPython shim. The C adapter and the object format are unchanged (the adapter still returns the int64 bits);
`ail_ffi_lower.py` writes the conversion into the AIL wrapper with constants that all fit int64 (`bits + 4 * 2**62`, so no
wide literal reaches the typed gates of PR #230), and the tagged lowering adds them exactly. A constant argument in the upper
half is rebuilt from a generated C function that returns its bits. The legacy int64 emitter (`AIL_NO_GENERAL=1 AIL_IR=0`)
stops with `integer overflow` (exit 1) when such a value appears. `check="allones"` fires on the unsigned `(T)-1`;
`check="minus1"` / `"negative"` on an unsigned result never fire and are refused by name. 64-bit signed parameters are
checked against int64 as well. Binary-size and call-cost numbers are in the PR. `test_ail_ffi_f3b.py`; F3a's refusal tests
for the upper-half constants became exactness tests.
## 2026-10-30 -- repre20: chr() of a non-BMP code point on the general path stops by name (job-repre20-10300611)

Today's integ already refused a statically known non-BMP `chr()` argument at build time (`test_ail_pre36.py`, added after the old pre20 diff), but a value only known at run time still reached `ail_bi_chr`'s `ail_die` and ended with `AIL internal error: chr() non-BMP code point requires 32-bit strings`. The general runtime stores UTF-16 units and cannot represent U+10000..U+10FFFF; the typed/default build can. `ail_bi_chr` now returns `ail_hit_limit(cx, "chr_non_bmp", ...)` (the uncatchable `AIL limit: chr_non_bmp`, exit 3) for such a value, in the `str_title_nonascii` limit style, and the build-time refusal wording is `chr() of the non-BMP code point U+... in the 16-bit v2 runtime` (pre267's `bytes.decode()` style). `test_ail_pre36.py` was updated for the wording; new `test_ail_repre20.py` (8 tests) compares with CPython through a literal, an argument, a list item, an attribute, a dict value and stdin on both builds, checks the limit is uncatchable (`except`/`finally` do not run), and keeps the U+FFFF boundary and the ValueError range errors unchanged.

Probes in `/tmp/probes`: `p20_literal` (general refused by name; the default build of a lone top-level statement falls back to the general path here, the three-line `p20_default` matches CPython), `p20_runtime_value` / `p20_attr_only` / `p20_dict_only` / `p20_try` (named limit, exit 3), `p20_bmp` / `p20_range` (match on both builds), `p20_typed_simple` (default matches CPython, general stops with the limit).

## 2026-10-30 -- GPU stage G1: `# ail: gpu`, the eligibility proof, kernel IR and its CPU emulation

`compile --gpu` (or `AIL_GPU_BUILD=1`) reads `# ail: gpu` on the line before a loop (or at the end of a list-comprehension
assignment), proves the loop eligible (docs/design/GPU.md 1.1, 1.3) or refuses it by name with file:line and a `write
instead:` hint, lowers it to a kernel IR (`python/pkg-v12/gpu.py`) and emits the kernel as a C function that runs on the CPU
with the flag word and CPU replay of GPU.md 3.1 / 5.1. No SPIR-V, no Vulkan, no cost model (G2, G3, G7). A program without a
marker, or built without `--gpu`, generates byte-identical C. Section 6.1 of GPU.md lists what is built, the refusals, and
every deviation from the design. `test_ail_gpu_g1.py` (42 tests) compares marked programs byte for byte with CPython, with
the same binary under `AIL_GPU=0` and with the build without `--gpu`; covers empty and one-element lists, lists of different
lengths, NaN/inf/-0.0/denormals, values at the int64 limits, division by zero and an IndexError inside the body, every
refusal, and the unchanged-C proof.
## 2026-10-31 -- cov19 suite fix: register through tests.d, not the module tuple (job-cov19-10311304)

The integration of the accepted cov19 change merged the edited `MODULES` line into the new
`LISTED_MODULES` group, leaving a duplicate copy of that group. `merge_modules` deduplicates it,
so `MODULES[:len(LISTED_MODULES)] != LISTED_MODULES` and `test_ail_registry` failed. The kept
cov19 behaviour and its test are unchanged; `test_ail_cov19` is now registered the way the
integration tree expects, as `AIL_CURRENT/tests.d/test_ail_cov19.txt`, and the tuple is left
alone. `test_ail_pre47` passes here and with the cov19 diff applied alone on the integration
base; the candidate failure was bisected to the separate ex32 integration (`ac4836c`), whose
`print(1<<63)` typed-path regression reproduces with the cov19 sort change reverted.

## 2026-10-26 -- pre272 follow-up: refresh full-C output pins (job-pre272-10262304)

The accepted base-runtime mapping for `list assignment index out of range` changes the emitted C
for every program that pulls the exception runtime, so the full-C SHA-256 pins in
`test_ail_numeric_bindings` and `test_ail_record_initializers` were stale, so they were
regenerated on this tree.  Both modules and `test_ail_pre272` pass;
`tools/update_manifest.py --check` passes.

## 2026-10-26 -- pre272 review fix: keep out-of-range `del` catchable without reading text

The review found that the new `list assignment index out of range` trap was only mapped to
`AIL_EXC_INDEX` by the `exctext` patch, so on the default build a `try/except IndexError` around
an out-of-range `del` that did not read `str(e)`/`e.args` aborted uncatchably.  Added the message
to the base `ail_exc_kind_of()` index mapping (the now-redundant `exctext` edit was removed) and
added a catch-without-text case to `test_ail_pre272.py` covering an empty list, int/float/str
list fields, an argument, a list item, a dict value and an attribute.  Probe
`/tmp/probes/p272_caught_no_text.py` matches CPython on both builds.

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
## 2026-10-26 -- re-apply pre26: repr(e.args[i]) keeps the argument's kind (job-rbpre26-10270138)

Re-applied the accepted pre26 change on this tree. On the typed path `e.args[i]` reads as text, so
`repr(e.args[i])` repr'd that text: a `ValueError(3.0)` handler printed `'3.0'` where CPython prints
`3.0`, and int, bool and None arguments were quoted the same way. The handler rewrite now lowers
`repr(e.args[i])`, `f"{e.args[i]!r}"` and `%r` of one argument to a new `_ail_exc_arg_repr` accessor
that formats the stored argument (a str keeps its quotes, a number does not). Both builds agree with
CPython; the accepted `test_ail_pre26.py` keeps the probe, including negative and out-of-range
indexes, and is registered in `ail_check.MODULES`.
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

## 2026-10-26 -- reapply pre225: grouping with an unrecognised type code (job-rbpre225-10261321)
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
