# A six-step tutorial project: a log analyser

This project grows one small program in six steps. Every step reads the same log format from
stdin, is written as ordinary annotated Python, and prints exactly what CPython 3.12 prints for the
same source and input.

All six steps build on the typed path with `--strict`; there are no general-path steps and no
strict-mode refusals to record. The log is deterministic: `gen_log.py` uses a small LCG, not the
`random` module, so a seed and a line count produce the same bytes on every CPython version.

## The log and the sample

`gen_log.py SEED N` writes N lines of `TIMESTAMP METHOD PATH STATUS BYTES MILLIS`. About 2% of the
lines are malformed: a few have too few fields and a few have a non-number in BYTES. Every 10,000th
line has `BYTES` equal to `99999999999999999999`, which is beyond int64. The committed
`sample.log` is `gen_log.py 2026 200` (200 lines, 5 malformed).

```sh
python3 examples/tutorial_project/gen_log.py 2026 200 > /tmp/sample.log
python3 examples/tutorial_project/gen_log.py 4242 5000 > /tmp/generated.log
```

Build a step from the repository root, then run it beside CPython:

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step1.py --strict -o /tmp/step1.bin
python3 examples/tutorial_project/step1.py < examples/tutorial_project/sample.log
/tmp/step1.bin < examples/tutorial_project/sample.log
```

The `--strict` builds below all succeeded. The binary path is `/tmp/stepN.bin` in each command.

## Step 1: count lines and malformed lines

It reads stdin one line at a time, counts every line, and counts a line as malformed when it does
not have six fields or when BYTES is not a run of digits. `str.isdigit()` is the plain-Python check,
so the huge value is still a well-formed line here.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step1.py --strict -o /tmp/step1.bin
python3 examples/tutorial_project/step1.py < examples/tutorial_project/sample.log
/tmp/step1.bin < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 2: count by status code

It keeps `dict[str, int]` counts keyed by the STATUS field and prints them in sorted order. This is
the first container with a declared key and value type.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step2.py --strict -o /tmp/step2.bin
python3 examples/tutorial_project/step2.py < examples/tutorial_project/sample.log
/tmp/step2.bin < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 3: sum and maximum of BYTES and MILLIS

It adds running totals and maxima for BYTES and MILLIS. AIL integers are int64 and overflow stops
the program loudly, so the value `99999999999999999999` cannot be converted. The program treats it
as malformed after a plain Python check: more than 19 digits, or 19 digits and lexicographically
greater than `"9223372036854775807"`. That keeps every convertible value, skips only the
out-of-range one, and makes the program keep running like the CPython source does.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step3.py --strict -o /tmp/step3.bin
python3 examples/tutorial_project/step3.py < examples/tutorial_project/sample.log
/tmp/step3.bin < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 4: parse into an `Entry`

The parsing moves into `def parse(line: str) -> Entry | None`, with a small `Entry` class holding
the six fields. `main` now handles one optional entry per line instead of repeating the field
checks.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step4.py --strict -o /tmp/step4.bin
python3 examples/tutorial_project/step4.py < examples/tutorial_project/sample.log
/tmp/step4.bin < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 5: top paths and MILLIS percentiles

It counts paths in `dict[str, int]` and prints the top five with `sorted(..., key=...)`, breaking
ties by path. It also keeps the valid MILLIS values and prints p50 and p99 by the nearest-rank
method, using integer arithmetic for the ranks.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step5.py --strict -o /tmp/step5.bin
python3 examples/tutorial_project/step5.py < examples/tutorial_project/sample.log
/tmp/step5.bin < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 6: options

It adds `--top N` and `--status 5xx` from `sys.argv`. `--status` accepts a status class such as
`5xx` and filters the report; the line and malformed counts still cover the whole input. An
unknown option, a missing value or a bad value prints the usage line to stderr and exits 2.

```sh
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/tutorial_project/step6.py --strict -o /tmp/step6.bin
python3 examples/tutorial_project/step6.py < examples/tutorial_project/sample.log
/tmp/step6.bin < examples/tutorial_project/sample.log
python3 examples/tutorial_project/step6.py --top 3 < examples/tutorial_project/sample.log
/tmp/step6.bin --top 3 < examples/tutorial_project/sample.log
python3 examples/tutorial_project/step6.py --status 5xx --top 2 < examples/tutorial_project/sample.log
/tmp/step6.bin --status 5xx --top 2 < examples/tutorial_project/sample.log
```

Typed: yes (`--strict`).

## Step 6 on a 50 MB log

The log was `gen_log.py 2026 1030000` (1,030,000 lines, 50,053,699 bytes). Times are wall-clock
seconds, median of 3 runs, on the GitHub Actions runner used for this task, with stdout sent to
`/dev/null` and `ulimit -v 1500000`. The AIL binary was built with `--strict`.

| Program | Wall time (s) | Binary bytes |
| --- | ---: | ---: |
| `python3` 3.12 | 1.055 | — |
| AIL step 6 (`--strict`) | 0.372 | 86,216 |

The 50 MB file is not committed.
