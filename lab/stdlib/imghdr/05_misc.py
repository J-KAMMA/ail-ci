import imghdr

# SGI RGB.
print(imghdr.what(None, b'\001\332' + b'\x00' * 30))

# Sun raster.
print(imghdr.what(None, b'\x59\xa6\x6a\x95' + b'\x00' * 28))

# X bitmap, padded to 32 bytes.
print(imghdr.what(None, b'#define im_width 8\n' + b'\x00' * 12))

# BMP.
print(imghdr.what(None, b'BM' + b'\x00' * 30))
