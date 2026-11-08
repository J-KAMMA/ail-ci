"""Stage 1 / stage 2 driver: the ailtok token dump of every file in a path list.

    python3 selfhost/drv/tok_drv.py LIST        (stage 1, with selfhost/src on sys.path or AIL_PATH)
    ./tok_drv LIST                              (stage 2, the AIL build of this file)

LIST holds one path per line.  For each path the output is a line ``== PATH`` followed by one line
per token, ``TYPE r1,c1 r2,c2 repr(string)``, or a single ``!! refused: MESSAGE`` line when the
tokenizer rejects the text.  The format is the same as selfhost/ref/tok_ref.py (stage 0).
"""
import sys

from ailtok import TokError, dump_line, tokenize


def dump_file(path: str) -> str:
    f = open(path, encoding="utf-8", newline="")
    text = f.read()
    f.close()
    out = ["== " + path]
    try:
        toks = tokenize(text)
        for t in toks:
            out.append(dump_line(t))
    except TokError as e:
        out.append("!! refused: " + str(e))
    return "\n".join(out)


def main():
    f = open(sys.argv[1], encoding="utf-8")
    paths = f.read().split("\n")
    f.close()
    for p in paths:
        if p != "":
            print(dump_file(p))


main()
