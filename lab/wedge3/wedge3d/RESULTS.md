# wedge3d: two real libraries vs the CPython hybrid and a native rewrite

Run 2026-11-09 on a 4-core GitHub Actions runner, CPython 3.12.3, PyPy 7.3.19 (Python 3.10.16),
gcc 13.3.0.  Hybrid AIL is worktree `../obs5` at commit **69e2dcd0a82580fa06e26b275352fbedfb7d31e1**
(branch `job-obs5-op1109`, observed-type work), not this checkout's `AIL_CURRENT`.  Native rewrites:
**ciso8601 2.3.3 (C)** for dateutil and **ahocorasick_rs 1.0.3 (Rust)** for ahocorapy.  Every timed
run used `ulimit -v 2500000`, one workload at a time; every run's stdout was compared byte for byte
with CPython before its time was recorded.

## Headline

**The observed-type hybrid accelerated nothing on either real library: 0 of 61 dateutil definitions
and 0 of 20 ahocorapy definitions, with or without observed kinds, so it ran at CPython speed while
the native rewrites ran 7.5x and 8.4x faster.**

## 1. Workloads

| library | pure Python path | native path | workload | output checked |
| --- | --- | --- | --- | --- |
| python-dateutil 2.9.0.post0 | `dateutil.parser.parse` | `ciso8601.parse_datetime` | 50,000 ISO/RFC-3339 date strings (date-only, naive, `Z`, ±14:00 offsets, microseconds); canonical UTC/naive ISO digest | count, FNV-1a digest, first, last |
| ahocorapy 1.8.0 | `KeywordTree.search_all` | `ahocorasick_rs.AhoCorasick.find_matches_as_indexes(overlapping=True)` | 500 patterns over a 19.2 MB text built to hit ahocorapy's per-character loop; matches canonicalised to `(start, pattern)` and hashed | pattern/text/match counts, FNV-1a digest, first, last |

Both drivers are in `workloads/`; `W3D_IMPL=python|native` selects the implementation and the
printed line is identical across implementations (verified by the harness on every timed run).
The date workload rejects non-ISO natural-language inputs because ciso8601 cannot parse them; the
same ISO string set is given to both paths.  The Aho text uses `pppppppx` filler so ahocorapy's
skip-regex fast path cannot skip most of the text; that is what makes the pure scan visible.

## 2. Per-library results

Wall seconds are the median of 5 fresh processes.  `hybrid` is `ail build --cpython` on the hot
module; `hybrid+obs` is the same build after `ail_observe.py run --fast` and
`ail_observe.py annotate --strip`.  Ratios are time ratios (below 1.0 is hybrid faster).

| library | hot module | defs / top-level / methods | native hybrid | native hybrid+obs | CPython s | PyPy s | hybrid s | hybrid+obs s | native s | hybrid/CPython | hybrid/PyPy | hybrid/native | obs/CPython | obs/PyPy | obs/native |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| python-dateutil | `dateutil/parser/_parser.py` | 61 / 4 / 54 | 0 | 0 | 1.1174 | 1.0785 | 1.1297 | 1.1282 | 0.1491 | 1.011x | 1.047x | 7.577x | 1.010x | 1.046x | 7.567x |
| ahocorapy | `ahocorapy/keywordtree.py` | 20 / 2 / 17 | 0 | 0 | 1.2366 | 0.3673 | 1.2467 | 1.2234 | 0.1492 | 1.008x | 3.394x | 8.355x | 0.989x | 3.331x | 8.198x |

The hybrid rows are noise around 1.0x: `build.json` lists `"accelerated": []` in all four builds
(plain and observed, both libraries), so no function ever entered native code.  PyPy is about equal
to CPython on dateutil and 3.4x faster on ahocorapy; the native rewrites are 7.5x and 8.4x faster
than the hybrid.  The observed recorder ran over the same package copies and annotated the hot
module, but it changed no selection (0 -> 0); the annotated module still produced byte-identical
output before it was rebuilt (`annotated_output_matches: true`).

## 3. Refusal reasons, ranked by the CPython time they cost

`cProfile` on the CPython driver gives each hot-module function's self time; a function the hybrid
did not wrap is charged to the reason in `build.json` (or to "no refusal recorded" when the build
never produced a candidate).  The profiled hot-module self time is 2.447 s for dateutil and 2.701 s
for ahocorapy, larger than the wall times above because cProfile adds per-call overhead; the
numbers rank reasons, they are not shares of wall time.

### python-dateutil (`_parser.py`, 56 rejected entries)

