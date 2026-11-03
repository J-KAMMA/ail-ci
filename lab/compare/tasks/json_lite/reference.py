"""Reference implementation of json_lite (see spec.md): reference.py reads standard input."""
import sys


def skip_ws(s, i):
    n = len(s)
    while i < n and s[i] in ' \t\r\n':
        i += 1
    return i


def skip_string(s, i):
    n = len(s)
    i += 1
    while i < n:
        if s[i] == '\\':
            i += 2
        elif s[i] == '"':
            return i + 1
        else:
            i += 1
    return i


def parse_value(s, i, total):
    i = skip_ws(s, i)
    n = len(s)
    if i >= n:
        return i
    c = s[i]
    if c == '{':
        i += 1
        if i < n and s[i] == '}':
            return i + 1
        while True:
            i = skip_ws(s, i)
            if i >= n:
                return i
            i = skip_string(s, i)
            i = skip_ws(s, i)
            if i < n and s[i] == ':':
                i += 1
            i = parse_value(s, i, total)
            i = skip_ws(s, i)
            if i < n and s[i] == ',':
                i += 1
                continue
            if i < n and s[i] == '}':
                return i + 1
            return i
    if c == '[':
        i += 1
        if i < n and s[i] == ']':
            return i + 1
        while True:
            i = skip_ws(s, i)
            if i < n and s[i] == ']':
                return i + 1
            if i >= n:
                return i
            i = parse_value(s, i, total)
            i = skip_ws(s, i)
            if i < n and s[i] == ',':
                i += 1
                continue
            if i < n and s[i] == ']':
                return i + 1
            return i
    if c == '"':
        return skip_string(s, i)
    if c == '-' or ('0' <= c <= '9'):
        start = i
        if s[i] == '-':
            i += 1
        while i < n and '0' <= s[i] <= '9':
            i += 1
        total[0] += int(s[start:i])
        return i
    for word in ('true', 'false', 'null'):
        if s.startswith(word, i):
            return i + len(word)
    return i + 1


def main():
    data = sys.stdin.read()
    total = [0]
    i = 0
    n = len(data)
    while True:
        i = parse_value(data, i, total)
        i = skip_ws(data, i)
        if i >= n:
            break
    sys.stdout.write('%d\n' % total[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
