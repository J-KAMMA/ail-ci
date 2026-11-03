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


def h0(a: int, b: int) -> int:
    v1: int = 'hello'.find('-'.join('abc'.split(',')))
    v2: str = f'{'a,b,c'}'
    v3: list[int] = list(range(-2, 10, 2))
    w4: int = 0
    while w4 < 5:
        w4 += 1
        if ((v2.replace('a', '').find('日本') != (68 - v1)) or (("%d" % 21) == v2.replace('l', ''))):
            print(len(v3))
            if ((v2 in v2) and (b != (36 - v1))):
                continue
        else:
            v5: list[int] = [3] * 1
            if ((a << 12) <= sum(v3)):
                break
    try:
        print(int('ab'), abs(b), 0.5)
    except ValueError:
        print(-39)
    if ((b ** 3) <= a):
        return (0 // -8)
    return ((b - 255) // (abs(b) + 1))


def main() -> int:
    pt0: Pt = Pt(4, 7, 1e10, 'AbCd', [])
    try:
        if (not (ord((' pad ' + '12')[3]) != (93 * 0))):
            assert ((255 != (35 - 46)) and ((49 + 42) == -6)), "boom"
    except AssertionError:
        print(-73)
    else:
        print(2)
    print((min(42, 66) - (16 // (abs(14) + 1))))
    v6: bytes = (b"a,b" * 2)
    v8: list[int] = [min(9, c7) for c7 in range(5) if c7 % 2 == 0]
    for i9 in range(4):
        v10: str = f'{max(0.5, 0.5):.0f}'
        print((abs(abs(0.1)) ** 0.5))
    try:
        print((h0(abs(33), (-1 // -7)) ^ (41 - 86)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-87)
    try:
        v8.pop()
    except IndexError:
        print(-55)
    print(((1.25 + 0.5) > float(min(72, 11))))
    v11: str = 'x'
    v12: dict[str, int] = {}
    v12['c'] = 62
    v12['a'] = 3
    if (v11[2] == '-'.join(v11.split('a'))):
        print(((100.75 + 1.25) - abs(123456.789)))
    elif (43 > h0((15 - 51), (57 >> 9))):
        v12.pop('a', 8)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v6), v6.decode())
    print(len(v8), sum(v8))
    print(v11)
    ks14: list[str] = []
    for k13 in sorted(v12):
        ks14.append(k13)
    print(len(v12), sum(v12.values()), ','.join(ks14))
    return 0


sys.exit(main())
