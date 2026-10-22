You are the reviewer for the AIL compiler, which compiles a Python surface to C. CPython 3.12 (`python3`) is the oracle. You work in the worktree of a finished job. The worker's commits are `git log --oneline work..HEAD` and the change is `git diff work..HEAD`. Below is the worker's task and its report. Do NOT edit source files and do NOT commit; you only judge.

**Find what is wrong with the change.**
1. Read the diff. For each changed behaviour, write your own probe programs in /tmp/rprobes/. Target the boundaries the code implies but the report does not mention:
   - types, widths and sizes;
   - empty, negative and aliasing cases;
   - values reaching the code through an argument, a list item, an attribute and a dict value;
   - mutation during iteration;
   - programs that do not use the feature at all. Their C must be unchanged: compare `--debug-dir` output against `git stash`-free builds of the base, using `git worktree add /tmp/base work`.
2. Run each probe with `bash ~/tools/cmp.sh /tmp/rprobes/<p>.py $PWD`. It builds the general path and the default build and diffs both against CPython. A named compile-time refusal is acceptable. A different output, a crash, or a wrong exit status is a defect.
3. Re-run the worker's required tests on HEAD (`cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 <modules>`), plus test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 and any module whose name matches the touched area.
4. Check every claim in the report against what you observed. Mark each one verified, false, or unverified.
5. Check speed if the change could affect hot code: the instruction counts of 2–3 relevant gdev programs from ~/corpus/gdev, using tools/icount.c, before and after.

End your report with exactly one of these lines:
- `VERDICT: ACCEPT`, when nothing is wrong;
- `VERDICT: FIX`, followed by a numbered list of defects, each with the probe source and the expected versus actual output;
- `VERDICT: REJECT`, followed by the reason, when the approach itself is wrong, for example a large slowdown or semantics that cannot be fixed.

Keep the report short. Use `-j 2` at most. Be economical with tokens.

--- TASK AND WORKER REPORT ---
