import mimetypes

mimetypes.init([])

for name in ("FILE.TXT", "PAGE.HTML", "MOVIE.MP4", "PIC.JPG", "DATA.JSON",
             "ARCHIVE.GZ", "IMAGE.SVGZ", "A.TAR.GZ", "X.PNG"):
    print(name, mimetypes.guess_type(name))
