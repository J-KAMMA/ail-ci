# job job-linecache1-11052048  started 2026-11-05T11:58:14Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**What I built**
- `AIL_CURRENT/stdlib/linecache.py` — CPython 3.12's `linecache` as AIL source: `cache`, `getline`, `getlines`, `clearcache`, `checkcache`, `updatecache`, with CPython's stamping rules (`""` outside `1..len`, `[]` on unreadable, `"\n"` appended to a last line without one). `os.stat` isn't built, so freshness compares content; files open with `encoding="utf-8"` instead of `tokenize.open`; `lazycache`/loader path dropped. Each difference is in the module docstring.
- 10 programs + `data/` + `RESULTS.md` in `lab/stdlib/linecache/`; `AIL_CURRENT/test_ail_std_linecache.py` + `tests.d/test_ail_std_linecache.txt`; manifest pins via `tools/update_manifest.py` (`--check` clean).

**Numbers**
- Before: **0/10** (all `not in the subset: linecache.getline (not yet published in NAMES_library.json)`). After: **10/10 build and match CPython stdout+exit** in the default build and with `AIL_UNIFIED_FORCE=1` (all general path).
- `test_ail_std_linecache`: 2 tests OK (20 builds). `test_ail_files` 18 OK/1 skipped, `test_ail_safetynet` 5 OK, `test_ail_corpus_findings3` 2 OK — all on the final commit.

**Self-check probes** (`~/tools/cmp.sh`, both builds vs `python3`): `p1_paths` (list/dict/attribute filenames, empty+CRLF files, lineno 0/−3/4/2^62) same; `p2_checkcache` (path/None/removed/missing) same; `p3_cache_and_angles` (entry shape, `clearcache`, `<string>`, `<x y>`, `""`, directory) same; `p4_int_limits` (int64 max) same; `p5_int_beyond` loud `OverflowError` in `int()` (documented int64 rule); `p6/p8` invalid UTF-8 gives `[]` both. One real corpus difference: a `latin-1` coding-cookie file decodes in CPython and returns `[]` here — the documented `tokenize.open` difference. Probe `p7` (binary write + linecache) exposed `cache.pop(f, None)` being refused on the general path; replaced with `del cache[f]` and it now builds and matches.

**Note:** per the runner rules I committed but did not push, so no PR/CI run. 3 commits on `job-linecache1-11052048`; `git diff --stat` against the base shows only the 20 allowed files (17 new + 3 manifest shards). Also: `test_ail_safetynet` fails `S4_generators_gc` only under `ulimit -v 1500000`; it passes without the cap and touches nothing I changed.
[commandcode stop=end_turn turns=62 out_tokens=34069]

## review 0
[model commandcode/deepseek-v4.1-flash]
Found the boundary divergences. Writing the review.

## What the change really does

Adds `AIL_CURRENT/stdlib/linecache.py` — a hand-rewritten port of CPython 3.12 `linecache` (`cache`, `getline(s)`, `clearcache`, `checkcache`, `updatecache`); freshness is checked by re-reading the file and comparing the **live cached line list** to the fresh content instead of `st_size`/`st_mtime`; utf-8 instead of `tokenize.open`; `lazycache` dropped. Plus 10 lab programs + `data/` + `RESULTS.md`, `test_ail_std_linecache.py` + `tests.d` entry, 3 manifest pins. No compiler file touched. This matches the report's description.

## Claim check

| claim | result |
|---|---|
| 10/10 build & match CPython stdout+exit, both builds, all general path | **verified** (`test_ail_std_linecache` ok; built `01` and saw the general-path note) |
| 0/10 before, `not yet published in NAMES_library.json` | **verified** on `/tmp/base` |
| `test_ail_std_linecache` 2 tests OK / 20 builds | **verified** (90 s) |
| `test_ail_safetynet` 5 OK | **verified** on HEAD (166 s, no ulimit); the ulimit-`S4_generators_gc` note **unverified** |
| manifest `--check` clean, only allowed files | **verified** (exit 0, 20 files) |
| non-users' C unchanged | **verified**: `program.c` identical HEAD vs `/tmp/base` |
| docstring differences (utf-8/cookie, content-vs-mtime, no `sys.path`, no `lazycache`) | **verified** — but incomplete, see below |

Probes that matched CPython in both builds: empty/blank/CRLF/no-final-newline files, directory and `dir/` path, `<>`/`"<a>b"`, missing/removed/truncated/overwritten file, stale-without-`checkcache`, `None` filename, keyword args, `getline` reached via argument/list item/dict value/attribute, bool/float lineno (same `TypeError`).

## Defects

