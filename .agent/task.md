**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review report — job ffpkg1

**What the diff really does.** Commit `8e5ebff` adds a standalone `AIL_CURRENT/ail_pkg.py` (`add/remove/sync/list`) and a local-index test; `4c3af3b` fixes the five earlier review findings (sync refetch, prerelease filter, wheel tags, dependency pins, missing-tree refusal). It touches no compiler/runtime file, so generated C is trivially unchanged (`git diff work..HEAD -- AIL_CURRENT/ail_chatgpt.py` is empty). `cli.py` left untouched as the design permits.

**Probes.** `ail_pkg` is not an AIL program, so I exercised it directly with a `file://` fake index (`/tmp/rprobes/harness.py`, `probe_a.py`, `probe_b.py`, `probe_c.py`, `probe_d.py`, `probe_e.py`). Verified good: real PyPI `tabulate 0.9.0` hash `024ca478…`, `click`, `six`, `python-dateutil`; sync refetch restores trees, creates `.ail-wheels/`, leaves no temp dirs; sync leaves the tree intact on a tampered wheel; missing locked tree is refused by name. A differential matrix of `_accepts_python` vs `packaging.SpecifierSet` gives **23/99 mismatches**.

### Defects

1. **The new dependency-specifier matcher is not PEP 440; it silently accepts unsatisfied requirements (and `sync` reproduces them).**
   `/tmp/rprobes/probe_e.py`: index has `alpha 1.0.0`; `beta` has `Requires-Dist: alpha>1.0`.
   ```
   add alpha==1.0.0 ; add beta==1.0.0 ; sync
   expected: refusal (1.0.0 is not > 1.0 per PEP 440)   actual: "added beta 1.0.0", "synced 2 packages" (rc 0)
   ```
   `/tmp/rprobes/probe_d.py`: locked `alpha 2.0.0rc1`, `beta` requires `alpha>=2.0` → accepted by `add` and `sync`, but `SpecifierSet(">=2.0").contains("2.0.0rc1")` is `False`.
   Cause: `_version_key`/`_compare` compare tuples lexicographically (`1.0 < 1.0.0`, prerelease sorts above the final release), and `_accepts_python` is used by `_requirements`, `_check_reverse_requirements` and `sync`.

2. **The same matcher wrongly refuses valid requirements (loud false negatives).**
   `/tmp/rprobes/probe_a.py`: `alpha` locked `1.0.0`, `gamma` requires `alpha==1.0` → expected success (PEP 440 zero-padding), actual `ail_pkg: gamma requires alpha==1.0, but alpha is locked at 1.0.0`. Likewise `==1.0.*` is refused, and a parenthesised specifier `alpha (>=1.0)` fails with `unknown Requires-Python clause '(>=1.0)'`.

3. **`_is_stable` falsely classifies a stable local version as a prerelease.**
   `/tmp/rprobes/probe_b.py`: index has only `loc 1.0.0+1abc`; `add loc` → expected `added loc 1.0.0+1abc`, actual `loc: no non-yanked stable version with a pure-Python wheel`. The regex `(?:^|[._-]|\d)(?:…|a|b|c|…)` matches the `1a` inside a local segment.

### Claims
- sync refetch / `.ail-wheels/` / download kept until extraction — **verified**.
- bare name rejects `1.0.0rc1`, `a1`, `b1`, `dev1` — **verified** for those forms; **false** as a general PEP 440 claim (defect 3).
- py2-only wheels refused, py3 preferred — **verified** (`py2.py3` also accepted correctly).
- dependency specs stored and enforced by `add` and `sync` — **stored: verified; enforced correctly: false** (defects 1–2).
- missing locked vendor tree refused with “run `ail sync` first” — **verified**.
- `test_ail_pkg` passes — **verified** (module ok). Required modules `test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` with `-j 2`: **4/4 ok**. `update_manifest.py --check` rc=0; changed files are only the allowed ones + `manifest.d/0d.txt`, `21.txt` — **verified**.
- census 30/30 with matching hashes — **partially verified** (4 packages spot-checked against PyPI, all hashes match); `test_ail_packaging` — **unverified**.

