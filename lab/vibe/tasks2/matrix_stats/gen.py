"""Cases for matrix_stats (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def mat(rows):
    if not rows:
        return b'0 0\n'
    r = len(rows)
    c = len(rows[0])
    return ('%d %d\n' % (r, c) + ''.join(' '.join(str(x) for x in row) + '\n' for row in rows)).encode('utf8')


def cases(rng):
    public = [
        ('basic', mat([[1, 2, 3], [4, 5, 6]]), []),
        ('negative', mat([[-1, -2], [3, 4], [0, -5]]), []),
        ('single', mat([[42]]), []),
        ('max_tie', mat([[1, 9, 2], [9, 0, 3]]), []),
    ]
    hidden = [
        ('empty_input', b'', []),
        ('zero_by_zero', b'0 0\n', []),
        ('zero_cols', b'3 0\n\n\n\n', []),
        ('zero_rows', b'0 5\n', []),
        ('int64_edges', mat([[9223372036854775807], [-9223372036854775808]]), []),
        ('int64_row_sum', b'1 2\n9223372036854775807 -1\n', []),
        ('bad_header', b'2\n1 2\n', []),
        ('too_many_rows', b'2 2\n1 2\n3 4\n5 6\n', []),
        ('too_few_cols', b'2 2\n1 2\n3\n', []),
        ('bad_number', b'1 2\n1 x\n', []),
        ('overflow_value', b'1 1\n9223372036854775808\n', []),
        ('crlf', b'2 2\r\n1 2\r\n3 4\r\n', []),
        ('no_final_newline', b'1 3\n7 8 9', []),
        ('tabs', b'2 2\n1\t2\n3\t4\n', []),
    ]
    for k in range(4):
        r = rng.randrange(0, 40)
        c = rng.randrange(0, 40)
        rows = [[rng.randrange(-10 ** 12, 10 ** 12) for _ in range(c)] for _ in range(r)]
        data = ('%d %d\n' % (r, c) + ''.join(' '.join(str(x) for x in row) + '\n' for row in rows)).encode()
        hidden.append(('random%d' % k, data, []))
    r, c = 500, 200
    rows = [[rng.randrange(-10 ** 6, 10 ** 6) for _ in range(c)] for _ in range(r)]
    perf = ('perf', mat(rows), [])
    return public, hidden, perf
