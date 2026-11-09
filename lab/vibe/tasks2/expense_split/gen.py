"""Cases for expense_split (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def lines(rows):
    return ''.join(r + '\n' for r in rows).encode('utf8')


def cases(rng):
    public = [
        ('basic', lines([
            'alice 100 bob carol',
            'bob 60 alice carol',
            'carol 10 alice bob',
        ]), []),
        ('remainder', lines([
            'a 10 x y z',
            'b 7 x y',
            'c 0 x',
        ]), []),
        ('bad_lines', lines([
            'a 100 b c',
            'a 100 b b',
            'a -5 b c',
            'a 1000000000001 b',
            'a 100',
            'onlytwo 5',
            'a 1x b c',
            '',
            'z 3 y x',
        ]), []),
        ('unicode', lines([
            'josé 90 café niño',
            'café 30 josé',
        ]), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_only', b'\n \n\t\n', []),
        ('zero_amount', lines(['a 0 a', 'b 0 a b c']), []),
        ('one_participant', lines(['a 999999999999 b', 'b 1 a']), []),
        ('big_remainder', lines(['p 1000000000000 ' + ' '.join('u%d' % i for i in range(3))]), []),
        ('tabs', b'a\t100\tb\tc\n', []),
        ('no_final_newline', b'a 5 b c\nb 5 a c', []),
        ('int64_sum', lines(['a 1000000000000 b c', 'b 1000000000000 a c', 'c 1000000000000 a b']), []),
    ]
    for k in range(4):
        rows = []
        names = ['n%02d' % i for i in range(rng.randrange(2, 12))]
        for _ in range(rng.randrange(10, 300)):
            r = rng.random()
            if r < 0.1:
                rows.append('%s %d %s %s' % (rng.choice(names), rng.randrange(100), rng.choice(names),
                                             rng.choice(names)))
            else:
                kp = rng.randrange(1, 5)
                ps = rng.sample(names, min(kp, len(names)))
                rows.append('%s %d %s' % (rng.choice(names), rng.randrange(0, 10 ** 9), ' '.join(ps)))
        hidden.append(('random%d' % k, lines(rows), []))
    perf = ('perf', lines(['u%d %d v%d v%d' % (i, rng.randrange(10 ** 12), i, (i + 1) % 5000)
                           for i in range(200000)]), [])
    return public, hidden, perf
