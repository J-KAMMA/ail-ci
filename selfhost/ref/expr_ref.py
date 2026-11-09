"""Stage 0 reference and segment extractor for the self-hosting expression parser.

    python3 selfhost/ref/expr_ref.py extract SRCLIST OUTDIR
    python3 selfhost/ref/expr_ref.py SEGLIST

``extract`` reads every source path in SRCLIST (a plain list or CORPUS.txt lines), takes each
``ast.expr`` node whose parent is a statement, wraps a segment that spans lines in parentheses, and
writes one segment file per expression plus OUTDIR/list.txt and OUTDIR/labels.txt.

The second form reads SEGLIST, whose lines are segment files, and prints ``== PATH`` followed by the
single-line ``ast.dump(ast.parse(text, mode="eval").body)`` for each one.  An expression that CPython
rejects in eval mode prints ``!! refused: MESSAGE``.
"""
import ast
import os
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


def segments_of(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    tree = ast.parse(text, filename=path)
    lines = text.splitlines(keepends=True)
    offs = [0]
    for line in lines:
        offs.append(offs[-1] + len(line))
    out = []
    for st in ast.walk(tree):
        if isinstance(st, ast.stmt):
            for _, val in ast.iter_fields(st):
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    if isinstance(v, ast.expr):
                        s = text[offs[v.lineno - 1] + v.col_offset:
                                 offs[v.end_lineno - 1] + v.end_col_offset]
                        if "\n" in s or "\r" in s:
                            s = "(" + s + ")"
                        out.append(("%s:%d" % (path, len(out)), s))
    return out


def extract(src_paths, outdir):
    os.makedirs(outdir, exist_ok=True)
    listing = []
    labels = []
    n = 0
    for path in src_paths:
        for label, text in segments_of(path):
            seg = os.path.join(outdir, "%06d.expr" % n)
            with open(seg, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            listing.append(seg)
            labels.append(label + "\t" + seg)
            n += 1
    with open(os.path.join(outdir, "list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(listing) + ("\n" if listing else ""))
    with open(os.path.join(outdir, "labels.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(labels) + ("\n" if labels else ""))
    return n


def dump_segment(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        return "!! refused: " + str(e).split("\n")[0]
    return ast.dump(tree.body, include_attributes=False)


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "extract":
        n = extract(read_paths(sys.argv[2]), sys.argv[3])
        print("segments %d" % n)
        return
    paths = read_paths(sys.argv[1])
    for path in paths:
        print("== " + path)
        print(dump_segment(path))


if __name__ == "__main__":
    main()
