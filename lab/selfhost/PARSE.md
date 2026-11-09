# shparse1: `ailparse`, the expression parser in AIL

Measured 2026-11-08 on branch `job-shparse1-11081724` (base `origin/integ` after shast1), GitHub
Actions runner, CPython 3.12.3, gcc 13.3.  `selfhost/src/ailparse.py` is plain Python 3.12 that both
CPython and AIL run; it imports only `ailtok` and `ailast`.  `selfhost/ref/expr_ref.py` is the
CPython-only stage 0 reference and segment extractor, and `selfhost/drv/expr_drv.py` is the stage 1/2
driver.

## Extraction

For every file, `expr_ref.py` takes each `ast.expr` node whose parent is a statement, uses
`ast.get_source_segment`, and wraps a segment that spans a line boundary in parentheses.  On S376
that gives **164,248 segments**.  Writing them as one file each lets the stage 1 and stage 2 drivers
read exactly the same text; `OUTDIR/list.txt` is the driver list and `OUTDIR/labels.txt` maps each
segment back to `<source>:<index>`.

## Stage 1

`ailast.dump(ailparse.parse_expr(text))` against
`ast.dump(ast.parse(text, mode="eval").body)`, attributes off:

| count | value |
|---|---:|
| segments extracted | 164,248 |
| CPython eval mode accepts | 164,105 |
| identical | **164,105 (100.0000% of parseable)** |
| accepted but different | **0** |
| refused by `ailparse` among CPython-accepted | **0** |
| share of all extracted nodes | **99.9129%** |

The 143 expressions CPython itself rejects in eval mode are 106 `yield`, 35 `yield from`, and 2
starred assignment targets (`*x, y`, which is not an eval expression).  `ailparse` refuses all 143 by
name: 141 as `ailparse: yield not supported` and the 2 assignment targets as
`ailparse: token STAR not supported`.  No expression CPython rejects is accepted.

The full S376 pass takes **20.6 s** in one process and peaks at **233 MB** (extraction plus the stage
0 reference plus stage 1 parse/dump).

## Stage 2

`expr_drv.py` builds on the **general path** (the `ailast` class attributes are the same blocker
shast1 recorded):

    AIL_NO_CACHE=1 AIL_PATH=selfhost/src python3 -B AIL_CURRENT/ail_chatgpt.py compile \
        selfhost/drv/expr_drv.py -o expr_drv

The build takes **59.8 s** and the binary is 1,643,336 bytes.  On the 30 fixed S376 files of the test
(13,486 extracted segments, 13,457 of them parseable) stage 2 prints **byte for byte what stage 1
prints**: 0 different, 0 refused.

| run (30 files, 13,486 segments) | seconds, median of 3 | peak RSS |
|---|---:|---:|
| stage 0, CPython `ast` | 0.55 | 13 MB |
| stage 1, CPython + `ailparse` | 1.23 | 12 MB |
| stage 2, AIL build | **1.31** | 17 MB |

The stage 2 test in `AIL_CURRENT/test_ail_selfhost_parse.py` also runs the edge expressions below
(f-strings with `=`, nested specs, bytes/raw strings, lambdas with `/` and `*`, comprehensions,
displays, slices, walrus, `await`, `...`) and they match stage 1 too.

## Refused constructs

The parser refuses no expression that CPython accepts in eval mode on S376.  Named refusals exist for
constructs outside this step: a complex literal (`1j`) and string `\N{...}` escapes are refused with
`ailparse: ... not supported`; neither occurs in S376.  Bytes literals follow CPython instead: `\u`,
`\U` and `\N` stay as literal backslash text (`b'\u0041'` is `b'\\u0041'`), and an octal escape is
truncated to a byte (`b'\400'` is `b'\x00'`, `b'\777'` is `b'\xff'`).  An f-string `=` debug field
keeps the source from just after the opening `{`; a format spec keeps the empty `Constant` CPython
emits before each `{{` group; and an empty plain string next to an f-string is dropped as CPython
drops it.  `...` is represented by a small local
sentinel whose `repr` is `Ellipsis`, because AIL cannot hold the CPython `Ellipsis` object as a value.

The reference's own top refused constructs (not parser refusals) are:

| construct | count |
|---|---:|
| `yield` | 106 |
| `yield from` | 35 |
| starred assignment target | 2 |

## Test

`AIL_CURRENT/test_ail_selfhost_parse.py` (registered by
`AIL_CURRENT/tests.d/test_ail_selfhost_parse.txt`) checks 200 fixed S376 expressions at stage 1, the
edge expressions at stage 1, the `...` and named-refusal behaviour, and stage 2 against stage 1 on 20
fixed S376 expressions plus the edge expressions.  It passes in about 59 s including the build.

