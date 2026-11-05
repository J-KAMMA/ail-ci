import mimetypes

mimetypes.init([])

for url in ("http://example.com/a/b.txt",
            "https://example.org/files/report.pdf",
            "http://example.com/images/pic.PNG",
            "http://example.com/data.tar.gz",
            "ftp://example.com/pub/archive.zip",
            "http://example.com/download?file=a.txt",
            "data:text/plain;base64,SGVsbG8=",
            "data:,hello"):
    print(url, mimetypes.guess_type(url))
