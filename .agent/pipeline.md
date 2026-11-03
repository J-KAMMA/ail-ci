# job job-selfhost1-11040509  started 2026-11-03T20:10:31Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]

## review 0
[model opencode/deepseek-v4.1-flash-free]
# Review: selfhost1 census

The worker-report block is empty, so claims were checked against `DEVLOG.md` and `lab/selfhost/CENSUS.md`.

**What the change really does:** adds a measure-only census tool (`tools/selfhost_census.py`), `census.json`, hot profiling (`lab/selfhost/hot_functions.py`, `hot.json`), `CENSUS.md`, and a DEVLOG entry. No compiler/runtime source is touched (`git diff work..HEAD` is only these six files).

## Verified
- 156 scope files, 3152 top-level functions, 3538 methods: exact AST recount matches.
- `fastwalk.py`, `fecache.py`, `hash_prelude.py`, `prelude_array.py`, `prelude_fraction.py`, `prelude_ailarray.py` reproduce the census verdicts; `ail_cpython_hybrid.build()` returns the same accelerated names.
- `strt.py` chunk matches a whole-file run: 2 accepted (`total`, `bit_len`).
- `hot.json` reproduces exactly from the `/tmp/prof` profiles; 0 of the 30 ranked hot functions are accepted.
- `tools/update_manifest.py --check` passes; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (542 s, 0 failed).
- Counts 940 and 828 for the top two rejection reasons, and the 56% total, are correct.

## Defects
1. **`dtrt.py` is misclassified; the headline numbers are wrong.**
   Probe: the in-scope file `AIL_CURRENT/python/pkg-v12/dtrt.py`, run with
   `(ulimit -v 1500000; python3 tools/selfhost_census.py --one AIL_CURRENT/python/pkg-v12/dtrt.py --timeout 600 --out /tmp/dtrt.json)`.
   Expected (confirmed by `ail_cpython_hybrid.build()`): 5 accepted — `ord_year`, `kind_name`, `ampm`, `pad_space`, `hour12`; 162 rejected.
   Actual census: 0 accepted, 167 rejected, all with the chunk-only reason `AilStrp` is not known.
   Consequence: the real total is **21 accepted (0.67%)**, not 16 (0.51%); accepted functions live in **six** files, not five; `dtrt.py` is **5/167 (3.0%)**, so “every one of the 15 largest files is at 0%” is false. The top-10 rejection table is also wrong: “not emitted” is 497 not 347, the 167 `AilStrp` row disappears, and `re.sub` (21) enters the top 10.
   Root cause: the chunk text is only the preamble before the first `def` plus function bodies, so later classes and module-level assignments (`AilStrp`, `EPOCH_ORD`, …) are dropped. The whole file now finishes in ~150 s under the same limit, so rerunning it whole (or preserving module-level code in chunks) fixes it.

2. **Duplicate top-level `def`s are overcounted (latent; no scope file triggers it).**
   Probe source:
   ```python
   import functools
   @functools.cache
   def f(x: int) -> int:
       return x + 1

   def f(x: int) -> int:
       return x + 2
   ```
   Expected from `ail_cpython_hybrid.build()`: `accelerated == ['f']` (one definition).
   Actual census: both definitions marked `accept`. The tool keys verdicts by name, not by definition line. This does not change the current 21 total because no scope file has an accepted duplicate name.

## False / minor report claims
- “The 16 accepted … live in five prelude/helper files” — false (21 in six files).
- “Every one of the 15 largest files is at 0%” — false (`dtrt.py`, 15th largest, is 5/167).
- “`dtrt.py` … exceeded the 300 s budget whole” — not reproducible; it completes whole in ~150 s here.
- “the rest are front-end predicates in `pyfunc.py`” — false; the top 30 also includes `fastwalk.py`, `bigcap.py`, `boolkind.py`.
- “each takes AST nodes or compiler objects” — false for `_mvk`, which takes a scalar string `kind`; and “narrowed to a scalar/bool ABI” is not possible for `_owned_method_name`/`_is_owned_str_call`, which take `node`/`ctx`.

## Pre-existing
None relevant. No compiler source changed, so no `cmp.sh` behaviour probes apply.

## Unverified
- The 20 CI shards were not run (per reviewer rules).
- `pyfunc.py` was not independently rerun whole; its entry is not chunked and its uniform rejection reason is plausible.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1761235, "input": 71986, "output": 10839, "reasoning": 32202, "cache.write": 0, "cache.read": 1646208}]
    tool time: bash 20.7 min
        545s bash   date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test
        181s bash   date; (ulimit -v 1500000; timeout 560 python3 tools/selfhost_census.py --one AIL_CURRENT/python/pkg-v12/dtrt.p
        180s bash   date; (ulimit -v 1500000; timeout 480 python3 - <<'EOF' import sys,tempfile sys.path.insert(0,'AIL_CURRENT') i
        114s bash   date; (ulimit -v 1500000; timeout 650 python3 tools/selfhost_census.py --one AIL_CURRENT/python/pkg-v12/strt.p
         61s bash   date; timeout 300 python3 tools/selfhost_census.py --one AIL_CURRENT/python/pkg-v12/hash_prelude.py --timeout 
         61s bash   date; timeout 500 python3 - <<'EOF' import sys,tempfile sys.path.insert(0,'AIL_CURRENT') import ail_cpython_hy
         60s bash   date; timeout 500 python3 - <<'EOF' import sys,tempfile,json sys.path.insert(0,'AIL_CURRENT') import ail_cpyth
         14s bash   date; timeout 120 python3 tools/selfhost_census.py --one AIL_CURRENT/python/pkg-v12/prelude_array.py --chunk -

## worker report 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]

## review 1 failed to run: [model commandcode/deepseek-v4.1-flash] 

## review 1
[model commandcode/deepseek-v4.1-flash]

FINAL VERDICT: ERROR  2026-11-03T22:56:24Z
