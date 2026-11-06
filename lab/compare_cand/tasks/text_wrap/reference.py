"""Reference implementation of text_wrap (see spec.md): reference.py < input

Plain CPython, the oracle. One pass: validate the width, scan the text a line at a time, extract
words as maximal runs outside space/tab/newline, and wrap them greedily. The running hash is fed
each output byte (newlines, spaces, word bytes) as soon as the wrapping decides it, so no output
line is ever buffered.
"""
import sys

MOD = 1000000007
SPACE = 32
TAB = 9
NEWLINE = 10


def main():
    data = sys.stdin.buffer.read()
    n = len(data)

    # first line: 1..3 ASCII digits with a value 10..200
    e = 0
    while e < n and data[e] != NEWLINE:
        e += 1
    if e < 1 or e > 3:
        return 2
    w = 0
    for k in range(e):
        c = data[k]
        if c < 48 or c > 57:
            return 2
        w = w * 10 + c - 48
    if w < 10 or w > 200:
        return 2

    pos = e + 1 if e < n else n

    paragraphs = 0
    lines = 0
    words = 0
    longest = 0
    h = 0
    emitted_any = False
    in_para = False
    para_first_line = False
    cur_len = 0

    while True:
        e = pos
        while e < n and data[e] != NEWLINE:
            e += 1
        a = pos
        blank = True
        k = a
        while k < e:
            if data[k] != SPACE:
                blank = False
                break
            k += 1
        if blank:
            if in_para:
                in_para = False
                cur_len = 0
        else:
            k = a
            while k < e:
                c = data[k]
                if c == SPACE or c == TAB:
                    k += 1
                    continue
                ws = k
                while k < e:
                    c = data[k]
                    if c == SPACE or c == TAB:
                        break
                    k += 1
                we = k
                wl = we - ws
                words += 1
                if not in_para:
                    in_para = True
                    para_first_line = True
                    paragraphs += 1
                if cur_len == 0:
                    if para_first_line:
                        if emitted_any:
                            h = (h * 131 + NEWLINE) % MOD
                            h = (h * 131 + NEWLINE) % MOD
                        emitted_any = True
                        para_first_line = False
                    else:
                        h = (h * 131 + NEWLINE) % MOD
                    lines += 1
                    cur_len = wl
                elif cur_len + 1 + wl <= w:
                    h = (h * 131 + SPACE) % MOD
                    cur_len += 1 + wl
                else:
                    h = (h * 131 + NEWLINE) % MOD
                    lines += 1
                    cur_len = wl
                p = ws
                while p < we:
                    h = (h * 131 + data[p]) % MOD
                    p += 1
                if cur_len > longest:
                    longest = cur_len
        if e >= n:
            break
        pos = e + 1

    sys.stdout.write('paragraphs %d lines %d words %d longest %d hash %d\n'
                     % (paragraphs, lines, words, longest, h))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(1)
