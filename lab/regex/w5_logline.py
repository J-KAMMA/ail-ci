"""w5: parse every log line with five named groups."""
import re
import sys
import zlib

LINE = re.compile(r'^(?P<ts>\S+) (?P<host>\S+) (?P<app>[^\s:]+): level=(?P<level>\w+) '
                  r'msg="(?P<msg>[^"]*)"$')


def main() -> int:
    data = open(sys.argv[1], encoding="utf-8").read()

    lines = 0
    errors = 0
    h = 0
    msg_h = 0
    for line in data.split("\n"):
        if line == "":
            continue
        m = LINE.match(line)
        if m is None:
            continue
        lines += 1
        level = m.group("level")
        if level == "ERROR" or level == "error" or level == "FATAL" or level == "fatal":
            errors += 1
        h = zlib.crc32(line.encode(), h)
        msg_h = zlib.crc32(m.group("msg").encode(), msg_h)

    print("w5 lines=%d errors=%d hash=%d msg_hash=%d" % (lines, errors, h, msg_h))
    return 0


main()
