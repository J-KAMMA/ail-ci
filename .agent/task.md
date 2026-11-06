Lane: fe-infer

# feinf2: a byte-level BPE tokenizer written in AIL, id-exact against Hugging Face `tokenizers` and llama.cpp

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** lines of a fixed corpus whose ids from the compiled tokenizer equal the oracle's: (a) GPT-2's
own vocabulary (`openai-community/gpt2` `vocab.json` + `merges.txt`, MIT) against Hugging Face `tokenizers`, (b) the
zenz vocabulary from the pinned GGUF against the pinned llama.cpp fork's `llama-tokenize`. Today 0 (no tokenizer);
target every line equal for both, encode and decode round-trip equal. Third number: GPT-2 BPE tokens per second,
AIL against Hugging Face `tokenizers` (Rust), one thread, median of 5 (GPU.md 8.3 B6).

Base: `origin/integ`. Do not edit any compiler file. Files you may create or edit, and no others:
- `lab/infer/bpe.py` (new: the tokenizer, an ordinary AIL program and module), `lab/infer/bpe_cli.py` (new)
- `lab/infer/tok_fetch.sh`, `lab/infer/tok_oracle.py`, `lab/infer/tok_bench.sh` (new), `lab/infer/TOKENIZER.md` (new)
- `lab/infer/tok_corpus.txt` (new, about 2,000 lines of our own text: English, Japanese, code, emoji, whitespace runs,
  numbers, contractions such as `'s` and `'ll`)
- `AIL_CURRENT/test_ail_bpe.py` (new), `AIL_CURRENT/bpe_cases/*` (new: a tiny vocabulary trained on our corpus with
  `tokenizers` and the expected ids, committed), `AIL_CURRENT/tests.d/test_ail_bpe.txt` (new, one line)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Oracles (15 min).** `tok_fetch.sh` downloads the GPT-2 vocabulary at a pinned revision (sha256 checked; not
   committed). `tok_oracle.py` writes the expected ids for every corpus line with `tokenizers` (pinned version) and,
   for zenz, with `llama-tokenize` from the fork that `fetch.sh` builds. A tiny vocabulary (512 merges) trained on
   `tok_corpus.txt` goes into `bpe_cases/` with its expected ids for CI. Commit, push, and open the PR against `integ`.
2. **Tokenizer (30 min).** GPT-2 byte-to-unicode table, the pre-tokenizer split written as plain code (no `\p{L}`
   regex needed: classify with `str.isalpha`/`isnumeric`/`isspace` the way the GPT-2 pattern does, and document each
   rule), merges by rank with a cache, decode. For zenz, read `tokenizer.ggml.tokens`/`merges` from the GGUF metadata
   and implement the `gpt2-small-japanese-char` pre-tokenizer as the fork does (read its source; write our own code).
   Commit and push.
3. **Test and measure (15 min).** `test_ail_bpe.py`: the tiny vocabulary cases in both builds and CPython, ids equal.
   Register it. `tok_bench.sh`: the full corpus repeated to about 5 MB, tokens per second for AIL and `tokenizers`,
   peak RSS, binary size; table into `TOKENIZER.md`. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_bpe.py` passes in both builds; GPT-2 and zenz corpus ids 100% equal; round-trip equal.
- `TOKENIZER.md` has the B6 table (medians of 5); the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report the first corpus line whose ids differ, with both id lists. Stop if a vocabulary licence is not MIT
or compatible.
Stop at once and report if any build prints output different from CPython (or from the reference this task
names) without a refusal or a loud stop: give the program, both outputs and the commit. Never commit a change
that does that. Stop when 60 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug] [--debug-dir DIR] [--gpu]`.
  `DIR/program.c` is the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback
  to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations (`.py` files only; the `.ail` brace syntax is retired). Ints are
  int64, and overflow stops loudly. Never silent wrong output: a value AIL cannot compute exactly is refused by name
  or stops loudly.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- `lab/infer/` (README.md, RESULTS.md): GPT-2 `zenz-v3.2-small` (12 layers, 768 wide, 12 heads, vocab 6000, context
  1024), F32 weights from the pinned Q5_K_M GGUF via `fetch.sh` + `export_f32.py`; `gpt2.py` (typed path), `ref.py`
  (numpy float64 oracle), llama.cpp pinned to the azooKey fork (upstream rejects the `gpt2-small-japanese-char`
  pre-tokenizer). No weights are committed. Peak RSS is about 1 GB, so full-model runs go to GitHub as README says.
  fdinf1 adds `bench.sh` / `profile.sh`; fdinf2 adds `gpt2_ta.py` on `ta.f32`.
- The fdinf2 standard: greedy token ids must match exactly (`ref.py` and llama.cpp); logits may differ in the last
  bits. The compiled program must print exactly what CPython prints for the same file with the references.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
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
