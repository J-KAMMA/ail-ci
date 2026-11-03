"""Cases for csv_group (see spec.md). cases(rng) -> (public, hidden, perf)."""

A = []
STDIN = True


def rows(*pairs):
    return ''.join('%s,%s\n' % (key, value) for key, value in pairs).encode()


def cases(rng):
    public = [
        ('basic', rows(('a', 1), ('b', 2), ('a', 3)), A),
        ('empty', b'', A),
        ('no_final_newline', b'x,10\ny,5\nx,2', A),
    ]
    hidden = [
        ('single', rows(('only', 7)), A),
        ('leading_zeros', b'a,007\nb,000\na,0\n', A),
        ('sort_order', b'z,1\na,2\nm,3\n_a,4\ng0,5\n', A),
        ('blank_lines', b'\n\na,1\n\nb,2\n\n', A),
        ('zero_values', b'a,0\nb,0\na,0\n', A),
        ('long_key', ('k' * 80 + ',5\n').encode(), A),
        ('big_total', (''.join('g%d,1000000000\n' % i for i in range(1000))).encode(), A),
        ('many_groups', (''.join('g%03d,%d\n' % (i, i) for i in range(200))).encode(), A),
        ('same_group', (''.join('one,%d\n' % i for i in range(500))).encode(), A),
    ]
    names = ['g%04d' % i for i in range(1000)]
    parts = []
    for _ in range(200000):
        parts.append('%s,%d\n' % (rng.choice(names), rng.randrange(0, 1000000001)))
    perf = ('perf', ''.join(parts).encode(), A)
    return public, hidden, perf
