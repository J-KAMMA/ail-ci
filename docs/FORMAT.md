# Formatting: `ail fmt --check`

AIL is Python syntax, so AIL writes no formatter of its own. `ail fmt` wraps an existing one and
does not add it as a dependency of the package.

    ail fmt --check FILE...          # the `ail` command wires this to packaging/ail_lang/fmt.py
    python3 -m ail_lang.fmt --check FILE...    # from packaging/, before the wiring lands

`--check` only asks a question and prints the answer; it never writes a file (there is no `--write`
mode).

| exit | meaning |
|---|---|
| 0 | every file is already formatted |
| 1 | at least one file would change; the unified diff is on stdout |
| 2 | no formatter on `PATH`, or the formatter itself failed |

With no formatter it prints exactly:

    ail fmt needs ruff or black on PATH: pip install ruff

## Which formatter runs

`ruff format` when `ruff` is on `PATH`, else `black`. The search is a plain `PATH` lookup, so a
pinned formatter in a throwaway virtual environment is used by putting it first:

    python3 -m venv /tmp/fmtvenv
    /tmp/fmtvenv/bin/pip install ruff==0.14.4 black==25.11.0
    PATH=/tmp/fmtvenv/bin:$PATH ail fmt --check src/main.py

The result below was produced with `ruff 0.14.4`. Neither formatter is installed by the package, so
a test that needs one skips with the reason instead of failing.

## Line length

The nearest `ail.toml` above each file may set the formatter's line length:

    [fmt]
    line-length = 100

It is passed as `--line-length 100`; without it, the formatter's own default applies (88 for both
ruff and black). A directory with no `ail.toml` leaves the default alone.

## Formatting does not change the build

`lab/fmt/check_build.py` proves the number: it takes 60 programs (the ten `lab/compare/src`
programs plus a round-robin spread over `lab/stdlib/*/`, `lab/errux/progs/` and `lab/safety/`),
builds each from its source, formats the same file in place, and builds it again from the same
path. The two builds are compared on:

* `program.c` after removing source line numbers (`#line` directives and the line argument of
  `AIL_DBG_SITE`),
* stdout and the exit status on the same stdin,
* the refusal text with line and column numbers removed, for a program the compiler refuses.

It also checks that a `# ail: gpu` marker and a PEP 263 coding line survive formatting, and that
`ail fmt --check` gives the same answer as `ruff format --check` on all 60 files.

Result (per-program table in [`lab/fmt/RESULTS.md`](../lab/fmt/RESULTS.md)):

* **0 of 60** programs changed their generated C, stdout, exit status or refusal.
* **60 of 60** check answers agree with `ruff format --check`.
* The `# ail: gpu` marker and the PEP 263 coding line survive.

Run it with the formatter on `PATH`:

    PATH=/tmp/fmtvenv/bin:$PATH python3 lab/fmt/check_build.py

The test module is `AIL_CURRENT/test_ail_fmt.py`: the exit-2 message always runs; the formatted /
unformatted / C-equality cases skip when neither ruff nor black is on `PATH`.
