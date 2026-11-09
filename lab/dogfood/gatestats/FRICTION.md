# dog1: gatestats friction log

Date: 2026-11-09. Tool: `lab/dogfood/gatestats/gatestats.py`.
Fixture: `lab/dogfood/gatestats/fixture/ci_integ.out` (400 log lines copied verbatim from the task plus
3 noise lines at the end: two `git` usage lines and `fatal: not a git repository ...`).
Reference output: `expected.out` (CPython 3.12). Results below are for the final commit.

**Tool works: yes.** The CPython output and the native `ailc` binary output are byte-identical on the
fixture and on the probes. The `--strict` build is accepted, so the typed path built the whole program.

## What the report means

The program reads the log path from `argv[1]`. A timestamp smaller than the previous timestamp starts
the next day. Per day it prints candidates (`candidate` lines), merged jobs (sum of job names on
`merged` lines), red batches (`red:` lines that are not `red alone:`), red-alone jobs (`red alone:`
lines), culprit-unavailable lines, and the hours from each red event to the next `candidate` or
`merged` line. Red-batch and red-alone durations are listed separately. Top modules are the jobs
named after `broken by` plus the jobs on `red alone:` lines, ordered by count then name; at most five
are printed. An unresolved red event at end of file is reported on a final line.

## Friction rounds (write -> compile -> fix)

The loop was `python3 AIL_CURRENT/ail_chatgpt.py check --syntax python gatestats.py` after each edit,
then `compile`; `check` is the fast type gate.

| # | Command / edit | Error text (abridged) | Did the message alone tell the fix? | Minutes lost | Fell to the general path? |
|---|---|---|---|---|---|
| 1 | first `check` | `'rest' is annotated str in the source, but the caller also supplies int; refusing rather than silently choosing one.` Suggested: annotate the parameter `int` or decode first. | **No.** The real cause was the 3-way `message.partition(": ")` tuple unpack: `rest` was typed from the tuple, and the suggested int/decode fix was misleading. Replaced the unpack with `rest = message[message.find(": ") + 2:]`. | ~2 | No; `check` failed before any build. |
| 2 | `n = min(5, len(top))` in the top-module block | `'top' is a srows; only an array, a list, a list of floats, a set, a dict, bytes and a list of str are walked as flat sequences here.` Suggested: loop over the rows or index `top[i][j]`. | **No.** The diagnostic names the list of tuples (`srows`) but suggests walking rows, not replacing the tuple list. First rewrote `min` as `n = len(top); if n > 5: n = 5`, which did not help. | ~1 | No; `check` stage. |
| 3 | same block after the `min` rewrite | Same `'top' is a srows ...` message, now pointing at `n = len(top)`. | **Partly.** It identifies `top` as the problem but not the concrete replacement. Replaced `list[tuple[int, str]]` with a list of a small `@dataclass` (`Ranked(count, name)`) and sorted with `key=lambda r: (-r.count, r.name)`. `check` then passed. | ~3 | No; `check` stage. |
| 4 | `compile` (default) | No error. | n/a | 0 | **No.** Also built with `--strict`: it succeeded with the same 98,888-byte binary and the same SHA-256 as the default build, and no `built on the general path` note. `file` shows an ELF PIE executable and `ldd` lists only libc (no libpython). A forced general build (`AIL_UNIFIED_FORCE=1`) also prints the same stdout. |

Total friction: about 6 minutes, mostly the list-of-tuples refusal. No program-level refusal appeared
on the typed path after the three edits, and no stdlib piece was missing (the tool uses only
`sys`, `open`, `str`, `list`, `dict`, and `dataclass`).

## Measurements on the fixture (median of 5)

| Measurement | CPython 3.12 | AIL native binary |
|---|---|---|
| Compile, cold (`AIL_NO_CACHE=1`) | - | 2.04 s (range 2.00-2.18 s) |
| Compile, warm cache | - | 0.17 s |
| Binary size | - | 98,888 bytes |
| Run wall time | 0.0291 s | 0.0009 s |
| Peak RSS | 13,008 KB | 1,968 KB |

The fixture is tiny (403 lines), so the run-time ratio (about 32x) is dominated by CPython startup;
the point here is equality of output and the native binary, not a benchmark claim.

## Probes

Each probe was run with `bash ~/tools/cmp.sh /tmp/probes/gatestats/<p>.py $PWD`, which diffs both the
forced-general build (`g`) and the default build (`d`) against CPython. All produced `g same stdout`
and `d same stdout`, exit 0.

| Probe | Boundary covered |
|---|---|
| `fixture.py` | the real fixture (400 log lines + 3 noise lines) |
| `basic.py` | candidate/merge, a retry-in-halves batch, a red-alone job |
| `rollover.py` | red at 23:59:30 resolved by a candidate at 00:00:30 (next day) |
| `reds.py` | two red events before one candidate; first/second duration |
| `culprit.py` | culprit-unavailable count and a `merged ... here (shared-file conflicts resolved)` line |
| `nodesc.py` | red event with no later candidate/merge (unresolved at EOF) |
| `empty.py` | empty file (no days, no modules) |
| `noise.py` | noise-only file (no timestamped lines) |
| `topmany.py` | more than five modules, ties, top-5 truncation |

Also checked: running with no argument gives the same usage text on stderr and exit 2 in both builds.

## Required AIL tests

`python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3`:
3 modules, 0 failed (236 s). No compiler, runtime, test, or manifest file was changed; the only
changes are under `lab/dogfood/` plus the DEVLOG record.
