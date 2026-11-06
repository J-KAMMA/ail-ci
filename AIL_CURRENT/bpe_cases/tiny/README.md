# Tiny BPE case

A 512-merge byte-level BPE vocabulary trained with `tokenizers` on
`lab/infer/tok_corpus.txt` (initial alphabet: the 256 byte symbols, no specials).
`expected_ids.json` holds the ids for every corpus line.
Regenerate with `python3 lab/infer/tok_oracle.py --tiny`.
