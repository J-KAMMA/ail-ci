import nturl2path

PATHS = [
    "C:\\foo\\bar\\spam.foo",
    "C:",
    "C:\\foo",
    "\\\\host\\share\\x",
    "D:\\a b\\c.txt",
    "C:\\caf\u00e9\\r\u00e9sum\u00e9.txt",
    "E:\\a\\b\\c",
    "C:\\a+b\\c%20d.txt",
]

for path in PATHS:
    url = nturl2path.pathname2url(path)
    back = nturl2path.url2pathname(url)
    print(repr(path), "->", repr(url), "->", repr(back), back == path)
