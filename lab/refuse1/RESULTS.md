# refuse1: the first refusal the hybrid gives, for every function and method in the wedge3/wedge3b hot modules

Measurement only. No compiler, runtime or library source is changed. Branch `job-refuse1-11091608`,
run 2026-11-09 on a 4-core GitHub Actions runner (16 GB), CPython 3.12.3.

**Hybrid under test:** the `job-obs5-op1109` worktree at commit
**`69e2dcd0a82580fa06e26b275352fbedfb7d31e1`**; all builds use `../obs5/AIL_CURRENT`.

## What was measured

The five wedge3 pairs (networkx, jsonschema, chardet, tomli, difflib) and the two wedge3b pairs
(pydantic 1.10.27 pure, sqlparse 0.6.1) use the same hot modules and the same workload files as
those jobs (the copies in `workloads/` are byte-identical to the files on branches
`job-wedge3-11091201` / `job-wedge3b-11091226`). The pins are copied into this directory
(`requirements.txt`, `requirements-wedge3b.txt`) and installed into throw-away venvs
(`REFUSE_CPY3`, `REFUSE_CPY3B`); the script does not create or install the venvs itself, and no
library source is vendored.

For every module the script does two builds with `ail build --cpython`:

* **plain**: the installed source, no observed kinds;
* **observed**: the source after `ail_observe.py annotate` writes the workload's observed
  parameter/return kinds into it (existing annotations are kept).

The unit set is every direct top-level `def`/`async def` plus every method directly in a top-level
class: **519 definitions** (515 distinct `module:qualname` names; pydantic declares `create_model`
three times and `root_validator` three times as overloads, and those 6 rows share 2 build
decisions). Each definition is charged to the first reason `build.json` reports, or to `native`.
The reason text is folded to the first gate (field and callee names removed); the exact
`build.json` text is kept in `results.json:functions[cfg][].reason_raw`.

Time is **CPython cProfile self time (`tottime`) on the same workload**, not the observer's sampled
time. The table's time shares use the 11.622 s of self time inside the built hot modules; the whole
workloads total 26.086 s. cProfile inflates absolute times, so the shares rank functions, not wall
time. **Native functions: 0 in both configurations.** Every one of the 519 definitions had a
reason in `build.json`; there were no silent refusals.

## The first-refusal table

`fn` and `time` are shares of all 519 definitions and of the 11.622 s hot-module cProfile self
time. `obs` is the same build with observed kinds.

| first refusal reason | fn | fn share | time | time share | obs fn | obs time share | example |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| not a typed candidate (pymix cannot express a parameter/return kind, or no unit) | 271 | 52.2% | 6.626 s | 57.0% | 271 | 57.0% | `networkx.algorithms.shortest_paths.weighted:_dijkstra_multisource` |
| method: class shape (decorators, bases, metaclass or class attrs) | 207 | 39.9% | 4.649 s | 40.0% | 207 | 40.0% | `difflib:SequenceMatcher.find_longest_match` |
| method: field kind not expressible | 15 | 2.9% | 0.179 s | 1.5% | 13 | 1.4% | `sqlparse.engine.statement_splitter:StatementSplitter.process` |
| method: decorated, dunder or non-plain signature | 15 | 2.9% | 0.103 s | 0.9% | 15 | 0.9% | `tomli._parser:NestedDict.get_or_create_nest` |
| method: calls a method that stays in CPython | 4 | 0.8% | 0.043 s | 0.4% | 5 | 0.4% | `tomli._parser:NestedDict.append_nest_to_list` |
| method: self used other than reading a field | 4 | 0.8% | 0.020 s | 0.2% | 5 | 0.2% | `sqlparse.filters.reindent:ReindentFilter._process` |
| method: writes a self field (write-back is opt-in) | 2 | 0.4% | 0.001 s | 0.0% | 2 | 0.0% | `sqlparse.engine.statement_splitter:StatementSplitter._reset` |
| method: calls a method that is not a plain method | 1 | 0.2% | 0.000 s | 0.0% | 1 | 0.0% | `sqlparse.sql:NameAliasMixin.get_alias` |

The **top three reasons cover 98.55%** of the hot-module profiled time in the plain build and
**98.46%** with observed kinds (the first two alone are 97.0%). Their share of the whole-workload
cProfile time is 25.4%, 17.8% and 0.7%.

Per library (plain build; time is hot-module cProfile self time, `units` is definitions):

| library | units | self s | dominant first refusal |
| --- | ---: | ---: | --- |
| networkx | 41 | 2.840 | 100% not a typed candidate |
| jsonschema | 61 | 0.434 | 100% of profiled time not a typed candidate (15 methods are class-shape with 0 s) |
| chardet | 7 | 0.008 | 100% class shape; 2.0 s of the workload is in unbuilt prober modules |
| tomli | 38 | 2.108 | 89.3% not a typed candidate |
| difflib | 44 | 2.529 | 96.1% class shape (SequenceMatcher) |
| pydantic | 205 | 1.590 | 60.8% class shape, 39.1% not a typed candidate |
| sqlparse | 123 | 2.113 | 52.3% class shape, 35.4% not a typed candidate, 8.5% field kind |

## Which three reasons keep the time, and what fixing each would cost

