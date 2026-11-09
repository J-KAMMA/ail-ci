# Timing version of mlp.py: the same weights, the forward pass run REPS times; prints the checksum of the last pass and the
# median time of one pass in microseconds (the fill is outside the timed part).
import time
import ail_array as ta

REPS = 21


def fill(m: ta.Matrix[ta.f32], s: int, scale: float) -> int:
    r, c = m.shape
    for i in range(r):
        for j in range(c):
            s = (1664525 * s + 1013904223) % 4294967296
            m[i, j] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def fill1(v: ta.Array[ta.f32], s: int, scale: float) -> int:
    for i in range(len(v)):
        s = (1664525 * s + 1013904223) % 4294967296
        v[i] = (float(s) / 4294967296.0 - 0.5) * scale
    return s


def forward(x: ta.Matrix[ta.f32], w1: ta.Matrix[ta.f32], b1: ta.Array[ta.f32], w2: ta.Matrix[ta.f32],
            b2: ta.Array[ta.f32]) -> ta.Matrix[ta.f32]:
    h = ta.maximum(ta.matmul(x, w1) + b1, 0.0)
    return ta.matmul(h, w2) + b2


def main():
    x = ta.zeros((64, 784), ta.f32)
    w1 = ta.zeros((784, 512), ta.f32)
    b1 = ta.zeros(512, ta.f32)
    w2 = ta.zeros((512, 10), ta.f32)
    b2 = ta.zeros(10, ta.f32)
    s = fill(x, 1, 2.0)
    s = fill(w1, s, 0.1)
    s = fill1(b1, s, 0.1)
    s = fill(w2, s, 0.1)
    fill1(b2, s, 0.1)
    ts = []
    y = forward(x, w1, b1, w2, b2)
    for _ in range(REPS):
        t0 = time.perf_counter()
        y = forward(x, w1, b1, w2, b2)
        ts.append(time.perf_counter() - t0)
    total = 0.0
    for i in range(64):
        total += ta.sum(y[i])
    print("%.17g" % total)
    ts.sort()
    print("forward median us", round(ts[len(ts) // 2] * 1e6, 1))


main()
