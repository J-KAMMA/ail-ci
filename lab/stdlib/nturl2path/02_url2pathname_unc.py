import nturl2path

CASES = [
    "//host/share/x.txt",
    "///host/share/x.txt",
    "////host/path/on/remote/host",
    "//host/a%20b",
]

for url in CASES:
    print(repr(url), "->", repr(nturl2path.url2pathname(url)))
