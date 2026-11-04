"""Cases for csv_rollup (see spec.md). cases(rng) -> (public, hidden, perf). CSV on standard input."""

STDIN = True

HEADER = b'region,product,qty,price\n'


def row(region, product, qty, price):
    return ('%s,%s,%d,%d\n' % (region, product, qty, price)).encode()


def public_cases():
    basic = HEADER + b''.join([
        row('us', 'apple', 2, 100),
        row('us', 'apple', 3, 100),
        row('eu', 'pear', 1, 250),
        row('us', 'pear', -2, 50),
    ])
    ties_bad = HEADER + b''.join([
        row('a', 'b', 1, 10),
        row('a', 'b', 2, 5),
        row('z', 'z', 2, 10),
        b'a,b,1\n',
        b',b,1,10\n',
        b'A,b,1,10\n',
        row('a', 'b', -1001, 10),
        row('a', 'b', 1, 10000001),
        b'a,b,1,x\n',
        b'a,b,,10\n',
        b'a,b,1,10,5\n',
    ])
    zeros = HEADER + b''.join([
        row('r1', 'p', 7, 10),
        b'r1,p,-0,100\n',
        row('r2', 'q', 1, 70),
        row('r3', 's', -5, 10),
    ])
    return [
        ('basic', basic, []),
        ('ties_bad', ties_bad, []),
        ('zeros', zeros, []),
    ]


def long_names():
    a16 = 'a' * 16
    b16 = 'b' * 16
    a17 = 'a' * 17
    return HEADER + b''.join([
        row(a16, b16, 1, 1),
        row(a17, b16, 1, 1),
        row(a16, a17, 1, 1),
        row('ok_name', 'P', 1, 1),
        row('ok_name', 'p-1', 1, 1),
        row('ok_name', 'p_1', 1, 1),
        row('', 'p', 1, 1),
        row('_', '_', 2, 3),
    ])


def no_final_newline():
    return HEADER + b''.join([
        row('n', 'x', 1, 5),
        row('n', 'x', -2, 5),
        b'n,y,3,7',
    ])


def leading_zeros():
    return HEADER + b''.join([
        b'r0,p0,007,00010\n',
        b'r0,p0,-0,00100\n',
        b'r1,p1,-007,2\n',
        b'r1,p1,000,0\n',
        b'r2,p2,000123,000\n',
        b'r2,p2,01000,0000000\n',
        b'r2,p2,01001,1\n',
    ])


def random_case(rng, nlines):
    regions = ['r%02d' % i for i in range(23)]
    products = ['p%02d' % i for i in range(17)]
    buf = bytearray(HEADER)
    for _ in range(nlines):
        r = rng.randrange(100)
        if r < 8:
            bad = rng.randrange(6)
            if bad == 0:
                buf += b'a,b,1\n'
            elif bad == 1:
                buf += b',,1,2\n'
            elif bad == 2:
                buf += b'A,b,1,2\n'
            elif bad == 3:
                buf += b'a,b,1001,2\n'
            elif bad == 4:
                buf += b'a b,c,1,2\n'
            else:
                buf += b'a,b,1,2,3\n'
            continue
        reg = regions[rng.randrange(len(regions))]
        prod = products[rng.randrange(len(products))]
        qty = rng.randrange(-1000, 1001)
        price = rng.randrange(0, 10000001)
        buf += row(reg, prod, qty, price)
    return bytes(buf)


def perf_case(rng):
    nreg = 400
    nprod = 300
    regions = ['r%03d' % i for i in range(nreg)]
    products = ['p%03d' % i for i in range(nprod)]
    buf = bytearray(HEADER)
    for _ in range(4000000):
        r = regions[rng.randrange(nreg)]
        p = products[rng.randrange(nprod)]
        q = rng.randrange(-1000, 1001)
        c = rng.randrange(0, 10000001)
        buf += ('%s,%s,%d,%d\n' % (r, p, q, c)).encode()
    return bytes(buf)


def cases(rng):
    public = public_cases()
    hidden = [
        ('empty', b'', []),
        ('header_only', HEADER.rstrip(b'\n'), []),
        ('no_final_newline', no_final_newline(), []),
        ('leading_zeros', leading_zeros(), []),
        ('long_names', long_names(), []),
        ('random_mixed', random_case(rng, 400), []),
    ]
    perf = ('perf', perf_case(rng), [])
    return public, hidden, perf
