Lane: infer

# infer s1: GPT-2 inference written in AIL against llama.cpp (zenz-v3.2-small, f32, single thread)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** a new measurement, AIL / llama.cpp time for the same model, the same tokens and one thread, with the
outputs checked as equal. It is a showcase ("an AI model written in Python syntax"), not an IME speedup. Owner decision,
2026-11-04: start small, f32 only, and measure before any quantized work.

Base: `origin/integ`. All new files go under `lab/infer/` (new directory). Do not edit any compiler file
(`AIL_CURRENT/*.py`, `tools/*`) in this job. If AIL lacks something, write it down as a finding; do not fix it here.

## Sub-steps

1. **Model and reference (15 min cap).** Get zenz-v3.2-small (GPT-2 architecture; about 90M parameters) as f16 or f32
   weights. Try the Hugging Face repo `Miwa-Keita/zenz-v3.2-small` (safetensors) first, then its `-gguf` sibling. Do NOT
   commit weights: the model is CC BY-SA, and the files are large. `lab/infer/fetch.sh` downloads into `$RUNNER_TEMP`
   or `/tmp`. Write `lab/infer/export_f32.py` (CPython, `numpy` + `safetensors` or `gguf` from pip). It writes one raw
   little-endian f32 file per tensor, plus `manifest.txt` (name, shape). Build llama.cpp at a pinned release tag
   (CPU only, `-DGGML_NATIVE=ON`) and make an F32 GGUF of the same weights (`convert_hf_to_gguf.py --outtype f32`).
   Pin both versions in `lab/infer/README.md`. Commit, push, open the PR against `integ`.
2. **Reference logits.** `lab/infer/ref.py` (numpy) runs the GPT-2 forward pass for a fixed 64-token input from the
   model's tokenizer. Use a fixed Japanese sentence and write its token ids into `lab/infer/tokens.txt`. It prints the
   last-position logits' top-5 ids and values, and greedy-decodes 16 tokens. Check it against llama.cpp
   (`llama-cli`/`llama-simple` with `--temp 0`, `-t 1`, the same prompt tokens): the 16 greedy tokens must be equal. Commit.
3. **AIL forward pass.** `lab/infer/gpt2.py` is an annotated Python program that `ail_chatgpt.py compile --strict`
   builds. Use `from ail import ...` built-ins (look at `ail_array` / typed arrays in integ first; plain `list[float]`
   is the fallback). It reads the raw f32 files and implements embedding, layer norm, attention with a causal mask and a
   KV cache, GELU (tanh form, as GPT-2), the MLP and the final logits. It prints the same top-5 and the 16 greedy
   tokens. Check: greedy tokens equal to `ref.py`; top-5 logits within 1e-3 relative. Probe the boundaries: a 1-token
   prompt, and a prompt of exactly the model's context length if that is ≤ 1024 tokens. Commit.
4. **Measure.** One thread for both. Prefill the 64 tokens, then decode 16. Report the median of 5 wall times per phase,
   for AIL and for llama.cpp F32 (`-t 1`, timings from its own report). Add peak RSS (`/usr/bin/time -v`), binary size
   and AIL compile time. Put a table in `lab/infer/RESULTS.md` with the ratio AIL/llama.cpp per phase. If AIL is more
   than 2x slower, say where (one `perf`/callgrind look at the hottest function and the generated C loop of the
   matmul) as findings: e.g. no vectorized inner loop, bounds checks, boxed floats. Commit, push.

## Done-check

`lab/infer/RESULTS.md` has the table. AIL greedy tokens == llama.cpp greedy tokens == `ref.py`. The PR's 20 shards pass.
No weights are in git.

## Stop rule

Stop and report if the model cannot be fetched, converted or matched within the 15-minute cap of step 1. Also stop if
`--strict` refuses `gpt2.py` for a reason that needs a compiler change (name the construct and the refusal text), if AIL
and the reference disagree and you cannot find why in 15 minutes, or when 80 minutes pass. Push what is done and
report the numbers you have. Do not touch `.github/workflows`.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000` (the model run may need `ulimit -v 3000000`); `tools/par_check.py -j 2`
   at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`. (This job adds no test module unless it is quick and needs no download.)
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`;
  `DIR/program.c` is the generated C; `--strict` = typed path or refuse. `-o` must not exist yet.
- AIL is Python syntax plus optional annotations; AIL-only built-ins are spelled `from ail import ...`. Ints are int64 and
  overflow stops loudly; floats are IEEE double unless an f32 array type exists (check `ail_array` in integ).

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