1. `checkcache` drops an entry for a file that still exists and is unchanged but can no longer be read (`_read_lines` → `None`). CPython's `os.stat` succeeds, so it keeps the entry.
   `/tmp/rprobes/rp7_perm.py`: write `a\nb\n`, `getlines`, `os.chmod(p, 0)`, `checkcache()`, print `len(cache)` and `getline(p,1)`.
   expected (CPython): `1 'a\n'` — actual: `0 ''` (both builds). This also contradicts the module docstring, which says the entry is dropped only when the lines differ "or the file is gone".

2. `checkcache` compares the *cached list object* to the file, so a program that mutates the list returned by `getlines` loses its mutation, where CPython keeps it (it compares stat, not cache contents).
   `/tmp/rprobes/rp1_alias.py`: `getlines`, `lines.append`, `lines[0]="MUT\n"`, `checkcache(p)`, `print(getline(p,1))`.
   expected: `'MUT\n'` — actual: `'a\n'` (both builds).

Both are avoidable inside the permitted content/size comparison (compare against a snapshot recorded at read time, and keep the entry when the path still exists but cannot be read). `rp8_ident.py` (identical rewrite keeps the entry, so `old is new` is `True` vs CPython `False`, and a later mutation stays visible) is the already-documented mtime rule, so I did not count it.

## Unverified / not checked

- CI shards and the PR (worker did not push, per runner rules; no `gh` run).
- `--strict`/typed path for `linecache` (all programs are general path; task did not require it).
- Instruction counts: change adds only a module, no hot-path edit, so I skipped `tools/icount.c`.
- The latin-1 coding-cookie corpus difference was not re-run; it is documented.
- Pre-existing divergences: none found (base has no `linecache`).

VERDICT: FIX
1. `checkcache` drops the entry when the file still exists but is unreadable: `/tmp/rprobes/rp7_perm.py` expected `1 'a\n'`, actual `0 ''`.
2. `checkcache` compares the mutable cached list, discarding caller mutations: `/tmp/rprobes/rp1_alias.py` expected `'MUT\n'`, actual `'a\n'`.
[commandcode stop=end_turn turns=17 out_tokens=27296]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
## Report

Fixed both reviewer defects in `AIL_CURRENT/stdlib/linecache.py`:

1. **`checkcache` keeps entries whose file exists but is unreadable** — if `_read_lines` returns `None`, the entry is now dropped only when `os.path.isfile` is false (path gone / no longer a regular file). A chmod-0 file keeps its entry, matching CPython's successful `os.stat`.
2. **`checkcache` no longer compares the mutable cached list** — a private `_snapshots` dict records a copy of the lines at fill time; freshness compares re-read content against that snapshot, so caller mutations to the list from `getlines` survive `checkcache` as in CPython. `clearcache` and dropping clear both structures.

Docstring and `RESULTS.md` updated. Manifest regenerated; `update_manifest.py --check` exits 0.

**Probes (both default and `AIL_UNIFIED_FORCE=1`, compared to CPython, all same stdout + exit 0):**
- `rp1_alias.py` — mutate `getlines` result, `checkcache` keeps mutation (the reported case)
- `rp7_perm.py` — chmod 0, entry kept, cached line returned (the reported case)
- `rp2_removed.py` — removed file drops the entry
- `rp4_dir.py` — path replaced by a directory drops the entry
- `rp9_mutate_then_change.py` — mutation + real content change drops and re-reads
- `rp10_identity.py` — same list object, clearcache, out-of-range 0/-2/4 all match

**Tests:** `test_ail_std_linecache` 2 tests OK (103 s, 20 builds). `test_ail_files` OK (18, 1 skip). `test_ail_corpus_findings3` OK. `test_ail_safetynet` OK (5 tests, 169 s **without** the memory cap); under `ulimit -v 1500000` it fails only `S4_generators_gc` because the generated program is OOM-killed after its first output line — unrelated to `linecache`, and it passes uncapped.

Committed as `42daf72`; not pushed, per the runner rule. CI shards were therefore not exercised. Untracked `.agent/pipeline.md` left alone.
[commandcode stop=end_turn turns=14 out_tokens=9831]

## review 1
[model commandcode/deepseek-v4.1-flash]
All probes and tests are in. Here is what I found.

