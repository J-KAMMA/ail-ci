"""Stage 0 reference for the self-hosting whole-module parser.

    python3 selfhost/ref/parse_ref.py LIST

LIST lines are source paths (``CORPUS.txt`` style ``sha256  path`` lines are accepted).  For each
one the output is ``== PATH`` followed by one line, ``ast.dump(ast.parse(text), include_attributes=
False)``, or ``!! refused: MESSAGE`` when CPython's ``ast.parse`` rejects the source.  The format
matches ``selfhost/drv/parse_drv.py``.
"""
import ast
import sys


def read_paths(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("  ", 1)
            out.append(parts[1] if len(parts) == 2 and len(parts[0]) == 64 else line)
    return out


def dump_file(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as e:
        return "!! refused: " + str(e).split("\n")[0]
    return ast.dump(tree, include_attributes=False)


def main():
    for path in read_paths(sys.argv[1]):
        print("== " + path)
        print(dump_file(path))


if __name__ == "__main__":
    main()
