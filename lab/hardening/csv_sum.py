import sys


def main() -> int:
    data = sys.stdin.buffer.read()
    rows = 0
    total = 0
    minimum = 0
    maximum = 0
    field = 0
    negative = False
    have = False
    i = 0
    while i <= len(data):
        c = 10
        if i < len(data):
            c = data[i]
        if c == 44 or c == 10 or c == 13 or i == len(data):
            if have:
                if negative:
                    field = -field
                total += field
                if rows == 0:
                    minimum = field
                    maximum = field
                else:
                    if field < minimum:
                        minimum = field
                    if field > maximum:
                        maximum = field
                rows += 1
            field = 0
            negative = False
            have = False
        elif c == 45:
            negative = True
        elif c >= 48 and c <= 57:
            field = field * 10 + c - 48
            have = True
        i += 1
    print("rows=%d sum=%d min=%d max=%d" % (rows, total, minimum, maximum))
    return 0


main()
