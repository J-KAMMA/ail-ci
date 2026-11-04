"""GPT-2 inference in AIL: zenz-v3.2-small, f32 weights, float64 arithmetic.

Build: python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/infer/gpt2.py -o gpt2 --strict
Run:   ./gpt2 DATA_DIR TOKENS_FILE [STEPS]

DATA_DIR is the directory made by export_f32.py (one little-endian f32 file per
tensor).  This program decodes those bytes itself, so it does not rely on an
f32 array type in the compiler.  STEPS is the number of greedy tokens to decode
after the prompt (default 16).  A prompt at the context length needs STEPS=0;
otherwise the program prints the prompt's top-5 and then refuses the decode with
a named context error.
"""
import sys
import math
from ail import read_bytes

N_LAYER = 12
N_EMBD = 768
N_HEAD = 12
N_FF = 3072
N_CTX = 1024
VOCAB = 6000
HEAD_DIM = 64
EPS = 0.00001

def read_f32(path: str, count: int, pow2: list[float], sub: float) -> list[float]:
    data = read_bytes(path)
    out = [0.0] * count
    i = 0
    while i < count:
        o = i * 4
        u = data[o] + data[o + 1] * 256 + data[o + 2] * 65536 + data[o + 3] * 16777216
        sign = 1.0
        if u >= 2147483648:
            sign = -1.0
            u = u - 2147483648
        e = u // 8388608
        m = u % 8388608
        if e == 0:
            out[i] = sign * (m * sub)
        elif e == 255:
            out[i] = sign * (1.0e300)
        else:
            out[i] = sign * (1.0 + m * 0.00000011920928955078125) * pow2[e]
        i += 1
    return out


def layer_norm(x: list[float], w: list[float], b: list[float]) -> list[float]:
    n = len(x)
    i = 0
    total = 0.0
    while i < n:
        total += x[i]
        i += 1
    mean = total / n
    i = 0
    var = 0.0
    while i < n:
        d = x[i] - mean
        var += d * d
        i += 1
    var = var / n
    inv = 1.0 / math.sqrt(var + EPS)
    y = [0.0] * n
    i = 0
    while i < n:
        y[i] = (x[i] - mean) * inv * w[i] + b[i]
        i += 1
    return y


def linear(x: list[float], w: list[float], b: list[float], out_n: int, in_n: int) -> list[float]:
    y = [0.0] * out_n
    j = 0
    while j < out_n:
        s = b[j]
        base = j * in_n
        k = 0
        while k < in_n:
            s += x[k] * w[base + k]
            k += 1
        y[j] = s
        j += 1
    return y


def gelu(x: list[float]) -> list[float]:
    y = [0.0] * len(x)
    i = 0
    c = 0.7978845608028654
    while i < len(x):
        v = x[i]
        y[i] = 0.5 * v * (1.0 + math.tanh(c * (v + 0.044715 * v * v * v)))
        i += 1
    return y


