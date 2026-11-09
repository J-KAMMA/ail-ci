import sys

MIN = -9223372036854775807 - 1
MAX = 9223372036854775807


def parse_int64(s):
    if not s:
        return None
    neg = False
    start = 0
    if s[0] == '-':
        neg = True
        start = 1
    if start >= len(s):
        return None
    i = start
    while i < len(s):
        c = s[i]
        if c < '0' or c > '9':
            return None
        i += 1
    mag = s[start:].lstrip('0')
    if mag == '':
        return 0
    if len(mag) > 19:
        return None
    if len(mag) == 19:
        if neg:
            limit = '9223372036854775808'
        else:
            limit = '9223372036854775807'
        if mag > limit:
            return None
    if neg:
        return int('-' + mag)
    return int(mag)


def add_result(a, b):
    if b > 0:
        if a > MAX - b:
            return None
        return a + b
    if b < 0:
        if a < MIN - b:
            return None
        return a + b
    return a


def sub_result(a, b):
    if b > 0:
        if a < MIN + b:
            return None
        return a - b
    if b < 0:
        if a > MAX + b:
            return None
        return a - b
    return a


def mul_result(a, b):
    if a == 0 or b == 0:
        return 0
    if a == MIN:
        if b == 1:
            return MIN
        return None
    if b == MIN:
        if a == 1:
            return MIN
        return None
    if a > 0:
        ma = a
        sa = 1
    else:
        ma = -a
        sa = -1
    if b > 0:
        mb = b
        sb = 1
    else:
        mb = -b
        sb = -1
    if sa == sb:
        if ma > MAX // mb:
            return None
        return a * b
    if mb == 1:
        return a * b
    q = MAX // mb
    rem = MAX - q * mb
    if rem + 1 == mb:
        lim = q + 1
    else:
        lim = q
    if ma > lim:
        return None
    return a * b


def main():
    data = sys.stdin.buffer.read().decode('utf-8', 'replace')
    lines = data.split('\n')
    stack = []
    stores = {}
    out = []
    idx = 0
    total = len(lines)
    while idx < total:
        raw = lines[idx]
        ln = idx + 1
        idx += 1
        if raw.endswith('\r'):
            raw = raw[:len(raw) - 1]
        line = raw.strip(' \t')
        if line == '':
            continue
        if line[0] == '#':
            continue
        parts = line.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd == 'push':
            if len(args) != 1:
                out.append('error %d cmd' % ln)
                continue
            v = parse_int64(args[0])
            if v is None:
                out.append('error %d int' % ln)
                continue
            stack.append(v)
        elif cmd == 'add' or cmd == 'sub' or cmd == 'mul':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 2:
                out.append('error %d stack' % ln)
                continue
            b = stack[-1]
            a = stack[-2]
            if cmd == 'add':
                r = add_result(a, b)
            elif cmd == 'sub':
                r = sub_result(a, b)
            else:
                r = mul_result(a, b)
            if r is None:
                out.append('error %d overflow' % ln)
                continue
            stack.pop()
            stack.pop()
            stack.append(r)
        elif cmd == 'dup':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 1:
                out.append('error %d stack' % ln)
                continue
            stack.append(stack[-1])
        elif cmd == 'swap':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 2:
                out.append('error %d stack' % ln)
                continue
            t = stack[-1]
            stack[-1] = stack[-2]
            stack[-2] = t
        elif cmd == 'drop':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 1:
                out.append('error %d stack' % ln)
                continue
            stack.pop()
        elif cmd == 'store':
            if len(args) != 1:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 1:
                out.append('error %d stack' % ln)
                continue
            stores[args[0]] = stack.pop()
        elif cmd == 'load':
            if len(args) != 1:
                out.append('error %d cmd' % ln)
                continue
            name = args[0]
            if name in stores:
                stack.append(stores[name])
            else:
                out.append('error %d var' % ln)
        elif cmd == 'print':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            if len(stack) < 1:
                out.append('error %d stack' % ln)
                continue
            out.append('value %d' % stack[-1])
        elif cmd == 'clear':
            if len(args) != 0:
                out.append('error %d cmd' % ln)
                continue
            stack.clear()
        else:
            out.append('error %d cmd' % ln)

    out.append('stack %d' % len(stack))
    if len(stack) > 0:
        out.append(' '.join(str(v) for v in stack))
    sys.stdout.write('\n'.join(out) + '\n')


main()
