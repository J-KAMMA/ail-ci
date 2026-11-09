# NumPy version of mlp.py (same weights, same shapes, f32); NumPy's own summation order (BLAS sgemm), so the last digits differ.
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


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    x, s = fill(64, 784, 1, 2.0)
    w1, s = fill(784, 512, s, 0.1)
    b1, s = fill(1, 512, s, 0.1)
    w2, s = fill(512, 10, s, 0.1)
    b2, s = fill(1, 10, s, 0.1)
    b1, b2 = b1[0], b2[0]
    h = np.maximum(x @ w1 + b1, np.float32(0.0))
    y = h @ w2 + b2
    total = 0.0
    for i in range(64):
        total += float(np.sum(y[i]))
    print("%.17g" % total)
    print("%.17g" % y[0, 0])
    print("%.17g" % y[63, 9])
    print(int(np.argmax(y[0])), int(np.argmax(y[63])))
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        h = np.maximum(x @ w1 + b1, np.float32(0.0))
        y = h @ w2 + b2
        ts.append(time.perf_counter() - t0)
    if ts:
        ts.sort()
        print("forward median us", round(ts[len(ts) // 2] * 1e6, 1))


main()