**Pre-existing:** none identified. **Unverified:** full 30-package PyPI census; `test_ail_packaging`.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1156762, "input": 86388, "output": 7151, "reasoning": 33847, "cache.write": 0, "cache.read": 1029376}]
    tool time: bash 6.5 min
        250s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 900 python3 tools/par_check.py -j 2 test_ail_
        136s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 600 python3 tools/par_check.py -j 2 test_ail_
          1s bash   cd /tmp/rprobes && rm -rf real2 real3 && mkdir real2 real3 ulimit -v 1500000 cd /tmp/rprobes/real2 && timeout 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; git dif
          0s bash   mkdir -p /tmp/rprobes/realpkg && cd /tmp/rprobes/realpkg && rm -rf * .??* 2>/dev/null; ulimit -v 1500000; time
          0s bash   cat > /tmp/rprobes/probe_a.py <<'PY' from harness import * base=tempfile.mkdtemp(prefix="idx-"); ix=Index(base
          0s bash   cat > /tmp/rprobes/probe_b.py <<'PY' from harness import * # local-only stable version and wildcard/paren spec
          0s bash   cat > /tmp/rprobes/probe_c.py <<'PY' from harness import * base=tempfile.mkdtemp(prefix="idx3-"); ix=Index(bas


--- ORIGINAL TASK ---
Lane: ff-pkg
Needs: ffpkg0

# ffpkg1: `ail_pkg.py add NAME==VER`: fetch a pure-Python wheel, check its hash, vendor it, write `ail.lock`

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** census packages from `lab/pkg/RESULTS.md` that `ail_pkg.py add` installs into a fresh project
and whose 10-line program then builds and matches CPython. Target: every package the census marked as building
(and 0 that build without a lock entry or with a wrong hash).

Base: `origin/integ` with ffpkg0 merged. Read `docs/design/PACKAGES.md` first and follow it. Files you may create or
edit, and no others:
- `AIL_CURRENT/ail_pkg.py` (new): `add`, `remove`, `sync` (install exactly what `ail.lock` says), `list`; standard
  library only; refuses sdists, C-extension wheels and any hash mismatch by name
- `packaging/ail_lang/cli.py`: one dispatch line for `ail add|remove|sync` to `ail_pkg.py`, only if no other running
  job edits `cli.py` (owner decision 3); otherwise leave it and document `python3 -m ail_pkg`
- `AIL_CURRENT/test_ail_pkg.py` (new) and `tests.d` entry: the test serves a local index from a temp directory
  (`file://` or `http.server` on 127.0.0.1) with 3 tiny wheels it builds itself; it never touches the network
- `lab/pkg/RESULTS.md`, `docs/PACKAGES.md` (new user page, short)

## Sub-steps

1. **Offline core (25 min).** `add` against the local index in the test: download into a new empty directory, check
   sha256, unpack only `*.py` and metadata (refuse paths with `..` or absolute paths), write `ail.lock`, build. Commit,
   push, open the PR.
2. **Lock and sync (15 min).** `sync` reproduces `ail_packages/` byte for byte from `ail.lock`; a tampered wheel fails
   loudly.
3. **Real index (20 min).** Only if the owner allowed network use in `PACKAGES.md`: run `add` against PyPI for the
   census packages. Otherwise skip and say so.

## Done-check

- The test passes (local index); tamper and path-escape cases refused; the census packages counted in `RESULTS.md`.
- The 20 shards pass; only the files above changed.

## Stop rule

Stop on any package that builds and prints output different from CPython. Stop if the design's network decision is
missing. Stop when 60 minutes pass. Push first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed. Never silent wrong output: stop and report the moment
   any program prints something CPython does not.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`, unless this task names the file and
   the one minimal hook it may add there (owner decision 3 of 2026-11-06: only when no other running job edits that
   file). Do not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task
   names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. Release builds use
  gcc -O2.
- Library policy: a small spec library is written in AIL (`AIL_CURRENT/stdlib/*.py`, found by `ail_modules.py`
  `BUNDLED_DIR`); TLS, signatures and SQLite go through proven native libraries.
- Runtime-backed modules follow `AIL_CURRENT/python/pkg-v12/proclib.py` (stage G8, subprocess): a tree-to-tree pass
  plus a C core header (`ailproc_core.h`), wired by two lines in `filelib.py` (`PRIMS.update(...)` near line 66 and
  `rewrite_tree(...)` near line 152). A program that does not import the module must produce byte-identical C.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- Speed claims: instruction counts with `tools/icount.c`, output unchanged.

## Owner decision (2026-11-06)

- Fetching external tools is allowed when they come from the official source and their version is pinned and recorded: wasmtime, the Rust wasm32-wasip1 target, crates from crates.io (regex, vendored deps), and PyPI metadata.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
