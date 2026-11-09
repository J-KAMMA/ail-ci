# Timing version of attn.py: the same inputs, the attention block run REPS times; prints the checksum of the last pass and
# the median time of one pass in microseconds (the fill is outside the timed part).
import math
import time
import ail_array as ta

REPS = 101


def fill(m: ta.Matrix[ta.f32], s: int, scale: float) -> int:
    r, c = m.shape
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def attn(q: ta.Matrix[ta.f32], k: ta.Matrix[ta.f32], v: ta.Matrix[ta.f32]) -> ta.Matrix[ta.f32]:
    sc = ta.matmul(q, k.T) * (1.0 / math.sqrt(64.0))
    e = ta.exp(sc - ta.max(sc, axis=1, keepdims=True))
    p = e / ta.sum(e, axis=1, keepdims=True)
    return ta.matmul(p, v)


def main():
    q = ta.zeros((128, 64), ta.f32)
    k = ta.zeros((128, 64), ta.f32)
    v = ta.zeros((128, 64), ta.f32)
    s = fill(q, 7, 2.0)
    s = fill(k, s, 2.0)
    fill(v, s, 2.0)
    ts = []
    o = attn(q, k, v)
    for _ in range(REPS):
        t0 = time.perf_counter()
        o = attn(q, k, v)
        ts.append(time.perf_counter() - t0)
    total = 0.0
    for i in range(128):
        total += ta.sum(o[i])
    print("%.17g" % total)
    ts.sort()
    print("forward median us", round(ts[len(ts) // 2] * 1e6, 1))


main()
