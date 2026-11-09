import sys

MAX = 9223372036854775807
MIN = -MAX - 1


def parse_int(s):
    neg = False
    body = s
    if s[:1] == '-':
        neg = True
        body = s[1:]
    if body == '':
        return False, 0
    for c in body:
        if c not in '0123456789':
            return False, 0
    d = body.lstrip('0')
    if d == '':
        return True, 0
    if len(d) > 19:
        return False, 0
    if len(d) == 19:
        if neg:
            lim = '9223372036854775808'
        else:
            lim = '9223372036854775807'
        if d > lim:
            return False, 0
    return True, int(s)


def add_ok(a, b):
    if b > 0:
        if a > MAX - b:
            return False, 0
        return True, a + b
    if a < MIN - b:
        return False, 0
    return True, a + b


def sub_ok(a, b):
    if b < 0:
        if a > MAX + b:
            return False, 0
        return True, a - b
    if a < MIN + b:
        return False, 0
    return True, a - b


def mul_ok(a, b):
    if a == 0 or b == 0:
        return True, 0
    if a == MIN or b == MIN:
        if a == MIN:
            other = b
        else:
            other = a
        if other == 1:
            return True, MIN
        return False, 0
    neg = (a < 0) != (b < 0)
    x = -a if a < 0 else a
    y = -b if b < 0 else b
    q = MAX // y
    if x <= q:
        p = x * y
        if neg:
            return True, -p
        return True, p
    if neg and x - 1 <= (MAX - y + 1) // y:
        return True, MIN
    return False, 0


def main():
    data = sys.stdin.read()
    lines = data.split('\n')
    stack = []
    store = {}
    out = []
    for idx in range(len(lines)):
        lineno = idx + 1
        raw = lines[idx]
        if raw.endswith('\r'):
            raw = raw[:-1]
        s = raw.strip(' \t')
        if s == '' or s[0] == '#':
            continue
        toks = s.split()
        if len(toks) == 0:
            continue
        cmd = toks[0]
        args = toks[1:]
        n = len(args)
        ln = str(lineno)

        if cmd == 'push':
            if n != 1:
                out.append('error ' + ln + ' cmd\n')
            else:
                ok, v = parse_int(args[0])
                if ok:
                    stack.append(v)
                else:
                    out.append('error ' + ln + ' int\n')

        elif cmd == 'add' or cmd == 'sub' or cmd == 'mul':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 2:
                out.append('error ' + ln + ' stack\n')
            else:
                a = stack[-2]
                b = stack[-1]
                if cmd == 'add':
                    ok, v = add_ok(a, b)
                elif cmd == 'sub':
                    ok, v = sub_ok(a, b)
                else:
                    ok, v = mul_ok(a, b)
                if not ok:
                    out.append('error ' + ln + ' overflow\n')
                else:
                    stack.pop()
                    stack.pop()
                    stack.append(v)

        elif cmd == 'dup':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 1:
                out.append('error ' + ln + ' stack\n')
            else:
                stack.append(stack[-1])

        elif cmd == 'swap':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 2:
                out.append('error ' + ln + ' stack\n')
            else:
                t = stack[-1]
                stack[-1] = stack[-2]
                stack[-2] = t

        elif cmd == 'drop':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 1:
                out.append('error ' + ln + ' stack\n')
            else:
                stack.pop()

        elif cmd == 'store':
            if n != 1:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 1:
                out.append('error ' + ln + ' stack\n')
            else:
                store[args[0]] = stack.pop()

        elif cmd == 'load':
            if n != 1:
                out.append('error ' + ln + ' cmd\n')
            elif args[0] not in store:
                out.append('error ' + ln + ' var\n')
            else:
                stack.append(store[args[0]])

        elif cmd == 'print':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            elif len(stack) < 1:
                out.append('error ' + ln + ' stack\n')
            else:
                out.append('value ' + str(stack[-1]) + '\n')

        elif cmd == 'clear':
            if n != 0:
                out.append('error ' + ln + ' cmd\n')
            else:
                del stack[:]

        else:
            out.append('error ' + ln + ' cmd\n')

    out.append('stack ' + str(len(stack)) + '\n')
    if len(stack) > 0:
        out.append(' '.join([str(v) for v in stack]) + '\n')
    sys.stdout.write(''.join(out))


main()
