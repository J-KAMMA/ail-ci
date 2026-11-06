import nturl2path

CASES = [
    "/a%20b/c.txt",
    "///C|/a%20b/c%C3%A9",
    "/%C3%A9",
    "/a+b%2Bc",
    "/x%2Fy",
    "/bad%zz",
]

for url in CASES:
    print(repr(url), "->", repr(nturl2path.url2pathname(url)))
