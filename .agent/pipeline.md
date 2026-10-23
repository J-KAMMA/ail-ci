# job job-pre15-10240045  started 2026-10-23T16:09:29Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-present difference: `assert False, 42` now yields `e.args == (42,)` on both paths.

- Typed path: keeps numeric messages when `e.args` is read; still stringifies otherwise.
- General path: preserves the original message for `e.args` via `ail2x_raise_builtin`.
- Uncaught output remains `AssertionError: 42`.

Commit: `8d698fc` (branch `job-pre15-10240045`).

Probes in `/tmp/probes/`, all `g` and `d` builds same stdout:
`assert_args_int`, `assert_args_widths`, `assert_args_str`, `assert_args_sources`, `assert_args_uncaught`, `assert_args_containers` (6/6). The sources probe also passed a forced typed build.

Final-commit tests: `test_ail_pre15`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 28 tests OK, 1 skipped (`no zig`). `update_manifest.py --check` and `py_compile` pass.
[cost $0.0000, opencode tokens {"total": 5249642, "input": 111875, "output": 14656, "reasoning": 16295, "cache.write": 0, "cache.read": 5106816}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job-pre15-10240045 (`8d698fc`)

Change: `assert` messages now keep their value for `e.args` (pyboxed2 `ail2x_raise_builtin`; pyfunc skips the `str()` wrap when exception text is read). Adds `test_ail_pre15`, DIFFERENCES row, DEVLOG and manifest entry.

**Probes (HEAD, `cmp.sh`, g/d)**
- `r9/r10/r11/r24/r25`: `repr(e.args)`, `print(e.args)`, `str(e.args)`, f-string, `len`, index — all match CPython for int/float/str.
- `r12/r13/r14`, `r37/r38`: escaped and re-raised exceptions keep `(42,)`.
- `r21/r22/r23`: side-effecting messages (`f()`, `list.pop()`, walrus) evaluated once.
- `r15–r17`: iteration, slicing, tuple comparison match.
- `r18/r19/r20`: `None`, `bytes`, `nan` messages also now match (improvement beyond the requested int case).
- Worker's six probes: 6/6 match on both builds; `assert_args_uncaught` exits 1 with `AssertionError: 42` on both.
- `r8`: appended list/dict is reflected in `e.args`; `str(e)` remains stale (pre-existing, see below).

**Tests / records**
- `par_check -j 2 test_ail_pre15 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed.
- `update_manifest.py --check` and `py_compile`: pass.
- Generated C unchanged for programs not using the feature: `g08_014`, `g00_000`, and a numeric assert with no `.args` are byte-identical to base on both builds.

**Pre-existing (identical on base, non-blocking)**
- `repr(e.args[0])` / typed `e.args[i]` remains textual (e.g. `'3.0'`); `getattr(e, "args")` is still unsupported.
- Eager exception text: after mutating a list message, `str(e)` still shows the old contents (base same).
- General-path `repr(e)` of a numeric exception when `.args` is not read still quotes the value (base same).

**Claim check:** fix and no-regression claims verified; typed-path wording is slightly loose (it keys on any exception-text read, not only `.args`) — not a defect. Exact “28 tests, 1 skipped” count not independently reproduced, but all four modules pass. `tools/icount.c` is absent here, so instruction counts were not measured; codegen for the checked gdev programs is identical.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3479438, "input": 92038, "output": 10689, "reasoning": 26567, "cache.write": 0, "cache.read": 3350144}]

FINAL VERDICT: ACCEPT  2026-10-23T16:51:08Z
