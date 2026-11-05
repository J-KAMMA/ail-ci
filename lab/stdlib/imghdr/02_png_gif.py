import imghdr

# The PNG signature.
png = b'\211PNG\r\n\032\n' + b'\x00' * 24
print(imghdr.what(None, png))

# GIF 87a and 89a.
print(imghdr.what(None, b'GIF87a' + b'\x00' * 26))
print(imghdr.what(None, b'GIF89a' + b'\x00' * 26))

# Just the six-byte signature, shorter than 32 bytes.
print(imghdr.what(None, b'GIF87a'))
print(imghdr.what(None, b'GIF89a'))