# shparse2: whole modules and statements

Measured 2026-11-09 on branch `job-shparse2-11091432` (base `origin/integ` after shparse1), GitHub
Actions runner, CPython 3.12.3.  `selfhost/src/ailparse.py` now has `parse(src) -> Module`; it still
imports only `ailtok` and `ailast`.  `selfhost/drv/parse_drv.py` is the stage 1 / stage 2 driver and
`selfhost/ref/parse_ref.py` is the CPython stage 0 reference (`ast.parse` + `ast.dump` with
attributes off).  Both accept a `CORPUS.txt` list (sha256 lines included).

## Stage 1 result

    python3 tools/selfhost_diff.py --ref "python3 selfhost/ref/parse_ref.py" \
        --cand "python3 selfhost/drv/parse_drv.py" --list selfhost/CORPUS.txt --jobs 2

| count | value |
|---|---:|
| S376 files | 376 |
| identical (`ailast.dump(ailparse.parse(src))` == `ast.dump(ast.parse(src))`) | **376 (100%)** |
| different | **0** |
| refused by `ailparse` | **0** |
| reference seconds / candidate seconds | 2.45 / 8.24 |

The compiler-file part (156 files, 205k lines) is included in the 376.  Attributes are off in this
stage; positions are filled but not compared.  The parser covers expression statements, assignment
chains with tuple/list/star/attribute/subscript targets, augmented and annotated assignment
(`simple` flag), `return`, `raise ... from`, `assert`, `del`, `pass`, `break`, `continue`, `global`,
`nonlocal`, both import forms (dotted, `as`, `*`, parenthesized names), `if`/`elif`/`else`,
`for`/`while` with `else`, `try`/`except`/`else`/`finally`, `with` (several items and parenthesized
items), `def`/`async def` with decorators, positional-only, keyword-only, defaults, `*args`, `**kw`,
annotations and return annotations, `class` with bases/keywords/decorators, `lambda` defaults, and
`yield`/`yield from`.  Docstrings are ordinary `Expr(Constant(...))` nodes.

## S376 construct counts

Counts from `ast` over the 376 files; a construct with no occurrence is refused by name.

| construct | count | construct | count |
|---|---:|---|---:|
| `Assign` / multi-target | 38318 / 106 | `FunctionDef` | 8437 |
| decorated `def` | 88 | `ClassDef` / with bases / decorated | 447 / 251 / 13 |
| `Return` / bare | 18324 / 716 | `arg` / annotated | 19042 / 886 |
| defaults / keyword-only / `*args` / `**kw` / positional-only | 584 / 47 / 65 / 24 / 1 |
| `Raise` / bare / `from` | 3706 / 53 / 30 | `Assert` / with message | 11 / 5 |
| `Delete` | 69 | `Global` / `Nonlocal` | 46 / 8 |
| `Import` / `ImportFrom` | 991 / 258 | `alias` | 1481 |
| `If` / `For` / `While` | 29206 / 5896 / 787 | `For` else / `While` else | 10 / 1 |
| `Try` / handlers / `else` / `finally` | 744 / 629 / 3 / 156 | named handler / multi-handler | 135 / 25 |
| `With` / multi-item / bound `as` | 63 / 1 / 63 | `Yield` / `YieldFrom` | 106 / 35 |
| `AnnAssign` / without value / `simple=0` | 342 / 24 / 9 | `AugAssign` | 2171 |
| `NamedExpr` | 5 | `Constant` / bytes / ellipsis | 100502 / 137 / 1 |

Constructs with **zero** S376 occurrences are refused by name rather than built: `match`/`case`,
3.12 `type X = ...`, and generic `def f[T]`/`class C[T]` type parameters.  `async def`, `async for`,
`async with`, `await` and `except*` are implemented with local node classes in `ailparse.py`
(`ailast.py` has no such classes), but none occurs in S376, so they are not counted as moving the
number.

## Errors

`parse` raises `SyntaxError` where `ast.parse` does.  `AIL_CURRENT/test_ail_selfhost_parse.py` has 20
fixed snippets (5 legal, 15 rejected) and checks only error versus no error; the message text
differs and is not compared.  Result: **20/20 agree**.  `return` and `yield` at module level are not
errors for `ast.parse` and are accepted here as well.

## Test

The existing stage 1 expression tests still pass, and the test module now also parses 30 fixed S376
files and compares the dump with `ast.parse`, plus the 20 snippets.  All 7 tests pass in about 65 s,
including the existing stage 2 expression build.
