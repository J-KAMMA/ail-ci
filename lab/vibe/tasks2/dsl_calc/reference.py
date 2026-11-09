"""Reference implementation of dsl_calc (see spec.md): reference.py < program"""
import sys

MINI = -(1 << 63)
MAXI = (1 << 63) - 1
BINOPS = {'add': lambda a, b: a + b, 'sub': lambda a, b: a - b, 'mul': lambda a, b: a * b}


def parse_int(s):
    if not s:
        return None
    body = s[1:] if s[0] == '-' else s
    if not body or any(c < '0' or c > '9' for c in body):
        return None
    v = int(s)
    return v if MINI <= v <= MAXI else None


def main():
    text = sys.stdin.buffer.read().decode('utf8')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    stack = []
    stored = {}
    out = []

    def err(no, reason):
        out.append('error %d %s' % (no, reason))

    for no, raw in enumerate(lines, 1):
        line = raw[:-1] if raw.endswith('\r') else raw
        line = line.strip(' \t')
        if not line or line[0] == '#':
            continue
        toks = line.split()
        cmd = toks[0]
        args = toks[1:]
        if cmd == 'push':
            if len(args) != 1:
                err(no, 'cmd')
                continue
            v = parse_int(args[0])
            if v is None:
                err(no, 'int')
                continue
            stack.append(v)
        elif cmd in BINOPS:
            if args or len(stack) < 2:
                err(no, 'cmd' if args else 'stack')
                continue
            b = stack[-1]
            a = stack[-2]
            v = BINOPS[cmd](a, b)
            if v < MINI or v > MAXI:
                err(no, 'overflow')
                continue
            stack.pop()
            stack.pop()
            stack.append(v)
        elif cmd == 'dup':
            if args:
                err(no, 'cmd')
            elif not stack:
                err(no, 'stack')
            else:
                stack.append(stack[-1])
        elif cmd == 'swap':
            if args:
                err(no, 'cmd')
            elif len(stack) < 2:
                err(no, 'stack')
            else:
                stack[-1], stack[-2] = stack[-2], stack[-1]
        elif cmd == 'drop':
            if args:
                err(no, 'cmd')
            elif not stack:
                err(no, 'stack')
            else:
                stack.pop()
        elif cmd == 'store':
            if len(args) != 1:
                err(no, 'cmd')
            elif not stack:
                err(no, 'stack')
            else:
                stored[args[0]] = stack.pop()
        elif cmd == 'load':
            if len(args) != 1:
                err(no, 'cmd')
            elif args[0] not in stored:
                err(no, 'var')
            else:
                stack.append(stored[args[0]])
        elif cmd == 'print':
            if args:
                err(no, 'cmd')
            elif not stack:
                err(no, 'stack')
            else:
                out.append('value %d' % stack[-1])
        elif cmd == 'clear':
            if args:
                err(no, 'cmd')
            else:
                stack = []
        else:
            err(no, 'cmd')
    out.append('stack %d' % len(stack))
    if stack:
        out.append(' '.join(str(v) for v in stack))
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
