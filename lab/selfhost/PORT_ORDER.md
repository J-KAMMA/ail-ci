# shport0: the port order and the frozen differential corpus

Measured 2026-11-06 on branch `job-shtok1-op1106`, base `origin/integ` 8c2c99c18.  Measurement only;
no compiler file was edited.

- Tool: `python3 tools/selfhost_port_order.py [--inputs DIR] [--corpus]`
- Data: `lab/selfhost/port_order.json` (`schema: ail.selfhost_port_order/1`, `base_commit`)
- Corpus: `selfhost/CORPUS.txt`, 376 lines `sha256  path` (S376)

## Inputs, and where they came from

Three inputs are not on `origin/integ` yet.  They were read from their unmerged job branches
(`--inputs` pointed at a scratch copy; the JSON records each input's own base):

| input | branch (commit) | input base |
|---|---|---|
| `lab/selfhost/deps.json` (shdeps1) | `job-shdeps1-11060318` (29b637715) | 9326971cd |
| `lab/selfhost/files.json` (shfiles1) | `job-shfiles1-11060316` (82e3195dd) | 1d474e866 |
| `lab/profile/CTIME_FE.json` (ctimes1) | `job-ctimes1-11051342` (effbc50d1) | 2026-11-05 run |
| `lab/selfhost/SEED.md` (shseed1) | `job-shseed1-11060318` (1a71ef10c) | read, not joined |
| `docs/design/SELFHOST_FIXPOINT.md`, `DETERMINISM.md` (shfixpt1) | `job-shfixpt1-11060320` | **missing**: the branch holds only the task export |

`hot.json` and `census.json` are on the base.  The shfixpt1 documents are not needed by the ranking.

## Columns and rule

Per module of the full import graph reachable from `compile` (163 modules): lines, layer (full graph),
cycle id (index into `deps.json` full cycles), pooled own seconds over the 10 compare tasks
(`profile_view.modules`, the serial view for the three worker tasks) and its share of the pooled cold
wall (30.795 s), the whole-file build result and first refusal (files.json; `not in scope` for
`ir/*`, which shfiles1 did not build), `ast.` uses, `os.environ` reads, and the module's hot.json
functions.

Rank: 1500 lines or less, not "later", every eager import standard library or already ranked; an
import inside the module's own import cycle counts as satisfied (a cycle is ported as one unit;
without this the `ir.effects`/`ir.rtc` pair blocks all of `ir/`).  Highest own-time share first,
ties by name.  **135 of 163 modules are ranked**; 4 are "later", 21 are over 1500 lines, and 3 are
blocked by an over-limit import (`ail_sexpr` and `ail_source_edit` import `ail_syntax`; `filelib`).

## The first 10

| # | module | lines | layer | cycle | own s | share of cold wall | build | first refusal | `ast.` | `os.environ` | hot |
|---:|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|
| 1 | `fastwalk` | 49 | 0 | - | 0.860 | 2.79% | refused | `fastwalk.py:37:13: not in the subset: isinstance() with a non-name type argument` | 10 | 1 | walk |
| 2 | `ir.ir` | 469 | 0 | - | 0.307 | 1.00% | not in scope | - | 0 | 0 | - |
| 3 | `boolkind` | 1451 | 0 | - | 0.163 | 0.53% | refused | `boolkind.py:56: None stored in a list / tuple / dict / set ... use a sentinel value there` | 275 | 1 | _own_nodes |
| 4 | `callable_types` | 132 | 0 | - | 0.124 | 0.40% | refused | `callable_types.py:50:9: not in the subset: isinstance() with a non-name type argument` | 11 | 0 | - |
| 5 | `iterlower` | 1191 | 0 | - | 0.092 | 0.30% | refused | `iterlower.py:28: a module-level tuple constant must be numbers only ...` | 508 | 0 | - |
| 6 | `unbound` | 810 | 0 | - | 0.062 | 0.20% | refused | `unbound.py:59: a module-level tuple constant must be numbers only ...` | 208 | 0 | - |
| 7 | `pyfront` | 1456 | 4 | 2 | 0.055 | 0.18% | refused | `pyfunc.py:32:1: 'ast' is imported and also assigned or defined again in pyfunc.py ...` | 259 | 0 | - |
| 8 | `nested_lists` | 1004 | 0 | - | 0.035 | 0.11% | refused | `nested_lists.py:1: no repr for this type` | 289 | 0 | - |
| 9 | `typedforms` | 515 | 1 | - | 0.026 | 0.09% | refused | `typedforms.py:42: a module-level tuple constant must be numbers only ...` | 227 | 0 | - |
| 10 | `sortkeys` | 570 | 0 | - | 0.022 | 0.07% | refused | `sortkeys.py:1: a *argument in a call` | 146 | 0 | - |

Every one of them reads CPython `ast` (the `ast.` column) except `ir.ir`, so each port waits for
`ailast` (shast1) first.

## Later

| module | lines | own s | share of cold wall |
|---|---:|---:|---:|
| `pyfunc` | 42,062 | 12.946 | 42.0% |
| `cruntime` | 31,094 | 0.010 | 0.03% |
| `pyboxed2` | 13,856 | 0 | 0% |
| `ail_chatgpt` | 6,657 | 0 | 0% |

Together: 93,669 of 215,462 front-end lines (43.5%) and 12.956 of 16.788 own seconds (77.2%).
`pyfunc` alone is 77% of the measured module own time, so no compile-time gain is possible before it
is ported (and none is claimed until the whole front end runs).

## Class probe (`lab/selfhost/probe_nodes.py`)

The planned `ailast` shape: a base `AST` with class attributes `_fields`/`_attributes`, five
subclasses, `isinstance`, a mixed list, `None` fields, a breadth-first walk, `repr` of int, float,
str and bytes constants.

| mode | result | stdout = python3 |
|---|---|---|
| default | built, **general** path | yes |
| default, `AIL_UNIFIED_FORCE=1` | built, general (same binary hash) | yes |
| `--strict` | refused, 8 blockers | - |

First refusal (default note and strict blocker 1):

    lab/selfhost/probe_nodes.py:5:5: built on the general path (about 20x slower) because class
    attribute AST._fields = (); a class attribute here is an int, float, str or bool literal.

The other strict blockers are the six other tuple class attributes and `the constant None`.  No
miscompile.  The tokenizer (shtok1, `TOK.md`) adds a second blocker for the same plan: a field that
holds a list or str is not typed either.

## Expected order of the self-hosting jobs

1. shtok1: `ailtok` (done on this branch: S376 376/376 at stage 1 and stage 2, `TOK.md`)
2. shast1: `ailast` node classes (needs typed class fields beyond int/float/bytes to leave the general path)
3. shparse1-3: `ailparse`, the parser to `ailast`
4. shport1: `fastwalk.py` (rank 1; `walk` is the hottest single function, 2.264 s in hot.json)
5. shport2: `ir.ir` (rank 2 here; reads no `ast`)
6. shseed2: the committed C seed (tcc mob e23dabe)
7. shtcc1: the seed builds with tcc
8. shfix2: the fixpoint check
