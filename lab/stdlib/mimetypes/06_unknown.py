import mimetypes

mimetypes.init([])

for name in ("file.unknownext", "README", "Makefile", "a.", ".bashrc",
             "x.xyz", "", "dir/", "name.with.dots.unknownext"):
    print(repr(name), mimetypes.guess_type(name))
