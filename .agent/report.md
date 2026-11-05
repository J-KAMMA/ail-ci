# job job-advparse1-11060322  started 2026-11-05T18:23:05Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

**Implemented**
- `examples/advparse/advparse.py` — 302-line stdlib-only app: 6 rooms, 8 items, 2 containers, classes `Room`/`Item`/`Player`, 8 stdin scripts, locked door exits 3.
- `examples/advparse/README.md`, `RESULTS.md`, `scripts/*.txt` (8 scripts, 15-26 lines each).
- `AIL_CURRENT/test_ail_examples_advparse.py` + `tests.d/test_ail_examples_advparse.txt`; manifest refreshed and `--check` clean.

**Results**
- 8 of 8 scripts match CPython 3.12 byte-for-byte with the same exit status in the default build and with `AIL_UNIFIED_FORCE=1` (both builds land on the general path; first note line recorded in RESULTS.md). `win.txt` ends `score 50 of 50 in 21 moves`; `locked.txt` ends `the door will not move.`, exit 3.
- Probes: 6 extra stdin boundary cases (empty, blank-only, articles-only, no trailing newline, upper case, duplicate take) matched both builds; `probe_objects.py` and `probe_parser.py` matched under `cmp.sh` in both modes.
- Tests on final commit: `test_ail_examples_advparse` OK, `test_ail_files` OK, `test_ail_corpus_findings3` OK. `test_ail_safetynet` fails only `S4_generators_gc` (generators/GC; unrelated to these files, reproducible on the unmodified compiler path).
- `git diff --stat d6f361f`: 15 files, only the allowed example/test files plus the two `manifest.d` shards. Committed on `job-advparse1-11060322`; not pushed per the runner instruction.
[commandcode stop=end_turn turns=63 out_tokens=58161]

## review 0
[model commandcode/deepseek-v4.1-flash]
The change really adds a new example app plus its test; no compiler, runtime, I/O or hot-code file is touched.

**What it does.** 302-line `examples/advparse/advparse.py` (6 rooms, 8 items, 2 containers), 8 stdin scripts, README/RESULTS, one registered unittest module and its two manifest shards. Exactly the 15 allowed files.

**Verification (HEAD 5be9e95, worktree base d6f361f)**
- Built both modes: default and `AIL_UNIFIED_FORCE=1` produce the identical 322,280-byte binary, sha256 `1044d777…4abc4`, matching RESULTS.
- All 8 scripts: stdout byte-identical to `python3` 3.12.3 in both builds; exits 0/0/0/3 as reported (locked.txt = 3). Byte counts in the RESULTS table match exactly.
- Probes in `/tmp/rprobes/` (each the app with input supplied inline, run through `~/tools/cmp.sh`, general + default build):
  - `probe_crlf.py` (`\r\n`), `probe_tabs.py` (tab/space splitting), `probe_uni.py` (`é`, `Ä`), `probe_vtab.py` (`\x0b`, `\x0c` splitlines), `probe_nul.py` (`\x00`), `probe_empty.py`, `probe_quitfirst.py`, `probe_artonly.py` (articles/blank only) — **all same stdout, same exit 0 in both builds**.
- `par_check.py -j 2 test_ail_examples_advparse test_ail_safetynet` → both `ok` (0 failed). `tools/update_manifest.py --check` clean.
- Nothing else changed, so programs not using the feature are trivially unaffected; diff contains no compiler/runtime files.

**Report claims**
- 302 lines, both builds general path, note line and sha in RESULTS — verified.
- 8/8 scripts matching in both builds with exits — verified.
- 6 probe cases matched — unverified (their probes are not in the repo); my 8 independent probes matched.
- `test_ail_examples_advparse` OK — verified.
- `test_ail_files` / `test_ail_corpus_findings3` OK — unverified (not run per instructions).
- "test_ail_safetynet fails only `S4_generators_gc`" — **false on this run**: the whole module passed. Environment flake at worst; does not block.
- "15 files, only allowed ones, not pushed" — verified.

Nit, not a defect: README says a command after `quit` is "never read"; `sys.stdin.read()` reads it, it is just not processed.

**Pre-existing:** none observed.

**Unverified:** worker's own probes; test_ail_files/test_ail_corpus_findings3; behaviour on invalid UTF-8 stdin; speed (change adds no compiled hot code, so N/A).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=17 out_tokens=9906]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T20:11:58Z
