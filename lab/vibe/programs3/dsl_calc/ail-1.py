import sys

MAX = 9223372036854775807
MIN = -MAX - 1


def parse_int_token(tok):
    n = len(tok)
    if n == 0:
        return None

    neg = False
    start = 0
    if tok[0] == '-':
        neg = True
        start = 1
        if start == n:
            return None

    i = start
    while i < n:
        c = tok[i]
        if c < '0' or c > '9':
            return None
        i += 1

    digits = tok[start:]
    norm = digits.lstrip('0')
    if norm == '':
        norm = '0'

    if len(norm) > 19:
        return None
    if len(norm) == 19:
        if neg:
            if norm > '9223372036854775808':
                return None
        else:
            if norm > '9223372036854775807':
                return None

    if norm == '0':
        return 0
    if neg:
        if norm == '9223372036854775808':
            return MIN
        return int('-' + norm)
    return int(norm)


def add_fits(a, b):
    if b > 0:
        return a <= MAX - b
    if b < 0:
        return a >= MIN - b
    return True


def sub_fits(a, b):
    if b > 0:
        return a >= MIN + b
    if b < 0:
        return a <= MAX + b
    return True


def mul_fits(a, b):
    if a == 0 or b == 0:
        return True

    if a == MIN:
        return b == 1
    if b == MIN:
        return a == 1

    if a > 0:
        ma = a
    else:
        ma = -a

    if b > 0:
        mb = b
    else:
        mb = -b

    if (a > 0 and b > 0) or (a < 0 and b < 0):
        return ma <= MAX // mb

    if mb == 1:
        return True
    return ma <= MIN // (-mb)


def main():
    data = sys.stdin.read()
    lines = data.split('\n')

    stack = []
    stores = {}
    out = []
    line_no = 0

    for raw in lines:
        line_no += 1
        line = raw

        if len(line) > 0 and line[-1] == '\r':
            line = line[:-1]

        line = line.strip(' \t')

        if line == '' or line[0] == '#':
            continue

        parts = line.split()
        if len(parts) == 0:
            continue

        cmd = parts[0]
        args = parts[1:]

        if cmd == 'push':
            if len(args) != 1:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            value = parse_int_token(args[0])
            if value is None:
                out.append('error ' + str(line_no) + ' int')
                continue
            stack.append(value)

        elif cmd == 'add':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 2:
                out.append('error ' + str(line_no) + ' stack')
                continue
            a = stack[-2]
            b = stack[-1]
            if not add_fits(a, b):
                out.append('error ' + str(line_no) + ' overflow')
                continue
            stack.pop()
            stack.pop()
            stack.append(a + b)

        elif cmd == 'sub':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 2:
                out.append('error ' + str(line_no) + ' stack')
                continue
            a = stack[-2]
            b = stack[-1]
            if not sub_fits(a, b):
                out.append('error ' + str(line_no) + ' overflow')
                continue
            stack.pop()
            stack.pop()
            stack.append(a - b)

        elif cmd == 'mul':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 2:
                out.append('error ' + str(line_no) + ' stack')
                continue
            a = stack[-2]
            b = stack[-1]
            if not mul_fits(a, b):
                out.append('error ' + str(line_no) + ' overflow')
                continue
            stack.pop()
            stack.pop()
            stack.append(a * b)

        elif cmd == 'dup':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 1:
                out.append('error ' + str(line_no) + ' stack')
                continue
            stack.append(stack[-1])

        elif cmd == 'swap':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 2:
                out.append('error ' + str(line_no) + ' stack')
                continue
            tmp = stack[-1]
            stack[-1] = stack[-2]
            stack[-2] = tmp

        elif cmd == 'drop':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 1:
                out.append('error ' + str(line_no) + ' stack')
                continue
            stack.pop()

        elif cmd == 'store':
            if len(args) != 1:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 1:
                out.append('error ' + str(line_no) + ' stack')
                continue
            value = stack.pop()
            stores[args[0]] = value

        elif cmd == 'load':
            if len(args) != 1:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            name = args[0]
            if name not in stores:
                out.append('error ' + str(line_no) + ' var')
                continue
            stack.append(stores[name])

        elif cmd == 'print':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            if len(stack) < 1:
                out.append('error ' + str(line_no) + ' stack')
                continue
            out.append('value ' + str(stack[-1]))

        elif cmd == 'clear':
            if len(args) != 0:
                out.append('error ' + str(line_no) + ' cmd')
                continue
            stack.clear()

        else:
            out.append('error ' + str(line_no) + ' cmd')

    out.append('stack ' + str(len(stack)))

    if len(stack) > 0:
        values = []
        for value in stack:
            values.append(str(value))
        out.append(' '.join(values))

    sys.stdout.write('\n'.join(out) + '\n')


main()
