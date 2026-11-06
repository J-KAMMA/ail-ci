import nturl2path

CASES = [
    "C:\\foo\\bar\\spam.foo",
    "C:",
    "D:\\x",
    "C:\\a b\\c",
]

for path in CASES:
    print(repr(path), "->", repr(nturl2path.pathname2url(path)))
