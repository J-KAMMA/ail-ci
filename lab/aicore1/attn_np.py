# NumPy version of attn.py (same inputs, f32); NumPy's own summation order and exp, so the last digits differ.
import math
import sys
import time
import numpy as np


def fill(r, c, s, scale):
    out = np.zeros((r, c), np.float32)
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            out[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return out, s


def attn(q, k, v):
    sc = (q @ k.T) * np.float32(1.0 / math.sqrt(64.0))
    e = np.exp(sc - np.max(sc, axis=1, keepdims=True))
    p = e / np.sum(e, axis=1, keepdims=True)
    return q, p, p @ v


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    q, s = fill(128, 64, 7, 2.0)
    k, s = fill(128, 64, s, 2.0)
    v, s = fill(128, 64, s, 2.0)
    _, p, o = attn(q, k, v)
    total = 0.0
    for i in range(128):
        total += float(np.sum(o[i]))
    print("%.17g" % total)
    print("%.17g" % o[0, 0])
    print("%.17g" % o[127, 63])
    print("%.17g" % p[5, 7])
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        attn(q, k, v)
        ts.append(time.perf_counter() - t0)
    if ts:
        ts.sort()
        print("forward median us", round(ts[len(ts) // 2] * 1e6, 1))


main()
