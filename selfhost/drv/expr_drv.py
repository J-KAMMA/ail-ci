"""Stage 1 / stage 2 driver for the self-hosting expression parser.

    python3 selfhost/drv/expr_drv.py SEGLIST       (stage 1, with selfhost/src on sys.path)
    ./expr_drv SEGLIST                             (stage 2, the AIL build of this file)

SEGLIST lines are expression segment files (written by selfhost/ref/expr_ref.py extract).  For each
one the output is ``== PATH`` followed by one line, ``ailast.dump(ailparse.parse_expr(text))``, or
``!! refused: MESSAGE`` when the parser refuses.  The format matches selfhost/ref/expr_ref.py.
"""
import sys

import ailast
import ailparse
import ailtok


def dump_file(path):
    f = open(path, encoding="utf-8", newline="")
    text = f.read()
    f.close()
    try:
        return ailast.dump(ailparse.parse_expr(text))
    except ailparse.ParseError as e:
        return "!! refused: " + str(e)
    except ailtok.TokError as e:
        return "!! refused: " + str(e)


def main():
    f = open(sys.argv[1], encoding="utf-8")
    paths = f.read().split("\n")
    f.close()
    for path in paths:
        if path != "":
            print("== " + path)
            print(dump_file(path))


main()
