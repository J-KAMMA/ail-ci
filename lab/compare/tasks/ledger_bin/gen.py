"""Cases for ledger_bin (see spec.md). cases(rng) -> (public, hidden, perf)."""
from operator import mul

A = ['{input}']


def var(v):
    out = bytearray()
    while True:
        b = v & 0x7f
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def check(body):
    n = len(body)
    pw = POWERS.get(n)
    if pw is None:
        pw = POWERS[n] = [pow(31, n - 1 - i, 251) for i in range(n)]
    return sum(map(mul, body, pw)) % 251      # same as c = (c * 31 + b) % 251 byte by byte


POWERS = {}


def rec(body, bad_check=False):
    c = check(body)
    if bad_check:
        c = (c + 1) % 256
    return bytes(body) + bytes([c])


def OPEN(i, name, init):
    name = name.encode() if isinstance(name, str) else name
    return rec(b'\x01' + var(i) + bytes([len(name)]) + name + var(init))


def MOVE(a, b, amt):
    return rec(b'\x02' + var(a) + var(b) + var(amt))


def SHUT(i):
    return rec(b'\x03' + var(i))


def MINT(i, amt):
    return rec(b'\x04' + var(i) + var(amt))


def NOTE(content):
    return rec(b'\x05' + var(len(content)) + content)


def header(strict=False):
    return b'\xc7LXF\x02' + (b'\x01' if strict else b'\x00')


def file(*records, strict=False):
    return header(strict) + b''.join(records)


NAMES = ['alice', 'bob', 'Carol', 'd.e-f', 'x', 'ZZ_top', '~!@#', 'n0', 'q' * 32, 'acct-%']


