import nturl2path

CASES = [
    "///C|/foo/bar/spam.foo",
    "///C:/foo/bar",
    "C|/x",
    "///D:/a/b/c",
]

for url in CASES:
    print(repr(url), "->", repr(nturl2path.url2pathname(url)))
