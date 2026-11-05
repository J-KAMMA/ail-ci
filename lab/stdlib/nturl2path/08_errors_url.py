import nturl2path

CASES = ["C|/x|y", "1|/x", "12|/x", "x|a|b"]

for url in CASES:
    try:
        print(repr(url), "->", repr(nturl2path.url2pathname(url)))
    except OSError as error:
        print(repr(url), "->", "OSError", str(error))
