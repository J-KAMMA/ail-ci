# An agent's worked example: from a slow function to a verified speedup

This is one complete run, from a profile to a native build that still prints what CPython prints.
The two source files are [examples/agent_guide/slow.py](../examples/agent_guide/slow.py) (the
starting point) and [examples/agent_guide/fixed.py](../examples/agent_guide/fixed.py) (the result).

## 1. The agent finds the hot function

The program computes the total number of Collatz steps for every starting value below one million.
It also compares a text label with a number, which is a real bug in the source. The profile names one
function:

```sh
python3 -m cProfile -s tottime examples/agent_guide/slow.py
```

```text
finished 1000000
131434272
         7 function calls in 4.545 seconds

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    4.545    4.545    4.545    4.545 slow.py:4(collatz_total)
```

`collatz_total` takes 4.545 seconds of the 4.545-second profile. Its arguments and result are
`int`, so it is a candidate for AIL. The agent does not rewrite the whole program; it keeps the
function and asks the compiler to build it.

## 2. The strict build refuses it

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --strict --json --syntax python \
    examples/agent_guide/slow.py -o slow.bin
```

The command exits 3 and prints one `ail.strict/1` report (`--strict` uses that schema; a successful
build prints `ail.build/1`). `agent_diagnostics` has the same shape in both. The relevant part is:

```json
{
  "status": "refused",
  "exit_code": 3,
  "agent_diagnostics": [
    {
      "code": "AIL0103",
      "severity": "error",
      "file": "examples/agent_guide/slow.py",
      "line": 8,
      "col": 9,
      "cause": "`LABEL` is a str and `1` is a number; a str is never equal to a number, so this comparison is always False.",
      "fix": {
        "replace_range": [8, 8],
        "with": "        if LABEL == \"1\":"
      }
    }
  ]
}
```

The `cause` uses the names in the file, and `fix` is a literal edit: replace line 8 (1-based,
inclusive) with `fix.with`. The agent applies that edit and nothing else. The result is
[fixed.py](../examples/agent_guide/fixed.py): the comparison is now `LABEL == "1"`, which is the
intended comparison and is still `False` for `LABEL = "x"`, so this run's output does not change.

## 3. The rebuild passes

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --strict --json --syntax python \
    examples/agent_guide/fixed.py -o fixed.bin
```

Exit status is 0, `status` is `passed`, and `agent_diagnostics` is `[]`. The artifact is
`fixed.bin`; the original file was not modified.

## 4. The output still matches CPython

The agent runs both programs on the same source:

```sh
python3 examples/agent_guide/fixed.py > cpython.out
./fixed.bin > ail.out
diff -u cpython.out ail.out
```

Both print:

```text
finished 1000000
131434272
```

`diff` exits 0. With the installed `ail` wrapper, the same check is one command:

```sh
ail run --diff examples/agent_guide/fixed.py
```

which reports `ail diff: agree`.

## 5. The speedup

Three runs of each program on the same machine, measured with `/usr/bin/time -f '%e'`:

| run | CPython | `fixed.bin` |
| --- | --- | --- |
| 1 | 4.62 s | 0.16 s |
| 2 | 4.63 s | 0.16 s |
| 3 | 4.73 s | 0.15 s |
| median | 4.63 s | 0.16 s |

The median speedup is 4.63 / 0.16 = 28.9x. The numbers were recorded on a Linux x86-64 GitHub
Actions runner with 4 cores, CPython 3.12.3 and gcc 13.3.0, from the commit that added this page.
Only the run time changed: the compiled program prints CPython's two lines.

## 6. When a function cannot be accelerated

Not every function becomes native. The hybrid build keeps it on CPython and says why:

```sh
python3 AIL_CURRENT/ail_chatgpt.py build --cpython prog.py -o prog_fast
cat prog_fast/build.json
```

`accelerated` lists the functions that went native; `rejected` maps each remaining function to its
reason. The MCP server in [integrations/mcp](../integrations/mcp/README.md) exposes the same answer
as `ailc_explain(path, function)`. A function that stays in CPython still runs, and the program's
output is still the CPython output; the cost is the interpreter overhead for that function.

On this example the hybrid build is stricter than the standalone build above: it reports
`collatz_total` as `to_c-refused: 'LABEL' is read before it is assigned`, so the hybrid runs that
function in CPython. The standalone build types it (no general-path note, empty
`agent_diagnostics`), which is where the speedup comes from. If a hot function reads a module-level
constant, check the hybrid report before relying on it there.

## What the agent must not do

- Do not edit the program to make a diagnostic disappear if the edit changes what it prints.
- Do not apply a `fix` when it is absent; make the structural change named by `cause` instead.
- Re-run the CPython comparison after every edit, on real input.
- Stop and report if the compiler and CPython disagree; that is a compiler bug, not a speed-up.
