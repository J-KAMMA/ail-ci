# Missing agent CLI pieces: ready-to-queue task text

The aiknow1 plan asked for five agent-facing commands. Three exist and are documented in
[`llms.txt`](../../llms.txt) and the [agent guide](../AGENT_GUIDE.md):

- `ail build` (the `ail` wrapper over `compile`)
- `ail run` and `ail run --diff`
- `--json` diagnostics on `compile` (`ail.strict/1` on a `--strict` refusal, `ail.build/1` on success)

Two do not exist in this build, so they are deliberately absent from the agent docs. Each task
below is sized at about two hours and is written to be queued as-is.

## Not implemented: `ail ext`

There is no `ext` subcommand, and `ail build --cpython` does not work: the wrapper forwards to
`compile`, which has no `--cpython` flag. The hybrid build is reachable only through the compiler
entry point:

```sh
python3 AIL_CURRENT/ail_chatgpt.py build --cpython prog.py -o prog_fast
```

### Task A — `ail-ext1`: `ail ext` builds an importable CPython extension

```
Lane: packaging / CLI. 2 hours.

The hybrid build is the CPython-fallback story, but the agent-facing wrapper cannot reach it: `ail
build --cpython` forwards to `compile`, which rejects `--cpython`. Add one documented command.

1. packaging/ail_lang/cli.py: add `ext` to the command table. `ail ext SOURCE -o DIR` runs the
   compiler's `build --cpython SOURCE -o DIR`, passing `-o/--out` through and printing the same
   `ail.build/1`/`ail.strict/1` JSON when `--json` is given. With no `-o`, default to
   `SOURCE.with_suffix('')` (the hybrid already writes a directory). Reject `--strict` with a
   message that names the standalone build as the strict path; do not silently ignore it.
2. packaging/ail_lang/cli.py: update the `ail help` text and packaging/README.md with one `ext`
   example.
3. Test: new AIL_CURRENT/test_ail_cli_ext.py. Prove `ail ext` on a typed program produces
   `DIR/build.json`, `DIR/run.py` (the launcher) and the built extension; `--json` prints the
   report; the launcher's stdout equals CPython's on the same input; a program with a refused
   function still produces a runnable launcher and `rejected` names that function.
4. Prove: test_ail_cli_ext and packaging smoke (tools/install_smoke.py), plus test_ail_safetynet,
   test_ail_files and test_ail_corpus_findings3 on the final commit.
```

## Not implemented: `--why`

No `check`/`compile` flag explains why a function stays on CPython. Today the only answer is
`build --cpython`, which builds C first, then the caller reads `build.json.rejected`. The MCP server
wraps that full build for `ailc_explain`.

### Task B — `ail-why1`: `--why` reports the CPython fallback reason without building

```
Lane: compiler / CLI. 2 hours.

An agent that profiled a hot function needs the hybrid's per-function answer without paying for a
build. Add `--why` to `check` and `compile`, and the same option to the wrapper's `ail check`.

1. AIL_CURRENT/ail_chatgpt.py: `check --why --json SOURCE` and `compile --why --json SOURCE` print
   one `ail.why/1` object: for every top-level function, `accelerated: true` or
   `on_cpython: true` with the existing hybrid `rejected` reason string. Reuse the classifier that
   `build --cpython` uses; do not duplicate the reason text. With `--why` alone (no `--json`),
   print one line per function: `NAME: accelerated` or `NAME: on CPython -- REASON`.
2. AIL_CURRENT/ail_chatgpt.py: `--why` must not link or run the C compiler and must not write an
   artifact. It exits 0 when every function is accelerated, 3 when at least one is not (matching
   the standalone build's refusal code), and 2 on a bad path.
3. packaging/ail_lang/cli.py: let `ail check --why` reach the flag; document it in the `ail help`
   text and docs/CLI.md.
4. Test: new AIL_CURRENT/test_ail_why.py. Prove `accelerated: true` for a typed function and the
   exact hybrid reason for a refused one (list-parameter mutation, while-else, and a module-level
   constant read); prove no executable and no build directory appear; prove the wrapper form
   prints the same lines.
5. Prove: test_ail_why, test_ail_agent_integrations (update the llms.txt command test to include
   the now-supported flag), test_ail_safetynet, test_ail_files, test_ail_corpus_findings3.
```
