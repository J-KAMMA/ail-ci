# Call-site specialisation of unannotated functions (fcspec0)

Status: design, 2026-11-06, job `fcspec0`. No compiler file changes in this job. Base: `integ` at
`ff12fa938` (all `file:line` references below are on that commit). Sample, runner and baseline:
`lab/reach/callsite/` (`sample.txt`, `census.py`, `BASELINE.md`, `repro/`).

**Measured first, before the plan (section 7):** on the repository's plain-Python corpora the lever
is much smaller than the steal-list guessed. Of 960 programs traced (905 corpus/census, 55
pyproof), only 52 that the typed path does not take today have a function reached by two or more
instance keys; 19 fail first with a call-site message, only 2 of them because of a real
disagreement; and cloning every disagreeing def per key in the source makes 0 of the 52 typed.
That is far below fcspec0's own stop rule (30), so **fcspec1-fcspec3 should not start as written**; section 8 gives the re-ranked plan for the
owner. The design below is still the one to build when this lever is picked up, and it is cheap to
keep: most of the machinery exists already.

## 1. What exists today (the rule this design extends)

The typed path already monomorphises. AIL is not starting from Codon's position; it is extending
SEMANTICS.md section 26 (`AIL_CURRENT/python/pkg-v12/SEMANTICS.md` line 2233).

| piece | where (`AIL_CURRENT/python/pkg-v12/`) | what it does today |
|---|---|---|
| parameter kinds from the body | `pyfunc.py:_param_kinds` (5134) | body evidence: indexed/iterated → array, `b"..."` → bytes, `/` or a float literal → float, `range()`/index/`//`/bitwise → int; conflict float vs int-only site refused: "used both in float arithmetic and at a site that requires a whole number" (5604) |
| a caller-supplied kind | `pyfunc.py:_param_kinds`, `sig_override` (5640-5680) | "%r is annotated %s in the source, but the caller also supplies %s; refusing rather than silently choosing one" (5653, 5673) |
| the whole-program fixed point | `pyfunc.py:_signatures` (33598), loop at 33751 | interleaves `_propagate_signatures_pass` (33052), `_settle_return_kinds_pass` (33326), `_infer_strparam_pass`, `_infer_strcmp_pass` until nothing moves, `2*len(fns)+8` rounds |
| recursion | `pyfunc.py:_signatures` 33726-33730 | `recursive = {f for f in fns if f in reach[f]}`: a recursive def is never a propagation target and never cloned |
| one call site's claim | `pyfunc.py:_claim` (32903), `_call_site_signature` (32936), `_claim_key` (32982) | asks `_etype` over the caller's typed ctx (`_caller_ctx`, 32775); returns INT/FLT/BYTES/BYTEARRAY/STR/'array'/('rows', n) or None (silence) |
| agreeing sites | `_propagate_signatures_pass` 33085-33103 | one claim per parameter → `sig_override` of `_param_kinds` |
| disagreeing sites | `pyfunc.py:_plan_clones` (33466), `CLONE_CAP = 4` (32701) | one C function `g__t<idx>` per distinct claim tuple, **only if** (a) not recursive, not the entry, (b) every site passes exactly `len(params)` positional args (33496), (c) no str-vs-other conflict (33505-33512 drops the str sites), (d) `_clone_return_kind` (33436) settles the **same return kind as the generic** function (33531) |
| call rebinding | `pyfunc.py:_call_user_func` (16733), 16769-16781 | `ctx.clones[fname].get(_claim_key(site))` with the site re-claimed over `ctx.base_ctx`; no match → the generic symbol |
| the argument guard | `pyfunc.py:_call_user_func` 17120-17140 | "passing a float to %s(), whose %r is an int64; this language has no implicit truncation" (17136); "passing %s where %s() wants %s" (17134) |
| bool vs number | `boolkind.py:_infer` (581), message at 1039 | "parameter `x` of f() gets a bool from some calls and a number from others" |
| whole-program fallback | `pyc.py:_build_unshadowed_inner` (1738) | any typed refusal → the whole program goes to `pyboxed2.build`; there per-function typed islands are tried (mixed mode) |
| mixed mode (general host, typed islands) | `pymix.py:_fixed_point` (741), `_collect_calls` (694), `_merge` (95); `pyboxed2.py:_setup_mix` (7461), `_call_mix_guarded` (7616) | ONE kind per parameter; `_merge` widens int+float to FLOAT; the island is called only when every argument's runtime tag matches (`ail_mix_is_int`/`_is_float`/...), else the boxed body runs |
| CPython hybrid | `AIL_CURRENT/ail_cpython_hybrid.py:_select` (534), `_wrapper_source` (606); `docs/design/CPYTHON_HYBRID.md` | units come from mixed mode; the wrapper checks exact types and falls back to the Python function |

