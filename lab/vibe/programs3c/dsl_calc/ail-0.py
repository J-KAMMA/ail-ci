import sys
import re

MAX = 9223372036854775807
MIN = -9223372036854775807 - 1
MAXS = '9223372036854775807'
MINS = '9223372036854775808'


def parse_int(tok):
    m = re.fullmatch(r'(-?)([0-9]+)', tok)
    if m is None:
        return None
    neg = m.group(1) == '-'
    digits = m.group(2).lstrip('0') or '0'
    if len(digits) > 19:
        return None
    if len(digits) == 19:
        if neg:
            if digits > MINS:
                return None
            if digits == MINS:
                return MIN
        else:
            if digits > MAXS:
                return None
    v = int(digits)
    return -v if neg else v


def add_ok(a, b):
    if a >= 0 and b >= 0:
        return a <= MAX - b
    if a < 0 and b < 0:
        return b >= MIN - a
    return True


def sub_ok(a, b):
    if b >= 0:
        return a >= MIN + b
    return a <= MAX + b


def mul_ok(a, b):
    if a == 0 or b == 0:
        return True
    if a == MIN or b == MIN:
        other = b if a == MIN else a
        return other == 1
    ua = a if a > 0 else -a
    ub = b if b > 0 else -b
    neg = (a < 0) != (b < 0)
    q = MAX // ub
    if not neg:
        return ua <= q
    r = MAX % ub
    lim = q + (1 if r + 1 == ub else 0)
    return ua <= lim


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    lines = data.split('\n')
    out = []
    stack = []
    store = {}

    for idx, raw in enumerate(lines):
        lineno = idx + 1
        if raw.endswith('\r'):
            raw = raw[:-1]
        s = raw.strip(' \t')
        if s == '' or s[0] == '#':
            continue
        toks = re.split(r'[ \t]+', s)
        cmd = toks[0]
        args = toks[1:]

        def err(reason):
            out.append('error %d %s\n' % (lineno, reason))

        if cmd == 'push':
            if len(args) != 1:
                err('cmd')
                continue
            v = parse_int(args[0])
            if v is None:
                err('int')
                continue
            stack.append(v)

        elif cmd in ('add', 'sub', 'mul'):
            if args:
                err('cmd')
                continue
            if len(stack) < 2:
                err('stack')
                continue
            a = stack[-2]
            b = stack[-1]
            if cmd == 'add':
                ok = add_ok(a, b)
            elif cmd == 'sub':
                ok = sub_ok(a, b)
            else:
                ok = mul_ok(a, b)
            if not ok:
                err('overflow')
                continue
            if cmd == 'add':
                res = a + b
            elif cmd == 'sub':
                res = a - b
            else:
                res = a * b
            stack.pop()
            stack.pop()
            stack.append(res)

        elif cmd == 'dup':
            if args:
                err('cmd')
                continue
            if len(stack) < 1:
                err('stack')
                continue
            stack.append(stack[-1])

        elif cmd == 'swap':
            if args:
                err('cmd')
                continue
            if len(stack) < 2:
                err('stack')
                continue
            stack[-1], stack[-2] = stack[-2], stack[-1]

        elif cmd == 'drop':
            if args:
                err('cmd')
                continue
            if len(stack) < 1:
                err('stack')
                continue
            stack.pop()

        elif cmd == 'store':
            if len(args) != 1:
                err('cmd')
                continue
            if len(stack) < 1:
                err('stack')
                continue
            store[args[0]] = stack.pop()

        elif cmd == 'load':
            if len(args) != 1:
                err('cmd')
                continue
            if args[0] not in store:
                err('var')
                continue
            stack.append(store[args[0]])

        elif cmd == 'print':
            if args:
                err('cmd')
                continue
            if len(stack) < 1:
                err('stack')
                continue
            out.append('value %d\n' % stack[-1])

        elif cmd == 'clear':
            if args:
                err('cmd')
                continue
            stack.clear()

        else:
            err('cmd')

    out.append('stack %d\n' % len(stack))
    if stack:
        out.append(' '.join(str(v) for v in stack) + '\n')
    sys.stdout.write(''.join(out))
    sys.exit(0)


main()
