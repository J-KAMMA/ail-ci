"""Reference implementation of scar_life (see spec.md): reference.py RULE GENS < grid

The grid is kept as bit planes in Python integers (bit y*W + x), and one generation is computed
with shifts and bitwise adders over the whole grid at once.
"""
import re
import sys

CODES = '0123456789ABC'
RULE = re.compile(r'B([0-9A-C]*)/S([0-9A-C]*)')


def parse_set(s):
    vals = [CODES.index(ch) for ch in s]
    if any(a >= b for a, b in zip(vals, vals[1:])):
        return None
    return vals


def read_grid(data):
    if not data.endswith(b'\n'):
        data += b'\n'
    lines = data.split(b'\n')
    lines.pop()        # the empty piece after the final \n
    if not lines:
        return None
    m = re.fullmatch(rb'([1-9][0-9]{0,3}) ([1-9][0-9]{0,3})', lines[0])
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w > 4096 or h > 4096 or len(lines) != h + 1:
        return None
    rows = lines[1:]
    for row in rows:
        if len(row) != w or row.strip(b'.o'):
            return None
    return w, h, rows


def main(argv):
    if len(argv) != 3:
        return 1
    m = RULE.fullmatch(argv[1])
    if not m or not re.fullmatch(r'[0-9]+', argv[2]) or int(argv[2]) > 100000:
        return 1
    born = parse_set(m.group(1))
    stay = parse_set(m.group(2))
    if born is None or stay is None:
        return 1
    gens = int(argv[2])
    grid = read_grid(sys.stdin.buffer.read())
    if grid is None:
        return 1
    w, h, rows = grid
    n = w * h
    full = (1 << n) - 1
    # bit y*w + x  <->  row y, column x: build from the reversed row strings
    text = b''.join(row[::-1] for row in reversed(rows))
    alive = int(text.translate(bytes.maketrans(b'.o', b'01')), 2) if n else 0
    scar = 0
    row_unit = sum(1 << (y * w) for y in range(h))
    col_first = row_unit
    col_last = row_unit << (w - 1)
    not_first = full ^ col_first
    not_last = full ^ col_last

    def from_right(a):   # value at (x+1, y)
        return ((a >> 1) & not_last) | ((a << (w - 1)) & col_last)

    def from_left(a):    # value at (x-1, y)
        return ((a << 1) & not_first) | ((a >> (w - 1)) & col_first)

    def from_below(a):   # value at (x, y+1)
        return (a >> w) | ((a << (n - w)) & full)

    def from_above(a):   # value at (x, y-1)
        return ((a << w) & full) | (a >> (n - w))

    def count4(a, b, c, d):
        s = a ^ b
        cab = a & b
        t = c ^ d
        ccd = c & d
        cst = s & t
        return s ^ t, cab ^ ccd ^ cst, (cab & ccd) | (cab & cst) | (ccd & cst)

    def member(bits, values):
        nbits = [full ^ b for b in bits]
        acc = 0
        for v in values:
            m = full
            for i in range(4):
                m &= bits[i] if (v >> i) & 1 else nbits[i]
            acc |= m
        return acc

    out = []
    for g in range(1, gens + 1):
        r = from_right(alive)
        l = from_left(alive)
        o0, o1, o2 = count4(r, l, from_below(alive), from_above(alive))
        d0, d1, d2 = count4(from_below(r), from_above(r), from_below(l), from_above(l))
        # weight = 2 * O + D
        w0 = d0
        w1 = o0 ^ d1
        c1 = o0 & d1
        w2 = o1 ^ d2 ^ c1
        c2 = (o1 & d2) | (o1 & c1) | (d2 & c1)
        w3 = o2 ^ c2
        bits = (w0, w1, w2, w3)
        in_s = member(bits, stay)
        in_b = member(bits, born)
        dead = full & ~(alive | scar)
        new_alive = (alive & in_s) | (dead & in_b)
        scar = alive & ~in_s
        alive = new_alive
        out.append('%d %d %d' % (g, alive.bit_count(), scar.bit_count()))
    a_text = format(alive, '0%db' % n)[::-1]
    s_text = format(scar, '0%db' % n)[::-1]
    cells = bytearray(a_text.encode().translate(bytes.maketrans(b'01', b'.o')))
    for i, ch in enumerate(s_text):
        if ch == '1':
            cells[i] = ord('x')
    for y in range(h):
        out.append(cells[y * w:(y + 1) * w].decode())
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
