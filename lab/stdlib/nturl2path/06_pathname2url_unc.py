import nturl2path

CASES = [
    "\\\\host\\share\\x",
    "\\\\host\\share\\a b",
    "\\\\?\\C:\\x\\y",
    "\\\\?\\UNC\\host\\share\\f",
]

for path in CASES:
    print(repr(path), "->", repr(nturl2path.pathname2url(path)))
