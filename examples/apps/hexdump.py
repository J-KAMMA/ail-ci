"""Write standard input as xxd-style hex dump lines."""

import sys


def main() -> None:
    data = sys.stdin.buffer.read()
    offset = 0
    while offset < len(data):
        chunk = data[offset:offset + 16]
        cells = []
        index = 0
        while index < 16:
            if index + 1 < len(chunk):
                cells.append("%02x%02x" % (chunk[index], chunk[index + 1]))
            elif index < len(chunk):
                cells.append("%02x  " % chunk[index])
            else:
                cells.append("    ")
            index += 2
        text = ""
        for byte in chunk:
            if 0x20 <= byte <= 0x7e:
                text += chr(byte)
            else:
                text += "."
        print("%08x  %s  %s" % (offset, " ".join(cells), text))
        offset += 16


main()
