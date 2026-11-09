"""Reference implementation of log_levels (see spec.md): reference.py < logs"""
import sys

LEVELS = ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL')


def main():
    text = sys.stdin.buffer.read().decode('utf8')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    good = 0
    bad = 0
    stats = {lv: [0, 0, 0] for lv in LEVELS}
    for raw in lines:
        line = raw[:-1] if raw.endswith('\r') else raw
        if line == '':
            continue
        if not line.startswith('['):
            bad += 1
            continue
        end = line.find(']')
        if end < 0:
            bad += 1
            continue
        level = line[1:end]
        rest = line[end + 1:]
        if level not in stats or (rest and rest[0] != ' '):
            bad += 1
            continue
        msg = rest[1:] if rest else ''
        good += 1
        s = stats[level]
        s[0] += 1
        s[1] += len(msg)
        if len(msg) > s[2]:
            s[2] = len(msg)
    out = ['lines %d bad %d' % (good, bad)]
    for lv in LEVELS:
        c, chars, longest = stats[lv]
        out.append('level %s count %d chars %d longest %d' % (lv, c, chars, longest))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