1. **`not a typed candidate` — 271 definitions, 6.626 s, 57.0% of hot-module time.**
   This is still the opaque `pymix` gate. The hottest units are exactly the shapes it cannot carry:
   networkx's `_dijkstra_multisource` (graph object, dict of dicts), tomli's parser helpers
   (dict/list/tuple values), pydantic's `validate_model` (dict of unions, tuple return), sqlparse's
   `_group`/`imt` (`None` returns, `int|None` parameters), jsonschema's regex matches and
   validators. **Honest cost:** naming the sub-reason is about 1 hour (wedge3 already asked for
   it). Adding one concrete kind such as `dict[str, int|str]` is about 2 hours by the wedge3
   estimate, but that one kind would reach only a minority of these 271 units. The dominant
   shapes are user objects, nested dicts, tuples and unions, each needing a new checked ABI
   entry and fallback path: **2-5 days for a meaningful fraction, not a small patch.**

2. **`method: class shape` — 207 definitions, 4.649 s, 40.0% of hot-module time.**
   These are methods on classes with a base, class attributes, decorators or a metaclass:
   difflib `SequenceMatcher` (class attributes `b2j`, `bpopular`), sqlparse `Token`/`TokenList`
   (bases and class attributes), pydantic `BaseModel`/`ModelField` (bases/metaclass).
   **Honest cost:** the narrow relaxation wedge3 scoped (`class C(object)` with literal or
   `re.compile` class constants) is about 2 hours and would cover part of difflib/chardet. General
   inheritance, metaclasses and arbitrary class attributes need an attribute model and guarded
   reads: **2-4 days.** It is not a native win by itself: after the class gate these methods
   still hit the field-kind, self-use and calls-to-CPython gates.

3. **`method: field kind not expressible` — 15 definitions, 0.179 s, 1.5% of hot-module time.**
   Almost all are sqlparse fields that are lists/dicts/`None`/token objects (`self.tokens`,
   `self._block_stack`, `self._curr_stmt`). **Honest cost:** one checked non-scalar field kind is
   roughly **1-2 days**; several kinds plus the write-back rules are more. The payoff is capped by
   this reason's 1.5% share and by the class-shape gate in front of it. The first two reasons
   already cover 97.0%, so this third place is small: the next reason after it, decorated/dunder
   methods, is only 0.9%.

**Observed kinds do not change the answer.** `annotate` changed the raw first-refusal text of **3**
of the 519 definitions, all sqlparse: `ReindentFilter._get_offset` (`self.char` ->
`self.leading_ws`, both still `method: field kind not expressible`), `_process_identifierlist`
(field-kind -> self-use), and `_process_values` (field-kind -> calls-CPython). Folded to the
grouped gates, that is **2** changes (`_get_offset` stays in the same group), and either way
**0 native functions** were added.
Pydantic is already annotated (`Any` is kept), and the untyped libraries' observed kinds are
`None`, unions, containers and user objects, which are precisely the kinds the ABI cannot carry.
This matches the wedge3/wedge3b conclusion: the blocker is the unit/kind selection, not missing
annotations.

## Reproduce

```sh
python3 -m venv /tmp/r1/v3
/tmp/r1/v3/bin/pip install -r lab/refuse1/requirements.txt
python3 -m venv /tmp/r1/v3b
/tmp/r1/v3b/bin/pip install --no-binary pydantic -r lab/refuse1/requirements-wedge3b.txt
REFUSE_CPY3=/tmp/r1/v3/bin/python REFUSE_CPY3B=/tmp/r1/v3b/bin/python \
  python3 lab/refuse1/measure.py -o lab/refuse1/results.json
```

The two pins files are copies of the branch files named above (only the header comments and the
self-referencing filename differ), so no fetching of an unmerged branch is required. `measure.py` does not create the venvs or install the pins; it only
uses the two interpreters passed in `REFUSE_CPY3` / `REFUSE_CPY3B`. `results.json` holds the
per-definition raw reason and self time for both builds, the per-library totals, the grouped
tables and the `reason_changes_plain_to_obs` list (2 grouped gates; the raw-reason change count is
3 because `_get_offset` changes its raw field name within one group).

## What is not measured

* No instruction counts: `perf_event_open` is denied on this runner, as in wedge3/wedge3b.
* No wall-time or speed claim: the hybrid made 0 functions native, so there is no native path to
  time. cProfile self time is used only to rank refusals.
* Only the listed hot modules are built. For chardet that is 0.008 s of the 2.0 s workload; the
  per-byte work is in prober modules this job (like wedge3) does not build.
* The `not a typed candidate` group is not split further, because `build.json` does not expose
  `pymix`'s sub-reason. Splitting it is the ~1 hour task in item 1; this job did not change the
  compiler to obtain it.
* The 519 rows count definitions, not distinct names: pydantic's overloads add 4 extra rows under
  2 names.

## Self-check

No compiler or runtime behaviour changed. The one probe,
`/tmp/probes/refuse1_shapes.py` (scalar function, list parameter, graph-like untyped function, a
class with a class attribute, and a field-storing method), gives `g same stdout` and
`d same stdout` under `bash ~/tools/cmp.sh ...`; an obs5 `build --cpython` of it reports
`not a typed candidate` for the functions, `class shape` for `Plain.add`, and the opt-in
field-write-back reason for `Store.bump`, and its generated `_run.py` prints the same stdout as
CPython. The measurement was checked end to end: 40 hybrid builds (20 modules x plain/observed),
all returned a `build.json`; all 519 definitions received either a `native` entry or a
`build.json` refusal in both builds; native counts are 0 in both. `results.json` is the output of
the committed script, and the observed-kind changes (3 raw reasons, 2 grouped gates) were re-read
from it. The required
repository tests are run on the final commit.
