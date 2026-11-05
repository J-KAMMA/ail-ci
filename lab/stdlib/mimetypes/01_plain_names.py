import mimetypes

mimetypes.init([])

for name in ("file.txt", "page.html", "data.json", "archive.zip", "image.png",
             "song.mp3", "movie.mp4", "notes.pdf"):
    print(name, mimetypes.guess_type(name))
