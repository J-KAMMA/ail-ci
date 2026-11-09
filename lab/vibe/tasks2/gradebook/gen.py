"""Cases for gradebook (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def txt(s):
    return s.encode('utf8')


def cases(rng):
    public = [
        ('basic', txt("""alice quiz 80
bob quiz 90
alice exam 100
bob exam 70
carol quiz 85
"""), []),
        ('ties', txt("""z homework 50
a homework 50
m homework 50
b quiz 100
b exam 0
"""), []),
        ('bad', txt("""alice quiz 80
alice quiz
alice quiz x
alice quiz -1
alice quiz 1000000000001
a b 1 2
onlyone
"""), []),
        ('unicode', txt("""josé exam 90
日本 exam 80
josé quiz 70
"""), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_lines', b'\n \t\n', []),
        ('floor', txt("""a x 1
a y 2
b x 3
"""), []),
        ('big_sums', txt("""a x 1000000000000
a y 1000000000000
a z 1000000000000
b x 1
"""), []),
        ('duplicate_rows', txt("a x 5\na x 5\na x 5\n"), []),
        ('leading_zeros', b'a x 0007\nb y 0010\n', []),
        ('crlf', b'a x 5\r\nb y 6\r\n', []),
        ('no_final_newline', b'a x 1\nb y 2', []),
        ('unicode_tie', 'é x 10\nz x 10\n'.encode('utf8'), []),
    ]
    names = ['s%02d' % i for i in range(15)]
    assigns = ['hw', 'quiz', 'exam', 'proj']
    for k in range(4):
        rows = []
        for _ in range(rng.randrange(20, 500)):
            r = rng.random()
            if r < 0.08:
                rows.append('bad line here extra')
            else:
                rows.append('%s %s %d' % (rng.choice(names), rng.choice(assigns), rng.randrange(0, 10 ** 12 + 1)))
        hidden.append(('random%d' % k, txt('\n'.join(rows) + '\n'), []))
    perf = ('perf', txt('\n'.join('%s %s %d' % (names[i % len(names)], assigns[i % 4], i % 1000)
                                  for i in range(200000)) + '\n'), [])
    return public, hidden, perf
