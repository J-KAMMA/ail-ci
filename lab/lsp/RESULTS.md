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
