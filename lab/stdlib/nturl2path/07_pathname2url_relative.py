import nturl2path

CASES = [
    "foo\\bar.txt",
    "a",
    "a b\\c d.txt",
    "caf\u00e9\\na\u00efve.txt",
    "a:b",
]

for path in CASES:
    print(repr(path), "->", repr(nturl2path.pathname2url(path)))
