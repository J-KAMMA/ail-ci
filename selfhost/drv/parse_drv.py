"""Stage 1 / stage 2 driver for the self-hosting whole-module parser.

    python3 selfhost/drv/parse_drv.py LIST       (stage 1, with selfhost/src on sys.path)
    ./parse_drv LIST                             (stage 2, the AIL build of this file)

LIST lines are source paths (``CORPUS.txt`` style ``sha256  path`` lines are accepted).  For each
one the output is ``== PATH`` followed by one line, ``ailast.dump(ailparse.parse(text))`` with
attributes off, or ``!! refused: MESSAGE`` when the parser refuses.  The format matches
``selfhost/ref/parse_ref.py``.
"""
import sys

import ailast
import ailparse


def read_paths(path):
    f = open(path, encoding="utf-8")
    text = f.read()
    f.close()
    out = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.strip() == "":
            continue
        parts = line.split("  ", 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            out.append(parts[1])
        else:
            out.append(line)
    return out


def dump_file(path):
    f = open(path, encoding="utf-8", newline="")
    text = f.read()
    f.close()
    try:
        return ailast.dump(ailparse.parse(text))
    except SyntaxError as e:
        return "!! refused: " + str(e)
    except ailparse.ParseError as e:
        return "!! refused: " + str(e)


def main():
    for path in read_paths(sys.argv[1]):
        print("== " + path)
        print(dump_file(path))


main()
