# infer s1: GPT-2 inference in AIL against llama.cpp

A GPT-2 forward pass written as an ordinary Python-syntax AIL program, run on
`zenz-v3.2-small` (GPT-2 small, 12 layers, 768 wide, 12 heads, vocab 6000,
context 1024) and compared with llama.cpp on the same F32 weights, the same 64
prompt tokens and one thread. This is a showcase and a measurement, not an IME
speedup claim.

The AIL side is `gpt2.py`; it compiles with `--strict` (typed path) and decodes
the raw little-endian f32 files itself. `ref.py` is an independent numpy
float64 oracle. The greedy tokens agree exactly:

```
AIL     244 249 248 172 120 202 435 354 280 386 259 623 241 435 354 280
ref.py  244 249 248 172 120 202 435 354 280 386 259 623 241 435 354 280
llama   244 249 248 172 120 202 435 354 280 386 259 623 241 435 354 280
```

## Pins

| component | pin |
| --- | --- |
| model | `Miwa-Keita/zenz-v3.2-small-gguf` @ `c67e03e07d215c869f591b274c1631170d3e11fe` |
| model file | `ggml-model-Q5_K_M.gguf`, sha256 `29c223d4c23327b80fd13ebb5ab2555057a46317997d5da391584ffbef0db673` |
| llama.cpp | `azooKey/llama.cpp` @ `88b97a47dc7f5892e2d5a6856fbe9cfe237f9e5c` |
| numpy | 2.5.4 |
| gguf | 0.19.0 |

`Miwa-Keita/zenz-v3.2-small` (safetensors) answers 401 today, so the public
`-gguf` sibling was used, as the task allows. That sibling ships only Q5_K_M;
`llama-quantize --allow-requantize --pure ... F32` produces the F32 GGUF used by
both programs. The comparison is therefore against the dequantized Q5 weights,
not against an original f32 checkpoint. No weights are committed.

The upstream `ggml-org/llama.cpp` cannot load this model: it rejects
`tokenizer.ggml.pre = gpt2-small-japanese-char`. The azooKey fork adds that
pre-tokenizer; it is pinned above.

## Reproduce

```bash
python3 -m pip install numpy gguf
bash lab/infer/fetch.sh /tmp/ail-infer          # model + llama.cpp + F32 GGUF + exported tensors

# reference (numpy float64); optional STEPS defaults to 16, like gpt2.py
cd lab/infer
ulimit -v 3000000
python3 ref.py /tmp/ail-infer/exported tokens.txt

# AIL
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/infer/gpt2.py -o /tmp/gpt2 --strict
ulimit -v 3000000
/tmp/gpt2 /tmp/ail-infer/exported tokens.txt

# AIL at exactly the 1024-token context length: check the prompt's top-5 and stop
/tmp/gpt2 /tmp/ail-infer/exported tokens1024.txt 0

# llama.cpp, one thread
/tmp/ail-infer/llama-azoo/build/bin/llama-cli \
    -m /tmp/ail-infer/zenz-f32.gguf -p "$(cat lab/infer/prompt.txt)" \
    -n 16 -t 1 --temp 0 --top-k 1 -c 1024 -no-cnv --no-display-prompt
```

`tokens.txt` is the first 64 token ids of `prompt.txt` (the model's tokenizer,
via `llama-tokenize`). It is committed so the three programs see exactly the
same ids. `tokens1024.txt` is `tokens.txt` repeated 16 times, the 1024-token
context length, so the boundary probe is reproducible. Both `gpt2.py` and
`ref.py` take an optional third argument, `STEPS` (default 16), the number of
greedy tokens to decode after the prompt. At a prompt of exactly 1024 ids there
is no room for those steps, so pass `0`; without it both programs still print
the prompt's top-5 and then refuse the decode with the same named context error
on stderr (exit 2). `export_f32.py` refuses a quantized GGUF by name instead of
writing its raw block bytes as f32. `RESULTS.md` has the timing table.

## AIL source shape

`gpt2.py` uses `list[float]` (the fallback named in the task): the typed-array
module has no f32 stage in this tree (`ta.f32` is refused as stage T3), and
2-D/matmul is stage T6. Weights are loaded from the raw f32 files with a small
IEEE-754 decoder. The forward pass has layer norm, causal attention with a KV
cache, GPT-2's tanh GELU, the MLP and the final logits. `--strict` accepts it
without a compiler change.
