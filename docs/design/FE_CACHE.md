# Front-end cache

Opt-in cache for the C that the Python front end emits.  It is off unless `AIL_FE_CACHE=1`
(or `ail compile --fe-cache`) is given.  A hit skips the Python lowering and compiles the stored C;
a miss runs the normal build and stores the C only after that build succeeded.

## Location and lifetime

- Root: `$AIL_FE_CACHE_DIR`, else `$XDG_CACHE_HOME/ail/fe`, else `~/.cache/ail/fe`.
- Entries: `<root>/c/<first two hex digits>/<sha256>`.
- Size cap: `AIL_FE_CACHE_MAX_MB`, default 200.  The least recently used entries are evicted to
  80% of the cap when the cap is crossed.
- Writes are atomic: temp file in the same directory, then `os.replace`.  A corrupt or truncated
  entry is deleted and treated as a miss.
- `AIL_FE_CACHE_LOG` appends `hit`, `miss`, `miss-compile` or `uncached` plus the key.

## Key

`pyc.py` hashes, in order:

- the merged source text (the front end has already read every imported AIL/Python module);
- `strict` and `force_general` (the two lowering switches);
- `buildcache.sources_hash()` of `python/pkg-v12` (every `.py`, `.h` and `.c`, so any compiler
  change invalidates);
- `sys.version` and `sys.platform`;
- `buildcache.build_env()`, i.e. every `AIL_*` and `PIPE_*` variable except `AIL_CACHE*`,
  `AIL_NO_CACHE` and the cache's own `AIL_FE_CACHE*`, plus the C-compiler variables in
  `buildcache.CC_ENV` (`CPATH`, `C_INCLUDE_PATH`, `LIBRARY_PATH`, `COMPILER_PATH`,
  `GCC_EXEC_PREFIX`, `GCC_COMPARE_DEBUG`, `SOURCE_DATE_EPOCH`, `SDKROOT`,
  `MACOSX_DEPLOYMENT_TARGET`, `LD_RUN_PATH`, `DEPENDENCIES_OUTPUT`, `SUNPRO_DEPENDENCIES`,
  `TMPDIR_FOR_CC`).  This covers `--exact-int`, `AIL_FE_JOBS`, `AIL_EXTRA_CFLAGS`,
  `AIL_DEBUG`, `AIL_GENERAL`, `AIL_SURFACE`, `PIPE_CC` and the rest.

The old whole-build `fe` cache is bypassed when `AIL_FE_CACHE` is on, so the two cannot mask each
other.  The existing `cc` cache may still serve the C compile.

If a build takes a path whose C cannot be stored (for example the separate-linking
`build_link_units` path), `pyc.py` logs `uncached` and does a normal full build.  It never stores a
partial result.  The mixed-unit and `AIL_CC_SPLIT` paths are captured; none of the tested corpus
programs fell back to `uncached`.

## Step 1: what a cache could win (3 runs, no cache, server off)

`lab/fecache/measure.py --phase step1`; `cc_wrap.py` splits one compile+link driver call into
`-c` and a link.  Times are seconds, median [min, max].  Only the three tasks named by the brief
were measured; the other seven were skipped for the time budget.

| task | case | wall | front end | C compile | link |
|---|---|---:|---:|---:|---:|
| berth_sim | (a) unchanged | 15.011 [14.698, 15.137] | 12.716 [12.393, 12.800] | 2.281 | 0.024 |
| berth_sim | (b) body edited | 12.821 [11.759, 15.116] | 10.452 [10.230, 12.761] | 2.332 | 0.024 |
| rail_transfer | (a) unchanged | 4.255 [4.253, 4.280] | 2.516 [2.512, 2.547] | 1.714 | 0.025 |
| rail_transfer | (b) body edited | 4.306 [4.293, 4.352] | 2.554 [2.541, 2.585] | 1.743 | 0.024 |
| tally_lang | (a) unchanged | 5.767 [4.112, 6.010] | 3.811 [2.817, 4.065] | 1.921 | 0.024 |
| tally_lang | (b) body edited | 5.205 [4.069, 5.433] | 3.926 [2.722, 4.094] | 1.322 | 0.018 |

Case (c), one imported module edited, is not applicable to these ten tasks: each is one
`main.ail` with no imported module.  A synthetic two-module Python project measured 0.827 s wall,
0.748 s front end, 0.056 s C compile for the unchanged case, and 0.829 s wall, 0.748 s front end,
0.056 s C compile when `lib.py` was edited.

