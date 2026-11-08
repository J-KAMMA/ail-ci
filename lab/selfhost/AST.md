# shast1: `ailast`, the AST node classes in AIL

Measured 2026-11-08 on the `job-shast1` branch (base `origin/integ` after shtok1), GitHub Actions
runner, CPython 3.12.3, gcc 13.3.  `selfhost/src/ailast.py` is plain Python 3.12 that both CPython and
AIL run; `selfhost/ref/from_cpython.py` is the CPython-only converter.

## Node set

`ast.walk` over the 376 files of `selfhost/CORPUS.txt` gives **1,599,310 nodes of 87 types**.  All 87
are defined in `ailast.py` with CPython 3.12's `_fields` and `_attributes` in CPython's order, plus the
three operator/context singletons that S376 does not happen to hold (`MatMult`, `AugLoad`,
`AugStore`).  That is **90 concrete classes and the `AST` base**.  The one non-name class (`alias`,
`arg`, ...) keeps CPython's lowercase name, because `dump` prints `node.__class__.__name__`.

| type | count |
|---|---:|
| `Add` | 8807 |
| `And` | 10232 |
| `AnnAssign` | 342 |
| `Assert` | 11 |
| `Assign` | 38206 |
| `Attribute` | 124433 |
| `AugAssign` | 2165 |
| `BinOp` | 19474 |
| `BitAnd` | 300 |
| `BitOr` | 740 |
| `BitXor` | 57 |
| `BoolOp` | 14159 |
| `Break` | 258 |
| `Call` | 94536 |
| `ClassDef` | 447 |
| `Compare` | 30055 |
| `Constant` | 100225 |
| `Continue` | 1507 |
| `Del` | 69 |
| `Delete` | 69 |
| `Dict` | 2222 |
| `DictComp` | 359 |
| `Div` | 321 |
| `Eq` | 10335 |
| `ExceptHandler` | 624 |
| `Expr` | 17914 |
| `FloorDiv` | 339 |
| `For` | 5869 |
| `FormattedValue` | 813 |
| `FunctionDef` | 8415 |
| `GeneratorExp` | 2655 |
| `Global` | 45 |
| `Gt` | 1029 |
| `GtE` | 580 |
| `If` | 29108 |
| `IfExp` | 4222 |
| `Import` | 988 |
| `ImportFrom` | 257 |
| `In` | 6329 |
| `Invert` | 16 |
| `Is` | 2770 |
| `IsNot` | 2970 |
| `JoinedStr` | 451 |
| `LShift` | 258 |
| `Lambda` | 416 |
| `List` | 6112 |
| `ListComp` | 1732 |
| `Load` | 472933 |
| `Lt` | 1250 |
| `LtE` | 754 |
| `Mod` | 7734 |
| `Module` | 376 |
| `Mult` | 1257 |
| `Name` | 365003 |
| `NamedExpr` | 4 |
| `Nonlocal` | 8 |
| `Not` | 5212 |
| `NotEq` | 2149 |
| `NotIn` | 2177 |
| `Or` | 3927 |
| `Pass` | 161 |
| `Pow` | 73 |
| `RShift` | 108 |
| `Raise` | 3702 |
| `Return` | 18245 |
| `Set` | 537 |
| `SetComp` | 636 |
| `Slice` | 1210 |
| `Starred` | 622 |
| `Store` | 63442 |
| `Sub` | 1645 |
| `Subscript` | 19360 |
| `Try` | 739 |
| `Tuple` | 20914 |
| `UAdd` | 5 |
| `USub` | 1285 |
| `UnaryOp` | 6518 |
| `While` | 783 |
| `With` | 63 |
| `Yield` | 106 |
| `YieldFrom` | 35 |
| `alias` | 1477 |
| `arg` | 19002 |
| `arguments` | 8831 |
| `comprehension` | 5603 |
| `keyword` | 8119 |
| `withitem` | 64 |

## Class shape

`lab/selfhost/probe_nodes.py` (shport0, `PORT_ORDER.md`) found that a tuple class attribute such as
`_fields = ()` is refused on the typed path but the general path builds it and prints exactly what
CPython prints.  This port uses the same shape and therefore builds on the **general path** (one
`note: ... built on the general path ... class attribute AST._fields ...` line).  The other refusals
from that probe are avoided:

- `type(node)` is not in AIL's subset, so each class carries a string class attribute `_typename`
  (the class name) and `dump` / the self-test read that instead.
