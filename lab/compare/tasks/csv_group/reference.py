"""Reference implementation of csv_group (see spec.md): reference.py reads standard input."""
import sys


def main():
    totals = {}
    for line in sys.stdin.read().split('\n'):
        if not line:
            continue
        key, value = line.split(',', 1)
        totals[key] = totals.get(key, 0) + int(value)
    parts = []
    for key in sorted(totals):
        parts.append('%s,%d\n' % (key, totals[key]))
    sys.stdout.write(''.join(parts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