def main() -> int:
    data_dir = sys.argv[1]
    tokens_file = sys.argv[2]
    prefix = data_dir + "/"
    pow2 = [0.0] * 256
    I = 0
    while I < 256:
        pow2[I] = 2.0 ** (I - 127)
        I += 1
    sub = 2.0 ** -149

    wte = read_f32(prefix + "token_embd.weight.f32", VOCAB * N_EMBD, pow2, sub)
    wpe = read_f32(prefix + "position_embd.weight.f32", N_CTX * N_EMBD, pow2, sub)
    lnf_w = read_f32(prefix + "output_norm.weight.f32", N_EMBD, pow2, sub)
    lnf_b = read_f32(prefix + "output_norm.bias.f32", N_EMBD, pow2, sub)
    head_w = read_f32(prefix + "output.weight.f32", VOCAB * N_EMBD, pow2, sub)

    ln1_w = []
    ln1_b = []
    qkv_w = []
    qkv_b = []
    o_w = []
    o_b = []
    ln2_w = []
    ln2_b = []
    up_w = []
    up_b = []
    down_w = []
    down_b = []
    layer = 0
    while layer < N_LAYER:
        q = prefix + "blk." + str(layer) + "."
        ln1_w.append(read_f32(q + "attn_norm.weight.f32", N_EMBD, pow2, sub))
        ln1_b.append(read_f32(q + "attn_norm.bias.f32", N_EMBD, pow2, sub))
        qkv_w.append(read_f32(q + "attn_qkv.weight.f32", 3 * N_EMBD * N_EMBD, pow2, sub))
        qkv_b.append(read_f32(q + "attn_qkv.bias.f32", 3 * N_EMBD, pow2, sub))
        o_w.append(read_f32(q + "attn_output.weight.f32", N_EMBD * N_EMBD, pow2, sub))
        o_b.append(read_f32(q + "attn_output.bias.f32", N_EMBD, pow2, sub))
        ln2_w.append(read_f32(q + "ffn_norm.weight.f32", N_EMBD, pow2, sub))
        ln2_b.append(read_f32(q + "ffn_norm.bias.f32", N_EMBD, pow2, sub))
        up_w.append(read_f32(q + "ffn_up.weight.f32", N_FF * N_EMBD, pow2, sub))
        up_b.append(read_f32(q + "ffn_up.bias.f32", N_FF, pow2, sub))
        down_w.append(read_f32(q + "ffn_down.weight.f32", N_EMBD * N_FF, pow2, sub))
        down_b.append(read_f32(q + "ffn_down.bias.f32", N_EMBD, pow2, sub))
        layer += 1

    kcache = [0.0] * (N_LAYER * N_CTX * N_EMBD)
    vcache = [0.0] * (N_LAYER * N_CTX * N_EMBD)
    zero_bias = [0.0] * VOCAB

    token_text = read_bytes(tokens_file).decode()
    prompt = []
    for word in token_text.split():
        prompt.append(int(word))

    if len(prompt) > N_CTX:
        print("refused: prompt has " + str(len(prompt)) + " tokens, context length is "
              + str(N_CTX), file=sys.stderr)
        return 2

    last_logits = [0.0] * VOCAB
    seq = list(prompt)
    pos = 0
    while pos < len(seq):
        token = seq[pos]
        x = [0.0] * N_EMBD
        i = 0
        tb = token * N_EMBD
        pb = pos * N_EMBD
        while i < N_EMBD:
            x[i] = wte[tb + i] + wpe[pb + i]
            i += 1
        layer = 0
        while layer < N_LAYER:
            h = layer_norm(x, ln1_w[layer], ln1_b[layer])
            qkv = linear(h, qkv_w[layer], qkv_b[layer], 3 * N_EMBD, N_EMBD)
            cb = (layer * N_CTX + pos) * N_EMBD
            att = [0.0] * N_EMBD
            hd = 0
            while hd < N_HEAD:
                db = hd * HEAD_DIM
                i = 0
                while i < HEAD_DIM:
                    kcache[cb + db + i] = qkv[N_EMBD + db + i]
                    vcache[cb + db + i] = qkv[2 * N_EMBD + db + i]
                    i += 1
                n = pos + 1
                scores = [0.0] * n
                t = 0
                maxscore = -1.0e300
                while t < n:
                    kb = (layer * N_CTX + t) * N_EMBD + db
                    s = 0.0
                    i = 0
                    while i < HEAD_DIM:
                        s += qkv[db + i] * kcache[kb + i]
                        i += 1
                    s = s * 0.125
                    scores[t] = s
                    if s > maxscore:
                        maxscore = s
                    t += 1
                total = 0.0
                t = 0
                while t < n:
                    e = math.exp(scores[t] - maxscore)
                    scores[t] = e
                    total += e
                    t += 1
                t = 0
                while t < n:
                    p = scores[t] / total
                    vb = (layer * N_CTX + t) * N_EMBD + db
                    i = 0
                    while i < HEAD_DIM:
                        att[db + i] += p * vcache[vb + i]
                        i += 1
                    t += 1
                hd += 1
            a = linear(att, o_w[layer], o_b[layer], N_EMBD, N_EMBD)
            i = 0
            while i < N_EMBD:
                x[i] += a[i]
                i += 1
            h = layer_norm(x, ln2_w[layer], ln2_b[layer])
            u = linear(h, up_w[layer], up_b[layer], N_FF, N_EMBD)
            u = gelu(u)
            d = linear(u, down_w[layer], down_b[layer], N_EMBD, N_FF)
            i = 0
            while i < N_EMBD:
                x[i] += d[i]
                i += 1
            layer += 1
        h = layer_norm(x, lnf_w, lnf_b)
        last_logits = linear(h, head_w, zero_bias, VOCAB, N_EMBD)
        pos += 1

    idx = [0] * 5
    vals = [0.0] * 5
    tmp = list(last_logits)
    i = 0
    while i < 5:
        best = 0
        j = 1
        while j < VOCAB:
            if tmp[j] > tmp[best]:
                best = j
            j += 1
        idx[i] = best
        vals[i] = tmp[best]
        tmp[best] = -1.0e300
        i += 1
    i = 0
    while i < 5:
        print("top5 %d %.9g" % (idx[i], vals[i]))
        i += 1

    steps = 16
    if len(sys.argv) > 3:
        steps = int(sys.argv[3])
    if steps < 0:
        steps = 0
    if len(seq) + steps > N_CTX:
        print("refused: " + str(len(seq)) + "-token prompt plus " + str(steps)
              + " decode steps exceeds context length " + str(N_CTX)
              + "; pass STEPS=0 after TOKENS_FILE to stop at the prompt", file=sys.stderr)
        return 2
    generated = []
    step = 0
    while step < steps:
        best = 0
        j = 1
        while j < VOCAB:
            if last_logits[j] > last_logits[best]:
                best = j
            j += 1
        generated.append(best)
        seq.append(best)
        pos = len(seq) - 1
        token = best
        x = [0.0] * N_EMBD
        i = 0
        tb = token * N_EMBD
        pb = pos * N_EMBD
        while i < N_EMBD:
            x[i] = wte[tb + i] + wpe[pb + i]
            i += 1
        layer = 0
        while layer < N_LAYER:
            h = layer_norm(x, ln1_w[layer], ln1_b[layer])
            qkv = linear(h, qkv_w[layer], qkv_b[layer], 3 * N_EMBD, N_EMBD)
            cb = (layer * N_CTX + pos) * N_EMBD
            att = [0.0] * N_EMBD
            hd = 0
            while hd < N_HEAD:
                db = hd * HEAD_DIM
                i = 0
                while i < HEAD_DIM:
                    kcache[cb + db + i] = qkv[N_EMBD + db + i]
                    vcache[cb + db + i] = qkv[2 * N_EMBD + db + i]
                    i += 1
                n = pos + 1
                scores = [0.0] * n
                t = 0
                maxscore = -1.0e300
                while t < n:
                    kb = (layer * N_CTX + t) * N_EMBD + db
                    s = 0.0
                    i = 0
                    while i < HEAD_DIM:
                        s += qkv[db + i] * kcache[kb + i]
                        i += 1
                    s = s * 0.125
                    scores[t] = s
                    if s > maxscore:
                        maxscore = s
                    t += 1
                total = 0.0
                t = 0
                while t < n:
                    e = math.exp(scores[t] - maxscore)
                    scores[t] = e
                    total += e
                    t += 1
                t = 0
                while t < n:
                    p = scores[t] / total
                    vb = (layer * N_CTX + t) * N_EMBD + db
                    i = 0
                    while i < HEAD_DIM:
                        att[db + i] += p * vcache[vb + i]
                        i += 1
                    t += 1
                hd += 1
            a = linear(att, o_w[layer], o_b[layer], N_EMBD, N_EMBD)
            i = 0
            while i < N_EMBD:
                x[i] += a[i]
                i += 1
            h = layer_norm(x, ln2_w[layer], ln2_b[layer])
            u = linear(h, up_w[layer], up_b[layer], N_FF, N_EMBD)
            u = gelu(u)
            d = linear(u, down_w[layer], down_b[layer], N_EMBD, N_FF)
            i = 0
            while i < N_EMBD:
                x[i] += d[i]
                i += 1
            layer += 1
        h = layer_norm(x, lnf_w, lnf_b)
        last_logits = linear(h, head_w, zero_bias, VOCAB, N_EMBD)
        step += 1

    out = []
    for t in generated:
        out.append(str(t))
    print("greedy " + " ".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
