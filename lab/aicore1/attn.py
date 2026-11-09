# Single-head attention: seq 128, dim 64, softmax(Q K^T / sqrt(d)) V, f32, fixed deterministic inputs.
import math
import ail_array as ta


def fill(m: ta.Matrix[ta.f32], s: int, scale: float) -> int:
    r, c = m.shape
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def main():
    q = ta.zeros((128, 64), ta.f32)
    k = ta.zeros((128, 64), ta.f32)
    v = ta.zeros((128, 64), ta.f32)
    s = fill(q, 7, 2.0)
    s = fill(k, s, 2.0)
    fill(v, s, 2.0)
    sc = ta.matmul(q, k.T) * (1.0 / math.sqrt(64.0))
    e = ta.exp(sc - ta.max(sc, axis=1, keepdims=True))
    p = e / ta.sum(e, axis=1, keepdims=True)
    o = ta.matmul(p, v)
    total = 0.0
    for i in range(128):
        total += ta.sum(o[i])
    print("%.17g" % total)
    print("%.17g" % o[0, 0])
    print("%.17g" % o[127, 63])
    print("%.17g" % p[5, 7])


main()
