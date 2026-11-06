"""fdarr3: a long randomized run of f32 arrays through the public ail_array API (test_ail_array_f32native.py).

Every result is reduced to an FNV-1a hash of its tobytes() (or the repr of a scalar), so two builds that print the same
lines produced the same bits. The operands cover every class: zeros of both signs, subnormals, the smallest and largest
normals, values with few mantissa bits (exact ties under + and *), the top binade (overflow), +-inf and the canonical
NaN, and random bit patterns. ROUNDS is the first line so a test can shorten the run.
"""
ROUNDS = 400
import random
import ail_array as ta

SPECIAL = [0x00000000, 0x80000000, 0x00000001, 0x80000001, 0x007FFFFF, 0x00800000, 0x80800000, 0x7F7FFFFF, 0xFF7FFFFF,
           0x7F800000, 0xFF800000, 0x7FC00000, 0x3F800000, 0xBF800000, 0x3F800001, 0x4B800000, 0x33800000, 0x00400000,
           0x7F000000, 0x0C000000, 0x3DCCCCCD, 0x5F800000, 0x1F800000]


def pattern() -> int:
    c = random.randrange(8)
    sign = random.getrandbits(1) * 2147483648
    u = 0
    if c == 0:
        u = SPECIAL[random.randrange(len(SPECIAL))]
    elif c == 1:
        u = sign + random.getrandbits(23)
    elif c == 2:
        u = sign + (random.randrange(254) + 1) * 8388608 + random.getrandbits(23)
    elif c == 3:
        u = sign + 1056964608 + random.getrandbits(24)
    elif c == 4:
        u = sign + (random.randrange(60) + 97) * 8388608 + random.getrandbits(4) * 524288
    elif c == 5:
        u = sign + 2130706432 + random.getrandbits(23)
    else:
        u = random.getrandbits(32)
    if (u // 8388608) % 256 == 255 and u % 8388608 != 0:
        u = 0x7FC00000
    return u


def make(n: int) -> bytes:
    out = bytearray(4 * n)
    for k in range(n):
        u = pattern()
        out[4 * k] = u % 256
        out[4 * k + 1] = (u // 256) % 256
        out[4 * k + 2] = (u // 65536) % 256
        out[4 * k + 3] = u // 16777216
    return bytes(out)


def h(data: bytes) -> int:
    x = 2166136261
    for c in data:
        x = ((x ^ c) * 16777619) % 4294967296
    return x


def length() -> int:
    c = random.randrange(4)
    if c == 0:
        return random.randrange(40)
    if c == 1:
        return 1008 + random.randrange(40)
    if c == 2:
        return 2032 + random.randrange(40)
    return random.randrange(2100)


def main():
    random.seed(20261106)
    ops = 0
    for rnd in range(ROUNDS):
        n = length()
        a = ta.frombytes(make(n), ta.f32)
        b = ta.frombytes(make(n), ta.f32)
        s = float(ta.frombytes(make(1), ta.f32)[0])
        if random.randrange(3) == 0:
            s = float(random.random()) * 8.0 - 4.0
        print(rnd, n, h((a + b).tobytes()), h((a - b).tobytes()), h((a * b).tobytes()), h((a / b).tobytes()))
        print(rnd, h((a + s).tobytes()), h((s - a).tobytes()), h((a - s).tobytes()), h((a * s).tobytes()),
              h((a / s).tobytes()), h((s / a).tobytes()))
        print(rnd, h((-a).tobytes()), h(abs(a).tobytes()), h(ta.sqrt(a).tobytes()), h(ta.exp(b).tobytes()),
              h(ta.log(a).tobytes()), h(ta.tanh(b).tobytes()))
        c = a.copy()
        c += b
        c *= s
        c -= a
        c /= b
        print(rnd, h(c.tobytes()), h(ta.minimum(a, b).tobytes()), h(ta.maximum(a, s).tobytes()), h(a.astype(ta.f64).tobytes()))
        print(rnd, repr(ta.sum(a)), repr(ta.dot(a, b)), repr(ta.sum(a, acc=ta.f64)), repr(ta.dot(a, b, acc=ta.f64)))
        ops = ops + 24 * n
        if rnd % 4 == 0:
            m = random.randrange(1, 24)
            k = random.randrange(0, 40)
            if random.randrange(5) == 0:
                k = 1000 + random.randrange(60)
            p = random.randrange(1, 24)
            A = ta.zeros((m, k), ta.f32)
            B = ta.zeros((k, p), ta.f32)
            da = ta.frombytes(make(m * k), ta.f32)
            db = ta.frombytes(make(k * p), ta.f32)
            for i in range(m):
                for j in range(k):
                    A[i, j] = da[i * k + j]
            for i in range(k):
                for j in range(p):
                    B[i, j] = db[i * p + j]
            print(rnd, m, k, p, h(ta.matmul(A, B).tobytes()), h(A.T.tobytes()))
            ops = ops + m * k * p * 2
    print("element operations:", ops)


main()
