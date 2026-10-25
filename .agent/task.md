# bigint-fix12: remaining IR-coverage and peak-memory regressions after fix02..fix11 (B, plus possible C) -- run this LAST

These modules assert "function F is lowered by the IR" or pin a memory/plan property, and failed in the triage with
causes that may be covered by fix02..fix11 (a function that parses an int, writes a module variable, etc. is now
refused or left on the legacy emitter). Re-run them after the earlier tasks land, then fix whatever is left. Do not
weaken a test: if the property cannot hold with exact ints, show it (and write the number) instead.

## Modules and what was seen
- test_ail_ir_s3 (16 failures): the list-owner programs (`every_pass_subset`, `generated_owner_programs` seeds 3/11/29,
  owned lists/bytearrays, second-name-for-a-list shapes, `switch_off_leaves_no_trace_of_the_s3a_runtime`, sanitizers):
  expected-IR sets missing `w2`, `put` (bit operations: fix11), `h1`, and `ValueError: substring not found` /
  `index('int64_t steps(void) {')` (the C of `steps` is shaped differently now: a pin, decide A or B). The 'uncaught'
  sanitizer case and an IndexError wording difference are A (fix17).
- test_ail_ir_s4a (18 failures): `Items in the first set but not the second: 'main'` (also 'pick', 'parse', 'risky',
  'probe'): the function is not IR-lowered; most are `int(sys.argv[1])` (fix02). Others: `build() needs the tagged-int
  lowering, which does not cover it: builder locals` (2 tests; "the general path could not build this program either:
  a non-BMP string literal in the 16-bit v2 runtime" -- real: a str builder local, `t += s` in a loop, together with a
  tagged int in the same function is refused; the stand-alone `total(s)` loop compiles), one `collect2: ld returned 1`
  (check whether fix05), `ir build of textops failed`.
- test_ail_ir_s3b (6): `KeyError: 'two_fields'`, `KeyError: 'tidy'`, sets of expected-IR functions missing items.
- test_ail_ir_s3c1 (6): sets of functions missing from the IR, `ValueError: substring not found` and
  **peak memory**: `10496 not less than or equal to 2060.8 : {'legacy': 1408, 'ir': 10496}` in
  test_an_iteration_local_list_keeps_the_legacy_peak_memory (the IR build uses 7x the legacy peak: investigate, may be
  a real leak/arena regression in the tagged list code, category C).
- test_ail_ir_s3d1 (1): `{'big','main','missing','count','lookups','rebuild'} not <= {'big','lookups','rebuild','missing','count'}`: main not lowered.
- test_ail_ir_s4c1 (3): test_forward_scans_are_windowed (programs `lines`, `slices`: `has_window` false, the windowed
  scan plan no longer applies), and test_a_large_input_costs_a_fraction_of_the_input_in_peak_memory
  (`33280 not less than 16640.0`: peak memory doubled).
- test_ail_ir_cover (1) and test_ail_ir_gridbounds (2 of its 8): `FileNotFoundError: .../stats.jsonl` -- the stats file
  is never written because the grid `main` is no longer lowered (compile falls back before the IR runs).
- test_ail_stdin_list_batch (2): `_stdin_broots` (the batched stdin-lines optimisation) is no longer in the C of
  join_after and for_print_after:
  ```
  import sys
  def main() -> int:
      out: list[str] = []
      for line in sys.stdin:
          out.append(line.strip() + "!")
      print("\n".join(out))
      return 0
  main()
  ```
  The output is right (check with `printf 'a\nb\n' | ./x.exe`); the optimisation pass lost this shape.
- test_ail_strict (1): test_s7_refusal_without_a_position_is_located expects `strict: 1 typed-path blocker;` but the report
  lists 2: the second is a derived blocker "Node___ail_init_rest() needs the tagged-int lowering, which does not cover it:
  a method" for
  ```
  class Node:
      def __init__(self, v: int):
          self.v = v
          self.next = None
  def main():
      print(1)
  main()
  ```
  (`python3 -B ail_chatgpt.py compile st.py --syntax python --strict -o st.exe`). A refusal caused by an earlier one
  must not be listed (see test_s7_a_refusal_caused_by_an_earlier_one_is_not_listed).

## Category
Mostly B; the memory numbers and the `ld` error are C if they persist.

## Fixed means
Each listed test passes, or you report for it (a) the cause, (b) whether it is A (the old expectation is wrong; show the
CPython evidence) and (c) what you changed.

run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing.

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
