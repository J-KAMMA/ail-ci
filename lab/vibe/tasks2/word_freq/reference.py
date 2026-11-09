"""Reference implementation of word_freq (see spec.md): reference.py < text"""
import re
import sys

WORD = re.compile(rb'[A-Za-z]+')


def main():
    data = sys.stdin.buffer.read()
    counts = {}
    total = 0
    for m in WORD.finditer(data):
        w = m.group(0).lower()
        counts[w] = counts.get(w, 0) + 1
        total += 1
    out = ['words %d unique %d' % (total, len(counts))]
    order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for w, c in order[:20]:
        out.append('%s %d' % (w.decode('ascii'), c))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
