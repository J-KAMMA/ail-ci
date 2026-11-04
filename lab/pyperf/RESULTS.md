# pyperf subset: ten plain-Python programs through AIL

Date: 2026-11-04.  Commit: a2d6570 (the ten programs and `run.py`).  CPU: AMD
EPYC 9V45 96-Core Processor.  Oracle: CPython 3.12.3.  Build: the default
command (`AIL_NO_CACHE=1`, 300 s timeout, 1.5 GB address space), measured by
`python3 lab/pyperf/run.py`.

All ten programs build in the default mode and print exactly what CPython
prints at the default size, with the same exit status.  Two take the typed
path; eight fall back to the general path; none is refused.

| program | path | matches | CPython instructions | AIL instructions | ratio | CPython wall (s) | AIL wall (s) |
|---|---|---|---|---|---|---|---|
| fannkuch | typed | yes | n/a | n/a | n/a | 4.953 | 0.184 |
| float_bench | typed | yes | n/a | n/a | n/a | 1.398 | 0.203 |
| generators | general | yes | n/a | n/a | n/a | 1.568 | 2.291 |
| nbody | general | yes | n/a | n/a | n/a | 1.288 | 1.796 |
| nqueens | general | yes | n/a | n/a | n/a | 1.787 | 2.725 |
| raytrace | general | yes | n/a | n/a | n/a | 1.201 | 1.137 |
| richards | general | yes | n/a | n/a | n/a | 1.486 | 1.272 |
| scimark_fft | general | yes | n/a | n/a | n/a | 0.967 | 2.004 |
| scimark_sor | general | yes | n/a | n/a | n/a | 1.067 | 4.366 |
| spectral_norm | general | yes | n/a | n/a | n/a | 2.053 | 0.866 |

Wall time is the median of three runs of each binary at the default size.

## Instruction ratio

`tools/icount.c` cannot read the counter on this machine:
`perf_event_open: Permission denied` (`/proc/sys/kernel/perf_event_paranoid`
is 4), so the instruction columns and the geomean instruction ratio are not
available.  Per the task's stop rule the measurement is wall time only.

**Geomean wall ratio CPython/AIL over the ten matching programs: 1.353**
(AIL is 1.35x faster overall; 27x on the typed fannkuch, 0.24x on the general
scimark_sor).

## Follow-ups: the first fallback line of each non-typed program

These are printed by the default build (`note: ... built on the general path
...`), kept verbatim from `results.json`:

- `generators.py:14:9: ... because yield: this language has no generators. write instead: build a list with `out.append(x)` and `return out`; run with --strict to see why`
- `nbody.py:31:13: ... because a int holds integers; storing a float would truncate it; a set and a dict are not widened to floats at all (SEMANTICS section 13 says why not), so key them by a whole number you compute yourself; run with --strict to see why`
- `nqueens.py:16:13: ... because 'cols' is a list parameter, which is read-only; to change it in a helper, keep the list in a class field and pass the class (`s.xs[i] = v` and `s.xs.append(v)` work), or build and return a new list; run with --strict to see why`
- `raytrace.py:18:9: ... because field 'x' requires a class instance; run with --strict to see why`
- `richards.py: ... because the constant None; this language has no null value, so nothing holds one -- build a linked structure as parallel index lists (left[] and right[] of int, -1 where Python would put None) and walk it with a list used as an explicit stack; run with --strict to see why`
- `scimark_fft.py:24:13: ... because 'xr' is a list parameter, which is read-only; ...`
- `scimark_sor.py:21:5: ... because line 21: `gi = grid[i]` makes a second reference to the same container (`gi` and `grid` are one list/dict/set, or one holds the other), and one of the two is written while the other is read afterwards. CPython shares the object there; this compiler would copy and print something else, so it refuses rather than differ. write instead: store `gi.copy()` (or list(gi) / dict(gi) / set(gi)) for a copy; to share, keep a single name or pass the container to a function; run with --strict to see why`
- `spectral_norm.py:22:9: ... because 'out' is a list parameter, which is read-only; ...`

The two typed programs (`fannkuch`, `float_bench`) produce no note.

## Forced unified build (record only)

Every program was also built with `AIL_UNIFIED_FORCE=1` and compared with
CPython at the small size (`python3 lab/pyperf/run.py --unified --small`).
All ten unify to the typed path and all ten match stdout and exit status.
This is recorded for information; the table above is the default build.
