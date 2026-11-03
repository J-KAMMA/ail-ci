"""Cases for log_scan (see spec.md). cases(rng) -> (public, hidden, perf)."""

A = []
STDIN = True
STATUSES = ['DEBUG', 'INFO', 'WARN', 'ERROR']


def line(hour, status, message='ok'):
    text = '2024-05-01 %02d:00:00 %s' % (hour, status)
    if message is not None:
        text += ' ' + message
    return text + '\n'


def cases(rng):
    public = [
        ('basic', (line(9, 'INFO') + line(10, 'WARN') + line(9, 'INFO')).encode(), A),
        ('empty', b'', A),
        ('no_final_newline', b'2024-05-01 09:15:00 WARN disk\n2024-05-01 23:59:59 ERROR boom', A),
    ]
    hidden = [
        ('status_sort', (line(1, 'WARN') + line(2, 'INFO') + line(3, 'ERROR') + line(4, 'DEBUG')).encode(), A),
        ('hours_sort', (line(23, 'INFO') + line(0, 'INFO') + line(12, 'INFO') + line(3, 'INFO')).encode(), A),
        ('all_hours', (''.join(line(h, 'INFO') for h in range(24))).encode(), A),
        ('same_status', (''.join(line(i % 24, 'ERROR') for i in range(100))).encode(), A),
        ('messages_with_spaces', (line(5, 'INFO', 'user 42 did a thing [1, 2]') + line(6, 'WARN', '')).encode(), A),
        ('no_message', (line(7, 'DEBUG', None) + line(8, 'INFO', None)).encode(), A),
        ('one_line', line(0, 'DEBUG').encode(), A),
        ('leading_zero_hour', line(1, 'WARN').encode(), A),
        ('all_statuses', (''.join(line(i, s) for i, s in enumerate(STATUSES))).encode(), A),
    ]
    parts = []
    for i in range(500000):
        parts.append(line(rng.randrange(24), rng.choice(STATUSES), 'request %d done' % (i % 1000)))
    perf = ('perf', ''.join(parts).encode(), A)
    return public, hidden, perf
