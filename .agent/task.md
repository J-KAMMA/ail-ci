**A Python-syntax module of definitions only must build as a no-op (and Rust tests must skip when rustup has no toolchain).**

Background: an old job (`ex24`, accepted but its diff no longer applies) fixed two things that are still open on integ.

1. `AIL_CURRENT/language_examples/math.ail` is a module (`LIMIT = 6`, `def sum_to(n)`), not a program. CPython loads it, prints nothing, exits 0. On integ the default build refuses it with `not in the subset: the first parameter must be the sequence read from the file` (`pyc.py`, near line 599, where the last function is treated as the entry). `integer_series.ail` has the same shape and compiles as a file-reading tool (`usage: tool FILE`, exit 2) where CPython exits 0 silently. Reproducer: build and run both examples on both builds and compare with `python3`.
   Fix: a Python-surface file whose top level is only effect-free definitions and literal module constants builds a no-op entry (empty `main`; the boxed path needs a trailing `pass` so it does not call the last function). Annotations count as effect free when made of builtin names, literals, subscripts and `|` unions (`list[int]`, `dict[str, int]`, `int | None`); defaults must be literals. A decorator, a non-constant annotation or default, or any top-level statement that runs code keeps today's behaviour (do not make those silently exit 0).
2. `test_ail_c_export` and `test_ail_cratebridge` take `RUSTC = shutil.which('rustc')`. Under a task-local `HOME` with no `~/.rustup` the rustup proxy is found but every call exits 1 ("could not choose a version of rustc"). Probe `rustc --version` in a small helper (`ail_testenv.rustc()`) and skip the Rust tests when it fails; a configured toolchain still runs them. No compiler change.

Start from today's integ, read `git log --oneline -40` first, and do not reuse the old diff (old branch: `out/ci/ex24.branch` in the agents folder, reference only). If either item no longer reproduces, change nothing for it and say so.

Add a CPython-compared test module `AIL_CURRENT/test_ail_reex24.py` registered in `ail_check.py` MODULES, run `python3 tools/update_manifest.py`, then only that module, the modules of the files you touched, and `test_ail_safetynet`. Commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