So today, for `def add(a, b): return a + b` called as `add(1, 2)` and `add(1.5, 2)`, `_plan_clones`
sees two claim tuples but the float variant returns float while the generic returns int, so no
clone is built; the generic int instance is compiled and the float call is refused by the argument
guard (17136); the program goes to the general path. Reproducers: `repro/scalar_int_float.py`,
`repro/scalar_ret_moves.py`.

## 2. Instance keys (the kind lattice)

An instance key is the tuple of argument kinds of one call site, in parameter order, after defaults
are filled (section 3). Kinds:

| kind | spelling in a key | notes |
|---|---|---|
| int | `i` | int64; overflow stops loudly as everywhere (`ck_add` & co.); never converted to float |
| float | `f` | IEEE double |
| bool | `b` | its own key: `f(True)` prints `True`, `f(1)` prints `1` (boolkind's rule stays) |
| str | `s` | |
| bytes | `y` | bytearray is claimed as bytes where the callee only reads (32955) |
| None-tagged Optional of K | `oK` | only where the typed path already has a tagged None for K (struct `C \| None`, pyreach's tagged None) |
| list[K] | `lK` | `l?` (empty literal) is not a key: it takes K from the callee's own uses or from the other sites, else the site has no claim (section 3) |
| dict[K,V] | `dKV` | |
| set[K] | `tK` | |
| tuple of kinds | `(k1k2...)` | fixed arity; the existing row/tuple-list ABI ('rows', n) is one case |
| class C | `cC` | one key per class; a subclass is a different key (no virtual dispatch through an instance) |

Rules that keep it exact:
- int and float are different keys. `f(1)` runs the `i` instance and returns int; `f(1.0)` runs the
  `f` instance and returns float. There is no join of int and float to float (unlike
  `pymix._merge`, section 5).
- bool is not int. `same(True)` and `same(1)` are two instances (`repro/scalar_bool_int.py`).
- A site whose claim is None for a parameter (the caller cannot type the argument) has no key: it
  binds to the generic instance, which is exactly today's compile (today's refusal included).
- An argument the caller can only bound as "int or big" (a value from `int(text)`) keys `i`; the
  int64 instance then stops loudly on overflow (`repro/bigint_from_text.py`), unchanged from today.

## 3. Collecting call sites

Standalone builds see the whole program, so collection is static and complete:

1. In `_signatures`, after the existing param/return fixed point has settled the agreeing
   functions, collect for every top-level def `g` the claim tuple of every direct call `g(...)`
   (`ast.Name` func) through `_call_site_signature` over the caller's `_caller_ctx`. **Change from
   today:** bind keyword arguments and fill omitted defaults per site (reuse `_bind_call_args`,
   the binder `_call` already uses), instead of skipping every site with
   `len(n.args) != len(gparams)` (33496). A default value contributes its literal kind.
2. Instance planning becomes a pass **inside** the fixed-point loop (33751), not after it (33841):
   an instance's return kind changes what its callers' `_etype` answers, which can change other
   claims. The loop gets a fifth interleaved pass, `_plan_instances_pass`, with the same
   "iterate until nothing moves, capped" discipline.
3. Instances are stored in `sigs` under their own names (`sigs['add__i_ii'] = (params, ret)`), and a
   per-call-node binding map `ctx.site_bind = {id(call_node): instance_name}` is filled by the pass.
   `_etype`'s Call branch (`ctx.funcs[node.func.id][1]`, 1030/1971) and `_call_user_func` (16769)
   look up `site_bind` first. This replaces today's re-claim over `base_ctx` at codegen time: the
   plan and the emitted call can never disagree, because the emitter reads the plan.
4. Recursion (fcspec2): a self or mutual call inside instance `g__i_K` is claimed over that
   instance's own ctx, not over the generic one. If its key is K it binds to the same instance; if
   it is a new key it adds an instance; the pass repeats. A strongly connected component whose
   instance count passes the cap goes back to today's behaviour for every function in it.
5. Return kinds per instance: `_clone_return_kind` (33436) already computes them; the equality
   test with the generic return (33463, 33531) is dropped. Two returns of one instance that
   disagree are still refused by `_reconcile_return_kinds` (31765), as today.

## 4. Limits and what stays out

- **K = 4 instances per def** (owner decision 2026-11-06; equals today's `CLONE_CAP`). Past K the
  def keeps today's single compile (or its refusal), for all sites.
- **First-class uses** (`map(f, xs)`, `key=f`, `f` stored in a list or passed as a callback): the
  def keeps one generic instance for those uses; direct sites may still get instances.
  `repro/firstclass_key.py`.
- `*args`, `**kwargs`, keyword-only parameters: out of scope; the def keeps today's rule.
- Nested defs and lambdas: out of scope (they are closures on the general path today).
- The entry point (`fns[-1]`) is never instanced, as today.
- An instance never moves a parameter that the source annotates: an annotation contradicting a
  site claim is still refused by name (`_explicit_annotation_conflicts`).

## 5. Fallback, and why a wrong guess cannot print a wrong answer

Every step keeps the invariant of SEMANTICS.md section 5: the compiler stops or falls back, it never
guesses.

1. **Per instance.** An instance whose body `_one_function` refuses is dropped; its sites bind to
   the generic instance; the generic instance is today's compile. Nothing new can be refused.
2. **Per function.** If the generic instance is refused too, the typed path refuses the program
   exactly as today, `pyc._build_unshadowed_inner` moves the whole program to `pyboxed2`, and mixed
   mode tries this def again as a typed island (step 4 below). "Falls back per function" therefore
   means: inside the typed path the unit of fallback is an instance; on the general path it is a
   function, through mixed mode, which already exists.
3. **No conversion at a boundary.** The argument guard (17120-17140) stays as it is: an instance is
   chosen by the exact kind tuple, so a float argument can only reach a float instance; an int can
   never reach a float slot (`_refuse_int_in_float_slot`, 16719) and a float never reaches an int
   slot. A mixed int/float **call site** cannot exist on the typed path (a local has one kind); on
   the general path a site can see both at run time, and there the mixed-mode guard dispatches on
   the runtime tag (step 4) or runs the boxed body.
4. **Mixed mode (general host).** `pymix._merge` (95) widens int+float to FLOAT. Under this design
   pymix keeps the per-site kind tuples (`_collect_calls` already produces them, 694) instead of
   merging, and `_setup_mix` compiles one island per tuple (≤ K) with `pyfunc.to_c(entry=name,
   sig=...)`. `_call_mix_guarded` (7616) tests the tuples in order with the tag checks it already
   has and calls the first island that matches; none → the boxed body. This is Numba's dispatcher,
   built from parts AIL has. The `__mix` int wrapper (`_mix_wrap_integer_clone`, 2562) keeps the
   overflow fallback per island.
5. **int64.** Every int instance is compiled by the same emitter with the same checked arithmetic;
   specialisation never adds a wider or narrower int. `int(text)` beyond int64 stops loudly
   (OverflowError, exit 1) exactly as today, in both builds (`repro/bigint_from_text.py`: CPython
   prints `9223372036854775808`, AIL stops loudly; that row is a declared limit, not a wrong).
6. **Checks each step must pass** (fcspec1-3 done-checks): zero wrong on the sample and the
   probes, in the default build and with `AIL_UNIFIED_FORCE=1`; byte-identical `program.c` for
   every typed pyproof program that has no disagreeing call site (the plan is empty, so emission
   must be the old code path).

## 6. Names, diagnostics, CPython hybrid

- C names: `<csym>__i_<key>` where `<key>` is the key spelling of section 2 with every kind
  joined, e.g. `add__i_ii`, `add__i_fi`, `total__i_li`, `total__i_lf`. Today's `__t<idx>` (33534)
  is replaced; the key-based name is stable across unrelated edits (an index is not), which keeps
  `fecache` hits and makes `program.c` diffs readable. A name longer than 48 characters uses
  `__i<8-hex hash of the key>`.
- `--debug-dir` writes `instances.txt`: one line per def, its instances, and for each call site
  `file:line:col -> instance`. `ail explain` (or `--strict` output) prints the same for the def a
  refusal names.
- Error lines name the source line: an instance carries the original `ast.FunctionDef` (same
  `lineno`/`col_offset`), so every refusal and runtime error inside an instance still says
  `file:line:col` of the source; a runtime traceback line names the def, not the instance.
- **CPython hybrid** (`docs/design/CPYTHON_HYBRID.md`): every island instance is exported under its
  instance name; the generated wrapper (`ail_cpython_hybrid.py:_wrapper_source`) tests the exact
  type tuple (`type(a) is int` etc., the boundary table of CPYTHON_HYBRID.md section 2) against each
  exported instance in order and calls the first match; no match, or the overflow flag, calls the
  original Python function. The per-call cost grows by one type test per instance tried (≤ K).

## 7. The sample and what it says

How the sample was made (`census.py select`): every program of `lab/census/programs/` (686),
`lab/corpus/programs/` (219) and `lab/pyproof/programs.txt` (55) was run under CPython with a
profile hook that records, for every call of a function the program defines, the kind tuple of its
parameters and the call site. A function is **disagreeing** when two or more tuples reach it. The
typed attempt (the compile-only steps of `lab/census/fallback_census.py`) then says whether the
typed path takes the program, and a **counterfactual** clones each disagreeing top-level def in the
source, once per tuple, rebinding each direct site, and runs the typed attempt again: that is what
per-tuple instances would give the existing typed path with no other change.

Results (details and the per-program table in `lab/reach/callsite/BASELINE.md`):

| measure | count |
|---|---:|
| programs traced | 960 |
| typed by the compile-only attempt | 320 of 926 attempted |
| not typed and a function reached by ≥ 2 raw tuples | 74 |
| ... after dropping `?` elements and subclass receivers (the sample) | **52** |
| first reason is a call-site message (any program) | 19 |
| ... of which a real runtime disagreement exists | 2 |
| counterfactual (source clones per key) typed | **0 of 52** |
| counterfactual with every def unannotated (`--strip`) typed | **0 of 52** |
| real build of the sample: typed / general / refused / wrong | 2 / 39 / 11 / 0 |

Of the 82 disagreeing functions in the sample, 30 have more than K = 4 keys and 23 carry
heterogeneous (`mix(...)`) or None-holding containers (JSON-like trees, `flatten`, `describe(v)`):
dynamic code the general path is right to keep. 29 are clean with at most 4 keys, in 19 programs,
all of which have an unrelated first blocker (json result types, `list[Any]`/`object`
annotations, class features). The corpus is almost fully annotated (57 of 1,872 parameters
unannotated), and the pyproof programs have one disagreement only (`examples/hybrid/
fallback_demo.py`, deliberately bigint/bool/float). raytrace, mdlite, nbody and tsv_join do not
disagree at all: their blockers are single-key inference (a class-typed parameter and a method
returning a class, a bool/int return, an int field given a float, a tuple-or-scalar return).

**Confidence of the +N figures in section 8:** high that the short-term gain on the sample is
0-2 programs per step (the counterfactual is an upper bound for S1/S2 because it gives the typed
path exact per-key bodies; it cannot model S3 or a site that sees several keys, and the
compile-only attempt can differ from the real build, which typed 2 rows the attempt did not).

## 8. Step plan

As written in the task files, each step would move the sample by about 0, so the stop rule
applies. The plan, should the owner keep the lever:

| step | scope | files | +N sample (measured bound) | pyproof rows |
|---|---|---|---:|---|
| fcspec1 | scalar keys of top-level defs: instances may have their own return kind (drop the equality at `_clone_return_kind` 33463/33531); bool and str keys; bind keyword/default sites (`_bind_call_args`, 16278); plan inside the fixed point; `site_bind` read by `_etype` and `_call_user_func` | `pyfunc.py` (`_plan_clones`, `_signatures`, `_etype` Call, `_call_user_func`), `boolkind.py` only to let a keyed bool site through (owner: boolkind is not in fcspec1's file list) | 0 (S1 has 5 rows; the 1 medium row, `gdev/g10_016.py` `format_cell(int|float)`, fails first on `a method on Call`) | none |
| fcspec2 | container keys, per-instance returns to callers, recursion fixpoint | `pyfunc.py`, `optlib.py` | 0 (S2: 19 rows, every clean function's program has an unrelated first blocker) | none |
| fcspec3 | methods and constructors: per-construction-site keys, defaults filled per site, class-typed parameters | `pyfunc.py` | 0 (S3: 23 rows; the clean case, `gdev/g13_000.py` `Rectangle`/`Circle` int/float constructors, fails first on `dunder method Shape.__repr__`) | raytrace and mdlite need single-key class/return inference first, not instances |
| mixed mode | per-key islands in `_setup_mix`, tag dispatch in `_call_mix_guarded` (section 5, step 4) | `pymix.py`, `pyboxed2.py` | general-path speed, not typed count | `fallback_demo` |

**Recommendation for the re-rank (owner decision):**
1. Do not start fcspec1-fcspec3 as separate 60-minute jobs now; keep this design for when an
   unannotated corpus shows the lever (re-run `census.py select` on it; the runner needs no
   change).
2. The 17 call-site-message programs without a real disagreement are inference bugs worth one
   job: a claim of `int` reaching a parameter annotated `str`/`list`/`iset` (`dev/t142.py`,
   `t352.py`, `t460.py`, `t462.py`, `gdev/g01_008.py`, `g10_022.py`, `g15_010.py`, `g22_000.py`,
   `corpus/*/t243.py`, `t353.py`) and the front end's generated helpers refused by their own
   argument rules (`_ail_ctr_new_int`, `_ail_dcv`: `dev/t008.py`, `gdev/g14_008.py`,
   `corpus/*/t155.py`).
3. The pyproof rows named in fcspec3 (raytrace, mdlite) are single-key inference: a parameter
   that receives one class, a method returning that class, `__init__` defaults. That is the part of
   fcspec3 worth doing first, without instances.
4. If the lever is kept anyway, merge fcspec1 and fcspec2 into one job (the fixed-point move and
   `site_bind` are shared), gated on the byte-identity check, and judge it on a corpus with
   unannotated defs.

## 9. Costs and how they are measured

- **Binary:** each instance duplicates one C function. Expected growth is the sum of the instanced
  bodies, a few hundred bytes to a few KB per instance against binaries of 30-200 KB, so far under
  the owner's 1.5x cap on the compare-lab programs; a def at the cap K=4 with a large body is the
  worst case and is the one the gate exists for.
- **Compile time:** one extra `_one_function` and one extra gcc function per instance, plus one
  claim pass per fixed-point round. Measure the compiler process with `tools/icount.c` (instruction
  counts; this laptop's wall time is noise), and gcc time with `-ftime-report` totals.
- **Gate in each step:** for every compare-lab program (`lab/compare/src/*/main.py`) and every
  sample program that gained, record exe bytes, `program.c` bytes and icount of the compile, before
  and after; stop and report if any exe grows over 1.5x or any compile icount over 1.3x (owner
  decision 2026-11-06). Programs with no disagreeing site must be byte-identical, so their cost is
  zero by construction; only gainers pay.
- Runtime: an instance is the same code the program would get if the author had written the
  annotations, so no new speed claim is made; the gain is moving a program from the general path
  (about 20x slower) to typed, measured by pyproof's speed-up column.
