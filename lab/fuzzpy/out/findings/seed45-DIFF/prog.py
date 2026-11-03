import sys

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


def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 1 + 1) % 45003
    return (h0(n - 1, a + 0) * 3 + h0(n - 1, a - 2) + n) % 45003


def main() -> int:
    pt0: Pt = Pt(0, 9, 1.25, 'hello', [])
    for i1 in range(1, 3):
        print((i1 > 3))
        print(abs((abs(123456.789) ** 0.5)))
    v2: int = ((40 ** 0) * (-6 ^ 71))
    print(v2)
    p3: Pt = Pt(64, 70, 2.5e-3, 'café', [])
    v4: list[int] = [(-10)]
    v5: str = ""
    try:
        v5 = f'{max(40, v2):d}{'ab'}{(7.0 / (57 // v2)):>10.1f}'
    except ZeroDivisionError:
        print(-71)
    finally:
        print(110)
    try:
        if (v4.count((v2 + v2)) > 3):
            raise IndexError('m4')
    except (IndexError, ValueError):
        print(-47)
    else:
        print(18)
    v5 = f'{(0.5 % 0.75)}-'
    try:
        if (v5 in '-'.join('hello'.split(' '))):
            raise RuntimeError('m7')
    except RuntimeError:
        print(-69)
    v6: dict[str, int] = {}
    v6['dd'] = 4
    v6['a'] = 64
    v6['e'] = 44
    v6['c'] = 15
    pt0.items.append(len(v6))
    w7: int = 0
    while w7 < 3:
        w7 += 1
        if ((3.0 / (abs(1e10) + 1.0)) == (3.0 / (abs(0.5) + 1.0))):
            continue
        if ('日本' in f'{v4.pop():3d}{(abs(1e-7) ** 0.5):.0f}'):
            continue
        v8: int = 0
        try:
            v8 = ((v2 + 27) - h0(7, (~w7)))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-40)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v2)
    print(p3.a, p3.b, p3.c, p3.name, len(p3.items))
    print(len(v4), sum(v4))
    print(v5)
    ks10: list[str] = []
    for k9 in sorted(v6):
        ks10.append(k9)
    print(len(v6), sum(v6.values()), ','.join(ks10))
    return 0


sys.exit(main())
