import mimetypes

mimetypes.init([])

names = [
    "/home/example.com/docs/report.txt",
    "relative/dir/style.css",
    "./a/b/photo.jpeg",
    "dir/sub/archive.tar",
    "/srv/www/example.org/index.html",
    "C:/notes/readme.md",
    "dir/.hidden",
    "a/b/.config.json",
]
for name in names:
    print(name, mimetypes.guess_type(name))
