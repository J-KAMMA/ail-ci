import imghdr

# JPEG with a JFIF marker in bytes 6..10.
jfif = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'\x00' * 20
print(imghdr.what(None, jfif))

# JPEG with an Exif marker in bytes 6..10.
exif = b'\xff\xd8\xff\xe1\x00\x10Exif\x00\x00' + b'\x00' * 20
print(imghdr.what(None, exif))

# Raw JPEG: no JFIF/Exif, but the SOF0 marker starts the stream.
raw = b'\xff\xd8\xff\xdb' + b'\x00' * 28
print(imghdr.what(None, raw))

# A JFIF stream shorter than 32 bytes still reports jpeg.
print(imghdr.what(None, b'\xff\xd8\xff\xe0\x00\x10JFIF'))
