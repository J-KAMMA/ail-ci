"""Generated big-value programs for lab/regress/run.py.

Each entry is (key, format, source). The format says how the token sets of INPUT_SETS are written to stdin:
  sp    one line, space separated          cnt   a count line, then one line of values
  nl    one value per line                 none  the program reads nothing
The programs are the idioms that the typed path took over in 2026-10 (ints from `int(text)`, record fields, arithmetic,
comprehensions and slices over parsed ints), each probed with values near and beyond +-2**63.
"""

INPUT_SETS = {
    'empty': [],
    'small': ['5', '3', '-2', '7', '1', '0'],
    'edge64': ['9223372036854775807', '-9223372036854775808', '9223372036854775806', '1', '-1', '0'],
    'beyond': ['9223372036854775808', '-9223372036854775809', '99999999999999999999', '5', '-7', '3'],
    'huge': ['123456789012345678901234567890', '-340282366920938463463374607431768211456', '18446744073709551616',
             '2', '3'],
    'near62': ['4611686018427387904', '4611686018427387905', '4611686018427387906', '4611686018427387907'],
    'single': ['4611686018427387904'],
    'mid': ['3037000500', '3037000500', '-3037000500', '4294967296', '4294967297', '2147483648'],
}


def render(fmt, tokens):
    if fmt == 'none':
        return ''
    if fmt == 'sp':
        return ' '.join(tokens) + '\n'
    if fmt == 'nl':
        return ''.join(t + '\n' for t in tokens)
    if fmt == 'cnt':
        return str(len(tokens)) + '\n' + ' '.join(tokens) + '\n'
    raise ValueError(fmt)


PROGRAMS = []


def add(key, fmt, src):
    PROGRAMS.append((key, fmt, src))


add('sum_minmax', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    print(len(xs), sum(xs))
    if xs:
        print(min(xs), max(xs), sorted(xs)[0], sorted(xs, reverse=True)[0])
    t = 0
    for x in xs:
        t += x * 3
    print(t)
    print(xs)


if __name__ == "__main__":
    main()
''')

add('arith', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    out: list[int] = []
    for i in range(len(xs)):
        x = xs[i]
        out.append(x * x)
        out.append(x + x)
        out.append(x - 1)
        out.append(-x)
        out.append(abs(x))
        out.append(x // 3)
        out.append(x % 7)
    print(out)
    acc = 1
    for x in xs:
        acc = acc * (x % 1000 + 1)
    print(acc)
    for x in xs:
        print(x + x, x - 1, -x, abs(x), x // 3, x % 7, x * 2)


if __name__ == "__main__":
    main()
''')

add('slices_comps', 'cnt', '''import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return
    n = int(data[0])
    xs = [int(t) for t in data[1:1 + n]]
    print(xs[1:], xs[::-1], xs[:2])
    print([x * 2 for x in xs if x > 0])
    print([x * x for x in xs[1:]])
    ys = sorted(xs)
    print(ys[1:-1], sum(ys[1:]), sum(x + 1 for x in ys))
    if len(xs) > 1:
        print(max(xs[1:]), min(xs[:-1]))
    print(sum([x for x in xs if x % 2 == 0]))


if __name__ == "__main__":
    main()
''')

add('rec_sum', 'sp', '''import sys
from dataclasses import dataclass


@dataclass
class Rec:
    name: str
    score: float
    hits: int


def count_hits(recs: list[Rec]) -> int:
    h = 0
    for r in recs:
        h += r.hits
    return h


def bump(recs: list[Rec], k: int) -> None:
    for r in recs:
        r.hits += k


def triple(recs: list[Rec]) -> None:
    for r in recs:
        r.hits *= 3


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    recs: list[Rec] = []
    for i in range(len(xs)):
        recs.append(Rec("n" + str(i), i * 0.5, xs[i]))
    print(count_hits(recs))
    bump(recs, 5)
    print(count_hits(recs))
    triple(recs)
    print(count_hits(recs))
    for r in recs:
        print(r.name, r.score, r.hits)


if __name__ == "__main__":
    main()
''')

add('rec_mul', 'sp', '''import sys
from dataclasses import dataclass


@dataclass
class Pair:
    a: int
    b: int


def dot(ps: list[Pair]) -> int:
    t = 0
    for p in ps:
        t += p.a * p.b
    return t


def spread(ps: list[Pair]) -> int:
    lo = ps[0].a
    hi = ps[0].a
    for p in ps:
        if p.a < lo:
            lo = p.a
        if p.b > hi:
            hi = p.b
    return hi - lo


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    ps: list[Pair] = []
    for i in range(len(xs) - 1):
        ps.append(Pair(xs[i], xs[i + 1]))
    if not ps:
        print("none")
        return
    print(dot(ps))
    print(spread(ps))
    p = ps[0]
    p.a = p.a * p.b
    p.b = p.a + p.b
    print(p.a, p.b, p)


if __name__ == "__main__":
    main()
''')

add('rec_const', 'none', '''from dataclasses import dataclass


@dataclass
class Rec:
    name: str
    score: float
    hits: int


def count_hits(recs: list[Rec]) -> int:
    h = 0
    for r in recs:
        h += r.hits
    return h


def bump(recs: list[Rec]) -> None:
    for r in recs:
        r.hits = r.hits * 4


def main() -> None:
    recs: list[Rec] = []
    for i in range(3):
        recs.append(Rec("n" + str(i), i * 0.5, 4611686018427387904 + i))
    print(count_hits(recs))
    bump(recs)
    print(recs[0].hits, count_hits(recs))
    big = [Rec("b", 1.5, 9223372036854775800 + i) for i in range(10)]
    print(count_hits(big))


if __name__ == "__main__":
    main()
''')

