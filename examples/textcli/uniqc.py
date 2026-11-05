"""uniqc.py [-d]: count runs of equal adjacent lines, like `uniq -c`."""
import sys


def main() -> int:
    only_repeats = len(sys.argv) > 1 and sys.argv[1] == "-d"
    have = False
    last = ""
    count = 0
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if have and line == last:
            count += 1
            continue
        if have and (count > 1 or not only_repeats):
            print("%7d %s" % (count, last))
        last = line
        count = 1
        have = True
    if have and (count > 1 or not only_repeats):
        print("%7d %s" % (count, last))
    return 0


if __name__ == "__main__":
    sys.exit(main())
