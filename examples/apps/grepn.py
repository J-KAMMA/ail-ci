"""Print the lines containing TEXT as lineno:line, exiting 1 when none match."""

import sys


def main() -> None:
    text = sys.argv[1]
    found = False
    number = 0
    for line in sys.stdin:
        number += 1
        stripped = line.rstrip("\n")
        if text in stripped:
            print("%d:%s" % (number, stripped))
            found = True
    if not found:
        sys.exit(1)


main()
