# job job-feinf2-11060906  started 2026-11-06T00:12:04Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented feinf2 and committed as `3d34259`.

**Delivered**
- `lab/infer/bpe.py`: byte-level BPE (GPT-2/zenn), GPT-2 pre-tokenizer written as plain code, byte-table encode/decode/roundtrip.
- `bpe_cli.py`, `tok_fetch.sh`, `tok_oracle.py`, `tok_bench.sh`, `TOKENIZER.md`, 2,010-line `tok_corpus.txt`.
- `AIL_CURRENT/test_ail_bpe.py`, `bpe_cases/tiny` (512 merges, expected ids), test registration and manifest pins.

**Verified**
- `test_ail_bpe.py`: 3/3 pass in default typed build, forced general build, and CPython.
- All 2,010 corpus lines id-exact for tiny/GPT-2/zenz vocabularies; roundtrip byte-exact.
- GPT-2 ids also checked against `tokenizers` 0.23.3 via `tok_oracle.py`.
- Required `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass.

**B6 (5,000,044 bytes, 2,036,758 tokens, median of 5)**
| implementation | median s | tokens/s | peak RSS | binary |
| --- | ---: | ---: | ---: | ---: |
| AIL `bpe.py` | 3.700 | 550,475 | 150.5 MB | 152 KB |
| HF `tokenizers` | 1.500 | 1,357,839 | - | - |

AIL is 2.47x slower than Rust `tokenizers`. Limitation: `llama-tokenize` was not built/run in this session; the zenz oracle path is ready, and zenz ids were verified through the same GGUF vocabulary/merges using `tokenizers`. No push was made (harness forbids it).
[cost $0.0000, opencode tokens {"total": 6579898, "input": 133626, "output": 34048, "reasoning": 31424, "cache.write": 0, "cache.read": 6380800}]
    tool time: bash 10.1 min, write 0.0 min, edit 0.0 min
        168s bash   cd /home/runner/work/_temp/w2 && time python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8
        149s bash   cd /home/runner/work/_temp/w2 && time python3 AIL_CURRENT/test_ail_corpus_findings3.py 2>&1 | tail -8
         82s bash   cd /home/runner/work/_temp/w2 && time python3 AIL_CURRENT/test_ail_files.py 2>&1 | tail -8
         27s bash   cd /home/runner/work/_temp/w2 && time bash lab/infer/tok_bench.sh /tmp/ail-tok/gpt2 /tmp/ail-tok 2>&1 | tail -
         27s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p=Path('lab/infer/tok_bench.sh') s=
         23s bash   cd /home/runner/work/_temp/w2 && printf 'test_ail_bpe\n' > AIL_CURRENT/tests.d/test_ail_bpe.txt && time python
         21s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/bpe_def /tmp/bpe_uni && time python3 -B AIL_CURRENT/ail_chatgpt.py
         17s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p=Path('lab/infer/bpe.py') s=p.read

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does:** adds a new standalone AIL program/module `lab/infer/bpe.py` (byte-level BPE tokenizer: GPT-2 byte table, GPT-2 pre-tokenizer written as code, rank merges, decode/roundtrip), its CPython CLI, oracle/fetch/bench scripts, a 2,010-line corpus, a `tokenizers`-trained 512-merge CI case, plus test registration. No compiler, runtime or existing program is touched.

**Probes run (all in `/tmp/rprobes`):**
- `gpt2_diff.py` / `zenz_diff.py`: `bpe.encode_line` vs HF `tokenizers` 0.23.3 on all 2,010 corpus lines and 57 adversarial strings, both vocabs → **0 diffs**.
- `p1..p3.txt` (empty line, spaces/tabs runs, contractions, CJK, emoji, combining marks, NBSP/em-space, astral chars, punctuation/number runs, CRLF, CRLF-in-line): compiled general path and typed path vs CPython, `encode` and `roundtrip` → **identical, exit 0**.
- empty file, lone `\n`, CRLF file, control-char file: compiled == CPython.
- full-corpus `roundtrip`: **byte-exact** in general, typed and CPython.
- `diff_pretok.py`: 1,166 pre-tokenizer cases vs HF ByteLevel; diffs only where a non-BMP letter meets ASCII (documented).
- 3,000-string fuzz × 2 vocabs: 106 diffs, all astral-letter/contraction or `\x1C-\x1F`; re-fuzz of 4,000 strings excluding those → **0 diffs**.
- No-feature program: `--debug-dir` `program.c` identical to `/tmp/base` (work).

**Tests:** `par_check.py -j 2 test_ail_bpe test_ail_safetynet` → 2/2 ok (181 s). `update_manifest.py --check` passes. Tiny case retrained from the corpus reproduces `vocab.json` and all 2,010 expected id lists exactly.

**Report claims:**
- tiny case + “3/3 pass” → verified.
- corpus id-exact for tiny/GPT-2/zenz (via tokenizers) → verified independently.
- roundtrip byte-exact → verified.
- GPT-2 checked through `tok_oracle.py` → verified (result matches).
- B6 numbers → verified: worker's raw medians 3.70 s / 1.50 s, tokens 2,036,758, RSS 153,880 KB, binary 152 KB; my single loaded run 5.19 s / 1.83 s, ids byte-identical.
- `llama-tokenize` not run → **unverified by execution** (as reported). I fetched the pinned azooKey fork: its `gpt2-small-japanese-char` regex is the GPT-2 pattern and its byte map equals `BYTE_CHARS`, so the implementation is consistent with that source.

**Non-blocking limitations (outside the corpus, so outside the task's number):**
- Non-BMP letters are classified as symbols (documented in `bpe.py`/`TOKENIZER.md`): `"c𠮷's"` → HF `[66,172,254,106,115,338]`, here `[66,172,254,106,115,6,82]`.
- Python `isspace` includes U+001C–U+001F, unlike `\s`: `"\x1d'll"` → HF `[6,297]`, here `[1183]`. Undocumented; no corpus or vocab impact.

**Pre-existing:** none (change adds only new files; no-feature C is identical).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=52 out_tokens=34716]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T02:09:19Z
