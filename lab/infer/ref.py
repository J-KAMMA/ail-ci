#!/usr/bin/env python3
"""GPT-2 forward pass in numpy float64, the oracle for lab/infer/gpt2.py.

Usage: python3 ref.py DATA_DIR TOKENS_FILE
Prints the last prompt position's top-5 (id value) and 16 greedy tokens.
The KV cache is deliberately not used: every generated step runs the whole
sequence again, so an error in the AIL cache cannot hide in both programs.
"""
import sys
from pathlib import Path

import numpy as np

N_LAYER = 12
N_EMBD = 768
N_HEAD = 12
N_FF = 3072
N_CTX = 1024
VOCAB = 6000
EPS = 1e-5
HEAD_DIM = N_EMBD // N_HEAD


class Model:
    def __init__(self, data_dir):
        self.d = Path(data_dir)
        self.wte = self.load2("token_embd.weight", VOCAB, N_EMBD)
        self.wpe = self.load2("position_embd.weight", N_CTX, N_EMBD)
        self.ln_f_w = self.load("output_norm.weight")
        self.ln_f_b = self.load("output_norm.bias")
        self.lm_head = self.load2("output.weight", VOCAB, N_EMBD)
        self.blocks = []
        for i in range(N_LAYER):
            p = "blk.%d." % i
            self.blocks.append({
                "ln1_w": self.load(p + "attn_norm.weight"),
                "ln1_b": self.load(p + "attn_norm.bias"),
                "qkv_w": self.load2(p + "attn_qkv.weight", 3 * N_EMBD, N_EMBD),
                "qkv_b": self.load(p + "attn_qkv.bias"),
                "out_w": self.load2(p + "attn_output.weight", N_EMBD, N_EMBD),
                "out_b": self.load(p + "attn_output.bias"),
                "ln2_w": self.load(p + "ffn_norm.weight"),
                "ln2_b": self.load(p + "ffn_norm.bias"),
                "up_w": self.load2(p + "ffn_up.weight", N_FF, N_EMBD),
                "up_b": self.load(p + "ffn_up.bias"),
                "down_w": self.load2(p + "ffn_down.weight", N_EMBD, N_FF),
                "down_b": self.load(p + "ffn_down.bias"),
            })

    def load(self, name):
        return np.fromfile(self.d / (name + ".f32"), dtype="<f4").astype(np.float64)

    def load2(self, name, rows, cols):
        return self.load(name).reshape(rows, cols)

    def forward(self, tokens):
        n = len(tokens)
        x = self.wte[tokens] + self.wpe[:n]
        for b in self.blocks:
            h = layernorm(x, b["ln1_w"], b["ln1_b"])
            qkv = h @ b["qkv_w"].T + b["qkv_b"]
            q = qkv[:, :N_EMBD].reshape(n, N_HEAD, HEAD_DIM).transpose(1, 0, 2)
            k = qkv[:, N_EMBD:2 * N_EMBD].reshape(n, N_HEAD, HEAD_DIM).transpose(1, 0, 2)
            v = qkv[:, 2 * N_EMBD:].reshape(n, N_HEAD, HEAD_DIM).transpose(1, 0, 2)
            scores = (q @ k.transpose(0, 2, 1)) / np.sqrt(HEAD_DIM)
            mask = np.triu(np.ones((n, n), dtype=bool), k=1)
            scores = np.where(mask, -np.inf, scores)
            scores = scores - scores.max(axis=-1, keepdims=True)
            probs = np.exp(scores)
            probs = probs / probs.sum(axis=-1, keepdims=True)
            att = (probs @ v).transpose(1, 0, 2).reshape(n, N_EMBD)
            x = x + att @ b["out_w"].T + b["out_b"]
            h = layernorm(x, b["ln2_w"], b["ln2_b"])
            h = h @ b["up_w"].T + b["up_b"]
            h = 0.5 * h * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (h + 0.044715 * h ** 3)))
            x = x + h @ b["down_w"].T + b["down_b"]
        x = layernorm(x, self.ln_f_w, self.ln_f_b)
        return x @ self.lm_head.T


def layernorm(x, w, b):
    mean = x.mean(axis=-1, keepdims=True)
    var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + EPS) * w + b


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "exported"
    tokens_file = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).with_name("tokens.txt"))
    model = Model(data_dir)
    tokens = [int(s) for s in Path(tokens_file).read_text().split()]
    logits = model.forward(tokens)[-1]
    top = np.argsort(logits)[::-1][:5]
    for i in top:
        print("top5 %d %.9g" % (i, logits[i]))
    generated = []
    seq = list(tokens)
    for _ in range(16):
        logits = model.forward(seq)[-1]
        nxt = int(np.argmax(logits))
        generated.append(nxt)
        seq.append(nxt)
    print("greedy", " ".join(str(t) for t in generated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
