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
| refused by `ailparse` | **0** |
| share of all extracted nodes | **99.9129%** |

The 143 expressions CPython itself rejects in eval mode are 106 `yield`, 35 `yield from`, and 2
starred assignment targets (`*x, y`, which is not an eval expression).  They are outside the stage-1
set and the parser is not asked to accept them.

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
keeps the source from just after the opening `{`, and a format spec that begins with `{{` keeps the
empty leading `Constant` CPython emits.  `...` is represented by a small local
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
