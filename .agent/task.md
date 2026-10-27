**Your change fails tests on top of the current integration branch.** Applied alone on today's integ, one or more of these test modules fail: test_ail_callable_values test_ail_crypto test_ail_fuzz42 test_ail_fuzz55 test_ail_fuzz56 test_ail_fuzz58 test_ail_fuzz60 test_ail_fuzz61 test_ail_fuzz62 test_ail_fuzz65 test_ail_fuzz83 test_ail_fuzz86 test_ail_fuzz87 test_ail_fuzz89 test_ail_fuzz94 test_ail_gcstress test_ail_hostile_input test_ail_numeric_bindings test_ail_pre100 test_ail_pre101 test_ail_pre102 test_ail_pre103 test_ail_pre104 test_ail_pre105 test_ail_pre107 test_ail_pre109 test_ail_pre110 test_ail_pre112 test_ail_pre113 test_ail_pre114 test_ail_pre116 test_ail_pre117 test_ail_pre120 test_ail_pre121 test_ail_pre124 test_ail_pre125 test_ail_pre126 test_ail_pre127 test_ail_pre128 test_ail_pre130 test_ail_pre132 test_ail_pre133 test_ail_pre134 test_ail_pre137 test_ail_pre138 test_ail_pre141 test_ail_pre160 test_ail_pre163 test_ail_pre165 test_ail_pre166 test_ail_pre167 test_ail_pre168 test_ail_pre170 test_ail_pre171 test_ail_pre172 test_ail_pre173 test_ail_pre175 test_ail_pre177 test_ail_pre179 test_ail_pre18 test_ail_pre180 test_ail_pre181 test_ail_pre182 test_ail_pre183 test_ail_pre184 test_ail_pre185 test_ail_pre186 test_ail_pre188 test_ail_pre190 test_ail_pre191 test_ail_pre192 test_ail_pre195 test_ail_pre196 test_ail_pre197 test_ail_pre199 test_ail_pre2 test_ail_pre201 test_ail_pre203 test_ail_pre204 test_ail_pre205 test_ail_pre206 test_ail_pre209 test_ail_pre211 test_ail_pre212 test_ail_pre213 test_ail_pre214 test_ail_pre215 test_ail_pre216 test_ail_pre218 test_ail_pre220 test_ail_pre225 test_ail_pre227 test_ail_pre23 test_ail_pre236 test_ail_pre237 test_ail_pre238 test_ail_pre241 test_ail_pre242 test_ail_pre243 test_ail_pre246 test_ail_pre248 test_ail_pre251 test_ail_pre253 test_ail_pre254 test_ail_pre255 test_ail_pre257 test_ail_pre258 test_ail_pre26 test_ail_pre263 test_ail_pre265 test_ail_pre267 test_ail_pre269 test_ail_pre27 test_ail_pre270 test_ail_pre271 test_ail_pre273 test_ail_pre279 test_ail_pre283 test_ail_pre285 test_ail_pre29 test_ail_pre290 test_ail_pre296 test_ail_pre298 test_ail_pre36 test_ail_pre44 test_ail_pre48 test_ail_pre87 test_ail_pre89 test_ail_pre90 test_ail_pre93 test_ail_pre96 test_ail_pre97 test_ail_pre98 test_ail_record_initializers test_ail_safetynet test_ail_typed_inherit.

Run each of them (`cd AIL_CURRENT && python3 -m unittest -q <module>`), find why it fails here (another change may have altered behaviour or output your test expects), and fix it so they pass while keeping your fix and its test. Commit.

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