- `getattr(cls, name, ...)` (CPython's test for an optional field whose class default is `None`) is
  replaced by the class attribute `_optional`, the tuple of optional field names; each such field
  also has the class attribute `None` exactly as in CPython.
- `_fields` / `_attributes` are tuples of strings and `_optional` is a tuple of strings; `repr`,
  `isinstance`, `getattr` by a name read from a tuple, generators, nested functions and tuple returns
  all work on the general path (probed).
- The end positions are optional attributes, as in CPython 3.12: every class that has positions in
  `_attributes` also lists `'end_lineno'` and `'end_col_offset'` in `_optional`, carries class
  attributes `end_lineno = None` / `end_col_offset = None`, and defaults the constructor arguments to
  `None`.  `dump(include_attributes=True)` therefore omits an end position whose value is `None`, and
  prints an explicit `0` as CPython does; `lineno` / `col_offset` are not optional and print even when
  `None`.

## Stage 1

`ast.parse` -> `from_cpython.convert` -> `ailast.dump` against `ast.dump`, all 376 files, both with
`include_attributes=False` and `True`: **376/376 identical, 752/752 dumps**.  `walk`,
`iter_child_nodes` and `iter_fields` agree with the CPython functions on the same 376 trees (node
class names and field names, same order).  The whole pass takes **9.83 s, 372 MB peak RSS**.

`annotate_fields=False`, `indent=2` and `indent="\t"` are checked on 8 fixed files in the test module
and match `ast.dump` too.  `repr` of the constant types that occur in S376 (int, float, str, bytes,
bool, None and Ellipsis) comes from the language, not from a hand-written table.

## Stage 2

`selfhost/drv/ast_selftest.py` builds **40 fixed trees by hand** (no parser) and prints for each: the
default dump, the dump with attributes, the `walk` class-name order and the `iter_child_nodes` order.
The trees cover the statement, expression, comprehension, argument, import and pattern-adjacent node
families, and the tricky constants `0.1`, `1e16`, `1e-7`, `float("inf")`, `-float("inf")`, `-0.0`,
non-ASCII text (`héllo 日本`), quoted text and `b"\x00b\xff"`.

    AIL_NO_CACHE=1 AIL_PATH=selfhost/src python3 -B AIL_CURRENT/ail_chatgpt.py compile \
        selfhost/drv/ast_selftest.py -o ast_selftest

| run | seconds | peak RSS |
|---|---:|---:|
| build (general path, uncached) | 12.9 | 39 MB |
| stage 1, CPython + ailast | 0.01 | 12 MB |
| stage 2, AIL build (1,063,280-byte binary) | 0.00 | 5 MB |

**Stage 2 prints byte for byte what stage 1 prints for all 40 trees.**  No miscompile.

## Named refusals (recorded, not stops)

- **An int beyond int64 as a source literal.**  The default build refuses
  `x = 99999999999999999999` with `int64 constant expression out of range:
  99999999999999999999`.  This is a compile-time literal limit, not a difference in `dump`.  With
  `--exact-int` the same program builds on the general path and prints the big integer exactly as
  CPython does (checked in `test_big_int_exact_stage2`).  Stage 1 dumps the big-int `Constant`
  identically to `ast.dump`.
- **An Ellipsis constant.**  `x = ...` is refused by name (`not in the subset: a constant of type
  ellipsis`), so a stage-2 tree cannot hold `Constant(value=Ellipsis)`.  Stage 1 handles the one
  Ellipsis constant that occurs in S376.  The 40-tree stage-2 self-test does not use Ellipsis.
- **A complex constant.**  `x = 1j` is refused by name (`not in the subset: a constant of type
  complex`), so a stage-2 tree cannot hold `Constant(value=1j)` either.  Stage 1 dumps a complex
  `Constant` exactly as `ast.dump` does; the 40-tree stage-2 self-test does not use complex.
- The general-path note above is the only build note; it is not a semantic difference.

## Test

`AIL_CURRENT/test_ail_selfhost_ast.py` (registered by `AIL_CURRENT/tests.d/test_ail_selfhost_ast.txt`)
runs 30 fixed S376 files through stage 1 with both attribute settings and the dump arguments, checks
`walk` / `iter_child_nodes` order, checks that a `None` end position is omitted while an explicit `0`
is printed, checks the big-int and Ellipsis stage-1 dumps and the default-build big-int refusal, and
builds `ast_selftest.py` for stage 2 (skipped without a C compiler).  It passes in about 15 s.
