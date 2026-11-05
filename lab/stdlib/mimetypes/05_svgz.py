import mimetypes

mimetypes.init([])

for name in ("image.svgz", "IMAGE.SVGZ", "icon.svg.gz", "vector.svg",
             "http://example.com/pics/logo.svgz"):
    print(name, mimetypes.guess_type(name))
