import nturl2path

CASES = ["C:x:y", "ab:/x", "\\\\?\\foo", "\\\\?\\ab"]

for path in CASES:
    try:
        print(repr(path), "->", repr(nturl2path.pathname2url(path)))
    except OSError as error:
        print(repr(path), "->", "OSError", str(error))
