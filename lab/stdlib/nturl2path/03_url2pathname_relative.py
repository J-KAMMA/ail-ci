import nturl2path

CASES = [
    "/foo/bar",
    "foo/bar",
    "",
    "/",
    "a/b/c.txt",
]

for url in CASES:
    print(repr(url), "->", repr(nturl2path.url2pathname(url)))