def random_ledger(rng, nrec, nacc, strict=False, maxamt=1000):
    ids = [rng.choice([rng.randrange(0, 200), rng.randrange(0, 1 << 32), rng.randrange(0, 1 << 14)]) for _ in range(nacc)]
    out = [header(strict)]
    for _ in range(nrec):
        r = rng.random()
        if r < 0.15:
            out.append(OPEN(rng.choice(ids), rng.choice(NAMES), rng.randrange(0, maxamt)))
        elif r < 0.75:
            out.append(MOVE(rng.choice(ids), rng.choice(ids), rng.randrange(0, maxamt // 2)))
        elif r < 0.8:
            out.append(SHUT(rng.choice(ids)))
        elif r < 0.95:
            out.append(MINT(rng.choice(ids), rng.randrange(0, maxamt)))
        else:
            out.append(NOTE(bytes(rng.randrange(256) for _ in range(rng.randrange(0, 20)))))
    return b''.join(out)


def cases(rng):
    basic = file(OPEN(1, 'alice', 100), OPEN(2, 'bob', 5), MOVE(1, 2, 30), MOVE(2, 1, 500), OPEN(1, 'again', 1),
                 MINT(3, 9), NOTE(b'hello'), SHUT(2), MOVE(1, 2, 1), MINT(1, 7), OPEN(300, 'carol', 77))
    public = [
        ('basic', basic, A),
        ('bad_check', file(OPEN(1, 'alice', 100), MOVE(1, 1, 0)[:-1] + b'\x00', MINT(1, 5)), A),
        ('strict_reject', file(OPEN(7, 'g', 10), MOVE(7, 8, 1), MINT(7, 1), strict=True), A),
    ]
    big = 4294967295
    hidden = [
        ('header_only', header(), A),
        ('header_only_strict', header(True), A),
        ('empty_file', b'', A),
        ('short_header', b'\xc7LXF\x02', A),
        ('bad_magic', b'\xc7LXG\x02\x00', A),
        ('bad_version', b'\xc7LXF\x01\x00', A),
        ('bad_flags', b'\xc7LXF\x02\x02' + OPEN(1, 'a', 1), A),
        ('bad_opcode_0', file(OPEN(1, 'a', 1), b'\x00\x00'), A),
        ('bad_opcode_6', file(OPEN(1, 'a', 1), MINT(1, 2), rec(b'\x06\x01')), A),
        ('varint_padding', file(OPEN(1, 'a', 1), rec(b'\x04\x01\x80\x00')), A),
        ('varint_zero_padding_id', file(rec(b'\x03\x80\x80\x00')), A),
        ('varint_5_bytes_max', file(rec(b'\x01\xff\xff\xff\xff\x0f\x01m\xff\xff\xff\xff\x0f'), MINT(big, 0)), A),
        ('varint_too_big', file(OPEN(1, 'a', 1), rec(b'\x04\x01\xff\xff\xff\xff\x10')), A),
        ('varint_6_bytes', file(OPEN(1, 'a', 1), rec(b'\x04\x01\x80\x80\x80\x80\x80\x01')), A),
        ('varint_long_valid_value', file(OPEN(268435456, 'big', 1), rec(b'\x04\x80\x80\x80\x80\x01\x05')), A),
        ('truncated_in_varint', file(OPEN(1, 'a', 1), b'\x04\x01\x80'), A),
        ('truncated_before_check', file(OPEN(1, 'a', 1), b'\x04\x01\x05'), A),
        ('truncated_name_len', file(b'\x01\x05'), A),
        ('truncated_in_name', file(b'\x01\x05\x04ab'), A),
        ('name_len_zero', file(OPEN(1, 'a', 1), rec(b'\x01\x02\x00\x05')), A),
        ('name_len_33', file(rec(b'\x01\x02\x21' + b'a' * 33 + b'\x05')), A),
        ('name_len_32', file(OPEN(2, 'b' * 32, 3)), A),
        ('name_with_space', file(rec(b'\x01\x02\x03a ba\x05')), A),
        ('name_bad_byte_before_truncation', file(b'\x01\x02\x05a\x7f'), A),
        ('name_del_byte', file(rec(b'\x01\x02\x02a\x7f\x05')), A),
        ('note_truncated', file(OPEN(1, 'a', 1), b'\x05\x0aabc'), A),
        ('note_empty_and_binary', file(NOTE(b''), NOTE(bytes(range(256))), OPEN(4, 'n', 4)), A),
        ('check_wrong', file(OPEN(1, 'a', 1), rec(b'\x03\x01', bad_check=True), MINT(9, 9)), A),
        ('structural_after_strict_reject', file(MOVE(1, 2, 3), OPEN(1, 'a', 1), rec(b'\x09'), strict=True), A),
        ('strict_no_rejection', file(OPEN(1, 'a', 10), OPEN(2, 'b', 0), MOVE(1, 2, 10), MINT(2, 5), SHUT(1), strict=True), A),
        ('strict_funds', file(OPEN(1, 'a', 10), OPEN(2, 'b', 0), MOVE(1, 2, 10), MOVE(1, 2, 1), strict=True), A),
        ('strict_self', file(OPEN(1, 'a', 10), MOVE(1, 1, 0), strict=True), A),
        ('strict_dup_of_shut', file(OPEN(1, 'a', 10), SHUT(1), OPEN(1, 'b', 1), strict=True), A),
        ('reject_order', file(OPEN(1, 'a', 10), OPEN(2, 'b', 10), SHUT(2),
                              MOVE(3, 2, 99), MOVE(2, 3, 0), MOVE(2, 1, 1), MOVE(1, 2, 1), MOVE(2, 2, 0),
                              MOVE(1, 1, 99), MOVE(1, 1, 0), MOVE(4, 4, 0), SHUT(2), SHUT(5), MINT(2, 1), MINT(6, 1),
                              OPEN(2, 'c', 0)), A),
        ('move_exact_balance', file(OPEN(1, 'a', 10), OPEN(2, 'b', 0), MOVE(1, 2, 10), MOVE(1, 2, 0), MOVE(1, 2, 1)), A),
        ('shut_keeps_balance', file(OPEN(1, 'a', 50), OPEN(2, 'b', 60), SHUT(2), MINT(1, 1)), A),
        ('top_ties', file(*[OPEN(i, 'p%d' % i, 100 if i % 2 else 50) for i in (9, 3, 7, 1, 5, 11, 2, 4)]), A),
        ('top_excludes_shut', file(OPEN(1, 'a', 9), OPEN(2, 'b', 8), OPEN(3, 'c', 7), OPEN(4, 'd', 6), OPEN(5, 'e', 5),
                                   OPEN(6, 'f', 4), OPEN(7, 'g', 3), SHUT(1), SHUT(4)), A),
        ('all_shut', file(OPEN(1, 'a', 9), SHUT(1)), A),
        ('extreme_ids_amounts', file(OPEN(0, 'zero', big), OPEN(big, 'max', big), MINT(0, big), MINT(big, big), MINT(0, big),
                                     MOVE(0, big, big), OPEN(2147483648, 'mid', 0)), A),
        ('reject_only', file(MOVE(1, 2, 3), SHUT(4), MINT(5, 6)), A),
    ]
    for k in range(6):
        strict = k == 5
        hidden.append(('random%d' % k, random_ledger(rng, rng.randrange(20, 400), rng.randrange(3, 30), strict), A))
    for k in range(4):
        data = bytearray(random_ledger(rng, rng.randrange(20, 200), rng.randrange(3, 30)))
        i = rng.randrange(6, len(data))
        data[i] ^= 1 << rng.randrange(8)
        hidden.append(('corrupt%d' % k, bytes(data), A))
    hidden.append(('cut_short', random_ledger(rng, 100, 10)[:-3], A))
    perf = ('perf', perf_ledger(rng), A)
    return public, hidden, perf


def perf_ledger(rng, nacc=300000, nrec=4000000):
    ids = rng.sample(range(1 << 32), nacc)
    out = [header()]
    names = [('u%x' % rng.getrandbits(40)).encode() for _ in range(1000)]
    for i in ids:
        out.append(OPEN(i, rng.choice(names), rng.randrange(0, 1 << 20)))
    rand = rng.random
    choice = rng.choice
    randrange = rng.randrange
    for _ in range(nrec - nacc):
        r = rand()
        if r < 0.85:
            out.append(MOVE(choice(ids), choice(ids), randrange(0, 1 << 19)))
        elif r < 0.95:
            out.append(MINT(choice(ids), randrange(0, 1 << 16)))
        elif r < 0.955:
            out.append(SHUT(choice(ids)))
        elif r < 0.975:
            out.append(OPEN(randrange(0, 1 << 32), b'late', randrange(0, 100)))
        else:
            out.append(NOTE(b'memo %d' % randrange(0, 100000)))
    return b''.join(out)