**What the diff really does:** adds `AIL_CURRENT/stdlib/linecache.py` (CPython's `getline`/`getlines`/`checkcache`/`updatecache`/`clearcache` over `cache`, with freshness by re-reading the file and comparing it to a private `_snapshots` copy), ten lab programs + `RESULTS.md`, `test_ail_std_linecache` (+ `tests.d` entry) and the three manifest pins. No compiler or runtime file is touched; `program.c` for a program that does not import `linecache` is byte-identical to `/tmp/base` (verified on `pG_plain.py`).

**Defects (all caused by this change; `/tmp/base` simply refuses these programs, and commit `4af33bd` shows the first one was correct before the fix commit):**

1. `checkcache` keeps a stale entry when the file exists but can no longer be **decoded**. This is a regression introduced by `42daf72`: probe `pC_badutf8.py` matches CPython on `4af33bd`, diverges on HEAD. `_read_lines` returns `None` for a `UnicodeDecodeError` and the new code only drops when `os.path.isfile` is false.
   ```
   import linecache
   open("c.txt","w").write("one\ntwo\n")
   print(repr(linecache.getline("c.txt",1)))
   f=open("c.txt","wb"); f.write(b"\xff\xfe bad bytes here\n"); f.close()
   linecache.checkcache()
   print("kept", "c.txt" in linecache.cache)
   print(repr(linecache.getline("c.txt",1)))
   ```
   expected (`python3`): `'one\n'` / `kept False` / `''` · actual (both builds): `'one\n'` / `kept True` / `'one\n'`. It also contradicts the module docstring's own "a decode error gives the empty result".

2. Entries installed in the public `linecache.cache` dict with `mtime is None` are dropped. CPython's `checkcache` does `if mtime is None: continue` (the real "cache seeded by a loader" idiom); here a missing `_snapshots` key means "drop".
   ```
   open("d.txt","w").write("one\ntwo\n")
   linecache.cache["d.txt"] = (8, None, ["seed\n"], "d.txt")
   print(repr(linecache.getline("d.txt",1)))
   linecache.checkcache()
   print("kept", "d.txt" in linecache.cache); print(repr(linecache.getline("d.txt",1)))
   ```
   expected: `'seed\n'` / `kept True` / `'seed\n'` · actual: `'seed\n'` / `kept False` / `'one\n'`. Fixable with `if mtime is None: continue`. The docstring's claim "`None` inside a tuple is not built" is **false** (`pI_none.py` prints `None True`).

3. An entry *replaced* in `cache` after being filled is kept with its synthetic lines, because the snapshot is keyed by name only and still matches the file. `pE_seed_int.py`: expected `kept False` / `'one\n'`, actual `kept True` / `'synth\n'`. Same root cause as (2).

4. Minor/doc: `cache[fn][0]` is described as "the number of characters read", but it counts the `"\n"` appended to a file without a final newline: `pF_bounds.py` prints `4 6 0` where CPython prints `4 5 <st_mtime>`. (`mtime` differing is documented; the `size` wording is not accurate.)

**Report claims:** fix 1 (unreadable file keeps its entry) — **verified** (`pB_perm.py`, chmod 0, both builds: `kept True`, cached line returned). Fix 2 (caller mutation survives `checkcache`) — **verified** for the mutation path (`pA_mutate.py`: mutation + append, same list, entry length 4; `pJ_mutate_change.py`: mutation + real content change drops and re-reads; `pH_truncate.py`: truncate then `checkcache` drops). "Manifest regenerated, `--check` exits 0" — **verified**. "`test_ail_std_linecache` 2 tests OK" — **verified** (`par_check.py -j 2`: 103.6 s, ok). "`test_ail_safetynet` OK" — **verified** (185.9 s, ok). "`test_ail_files` / `test_ail_corpus_findings3` OK", the six named probe files, and the CI shards — **unverified** (not re-run / not present; report itself says shards were never exercised).

**Speed:** no compiler/runtime change and `program.c` is byte-identical for non-users; 0 of 510 `~/corpus/gdev` programs mention `linecache`, so instruction counts are unchanged by construction (no `icount` run).

**Pre-existing:** `/tmp/base` has no `linecache` module at all, so those programs are refused there; nothing pre-existing blocks.

VERDICT: FIX
1. `checkcache` keeps a stale entry after the cached file is rewritten to non-UTF-8 bytes: `pC_badutf8.py` expected `kept False` / `''`, actual `kept True` / `'one\n'` (regression vs `4af33bd`; contradicts the docstring).
2. `checkcache` drops entries seeded in `linecache.cache` with `mtime is None`: `pD_seed_none.py` expected `kept True` / `'seed\n'`, actual `kept False` / `'one\n'`; add `if mtime is None: continue`, and fix the false "None inside a tuple is not built" docstring claim (`pI_none.py` prints `None True`).
3. An entry replaced in `cache` after being filled keeps its synthetic lines: `pE_seed_int.py` expected `kept False` / `'one\n'`, actual `kept True` / `'synth\n'`.
4. Minor: `cache[fn][0]` counts the appended newline (`pF_bounds.py`: `4 6 0` vs CPython `4 5 <mtime>`), and the docstring calls it "characters read".
[commandcode stop=end_turn turns=23 out_tokens=24751]

FINAL VERDICT: FIX  2026-11-05T13:00:35Z