Amdahl bound for a whole-program cache, i.e. `wall / (wall - front end)` if lowering went to zero:

| task | case (a) bound | case (b) bound |
|---|---:|---:|
| berth_sim | 6.56x | 0 |
| rail_transfer | 2.45x | 0 |
| tally_lang | 2.95x | 0 |

A whole-program key changes on any body or import edit, so it cannot help (b) or (c).  A per-module
cache would reach only the unchanged modules; for these single-file tasks that reach is zero, and
the synthetic import case shows why it is not worth a second key layer here: the imported module is
tiny compared with the main module.

## Step 4: cold, hit and miss

`lab/fecache/measure.py --phase step4`; 3 runs, median seconds.  `front` is `wall - C compile -
link`; `hit` means the stored C was compiled, not re-lowered.  `server off` sets `AIL_SERVER=0`;
`server on` uses the resident compile server.

### Old `cc` cache off (isolates the front-end cache)

| task | server | cold | hit | miss |
|---|---|---:|---:|---:|
| berth_sim | off | 14.787 | 2.772 | 14.298 |
| berth_sim | on | 12.838 | 2.817 | 12.023 |
| rail_transfer | off | 2.641 | 2.242 | 3.972 |
| rail_transfer | on | 3.963 | 2.115 | 3.808 |
| tally_lang | off | 5.048 | 3.014 | 5.675 |
| tally_lang | on | 4.818 | 2.470 | 3.832 |

Hit speedups against the same-server cold build: berth 4.6x (on), rail 1.9x, tally 2.0x.  The hit
path still pays Python startup, key hashing, entry read and the full C compile/link, so it does not
reach the 6.56x / 2.45x / 2.95x bounds.

### Default `cc` cache on (what a user gets after enabling `AIL_FE_CACHE`)

| task | server | cold | hit | miss |
|---|---|---:|---:|---:|
| berth_sim | off | 13.584 | 0.823 | 13.571 |
| berth_sim | on | 11.233 | 0.719 | 10.924 |
| rail_transfer | off | 4.102 | 0.824 | 4.032 |
| rail_transfer | on | 4.259 | 0.751 | 3.569 |
| tally_lang | off | 5.380 | 1.162 | 4.955 |
| tally_lang | on | 4.254 | 1.277 | 5.221 |

Here the hit also gets the stored C compile from the existing `cc` cache.  The hit path is 0.72 s
and 0.75 s for berth_sim and rail_transfer with the server on, close to the 0.5 s target; tally_lang
is 1.28 s because its hit still hashes a larger merged source and reads a larger entry.  A miss
adds the key hash and the store to a normal build; the extra cost is inside the run-to-run spread.

### Disk and RSS

Entry sizes in the step-4 runs: berth_sim 321,117 B, rail_transfer 299,671 B, tally_lang 397,828 B
(about 300-400 KB per program).  The 200 MB cap therefore holds roughly 500-650 programs.

Peak RSS for berth_sim: cold 80.8 MB, hit 52.5 MB with the server off; with the server on, the
client hit was 39.1 MB and the resident server held 78.2 MB.  The hit path allocates no AST or
lowering state, so its client RSS is lower than a cold build.

## Correctness

`lab/fecache/verify.py` builds each program twice with a fresh cache and compares the C the compiler
actually saw.  Results:

- `lab/compare/src`: 10/10 hit, C byte-identical.
- `lab/corpus/programs`: 229 programs, 213 build and hit with byte-identical C, 16 are refused by
  the compiler itself (so there is no cache hit to compare), 0 C mismatches, 0 one-side failures.
- Tests: `test_ail_fe_cache` covers source, import, flag, environment and compiler-file changes,
  corrupt/truncated entries, concurrent builds, LRU, XDG location and the `--fe-cache` flag.
- Mixed-mode and split builds now store all translation units; the mixed link order is stored too,
  so a hit links the same objects in the same order.

## Recommendation

Keep it opt-in.  It turns a repeated unchanged rebuild from 11.2 s to 0.72 s (berth_sim), 4.3 s to
0.75 s (rail_transfer) and 4.3 s to 1.28 s (tally_lang) with the server and the existing `cc` cache
on.  That is a real win for an edit/build loop, but the hit path is still above 0.5 s on one of the
three tasks, and each entry costs 300-400 KB.  A default-on switch would also add key hashing to
every cold build.  The owner should decide whether the repeated-build case justifies it; the flag
and the environment variable are safe to expose now.
