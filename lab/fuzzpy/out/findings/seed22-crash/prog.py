from dataclasses import dataclass


@dataclass
class Pt:
    a: int
    b: int
    c: float
    name: str
    items: list[int]


def bump(p: Pt, k: int) -> int:
    p.a += k
    p.items.append(k)
    return p.a + len(p.items)


def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 12:
            break
        t += abs(x) + 1
    return t


def main() -> int:
    pt0: Pt = Pt(5, 1, 0.1, 'Zed', [])
    print(b"x".decode())
    v1: int = 0
    try:
        v1 = (0 >> 0)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-95)
    try:
        print(int('日本'))
    except (ValueError, ZeroDivisionError):
        print(-84)
    pt0.items.append((51 // (abs(v1) + 1)))
    w2: int = 0
    while w2 < 2:
        w2 += 1
        print(((w2 - v1) + (w2 * v1)))
        v1 -= (3037000499 ** 3)
        try:
            if ((v1 * v1) < w2):
                raise ValueError
        except (ValueError, ZeroDivisionError):
            print(-10)
        else:
            print(99)
    try:
        if ((v1 * 42) < (v1 - -3)):
            assert (v1 >= (v1 * 24)), "boom"
    except AssertionError:
        print(-80)
    else:
        print(47)
    v1 = 94
    try:
        if (not ((v1 - -3) > (-v1))):
            raise ValueError('m1')
    except ValueError:
        print(-59)
    else:
        print(57)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v1)
    return 0


main()
