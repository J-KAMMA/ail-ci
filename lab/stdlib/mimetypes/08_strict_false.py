import mimetypes

mimetypes.init([])

for name in ("doc.rtf", "sound.midi", "photo.webp", "image.pict",
             "mouse.mid", "page.xul", "file.unknown"):
    print(name, mimetypes.guess_type(name), mimetypes.guess_type(name, False))
