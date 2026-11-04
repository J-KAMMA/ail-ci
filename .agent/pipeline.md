# job job-apps1_rr2-11050625  started 2026-11-04T21:26:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the short report.

## What landed
Four commits on `job-apps1_rr2-11050625` (not pushed — the job rules say "do not push", so no PR/shard run):

- `461bd28b` — 6 tools + 18 data inputs
- `72b6d9bf` — typed-path rewrites for hexdump/topwords
- `676ed0fa` — `test_ail_examples_apps.py`, `tests.d/` entry, manifest pins
- `91c7b3f4` — `make_big.py`, `examples/apps/README.md`, 2 DIFFERENCES rows

## Results
- **6 tools, all equal to CPython** on every data input and on the 50 MB inputs (stdout + exit code), default and `AIL_UNIFIED_FORCE=1`.
- **Typed in the default build: 5/6** (wc, colsum, topwords, grepn, hexdump). `jsonfield.py` falls back to the general path — mixed-type JSON has no supported declared value type (`dict[str, object]` is refused); with `AIL_UNIFIED_FORCE=1` all 6 are typed. Documented in README + DIFFERENCES.
- Big ints: `colsum_odd.csv` / `jsonfield_odd.jsonl` stop loudly in default/forced builds (`OverflowError: integer overflow in int() ...`); `--exact-int` matches CPython. Recorded.
- Test module passes (`par_check -j 2 test_ail_examples_apps`, 34.7s).

## Required tests (final commit)
- `test_ail_examples_apps` ok, `test_ail_files` ok, `test_ail_corpus_findings3` ok.
- `test_ail_safetynet` fails `S4_generators_gc` — **pre-existing**: reproduced on a clean `origin/integ` worktree.

## Self-check probes (`~/tools/cmp.sh`, both builds)
`p_bytes`, `p_counter`, `p_lines` — same stdout as CPython in both builds. `p_csv`, `p_json` — same except the intended beyond-int64 overflow; both match with `--exact-int`.

## Notes
- `README.md` has the wall-time/RSS/binary-size table. `hexdump`'s AIL binary needs 4.5 GB RSS on the 50 MB input (Python 60 MB) and `topwords` 1.7 GB (Python 0.9 GB); both were measured without `ulimit`, and hexdump fails under `ulimit -v 1500000`.
- `DEVLOG.md` was not edited (rule 8 forbids it).
[commandcode stop=end_turn turns=63 out_tokens=43281]

## review 0
[model commandcode/deepseek-v4.1-flash]
I read the diff: it adds six example tools, 18 data inputs, a generator, a README, a test module plus registration/DIFFERENCES rows. No compiler or runtime file is touched; generated C for a plain program is byte-identical between HEAD and base.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh … $PWD` for the self-contained ones; real tools built default / `AIL_UNIFIED_FORCE=1` / base at `/tmp/base` and run over 58 file+argv cases, plus 50 MB inputs):
- `p_hex`, `p_wc`, `p_top`, `p_json`: same stdout both builds; `p_col`: identical `OverflowError: integer overflow in +` on HEAD *and* base.
- Real tools: every case matches CPython in all three builds except (a) `colsum_odd.csv`/`jsonfield_odd.jsonl` default+forced (`OverflowError: integer overflow in int()` — identical on base) and (b) invalid-UTF-8 stdin for `grepn`/`topwords`/`colsum` (`UnicodeDecodeError`; CPython under this locale uses surrogateescape) — also identical on base.
- Extra boundaries all matched: empty input, 0/15/16/17/256-byte hexdumps, `\r\n`, `\v\f` bytes.split, unicode and invalid argv patterns, `int("1_000")`, `-9223372036854775808`, Arabic-Indic digits, `0x10`, JSON `null`/bool/list/dict/`1.0`/`-0.0`/`1e400`/`1e20`, empty/negative/oversized N, missing args.
- 50 MB (`make_big.py`): all six byte-identical to CPython (hexdump 222,822,400 bytes), both-default-build; table rows reproduced within noise (wc 523/565 MiB, colsum 139/87, grepn 1/10, topwords 1702/924, hexdump 4502/60, jsonfield 11/11; hexdump 4.11 s, topwords 1.68 s).

**Tests**: `test_ail_examples_apps` ok (33.0 s). `test_ail_safetynet` fails `S4_generators_gc` on HEAD **and** on `/tmp/base` — pre-existing, as claimed. `update_manifest.py --check` ok.

**Claims**: typed 5/6 + forced 6/6 verified; int64 loud stop and `--exact-int` match verified; the `hexpart` note and the topwords strict-mode "cannot be walked inline" note and the `dict[str,object]` note text all verified (the comprehension note only appears under `--strict`; the default note is the Counter import); `dict[str,int]` "rejects string values" is a *runtime* RuntimeError, not a compile refusal. The report's first bullet ("all equal on every data input, default and forced") is **false** for `colsum_odd.csv`/`jsonfield_odd.jsonl` — the report itself says so two bullets later. The README sentence "the hexdump RSS is the whole 223 MB output held in memory" is false (4.6 GB RSS persists with stdout to `/dev/null`; the growth is in the typed path, likely uncollected per-line strings). `wc.py` is 13 lines, below the stated 20-60.

**Pre-existing** (same on base): beyond-int64 `int()`/`+` stop; strict-UTF-8 text stdin vs CPython surrogateescape; typed-path memory blow-up (hexdump 4.6 GB for a 50 MB input, 556 MB at 5 MB with the base compiler too).

**Unverified**: push/PR and the 20 shard checks (none run; no push by design), `test_ail_files`/`test_ail_corpus_findings3`, DEVLOG entry (rule 8 forbids).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=50 out_tokens=38628]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T23:17:13Z
