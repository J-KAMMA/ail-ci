import re
import sys

INT_RE = re.compile(r'-?[0-9]+')
LO = -(1 << 63)
HI = (1 << 63) - 1


def parse_int(s):
    if not INT_RE.fullmatch(s):
        return None
    digits = s.lstrip('-').lstrip('0')
    if len(digits) > 19:
        return None
    v = int(s)
    if v < LO or v > HI:
        return None
    return v


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    lines = data.split('\n')
    stack = []
    variables = {}
    out = []

    for idx, raw in enumerate(lines, 1):
        line = raw.rstrip('\r').strip(' \t')
        if line == '' or line[0] == '#':
            continue
        toks = line.split()
        cmd = toks[0]
        args = toks[1:]

        if cmd == 'push':
            if len(args) != 1:
                out.append(f"error {idx} cmd")
            else:
                v = parse_int(args[0])
                if v is None:
                    out.append(f"error {idx} int")
                else:
                    stack.append(v)

        elif cmd in ('add', 'sub', 'mul'):
            if args:
                out.append(f"error {idx} cmd")
            elif len(stack) < 2:
                out.append(f"error {idx} stack")
            else:
                a = stack[-2]
                b = stack[-1]
                if cmd == 'add':
                    r = a + b
                elif cmd == 'sub':
                    r = a - b
                else:
                    r = a * b
                if r < LO or r > HI:
                    out.append(f"error {idx} overflow")
                else:
                    stack[-2:] = [r]

        elif cmd == 'dup':
            if args:
                out.append(f"error {idx} cmd")
            elif not stack:
                out.append(f"error {idx} stack")
            else:
                stack.append(stack[-1])

        elif cmd == 'swap':
            if args:
                out.append(f"error {idx} cmd")
            elif len(stack) < 2:
                out.append(f"error {idx} stack")
            else:
                stack[-1], stack[-2] = stack[-2], stack[-1]

        elif cmd == 'drop':
            if args:
                out.append(f"error {idx} cmd")
            elif not stack:
                out.append(f"error {idx} stack")
            else:
                stack.pop()

        elif cmd == 'store':
            if len(args) != 1:
                out.append(f"error {idx} cmd")
            elif not stack:
                out.append(f"error {idx} stack")
            else:
                variables[args[0]] = stack.pop()

        elif cmd == 'load':
            if len(args) != 1:
                out.append(f"error {idx} cmd")
            elif args[0] not in variables:
                out.append(f"error {idx} var")
            else:
                stack.append(variables[args[0]])

        elif cmd == 'print':
            if args:
                out.append(f"error {idx} cmd")
            elif not stack:
                out.append(f"error {idx} stack")
            else:
                out.append(f"value {stack[-1]}")

        elif cmd == 'clear':
            if args:
                out.append(f"error {idx} cmd")
            else:
                stack.clear()

        else:
            out.append(f"error {idx} cmd")

    out.append(f"stack {len(stack)}")
    if stack:
        out.append(' '.join(str(v) for v in stack))

    sys.stdout.write('\n'.join(out) + '\n')
    sys.exit(0)


if __name__ == '__main__':
    main()
