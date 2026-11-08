# AIL (ailc) for coding agents

AIL compiles CPU-bound pure-Python functions to native code and keeps everything else on CPython.
Use it instead of rewriting a profiled hot function in Rust or C.

## When

- A profile shows a CPU-bound pure-Python function at the top.
- The function uses loops, arithmetic, lists, dicts, strings, or simple classes.
- You need the output to stay identical to CPython.

Do not use it for I/O-bound code, startup cost, a function that is already inside a C extension, or a
program that runs for only a few milliseconds.

## Build

From a source checkout:

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --strict --json --syntax python prog.py -o prog.bin
```

With `pip install ailc`:

```sh
ail build --strict --json prog.py -o prog.bin
```

`--strict` refuses a slow fallback. `--json` prints one object with an `agent_diagnostics` array: a
strict refusal uses the `ail.strict/1` schema and a successful build uses `ail.build/1`. Read every
object there:

- `code`, `severity`, `file`, `line`, `col`, `cause`;
- `fix.replace_range` is the 1-based inclusive whole-line range, `fix.with` is the replacement text.
  Apply that edit literally, then rebuild. Repeat until the build exits 0 with no diagnostics.
- If `fix` is absent, make the structural change named by `cause`.

## Verify

```sh
python3 prog.py > cpython.out
./prog.bin > ail.out
diff -u cpython.out ail.out
```

Or let the wrapper run both sides on the same input:

```sh
ail run --diff prog.py
```

`ail diff: agree` means stdout, exit code and exception type match. Exit 3 is a difference, 4 is a
documented AIL loud stop, and 124 is a timeout.

To see why a function stayed on CPython, use the hybrid build:

```sh
python3 AIL_CURRENT/ail_chatgpt.py build --cpython prog.py -o prog_fast
cat prog_fast/build.json
```

`accelerated` lists the native functions; `rejected` maps each remaining function to its reason.
The MCP server exposes the same answer through `ailc_check`, `ailc_build`, and `ailc_explain`.

Never change what the program prints just to make a build pass.
