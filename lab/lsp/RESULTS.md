# LSP go-to-definition probe (`lab/lsp/def`)

40 cursor positions over `main.py`, `helper.py` and `lib/libmod.py` (the last found through
`AIL_PATH`), plus the bundled `struct` module. `expect.json` records the position and its expected
target; a `null` target means the answer must be empty (a builtin, a string, a comment, an
attribute of an unknown object).

| Stage | Correct | Wrong | Empty where a target exists |
| --- | --- | --- | --- |
| Before | 0/40 | 0 | 40 |
| After | 40/40 | 0 | 0 |

"Before" is the baseline: `ail lsp` did not answer `textDocument/definition` at all, so every
request returned `null`.

Reproduce:

    python3 AIL_CURRENT/test_ail_lsp_def.py

It starts the server, opens the probe files, and checks every position in `expect.json`.
