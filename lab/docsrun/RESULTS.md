# docsrun1: fenced blocks in README.md, docs/FFI.md, docs/LSP.md and docs/INSTALL.md

`AIL_CURRENT/test_ail_docs_blocks.py` parses every fenced block in those four files. A block is
run, parsed, or carries `<!-- docs-test: skip REASON -->` on the line before its opening fence.
An unmarked block of an unknown type fails the test.

## Before

`git grep` found no test that runs a block from these four files. Four FFI blocks are excerpts of
`examples/ffi/*.py`, which `AIL_CURRENT/test_ail_ffi_examples.py` builds and runs, but the blocks
themselves were never checked against those files. `test_ail_examples_mdlite.py` reads
`docs/INSTALL.md` and `README.md` as Markdown input; it does not run their code.

| File | Line | Language | Kind | Coverage before |
|---|---:|---|---|---|
| README.md | 28 | sh | shell commands (`tools/par_check.py`) | none |
| docs/FFI.md | 15 | sh | shell commands (zlib build/run) | none (same example indirectly exercised) |
| docs/FFI.md | 31 | python | FFI fragment (zlib) | excerpt of a tested example, block unchecked |
| docs/FFI.md | 48 | python | FFI fragment (libm) | excerpt of a tested example, block unchecked |
| docs/FFI.md | 60 | python | FFI fragment (libc) | excerpt of a tested example, block unchecked |
| docs/FFI.md | 83 | python | FFI fragment (sqlite) | excerpt of a tested example, block unchecked |
| docs/LSP.md | 45 | sh | shell commands (editor server) | none |
| docs/LSP.md | 52 | sh | shell commands (module server) | none |
| docs/LSP.md | 68 | json | VS Code package manifest | none |
| docs/LSP.md | 81 | js | VS Code extension | none |
| docs/LSP.md | 110 | js | VS Code client options | none |
| docs/LSP.md | 130 | lua | Neovim configuration | none |
| docs/LSP.md | 156 | sh | shell environment setup | none |
| docs/INSTALL.md | 30 | sh | Linux install commands | none |
| docs/INSTALL.md | 44 | sh | first program | none |
| docs/INSTALL.md | 53 | sh | typed program (fib) | none |
| docs/INSTALL.md | 75 | sh | macOS install commands | none |
| docs/INSTALL.md | 95 | powershell | native Windows install commands | none |
| docs/INSTALL.md | 128 | sh | checkout commands | none |
| docs/INSTALL.md | 138 | sh | `ail doctor` commands | none |

Total fenced blocks: **20** (README 1, FFI 5, LSP 7, INSTALL 7).
Uncovered blocks: **20** as written (4 are excerpts of files that another test runs).

## After

`python3 AIL_CURRENT/test_ail_docs_blocks.py` passes (6 tests).

| Outcome | Count | Blocks |
|---|---:|---|
| FFI examples built and run, stdout/stderr/exit compared with CPython | 4 | docs/FFI.md zlib, libm, libc, sqlite |
| Shell blocks run through the checkout in a temporary directory | 3 | INSTALL first program, typed fib (`12586269025`), `ail doctor` / `ail doctor --check` |
| JSON parsed with `json.loads` | 1 | docs/LSP.md `package.json` |
| Skipped with a reason | 12 | see below |
| Uncovered | **0** | |

The FFI blocks use `<!-- docs-test: ffi examples/ffi/NAME.py -->`: the test checks that every
paragraph of the block appears in the named whole example, then runs that example under CPython and
as an AIL executable. The shell blocks run with a temporary `ail` wrapper for
`python3 -m ail_lang`, with `AIL_CURRENT/` and `examples/` made visible from the checkout.

Skipped blocks and reasons:

| File | Line | Reason |
|---|---:|---|
| README.md | 29 | runs the whole suite, which CI does in 20 shards |
| docs/FFI.md | 16 | needs zlib.h and -lz; the same example is run by the zlib_check block below |
| docs/LSP.md | 46 | `ail lsp` is an interactive stdin/stdout server; run it from an editor |
| docs/LSP.md | 54 | starts the interactive server on stdin/stdout; an editor supplies the requests |
| docs/LSP.md | 84 | VS Code extension source; it needs VS Code and its extension host to run |
| docs/LSP.md | 114 | client-side VS Code configuration fragment; it needs VS Code to run |
| docs/LSP.md | 135 | Neovim configuration; it needs Neovim and starts an editor |
| docs/LSP.md | 162 | environment setup for an editor with placeholder paths; not a command sequence |
| docs/INSTALL.md | 31 | needs network, sudo and a fresh clone |
| docs/INSTALL.md | 77 | needs macOS, network and the Xcode Command Line Tools |
| docs/INSTALL.md | 98 | needs Windows, MSYS2 and network |
| docs/INSTALL.md | 132 | assumes hello.py from the First program section; doctor --check runs in Check the setup |

## Follow-ups

None. No doc example was wrong and no compiler bug was found: every block that was run matches
CPython (FFI examples) or exits successfully with the documented output (shell blocks). There is no
JSON-RPC request/response block in docs/LSP.md, so the LSP test parses the JSON block and does not
drive the server.

## Registration

`AIL_CURRENT/tests.d/test_ail_docs_blocks.txt` contains `test_ail_docs_blocks`; the manifest pins
were refreshed with `tools/update_manifest.py`.
