# LSP go-to-definition probe (`lab/lsp/def`)

50 cursor positions over `main.py`, `helper.py` and `lib/libmod.py` (the last found through
`AIL_PATH`), `edge.py`, `use_pkg.py` with its `pkg` package, plus the bundled `struct` module.
`expect.json` records the position and its expected target; a `null` target means the answer must
be empty (a builtin, a string, a comment, an attribute of an unknown object).

| Stage | Correct | Wrong | Empty where a target exists |
| --- | --- | --- | --- |
| Before | 0/40 | 0 | 40 |
| After | 40/40 | 0 | 0 |
| After the review regressions (10 more positions) | 50/50 | 0 | 0 |

"Before" is the baseline: `ail lsp` did not implement `textDocument/definition` (it answered
`-32601 method not found`), so none of the 40 positions had a target.

The last 10 positions were added after review. They pin the four defects that review found, now
fixed: a comprehension's first iterable resolves in the enclosing scope (`edge.py:1:25`), a plain
`import pkg.sub` binds the package `pkg/__init__.py` (`use_pkg.py`), positions are sent as UTF-16
code units (`edge.py:6:11`, the emoji definition), and `except ... as name` / `match` captures
answer the name, not the whole clause or pattern (`edge.py`).

Reproduce:

    python3 AIL_CURRENT/test_ail_lsp_def.py

It starts the server, opens the probe files, and checks every position in `expect.json`.

# LSP hover with compiler-inferred types (`lab/lsp/hover`)

35 names: the five lsp1b review names (`a b c d n`) plus 30 more (arithmetic, user calls, `len`,
a `range` loop variable, list and dict element reads, `str` methods, one name assigned an int and
then a float, and one name on the general path). `expect.json` records the LSP position, the type
hover must show (`expected`), the `type(x).__name__` CPython prints at that line (`oracle`), and why
a `null` case must stay empty. `oracle.py` runs an instrumented copy under CPython and checks every
`oracle` field.

| Stage | Shown and right | Wrong | Empty where CPython has a type |
| --- | --- | --- | --- |
| Before (source-only hover) | 0/35 | 0 | 35 |
| After | 32/35 | 0 | 3 |

The three empty names are deliberate: `d = sum([1.5, 2.5])` (the C type is the numeric sum
`ail_nsum`, which is `int` or `float` at run time), `mixed` (assigned an int and then a float, so
the compiler boxes it), and `picked` (its function is on the general path, so there is no typed C).

What each compiler output gives (probe `probe.py`, 2026-11-08):

| Output | Locals? | What it gives |
| --- | --- | --- |
| `ail_chatgpt.py check --interface` | no | declared signatures only (`probe()` returns void); absent types are null |
| `check --interface --types-used --symbol probe` | no | the same declaration, plus reachable declared structs; no local types |
| `compile --strict --json` | no | build status, blockers, generated C line ranges; no local types |
| `compile --strict --debug --debug-dir DIR` | yes | `program.c` has `double v_a`, `int64_t v_b`, `ail_str v_text`, `ail_list v_nums`, ... next to the `#line N "file.py"` directives; `native_report.json` gives each C function's line range |

The typed C is the source used. `int64_t` -> `int`, `double` -> `float`, `ail_str` -> `str`,
`ail_list`/`ail_slist`/`ail_flist` -> `list`, `ail_tab` -> `dict`. `int64_t` is not shown as `int`
unless the source expression proves it is not `bool` (CPython `bool` is also `int64_t` in the C);
a comparison or `not` is shown as `bool`, and an unknown expression shows nothing. The build is
cached per document version and runs only after `didSave` or 1 s idle.

Reproduce:

    python3 lab/lsp/hover/oracle.py
    python3 AIL_CURRENT/test_ail_lsp_hover.py
