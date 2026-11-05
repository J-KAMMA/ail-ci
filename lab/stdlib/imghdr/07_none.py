import imghdr

# Bytes whose prefixes match no test: CPython prints None.
print(imghdr.what(None, b'\x00' * 32))
print(imghdr.what(None, b'hello world, not an image' + b'\x00' * 6))
print(imghdr.what(None, bytes(32)))

# "P" with a digit that names no Netpbm format matches nothing.
print(imghdr.what(None, b'P7' + b'\x00' * 30))
print(imghdr.what(None, b'P0\n' + b'\x00' * 28))