add('funcs', 'sp', '''import sys


def f(a: int, b: int) -> int:
    return a * b + a


def g(n: int) -> int:
    t = 0
    for i in range(1, n + 1):
        t += i * n
    return t


def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    for i in range(len(xs) - 1):
        print(f(xs[i], xs[i + 1]), g(abs(xs[i]) % 50))
    for x in xs:
        print(fact(abs(x) % 30))
    print(f(f(xs[0], 3), 7) if xs else 0)


if __name__ == "__main__":
    main()
''')

add('dict_set', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    d: dict[int, int] = {}
    for x in xs:
        d[x] = d.get(x, 0) + x
        d[x * x] = d.get(x * x, 0) + 1
    for k in sorted(d):
        print(k, d[k])
    s = set(xs)
    s.add(2 ** 64)
    print(len(s), sorted(s))
    print(sum(d.values()))


if __name__ == "__main__":
    main()
''')

add('bits', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    m = 18446744073709551615
    for x in xs:
        print(x << 3, x >> 2, x & m, x | m, x ^ m, ~x)
        print(x << 70, (x & 255) << 62)


if __name__ == "__main__":
    main()
''')

add('strs', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    for x in xs:
        s = str(x)
        print(s, len(str(x * x)), int(s) + 1, f"{x:>25}", f"{x:x}", repr(x))
    print(" ".join(str(x * 2) for x in xs))
    print(",".join([str(x) for x in xs]))


if __name__ == "__main__":
    main()
''')

add('floats', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    for x in xs:
        print(float(x), x / 2, x * 0.5, x / 3)
    if xs:
        print(sum(xs) / len(xs))


if __name__ == "__main__":
    main()
''')

add('klass', 'sp', '''import sys


class Acc:
    def __init__(self) -> None:
        self.total = 0
        self.count = 0

    def add(self, x: int) -> None:
        self.total += x * x
        self.count += 1

    def mean(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total / self.count


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    a = Acc()
    for x in xs:
        a.add(x)
    print(a.total, a.count, a.mean())


if __name__ == "__main__":
    main()
''')

add('global_acc', 'sp', '''import sys

total = 0


def add(x: int) -> None:
    global total
    total += x * x


def main() -> None:
    for t in sys.stdin.read().split():
        add(int(t))
    print(total)


if __name__ == "__main__":
    main()
''')

add('lines', 'nl', '''import sys


def main() -> None:
    total = 0
    sq = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        n = int(line)
        total += n
        sq += n * n
        print(n, n + 1, n * 2)
    print(total, sq)


if __name__ == "__main__":
    main()
''')

add('input_lines', 'nl', '''def main() -> None:
    n = 0
    t = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        v = int(line)
        t += v
        n += 1
        print(v * v)
    print(n, t)


if __name__ == "__main__":
    main()
''')

add('list_methods', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    ys = xs
    ys.append(10 ** 20)
    ys.insert(0, 2 ** 63)
    ys.extend([x * 2 for x in xs])
    print(ys, len(ys))
    print(ys.count(10 ** 20), ys.index(10 ** 20), 2 ** 63 in ys)
    ys.remove(2 ** 63)
    print(ys.pop(), ys.pop(0), len(ys))
    ys.reverse()
    ys.sort()
    print(ys, sum(ys))


if __name__ == "__main__":
    main()
''')

add('ranges', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    a = xs[0] if xs else 0
    for i in range(a, a + 3):
        print(i, i * i)
    print([i * i for i in range(a, a + 4)])
    print(sum(range(a, a + 5)))
    t = 0
    for i in range(a - 2, a + 2):
        t += i
    print(t)


if __name__ == "__main__":
    main()
''')

add('tuples', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    ps = [(x, x * x) for x in xs]
    ps.sort(key=lambda p: p[1])
    print(ps)
    a, b = (xs[0], xs[-1]) if xs else (0, 0)
    a, b = b, a + b
    print(a, b, (a, b) < (b, a), max(ps) if ps else None)


if __name__ == "__main__":
    main()
''')

add('powers', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    for x in xs:
        print(x ** 2, x ** 3, pow(x, 3, 1000003), divmod(x, 1000000000000000009))
        print(min(x, 2 ** 63), max(x, -2 ** 63), min(x, 5, 7), max(3, x, 9))


if __name__ == "__main__":
    main()
''')

add('digits', 'sp', '''import sys
import math


def digit_sum(n: int) -> int:
    n = abs(n)
    s = 0
    while n > 0:
        s += n % 10
        n //= 10
    return s


def gcd(a: int, b: int) -> int:
    while b != 0:
        a, b = b, a % b
    return abs(a)


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    for x in xs:
        print(digit_sum(x), gcd(x, 123456789012), math.gcd(x, 6))
    print(math.isqrt(abs(xs[0])) if xs else 0)


if __name__ == "__main__":
    main()
''')

add('compare', 'sp', '''import sys


def main() -> None:
    xs = [int(t) for t in sys.stdin.read().split()]
    n = len(xs)
    for i in range(n):
        for j in range(i + 1, n):
            print(xs[i] < xs[j], xs[i] == xs[j], xs[i] * 2 >= xs[j] + 1)
    print(sorted(xs) == xs, xs == xs[::-1], sorted(set(xs)))


if __name__ == "__main__":
    main()
''')
