import sys
import re

INT_RE = re.compile(r'-?[0-9]+$')
MIN = -(1 << 63)
MAX = (1 << 63) - 1


def main():
    data = sys.stdin.read()
    lines = data.split('\n')

    stack = []
    stores = {}
    out = []

    for idx, raw in enumerate(lines, 1):
        line = raw
        if line.endswith('\r'):
            line = line[:-1]
        line = line.strip(' \t')
        if not line or line[0] == '#':
            continue

        tokens = line.split()
        cmd = tokens[0]
        args = tokens[1:]

        err = None

        if cmd == 'push':
            if len(args) != 1:
                err = 'cmd'
            elif not INT_RE.fullmatch(args[0]):
                err = 'int'
            else:
                v = int(args[0])
                if v < MIN or v > MAX:
                    err = 'int'
                else:
                    stack.append(v)

        elif cmd in ('add', 'sub', 'mul'):
            if len(args) != 0:
                err = 'cmd'
            elif len(stack) < 2:
                err = 'stack'
            else:
                b = stack[-1]
                a = stack[-2]
                if cmd == 'add':
                    r = a + b
                elif cmd == 'sub':
                    r = a - b
                else:
                    r = a * b
                if r < MIN or r > MAX:
                    err = 'overflow'
                else:
                    stack.pop()
                    stack.pop()
                    stack.append(r)

        elif cmd == 'dup':
            if len(args) != 0:
                err = 'cmd'
            elif not stack:
                err = 'stack'
            else:
                stack.append(stack[-1])

        elif cmd == 'swap':
            if len(args) != 0:
                err = 'cmd'
            elif len(stack) < 2:
                err = 'stack'
            else:
                stack[-1], stack[-2] = stack[-2], stack[-1]

        elif cmd == 'drop':
            if len(args) != 0:
                err = 'cmd'
            elif not stack:
                err = 'stack'
            else:
                stack.pop()

        elif cmd == 'store':
            if len(args) != 1:
                err = 'cmd'
            elif not stack:
                err = 'stack'
            else:
                stores[args[0]] = stack.pop()

        elif cmd == 'load':
            if len(args) != 1:
                err = 'cmd'
            elif args[0] not in stores:
                err = 'var'
            else:
                stack.append(stores[args[0]])

        elif cmd == 'print':
            if len(args) != 0:
                err = 'cmd'
            elif not stack:
                err = 'stack'
            else:
                out.append('value %d' % stack[-1])

        elif cmd == 'clear':
            if len(args) != 0:
                err = 'cmd'
            else:
                stack.clear()

        else:
            err = 'cmd'

        if err is not None:
            out.append('error %d %s' % (idx, err))

    out.append('stack %d' % len(stack))
    if stack:
        out.append(' '.join(str(v) for v in stack))

    sys.stdout.write('\n'.join(out) + '\n')


main()
