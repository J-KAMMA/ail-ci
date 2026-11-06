#!/usr/bin/env bash
# Fetch the tokenizer oracles used by lab/infer/TOKENIZER.md.
#
#   bash lab/infer/tok_fetch.sh [DEST]
#
# DEST defaults to ${RUNNER_TEMP:-/tmp}/ail-tok.  Nothing here is committed.
#
# GPT-2:
#   openai-community/gpt2 @ 607a30d783dfa663caf39e06633721c8d4cfcd7e (MIT)
#   vocab.json  sha256 196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783
#   merges.txt  sha256 1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5
#
# zenz:
#   the vocabulary and merges come from the pinned GGUF; llama-tokenize comes
#   from the pinned azooKey llama.cpp fork.  Run lab/infer/fetch.sh to build it:
#       bash lab/infer/fetch.sh $DEST
#   The GGUF itself is not downloaded here; tok_oracle.py reads the tokenizer
#   metadata from it (or uses the files $DEST/zenz/vocab.json + merges.txt).
set -euo pipefail

DEST="${1:-${RUNNER_TEMP:-/tmp}/ail-tok}"
GPT2_REV=607a30d783dfa663caf39e06633721c8d4cfcd7e
GPT2_VOCAB_SHA=196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783
GPT2_MERGES_SHA=1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5

mkdir -p "$DEST/gpt2"
fetch() {
    python3 - "$1" "$2" <<'PY'
import sys
import urllib.request
urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
PY
}

if [ ! -f "$DEST/gpt2/vocab.json" ]; then
    fetch "https://huggingface.co/openai-community/gpt2/resolve/$GPT2_REV/vocab.json" "$DEST/gpt2/vocab.json"
fi
if [ ! -f "$DEST/gpt2/merges.txt" ]; then
    fetch "https://huggingface.co/openai-community/gpt2/resolve/$GPT2_REV/merges.txt" "$DEST/gpt2/merges.txt"
fi
echo "$GPT2_VOCAB_SHA  $DEST/gpt2/vocab.json" | sha256sum -c -
echo "$GPT2_MERGES_SHA  $DEST/gpt2/merges.txt" | sha256sum -c -

echo "gpt2 tokenizer: $DEST/gpt2"
echo "for zenz, run: bash lab/infer/fetch.sh $DEST"
echo "then: python3 lab/infer/tok_oracle.py --zenz $DEST/zenz-f32.gguf $DEST/llama-azoo/build/bin/llama-tokenize"
