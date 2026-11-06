# Generated-C determinism, measured

Measured 2026-11-05 on `staging:integ` (branch `job-shfixpt1-11060320`) with
`tools/c_determinism.py`. Measure-only: no compiler file was edited.

This is the precondition for the self-hosting check in `docs/design/SELFHOST_FIXPOINT.md`. If the
compiler emitted different C for the same source from run to run, a stage-1/stage-2 fixpoint would
prove nothing.

## Method

30 programs: 10 from `lab/stdlib/` (one program in each of ten modules), 10 from `examples/`
(six `tutorial_project` steps and four `algos`), and the 10 `lab/compare/src/*/main.py`. Each was
built three times in the default (general) build and three times with `--strict` (typed), so 60
program-mode pairs and 180 builds. Every build had

- its own working directory (a fresh copy of the source),
- its own output directory and `--debug-dir`,
- `PYTHONHASHSEED` 0, 1 and `random` respectively,
- `AIL_NO_CACHE=1`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`,
- a 1.5 GB address-space limit; at most two builds ran at a time.

The three `program.c` files of a program-mode were compared byte for byte. A pair counts as
*identical* only when all three builds that produced C are byte-identical. A mode that refused in
all three builds (no `program.c`) is counted as *refused*, not as identical: a refusal is
deterministic, but it emits no C to compare. Every built binary was also run once; no two builds of
the same program produced different stdout or a different exit status, so there is no wrong-output
finding.

## Headline numbers

| measure | count |
|---------|-------|
| programs identical (every mode that built was identical) | **26 / 30** |
| program-mode pairs identical | **34 / 34 compared** (26 of 60 pairs were refused) |
| general build identical | **26 / 26 compared** (4 refused) |
| typed build identical | **8 / 8 compared** (22 refused) |
| differences observed | **0** |
| wrong-output findings | **0** |

Read the 34/34 carefully: it says *no nondeterminism was observed in the 34 program-modes this
probe could compare*. It does not say the compiler is deterministic for the programs it refused,
and it is one sample of three builds per program. The `random` seed in a 3-build sample can miss an
order difference that a pair of unlucky seeds would show; a positive result needs more seeds.

## Difference classes

Each class `tools/c_determinism.py` can record has count 0 here; there is no example diff to show.
The last column names the file `grep` found as the likely emitter if the class ever appears, so the
first occurrence can be routed without a fresh hunt. None of these is fixed by this task.

| class | count | example diff | file that would likely emit it |
|-------|-------|--------------|-------------------------------|
| hash order | 0 | none observed | `AIL_CURRENT/python/pkg-v12/pyfunc.py` (sets/frozensets iterated around lines 7, 92, 221, 504, 2109; line 415 already sorts `kinds`) |
| absolute path | 0 | none observed | `AIL_CURRENT/python/pkg-v12/c_object.py` (`.resolve()` of source/output at lines 125, 145) and `buildcache.py:243` |
| temporary name | 0 | none observed | `AIL_CURRENT/python/pkg-v12/c_api.py:253`, `c_export.py:226`, `c_object.py:356`, `c_api_bridge.py:165` (`tempfile` names) |
| time | 0 | none observed | `AIL_CURRENT/python/pkg-v12/buildcache.py:152` (`time.time()`), `clockrt.py` |
| counter | 0 | none observed | `AIL_CURRENT/python/pkg-v12/pyfunc.py` (`ctx.tmp += 1` at 1384 and 3157, `self.count += 1` at 5214) |
| other | 0 | none observed | — |

The two mechanisms that could still leak and are not covered by a class name: an emitter that
walks a `dict` of source names with a seed-dependent order (would show as *hash order*), and a
generated symbol built from `id()` or a process id (would show as *counter* or *other*). Neither
was observed.

## Per-program result

`identical` = all three builds in that mode emitted the same `program.c`; `refused` = no build in
that mode produced C. Every `general` refusal is a loud, named refusal, not a crash:

| program | general | typed |
|---------|---------|-------|
| `compare/berth_sim` | identical | refused |
| `compare/chain_relax` | refused | refused |
| `compare/echo_pack` | identical | identical |
| `compare/ledger_bin` | identical | refused |
| `compare/rail_transfer` | refused | refused |
| `compare/scar_life` | identical | refused |
| `compare/tally_lang` | refused | refused |
| `compare/term_rank` | identical | refused |
| `compare/ticket_audit` | identical | refused |
| `compare/tree_fold` | refused | refused |
| `examples/algos/dijkstra.py` | identical | refused |
| `examples/algos/levenshtein.py` | identical | refused |
| `examples/algos/mandelbrot.py` | identical | refused |
| `examples/algos/rpn.py` | identical | refused |
| `examples/tutorial_project/step1.py` | identical | identical |
| `examples/tutorial_project/step2.py` | identical | identical |
| `examples/tutorial_project/step3.py` | identical | identical |
| `examples/tutorial_project/step4.py` | identical | identical |
| `examples/tutorial_project/step5.py` | identical | identical |
| `examples/tutorial_project/step6.py` | identical | identical |
| `stdlib/base64/altchars_filesystem.py` | identical | refused |
| `stdlib/bisect/alias_import.py` | identical | identical |
| `stdlib/collections/config_layers.py` | identical | refused |
| `stdlib/csv/basic_roundtrip.py` | identical | refused |
| `stdlib/decimal/basic_arith.py` | identical | refused |
| `stdlib/getopt/01_short_options.py` | identical | refused |
| `stdlib/heapq/closest_points.py` | identical | refused |
| `stdlib/json/01_config_roundtrip.py` | identical | refused |
| `stdlib/shlex/01_command_line.py` | identical | refused |
| `stdlib/string/csv_punctuation_report.py` | identical | refused |

The 4 general refusals, reproduced by hand:

- `compare/chain_relax`: `main.py:27:27: int64 literal out of range: 18446744073709551615`.
- `compare/rail_transfer`: int64 literal out of range, then `cannot tell the type of element 0 of
  this tuple`.
- `compare/tally_lang`: `re.match(): these arguments are not built (pos / endpos are not)`, and
  the compiled pattern `TOK` used as a value.
- `compare/tree_fold`: `cannot tell the type of element 0 of this tuple`, and `NODE` used as a
  value.

The 22 typed refusals are the typed path's usual loud refusal (`--strict` prints the note and
exits non-zero). No typed refusal was a timeout or a crash in this sample.

## Reproducing

```
python3 tools/c_determinism.py -j 2 --json /tmp/cdet.json
python3 tools/c_determinism.py --summarize /tmp/cdet.json
```

The ratchet test `AIL_CURRENT/test_ail_c_determinism.py` re-builds three small programs twice with
`PYTHONHASHSEED` 0 and 1 and asserts identical C only for the rows above marked `identical`.
