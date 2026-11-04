#!/usr/bin/env bash
# Fetch zenz-v3.2-small, make an F32 GGUF, and export one raw f32 file per tensor.
#
#   bash lab/infer/fetch.sh [DEST]
#
# DEST defaults to ${RUNNER_TEMP:-/tmp}/ail-infer.  Nothing is written into the
# repository: the weights stay outside git.
#
# Pins:
#   model  Miwa-Keita/zenz-v3.2-small-gguf @ c67e03e07d215c869f591b274c1631170d3e11fe
#          ggml-model-Q5_K_M.gguf  sha256 29c223d4c23327b80fd13ebb5ab2555057a46317997d5da391584ffbef0db673
#   llama  azooKey/llama.cpp @ 88b97a47dc7f5892e2d5a6856fbe9cfe237f9e5c
#          (the fork is required: upstream rejects tokenizer pre =
#           "gpt2-small-japanese-char")
#
# The public -gguf sibling only ships Q5_K_M.  We dequantize it to F32 with
# llama-quantize, so both programs use exactly the same f32 values.
set -euo pipefail

DEST="${1:-${RUNNER_TEMP:-/tmp}/ail-infer}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$DEST/llama-azoo"
MODEL_Q5="$DEST/zenz-q5.gguf"
MODEL_F32="$DEST/zenz-f32.gguf"
MODEL_REV=c67e03e07d215c869f591b274c1631170d3e11fe
LLAMA_REV=88b97a47dc7f5892e2d5a6856fbe9cfe237f9e5c

mkdir -p "$DEST"

if [ ! -f "$MODEL_Q5" ]; then
    curl -L --retry 3 -o "$MODEL_Q5" \
        "https://huggingface.co/Miwa-Keita/zenz-v3.2-small-gguf/resolve/$MODEL_REV/ggml-model-Q5_K_M.gguf"
fi
echo "29c223d4c23327b80fd13ebb5ab2555057a46317997d5da391584ffbef0db673  $MODEL_Q5" | sha256sum -c -

if [ ! -d "$SRC/.git" ]; then
    git init -q "$SRC"
    git -C "$SRC" remote add origin https://github.com/azooKey/llama.cpp.git
fi
git -C "$SRC" fetch -q --depth 1 origin "$LLAMA_REV"
git -C "$SRC" checkout -q --detach FETCH_HEAD
cmake -S "$SRC" -B "$SRC/build" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
    -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON
cmake --build "$SRC/build" -j 4 --target llama-cli llama-quantize llama-tokenize llama-simple

"$SRC/build/bin/llama-quantize" --allow-requantize --pure "$MODEL_Q5" "$MODEL_F32" F32 4
python3 "$HERE/export_f32.py" "$MODEL_F32" "$DEST/exported"

echo "ready: $DEST"
echo "run:   $SRC/build/bin/llama-cli -m $MODEL_F32 -p \"\$(cat $HERE/prompt.txt)\" -n 16 -t 1 --temp 0 --top-k 1 -c 1024 -no-cnv"
