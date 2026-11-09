import sys

MIN_I64 = -(2 ** 63)
MAX_I64 = 2 ** 63 - 1


def parse_int(tok):
    s = tok
    if s.startswith('-'):
        s = s[1:]
    if not s:
        return None
    for ch in s:
        if ch < '0' or ch > '9':
            return None
    v = int(tok)
    if v < MIN_I64 or v > MAX_I64:
        return None
    return v


def main():
    data = sys.stdin.read()
    stack = []
    stores = {}
    out = []

    for lineno, raw in enumerate(data.split('\n'), 1):
        if raw.endswith('\r'):
            raw = raw[:-1]
        line = raw.strip(' \t')
        if not line or line[0] == '#':
            continue

        parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        args = parts[1:]

        error = None

        if cmd == 'push':
            if len(args) != 1:
                error = 'cmd'
            else:
                v = parse_int(args[0])
                if v is None:
                    error = 'int'
                else:
                    stack.append(v)

        elif cmd in ('add', 'sub', 'mul'):
            if args:
                error = 'cmd'
            elif len(stack) < 2:
                error = 'stack'
            else:
                a = stack[-2]
                b = stack[-1]
                if cmd == 'add':
                    r = a + b
                elif cmd == 'sub':
                    r = a - b
                else:
                    r = a * b
                if r < MIN_I64 or r > MAX_I64:
                    error = 'overflow'
                else:
                    stack.pop()
                    stack.pop()
                    stack.append(r)

        elif cmd == 'dup':
            if args:
                error = 'cmd'
            elif not stack:
                error = 'stack'
            else:
                stack.append(stack[-1])

        elif cmd == 'swap':
            if args:
                error = 'cmd'
            elif len(stack) < 2:
                error = 'stack'
            else:
                stack[-1], stack[-2] = stack[-2], stack[-1]

        elif cmd == 'drop':
            if args:
                error = 'cmd'
            elif not stack:
                error = 'stack'
            else:
                stack.pop()

        elif cmd == 'store':
            if len(args) != 1:
                error = 'cmd'
            elif not stack:
                error = 'stack'
            else:
                stores[args[0]] = stack.pop()

        elif cmd == 'load':
            if len(args) != 1:
                error = 'cmd'
            elif args[0] not in stores:
                error = 'var'
            else:
                stack.append(stores[args[0]])

        elif cmd == 'print':
            if args:
                error = 'cmd'
            elif not stack:
                error = 'stack'
            else:
                out.append('value ' + str(stack[-1]))

        elif cmd == 'clear':
            if args:
                error = 'cmd'
            else:
                stack.clear()

        else:
            error = 'cmd'

        if error is not None:
            out.append('error %d %s' % (lineno, error))

    out.append('stack %d' % len(stack))
    if stack:
        out.append(' '.join(str(v) for v in stack))

    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
