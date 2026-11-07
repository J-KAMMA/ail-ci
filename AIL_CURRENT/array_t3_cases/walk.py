import math
import ail_array as ta


def total(a: ta.Array[ta.f32]) -> float:
    t = 0.0
    for v in a:
        t += v
    return t


def main():
    a = ta.array([3.0, -1.5, 0.1, 1e39, -0.0, math.nan, 2.5e-45, 7.0], ta.f32)
    b = ta.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], ta.f32)
    # a for loop reads element k when step k starts: a store ahead of the loop is seen
    c = b.copy()
    seen = []
    for v in c:
        seen.append(v)
        if len(seen) < len(c):
            c[len(seen)] = float(v) * 0.1
    print(seen)
    for v in a:
        print(repr(v), end=" ")
    print()
    for v in ta.array([0.25, 0.5], ta.f32):
        print(v)
    print(total(a), total(b), len(a), len(ta.zeros(0, ta.f32)))
    for i, v in enumerate(b):
        print(i, v)
    for u, v in zip(a, b):
        print(u, v)
    for v in reversed(b):
        print(v, end=" ")
    print()
    print([v * 2.0 for v in a])
    print([u + v for u, v in zip(a, b)])
    print([v for v in b if v > 2.0], sum(v for v in b), max(v for v in b), list(a), sorted(b), min(b), max(b), sum(b))
    print(sorted(ta.array([3.0, -1.5, 0.1], ta.f32)), sum(ta.array([0.1, 0.2], ta.f32)), min(ta.full(3, 0.3, ta.f32)))
    print([[u * v for u in b] for v in ta.array([1.0, 0.5], ta.f32)])
    x = sum(b) if len(b) > 3 else 0.0
    print(x, ta.array(a, ta.f64), ta.array(b, ta.f32))


main()
