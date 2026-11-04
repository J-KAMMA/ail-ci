"""Cases for tsv_join (see spec.md). cases(rng) -> (public, hidden, perf). TSV on standard input."""

STDIN = True

USERS = b'#users\n'
ORDERS = b'#orders\n'

NAME_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ._-'


def user(uid, name, cc):
    return ('%s\t%s\t%s\n' % (uid, name, cc)).encode()


def order(oid, uid, amt):
    return ('%s\t%s\t%s\n' % (oid, uid, amt)).encode()


def public_cases():
    basic = (USERS
             + user(1, 'alice', 'US')
             + user(2, 'bob', 'GB')
             + user(3, 'carol', 'US')
             + user(4, 'dave', 'DE')
             + user(5, 'eve smith', 'US')
             + ORDERS
             + order(100, 1, 1000)
             + order(101, 1, 500)
             + order(102, 2, 1500)
             + order(103, 4, 0)
             + order(104, 99, 700))
    ties_bad = (USERS
                + user(1, 'alice', 'US')
                + user(1, 'bob', 'GB')
                + user(2, 'carol', 'GB')
                + user(3, 'dave', 'US')
                + user(0, 'zero', 'US')
                + b'4\tbad!name\tUS\n'
                + ('5\t' + 'x' * 25 + '\tUS\n').encode()
                + b'+6\tplus\tUS\n'
                + user(7, 'ok', 'usa')
                + b'8\teight\tU\n'
                + b'9\tnine\tUS\textra\n'
                + user(10, 'ten', 'US')
                + ORDERS
                + order(100, 1, 100)
                + order(101, 1, 50)
                + order(102, 2, 150)
                + order(103, 3, 150)
                + order(104, 999, 1000)
                + b'105\t1\t\n'
                + b'106\t1\t-5\n'
                + order(107, 1, 100000001)
                + b'108\t\t100\n'
                + b'109\t2\t100\textra\n'
                + b'110\t2\t0000000100\n')
    no_sections = b'hello\n1\t2\t3\n#orders\n100\t1\t5\n'
    return [
        ('basic', basic, []),
        ('ties_bad', ties_bad, []),
        ('no_sections', no_sections, []),
    ]


def no_final_newline():
    return (USERS
            + user(1, 'alice', 'US')
            + user(2, 'bob', 'GB')
            + ORDERS
            + order(100, 1, 100)
            + b'101\t2\t200')


def leading_zeros():
    return (USERS
            + user('0001', 'alice', 'US')
            + user('0002', 'bob', 'GB')
            + ORDERS
            + order('0000000100', '0001', '0000000100')
            + order(101, 2, 50))


def long_names():
    n24 = 'Name-. _' + 'a' * 15
    return (USERS
            + user(1, n24, 'US')
            + user(2, 'a' * 25, 'US')
            + user(3, '', 'US')
            + user(4, 'ok', 'US')
            + ORDERS
            + order(100, 1, 10)
            + order(101, 2, 20)
            + order(102, 3, 30)
            + order(103, 4, 40))


def empty_orders():
    return (USERS
            + user(1, 'alice', 'US')
            + user(2, 'bob', 'GB')
            + ORDERS)


def random_case(rng, nusers, norders):
    countries = ['%c%c' % (65 + i // 26, 65 + i % 26) for i in range(26)]
    ids = []
    seen = set()
    while len(ids) < nusers:
        uid = rng.randrange(1, 2000000001)
        if uid in seen:
            continue
        seen.add(uid)
        ids.append(uid)
    buf = bytearray(USERS)
    for uid in ids:
        n = rng.randrange(1, 25)
        name = ''.join(NAME_CHARS[rng.randrange(len(NAME_CHARS))] for _ in range(n))
        buf += user(uid, name, countries[rng.randrange(len(countries))])
    buf += ORDERS
    for _ in range(norders):
        r = rng.randrange(100)
        if r < 6:
            bad = rng.randrange(7)
            if bad == 0:
                buf += b'1\t2\n'
            elif bad == 1:
                buf += b'\t2\t3\n'
            elif bad == 2:
                buf += b'0\t1\t5\n'
            elif bad == 3:
                buf += b'1\t1\t100000001\n'
            elif bad == 4:
                buf += b'1\t1\t-1\n'
            elif bad == 5:
                buf += b'1\tx\t5\n'
            else:
                buf += b'1\t1\t5\t6\n'
            continue
        if r < 12:
            uid = 1999999999 - rng.randrange(0, 300)
            if uid in seen:
                uid = ids[rng.randrange(len(ids))]
        else:
            uid = ids[rng.randrange(len(ids))]
        buf += order(rng.randrange(1, 2000000001), uid, rng.randrange(0, 100000001))
    return bytes(buf)


def perf_case(rng):
    ncountries = 60
    countries = ['%c%c' % (65 + i // 26, 65 + i % 26) for i in range(ncountries)]
    buf = bytearray(USERS)
    for uid in range(1, 300001):
        n = rng.randrange(1, 25)
        name = ''.join(NAME_CHARS[rng.randrange(len(NAME_CHARS))] for _ in range(n))
        buf += user(uid, name, countries[rng.randrange(ncountries)])
    buf += ORDERS
    for i in range(4000000):
        uid = rng.randrange(1, 300001)
        buf += order(i + 1, uid, rng.randrange(0, 100000001))
    return bytes(buf)


def cases(rng):
    public = public_cases()
    hidden = [
        ('empty', b'', []),
        ('no_final_newline', no_final_newline(), []),
        ('leading_zeros', leading_zeros(), []),
        ('long_names', long_names(), []),
        ('empty_orders', empty_orders(), []),
        ('random_mixed', random_case(rng, 300, 4000), []),
    ]
    perf = ('perf', perf_case(rng), [])
    return public, hidden, perf
