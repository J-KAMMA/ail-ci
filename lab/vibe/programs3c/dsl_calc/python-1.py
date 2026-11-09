import re
import sys

MIN_I64 = -(1 << 63)
MAX_I64 = (1 << 63) - 1
INT_RE = re.compile(r'-?[0-9]+')
SPLIT_RE = re.compile(r'[ \t]+')

ARG_COUNTS = {
    'push': 1,
    'add': 0,
    'sub': 0,
    'mul': 0,
    'dup': 0,
    'swap': 0,
    'drop': 0,
    'store': 1,
    'load': 1,
    'print': 0,
    'clear': 0,
}


def main():
    data = sys.stdin.buffer.read().decode('utf-8', 'surrogateescape')
    lines = data.split('\n')

    out = []
    stack = []
    store = {}

    for idx, raw in enumerate(lines, 1):
        line = raw
        if line.endswith('\r'):
            line = line[:-1]
        line = line.strip(' \t')
        if line == '' or line[0] == '#':
            continue

        toks = SPLIT_RE.split(line)
        cmd = toks[0]
        args = toks[1:]

        if cmd not in ARG_COUNTS or len(args) != ARG_COUNTS[cmd]:
            out.append(f"error {idx} cmd\n")
            continue

        if cmd == 'push':
            text = args[0]
            if not INT_RE.fullmatch(text):
                out.append(f"error {idx} int\n")
                continue
            v = int(text)
            if v < MIN_I64 or v > MAX_I64:
                out.append(f"error {idx} int\n")
                continue
            stack.append(v)

        elif cmd in ('add', 'sub', 'mul'):
            if len(stack) < 2:
                out.append(f"error {idx} stack\n")
                continue
            a = stack[-2]
            b = stack[-1]
            if cmd == 'add':
                r = a + b
            elif cmd == 'sub':
                r = a - b
            else:
                r = a * b
            if r < MIN_I64 or r > MAX_I64:
                out.append(f"error {idx} overflow\n")
                continue
            stack.pop()
            stack.pop()
            stack.append(r)

        elif cmd == 'dup':
            if len(stack) < 1:
                out.append(f"error {idx} stack\n")
                continue
            stack.append(stack[-1])

        elif cmd == 'swap':
            if len(stack) < 2:
                out.append(f"error {idx} stack\n")
                continue
            stack[-1], stack[-2] = stack[-2], stack[-1]

        elif cmd == 'drop':
            if len(stack) < 1:
                out.append(f"error {idx} stack\n")
                continue
            stack.pop()

        elif cmd == 'store':
            if len(stack) < 1:
                out.append(f"error {idx} stack\n")
                continue
            store[args[0]] = stack.pop()

        elif cmd == 'load':
            name = args[0]
            if name not in store:
                out.append(f"error {idx} var\n")
                continue
            stack.append(store[name])

        elif cmd == 'print':
            if len(stack) < 1:
                out.append(f"error {idx} stack\n")
                continue
            out.append(f"value {stack[-1]}\n")

        elif cmd == 'clear':
            stack.clear()

    out.append(f"stack {len(stack)}\n")
    if stack:
        out.append(' '.join(str(v) for v in stack) + '\n')

    sys.stdout.write(''.join(out))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
