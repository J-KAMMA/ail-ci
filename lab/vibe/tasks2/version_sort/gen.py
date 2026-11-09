"""Cases for version_sort (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def txt(s):
    return s.encode('utf8')


def cases(rng):
    public = [
        ('basic', txt("""1.10.0
1.2.0
1.2.0-alpha
1.2.0-alpha.1
1.2.0-alpha.beta
1.2.0-beta
2.0.0
"""), []),
        ('builds', txt("""1.0.0+build.9
1.0.0+build.1
1.0.0
1.0.0-rc.1+meta
1.0.0-rc.1
"""), []),
        ('invalid', txt("""1.0
1.0.0.0
1.0.0-
1.0.0-á
v1.0.0
1.0.0+ok

1.2.3
"""), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_lines', b'\n\n\r\n', []),
        ('numeric_vs_alpha', txt("""1.0.0-1
1.0.0-a
1.0.0-2
1.0.0-10
1.0.0-a.1
"""), []),
        ('prefix_fewer', txt("""1.0.0-alpha
1.0.0-alpha.1
1.0.0-alpha.beta
"""), []),
        ('leading_zeros', txt("01.002.0003\n1.2.3\n1.2.3-00\n1.2.3-0\n"), []),
        ('int64_edges', txt("9223372036854775807.0.0\n9223372036854775808.0.0\n"
                            "1.0.0-9223372036854775807\n1.0.0-9223372036854775808\n"), []),
        ('equal_precedence_tie', txt("1.0.0+b\na1.0.0\na1.0.0\n1.0.0+a\n"), []),
        ('crlf', b'1.2.0\r\n1.1.0\r\n', []),
        ('no_final_newline', b'2.0.0\n1.0.0', []),
    ]
    for k in range(4):
        rows = []
        for _ in range(rng.randrange(20, 300)):
            r = rng.random()
            if r < 0.1:
                rows.append('not-a-version')
            else:
                base = '%d.%d.%d' % (rng.randrange(4), rng.randrange(5), rng.randrange(6))
                if rng.random() < 0.4:
                    base += '-' + rng.choice(['alpha', 'beta', 'rc.1', '0', '1', 'alpha.2', 'x-y'])
                if rng.random() < 0.2:
                    base += '+' + rng.choice(['b1', 'build.2', 'zz'])
                rows.append(base)
        hidden.append(('random%d' % k, txt('\n'.join(rows) + '\n'), []))
    perf = ('perf', txt('\n'.join('%d.%d.%d' % (rng.randrange(1000), rng.randrange(1000), rng.randrange(1000))
                                  for _ in range(200000)) + '\n'), [])
    return public, hidden, perf