| # | reason | self s | funcs | example functions |
| ---: | --- | ---: | ---: | --- |
| 1 | method of a class with decorators, bases, a metaclass or class attributes | 2.2815 | 34 | `_timelex.get_token`, `_timelex.isnum`, `_ymd.resolve_ymd`, `parserinfo.month` |
| 2 | no refusal recorded (not selected as a candidate) | 0.0774 | 32 | `<genexpr>`, `__getitem__`, `_escape`, `_parse_flags` |
| 3 | a decorated, dunder or non-plain-signature method | 0.0648 | 2 | `_resultbase.__init__`, `_resultbase.__len__` |
| 4 | not a typed candidate | 0.0235 | 1 | `parse` |

The hot path is the `_timelex` tokenizer and the `parser._parse` family; every one is a method of a
class that has bases, decorators or class attributes, so the method pass refuses it before the type
pass.  `parse` itself is not a typed candidate.  Observed kinds cannot fix either gate: the class
shape gate is structural and the `parse` refusal is at the candidate stage.

### ahocorapy (`keywordtree.py`, 17 rejected entries)

| # | reason | self s | funcs | example functions |
| ---: | --- | ---: | ---: | --- |
| 1 | method: field `self._zero_state` has no scalar or int/float list kind | 2.6951 | 4 | `_search_all_string`, `_search_all_generic`, `_precompute_outputs`, `search_lss` |
| 2 | method: field `self._finalized` has no scalar or int/float list kind | 0.0022 | 2 | `add`, `finalize` |
| 3 | method: calls a method that stays in CPython | 0.0021 | 1 | `search_lss_for_children` |
| 4 | method of a class with decorators, bases, a metaclass or class attributes | 0.0015 | 1 | `State.__init__` |
| 5 | method: field `self._case_insensitive` has no scalar or int/float list kind | 0.0000 | 1 | `search_all` |
| 6 | a decorated, dunder or non-plain-signature method | 0.0000 | 1 | `KeywordTree.__init__` |
| 7 | no refusal recorded (not selected as a candidate) | 0.0000 | 3 | `<module>`, `KeywordTree`, `State` |

The whole search loop is blocked by one field: the automaton's `_zero_state` is a `State` object,
not a scalar or an int/float list, and its transitions are a dict of `State` objects.  The class
field-kind inference has no kind for that, so the hottest four methods are refused before the body
is examined.

## 4. Probes

No compiler or runtime code was changed; this job only measures.  The mandatory self-check probes
therefore exercise the two workloads and the hybrid/observed builds, not a compiler delta.
`bash ~/tools/cmp.sh` (the typed-build probe) is not applicable here because there is no `.ail`
source or compiler change.

| probe | cases | result |
| --- | --- | --- |
| `/tmp/probes/w3d_date_edges.py` | 20 dates: year 0001 and 9999, leap day, `Z`, ±14:00 and ±05:45/±03:30 offsets, 1/6-digit fractions, date-only, naive/space, empty, impossible dates | CPython, hybrid, hybrid+obs, PyPy and ciso8601 all match.  The only boundary difference is the exception **class** for invalid text: dateutil raises `ParserError` (a `ValueError` subclass), ciso8601 raises `ValueError`; both are `ValueError`, and invalid text is outside the workload. |
| `/tmp/probes/w3d_aho_edges.py` | 10 texts: empty, one char, prefixes/overlaps (`a`/`aa`/`aaa`), case variation, 24-char repeats, no-match text | CPython, hybrid, hybrid+obs, PyPy and ahocorasick_rs produce identical sorted match lists. |
| harness output checks | every timed run of both libraries (CPython, PyPy, hybrid, hybrid+obs, native) | stdout byte-identical to CPython; 0 mismatches. |
| harness annotated-source check | annotated hot module run before rebuilding | identical to CPython for both libraries. |

There is no workload output mismatch to report as a bug.  `build.json` refused every hot-module
function by name; the top reasons are in section 3.

## 5. Limits

* Instruction counts are missing: `tools/icount.c` builds, but `perf_event_open` is denied on this
  runner (`Permission denied`), so no `icount` column is reported.
* cProfile inflates self time, so section 3 ranks reasons but is not a wall-time share.
* The date workload is the ISO subset both dateutil and ciso8601 accept; dateutil's broader
  natural-language parser is not compared against ciso8601.
* The Aho text is deliberately hostile to ahocorapy's regex skip optimisation; this measures the
  worst case of the pure search loop, not a mixed real-world corpus.

## 6. Reproduce

```sh
python3 -m venv /tmp/w3d-venv
/tmp/w3d-venv/bin/pip install -r lab/wedge3/wedge3d/requirements.txt
git fetch origin job-obs5-op1109 && git worktree add ../obs5 FETCH_HEAD
ulimit -v 2500000
python3 lab/wedge3/wedge3d/harness.py -o lab/wedge3/wedge3d/results.json
```

`harness.py` records the AIL commit, versions, every median-of-5 time, the byte-identical output
digest, `build.json` residues and the profiled refusal ranking in `results.json`.
