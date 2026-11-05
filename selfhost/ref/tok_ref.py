"""Stage 0: the token dump of every file in a path list from CPython's ``tokenize``.

    python3 selfhost/ref/tok_ref.py LIST

Same format as selfhost/drv/tok_drv.py: ``== PATH`` then ``TYPE r1,c1 r2,c2 repr(string)`` per token
(OP tokens by their exact type), or ``!! refused: MESSAGE`` when ``tokenize`` raises.  The text is
read with ``newline=""`` so CRLF line endings reach the tokenizer unchanged.
"""
import io
import sys
import token
import tokenize


def dump_file(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    out = ["== " + path]
    try:
        for t in tokenize.generate_tokens(io.StringIO(text).readline):
            out.append("%s %d,%d %d,%d %r" % (token.tok_name[t.exact_type], t.start[0], t.start[1],
                                              t.end[0], t.end[1], t.string))
    except (tokenize.TokenError, SyntaxError) as e:
        out.append("!! refused: " + str(e))
    return "\n".join(out)


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        paths = [p for p in f.read().split("\n") if p]
    for p in paths:
        print(dump_file(p))


if __name__ == "__main__":
    main()
