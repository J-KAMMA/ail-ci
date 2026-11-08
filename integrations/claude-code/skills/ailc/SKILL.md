---
name: ailc
description: Compile a CPU-bound pure-Python function with AIL (ailc) instead of rewriting it in Rust or C. Use when a profile names a slow pure-Python function and you need native speed with CPython-identical output.
---

# Speed up a slow pure-Python function with AIL

Use this skill when a profile shows a CPU-bound pure-Python function at the top and the rest of the
program is fine. AIL compiles the typed parts to C and keeps anything it cannot prove on CPython, so
the output still has to match CPython.

Do not reach for AIL when the cost is I/O, startup, a call into an existing C extension, or when the
program runs for only a few milliseconds.

## 1. Find the hot function

Profile first; do not guess. For a script:

```sh
python3 -m cProfile -s tottime prog.py
```

Pick one small top-level function whose self time dominates and whose arguments and result are
`int`, `bool`, `float`, `str`, or a list of those. Leave the rest of the program alone.

## 2. Build it

From a source checkout (the compiler is `AIL_CURRENT/ail_chatgpt.py`):

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --strict --json --syntax python prog.py -o prog.bin
```

After `pip install ailc`, the same build is:

```sh
ail build --strict --json prog.py -o prog.bin
```

`--strict` refuses a fallback instead of silently running the function on the general path. `--json`
prints one JSON object; `agent_diagnostics` is the list to read. A refusal under `--strict` uses the
`ail.strict/1` schema; a successful build uses `ail.build/1`. `agent_diagnostics` has the same shape
in both.

A successful build exits 0 and writes the executable named by `-o`; the report's `output.output`
repeats that path. A refusal exits 3 and still prints the JSON report. The build is additive: the
original `.py` file is unchanged.

## 3. Apply the diagnostics

Read each object in `agent_diagnostics`:

- `code`: a stable family, `AIL0101` through `AIL0116`.
- `severity`: `error` (the build refused) or `note` (it fell back to the slow general path).
- `file`, `line`, `col`: the position in the file you wrote.
- `cause`: one sentence using your names.
- `fix.replace_range` + `fix.with`: when present, replace those whole lines (1-based, inclusive) with
  the given text. Apply it literally; do not retype it from `message`.

Example: a `while ... else:` inside the hot function produces `AIL0109` with a `fix` that moves the
`else` body after the loop. Apply that edit, then rebuild with the same `--strict --json` command.
Repeat until the exit status is 0 and `agent_diagnostics` is empty.

If `fix` is absent, the cause names the structural change (a class instead of a mixed dict, a named
annotated list instead of a nested annotation, a returned list instead of a mutated parameter). Make
that change by hand and rebuild.

## 4. Confirm it still matches CPython

Check the output on real input, not just "it compiled":

```sh
python3 prog.py > cpython.out
./prog.bin > ail.out
diff -u cpython.out ail.out
```

The `ail` wrapper can do both runs with the same stdin, timeout and environment:

```sh
ail run --diff prog.py
```

It prints `ail diff: agree` when stdout, the exit code and the exception type match. Exit 3 means a
difference; exit 4 means an AIL loud stop that the docs list as a documented limit; 124 is a timeout.

## 5. When a function stays on CPython

With the hybrid build, functions that cannot be accelerated stay in CPython and the program still
runs:

```sh
python3 AIL_CURRENT/ail_chatgpt.py build --cpython prog.py -o prog_fast
cat prog_fast/build.json
```

`accelerated` lists the native functions. `rejected` maps every remaining function to the reason it
stayed on CPython. The MCP server exposes the same answer as `ailc_explain(path, function)`.

## Rules

- Never change the program's visible behaviour to make a build pass. If a suggested edit would change
  what prints, stop and report it instead.
- Keep the change local to the hot function unless the diagnostic names a call site.
- Re-run the CPython comparison after every edit.
- Do not add a dependency or a network call to make AIL accept the code.
