def make_term(tok: bytes):
    t = tok.replace(b"'", b"")
    if len(t) > 0:
        return b"#" + str(len(t)).encode()
    return 0

print(make_term(b"ab"))
