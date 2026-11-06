# feinf2: a byte-level BPE tokenizer in AIL

`lab/infer/bpe.py` is the tokenizer, written as an ordinary AIL program (and
module). It reads the usual Hugging Face `vocab.json` + `merges.txt` pair, or
the equivalent files exported from the pinned zenz GGUF, and implements

* GPT-2's 256-entry byte-to-unicode table (`BYTE_CHARS`),
* the GPT-2 pre-tokenizer written as plain code, with no `\p{...}` regex,
* merges by rank, merging every occurrence of the lowest-rank adjacent pair,
* decode back to bytes, and `roundtrip`.

`lab/infer/bpe_cli.py` is the CPython wrapper. `tok_fetch.sh` downloads the
GPT-2 files, `tok_oracle.py` writes expected ids, and `tok_bench.sh` makes the
B6 table below.

## Pins

| component | pin |
| --- | --- |
| GPT-2 vocabulary | `openai-community/gpt2` @ `607a30d783dfa663caf39e06633721c8d4cfcd7e` (MIT) |
| `vocab.json` | sha256 `196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783` |
| `merges.txt` | sha256 `1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5` |
| Hugging Face `tokenizers` | 0.23.3 |
| zenz model | `Miwa-Keita/zenz-v3.2-small-gguf` @ `c67e03e07d215c869f591b274c1631170d3e11fe` (Apache-2.0) |
| llama.cpp | `azooKey/llama.cpp` @ `88b97a47dc7f5892e2d5a6856fbe9cfe237f9e5c` |
| tiny case | 512 merges trained with `tokenizers` on `tok_corpus.txt`; 768-token vocabulary |

No vocabulary or weights are committed except the tiny case in
`AIL_CURRENT/bpe_cases/tiny`.

## Pre-tokenizer rules

The splitter is GPT-2's expression

```
's|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+
```

evaluated left to right:

1. `'s`, `'t`, `'re`, `'ve`, `'m`, `'ll`, `'d` (lowercase, contraction first).
2. one literal ASCII space plus a letter run, if the next code point is a letter;
3. one literal ASCII space plus a number run, if the next is a number;
4. one literal ASCII space plus a punctuation run, if the next is neither
   whitespace, letter nor number;
5. a whitespace run before a non-space is split as `k - 1` whitespace; its last
   code point then either starts rule 2-4's run (when it is an ASCII space) or
   is a one-code-point whitespace token;
6. a whitespace run at the end of the text is one token.

Classification uses Python's Unicode definitions (`isalpha` for L,
`isnumeric` for N, `isspace` for `\s`). Input is walked as UTF-8 bytes, so the
16-bit general build handles the corpus emoji too. A code point above U+FFFF is
classified as a symbol (exact for the corpus pictographs; a non-BMP letter would
not be grouped as a letter on that build). The pinned azooKey fork maps
`gpt2-small-japanese-char` to this same expression, so zenz shares the splitter.

## Results

`lab/infer/tok_corpus.txt` has 2,010 lines (99,798 bytes) of our own English,
Japanese, code, emoji, whitespace runs, numbers and contractions.

* Tiny 512-merge case: all 2,010 lines' ids equal the `tokenizers` ids in both
  AIL builds and CPython; `roundtrip` recovers the corpus bytes exactly.
* GPT-2 (`vocab.json` + `merges.txt`): all 2,010 lines' ids equal
  `tokenizers` 0.23.3 in the default AIL build.
* zenz (GGUF `tokenizer.ggml.tokens` + `tokenizer.ggml.merges`): all 2,010
  lines' ids equal the same vocabulary/merges through `tokenizers`. The
  `llama-tokenize` half of `tok_oracle.py` is ready but needs the pinned
  llama.cpp build from `fetch.sh`; that build was not available in this run, so
  this table does not claim to have executed it.

Run the test module with

```bash
python3 AIL_CURRENT/test_ail_bpe.py
```

## B6: GPT-2 tokens per second

Corpus repeated to 5,000,044 bytes (100,698 lines, 2,036,758 tokens), one
thread, median of 5, on the 4-core GitHub Actions runner. AIL is
`lab/infer/bpe.py` built with the default (typed) path; the reference is
Hugging Face `tokenizers` 0.23.3 with the same vocabularies.

| implementation | median s | tokens/s | peak RSS | binary |
| --- | ---: | ---: | ---: | ---: |
| AIL `bpe.py` | 3.700 | 550475 | 150.5 MB | 152 KB |
| HF `tokenizers` | 1.500 | 1357839 | - | - |

AIL is 2.47x slower than the Rust `tokenizers` on this machine. The tokenizer
does not cache merges per pre-token (the typed path keeps dictionary parameters
read-only); a cache would trade that rule for speed.

Reproduce:

```bash
bash lab/infer/tok_fetch.sh /tmp/ail-tok
bash lab/infer/tok_bench.sh /tmp/ail-tok/gpt2 /tmp/ail-tok
python3 lab/infer/tok_oracle.py --gpt2 /tmp/ail-tok/gpt2 --out /tmp/gpt2_ids.json
```
