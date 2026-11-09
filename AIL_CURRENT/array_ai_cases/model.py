# A small MLP and a small attention block written as a torch or NumPy user writes them (job aicore1), f32 and f64.
import math
import ail_array as ta


def fill(m: ta.Matrix[ta.f32], s: int, scale: float) -> int:
    r, c = m.shape
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def fill64(m: ta.Matrix[ta.f64], s: int, scale: float) -> int:
    r, c = m.shape
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def mlp():
    x = ta.zeros((8, 40), ta.f32)
    w1 = ta.zeros((40, 33), ta.f32)
    b1 = ta.zeros((1, 33), ta.f32)
    w2 = ta.zeros((33, 10), ta.f32)
    b2 = ta.zeros(10, ta.f32)
    s = fill(x, 3, 2.0)
    s = fill(w1, s, 0.3)
    s = fill(b1, s, 0.3)
    fill(w2, s, 0.3)
    for j in range(10):
        b2[j] = float(j) * 0.01
    h = ta.maximum(ta.matmul(x, w1) + b1[0], 0.0)
    y = ta.matmul(h, w2) + b2
    print("mlp", y.tobytes().hex())
    print("mlp argmax", ta.argmax(y, axis=1))


def softmax(s: ta.Matrix[ta.f32]) -> ta.Matrix[ta.f32]:
    e = ta.exp(s - ta.max(s, axis=1, keepdims=True))
    return e / ta.sum(e, axis=1, keepdims=True)


def attn():
    q = ta.zeros((19, 16), ta.f32)
    k = ta.zeros((19, 16), ta.f32)
    v = ta.zeros((19, 16), ta.f32)
    s = fill(q, 11, 4.0)
    s = fill(k, s, 4.0)
    fill(v, s, 4.0)
    p = softmax(ta.matmul(q, k.T) * (1.0 / math.sqrt(16.0)))
    o = ta.matmul(p, v)
    print("attn", o.tobytes().hex())
    print("attn rows", ta.sum(p, axis=1))


def attn64():
    q = ta.zeros((9, 8), ta.f64)
    k = ta.zeros((9, 8), ta.f64)
    s = fill64(q, 5, 4.0)
    fill64(k, s, 4.0)
    sc = ta.matmul(q, k.T) / math.sqrt(8.0)
    e = ta.exp(sc - ta.max(sc, axis=1, keepdims=True))
    p = e / ta.sum(e, axis=-1, keepdims=True)
    print("attn64", p.tobytes().hex())
    print("attn64 cols", ta.sum(p, axis=0))


mlp()
attn()
attn64()
