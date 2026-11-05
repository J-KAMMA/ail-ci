# job job-chunk1-11060507  started 2026-11-05T20:11:09Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final state:

**Result:** 9/10 chunk programs build and match CPython 3.12 (stdout + exit) in both the default build and `AIL_UNIFIED_FORCE=1`. `08_errors.py` is refused by the compiler's nested-function-as-value rule (exact text recorded in `RESULTS.md`); the same chunk calls inline build and match.

**Commits on `job-chunk1-11060507`:**
- `ae9911b` 10 lab programs + Before baseline
- `ae3f05f` bundled `AIL_CURRENT/stdlib/chunk.py` (CPython 3.12 source; `int.from_bytes` for sizes, `hasattr(file,"tell")` for seekability)
- `35a49d5` `test_ail_std_chunk.py`, `tests.d` registration, manifest update (`--check` passes)
- `cd210e0` results update

**Tests/probes:**
- `test_ail_std_chunk.py`: 2 tests OK (18 builds compared).
- Probes in `/tmp/probes`, all "same stdout" in both builds: `chunk_empty` (size 0), `chunk_widths` (0xFFFFFFFF, 0x80000000, 0x7FFFFFFF, inclheader sizes 0/3/4/8 incl. negative chunksize), `chunk_align` (odd 1/2/3/5, align both), `chunk_seek` (whence 0/1/2, out-of-range/negative RuntimeError, after close), `chunk_indirect` (sizes from list/dict/attribute, endian from attribute, align from argument), `chunk_eof` (0/3/4/6/8-byte headers).
- Required: `test_ail_files` OK, `test_ail_corpus_findings3` OK, `test_ail_safetynet` OK (the first run under `ulimit -v 1500000` failed `S4_generators_gc` with truncated output; it passes uncapped, so that was the memory cap, not this change).

**Not done:** I did not push or open the PR, per the runner instruction "Commit your work on the current branch; do not push", so the 20 shard checks were not run. `.agent/pipeline.md` remains untracked (pre-existing). `git diff --stat de5f03f` shows only the 17 permitted files.
[commandcode stop=end_turn turns=42 out_tokens=34646]

## review 0
[model commandcode/deepseek-v4.1-flash]
Time used: ~18 min. Everything I could probe matches.

## What the change does

Adds a bundled stdlib `AIL_CURRENT/stdlib/chunk.py` that is CPython 3.12's `Lib/chunk.py` with two rewrites: the size field decoded via `int.from_bytes` instead of `struct.unpack_from` (big/little), and seekability decided by `hasattr(file, "tell")` instead of `try/except (AttributeError, OSError)`. Plus 10 lab programs, a test module + `tests.d` entry, manifest entries and `RESULTS.md`. This matches the report's description.

The module only ever lands on the general path (`note: ... chunk.Chunk.__init__ must take plain positional arguments ... built on the general path`); the report says this.

## Probes (`/tmp/rprobes`, both builds vs `python3`) — all "same stdout", same exit

- `p_read_boundaries.py` — `read(0)`, partial, oversize, `read()`, `tell` after each, odd-size alignment dummy, `skip`, `close` twice, `seek(0)`.
- `p_nonseekable.py` — `Chunk` over a custom read-only object (`seekable False`), `seek` → `OSError 'cannot seek'`, `close`, after-close `tell`/`isatty` `ValueError`, short body → `close` raises `EOFError` with `closed True`.
- `p_huge_sizes.py` — 0xFFFFFFFF / 0x80000000 / 0x7FFFFFFF, read/skip/close, `seek(0,2)`, `inclheader` sizes 0/4/0xFFFFFFFF (negative chunksize).
- `p_indirect_values.py` — sizes from a list item, dict value, attribute, passed endian/align; mutate the list/dict after reading; overwrite the file after reading; held bytes unchanged.
- `p_eof_short.py` — 0/1/3/4/5/6/7/8-byte headers, little-endian, `inclheader`, binary chunk names/body (`\x00\xff...` repr), `from chunk import Chunk`, `Chunk` over `Chunk` at EOF. (Ends with a `FileNotFoundError` from my own probe bug — identical in CPython and both builds.)

Re-ran the worker's `/tmp/probes/chunk_{widths,seek,indirect,align,empty}.py`: all "same stdout" in both builds.

Non-feature check: a getopt-based program with `--debug-dir` produces **byte-identical `program.c`** on HEAD vs `/tmp/base`.

## Tests on HEAD

`par_check.py -j 2 test_ail_std_chunk test_ail_safetynet` → both ok (264 s, 0 failed). Manifest `--check` rc 0; `git diff --name-only work..HEAD` is the 17 permitted files. Re-ran all 10 lab programs through `cmp.sh`: 01–07, 09, 10 match in both builds; 08 refused with exactly the recorded nested-function text (rc 3). Before-baseline on `/tmp/base` reproduces the recorded import refusal.

## Report claims

Verified: 9/10 match in both builds; 08 refusal text (exact); 2 tests / 18 builds; probes all match; safetynet passes; manifest check and file list; nothing pushed (local commits only). Unverified: "same calls inlined build and match" for 08; `test_ail_files` / `test_ail_corpus_findings3` (out of scope); the claim that the safetynet failure seen under `ulimit -v` was solely the cap; the 20 shards (worker did not run them).

## Pre-existing (not blocking)

- Taking a bound method as a value (`m = c.f`, `c.f.__self__`) fails on **any** compiled class with `AttributeError: 'C' object has no attribute 'f'` — reproduced without `chunk` (`p_boundmethod.py`), and non-chunk C is unchanged. My first nonseekable probe hit this, not a chunk bug.
- A file-like object whose `tell` exists but raises `OSError` now raises from `Chunk.__init__` instead of setting `seekable = False`. This is exactly the deviation the task authorized (`hasattr`), so not a defect.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=24 out_tokens=27763]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T22:09:23Z
