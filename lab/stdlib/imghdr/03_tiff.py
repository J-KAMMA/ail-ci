import imghdr

# Motorola byte order.
print(imghdr.what(None, b'MM\x00\x2a' + b'\x00' * 28))

# Intel byte order.
print(imghdr.what(None, b'II\x2a\x00' + b'\x00' * 28))

# Two bytes are enough for the tiff test, shorter than 32.
print(imghdr.what(None, b'MM'))
print(imghdr.what(None, b'II'))
