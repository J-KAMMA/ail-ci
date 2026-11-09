"""Cases for log_levels (see spec.md). cases(rng) -> (public, hidden, perf)."""

STDIN = True


def txt(s):
    return s.encode('utf8')


def cases(rng):
    public = [
        ('basic', txt("""[INFO] server started
[ERROR] disk full
[DEBUG] x=1
[INFO] request ok
[WARN] slow
"""), []),
        ('bad', txt("""[INFO] ok
[info] lowercase
[INFO missing bracket
[UNKNOWN] level
[INFO]no space
just text
[] empty level
[ERROR] 
"""), []),
        ('brackets', txt("""[ERROR] a ] b [ c
[WARN]
[INFO]   
"""), []),
        ('unicode', '[INFO] café 日本語\n[INFO] 😀😀\n'.encode('utf8'), []),
    ]
    hidden = [
        ('empty', b'', []),
        ('blank_lines', b'\n\n\r\n', []),
        ('crlf', b'[INFO] hi\r\n[ERROR] bad\r\n', []),
        ('empty_message', b'[FATAL] \n[FATAL]\n', []),
        ('long_line', b'[DEBUG] ' + b'x' * 100000 + b'\n', []),
        ('all_levels', b''.join(b'[%s] m\n' % lv for lv in
                                (b'TRACE', b'DEBUG', b'INFO', b'WARN', b'ERROR', b'FATAL')), []),
        ('no_final_newline', b'[INFO] a', []),
        ('many_spaces', b'[INFO]  two leading spaces\n', []),
    ]
    levels = ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
    for k in range(4):
        rows = []
        for _ in range(rng.randrange(20, 400)):
            r = rng.random()
            if r < 0.1:
                rows.append(rng.choice(['not a log', '[BAD] x', '[INFO]x', '[] x']))
            else:
                rows.append('[%s] message %d' % (rng.choice(levels), rng.randrange(10000)))
        hidden.append(('random%d' % k, txt('\n'.join(rows) + '\n'), []))
    perf = ('perf', txt('\n'.join('[%s] message %d' % (levels[i % 6], i) for i in range(200000)) + '\n'), [])
    return public, hidden, perf
