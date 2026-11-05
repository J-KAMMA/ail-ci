import imghdr

# Empty h: every test sees an empty bytes and returns None.
print(imghdr.what(None, b''))

# Shorter than 32 bytes, no signature.
print(imghdr.what(None, b'a'))
print(imghdr.what(None, b'abc'))
print(imghdr.what(None, b'\x00' * 31))

# Short prefixes that do match.
print(imghdr.what(None, b'BM'))
print(imghdr.what(None, b'\x76\x2f\x31\x01'))

# A short JPEG prefix: bytes 6..10 exist but are empty.
print(imghdr.what(None, b'\xff\xd8\xff\xe0\x00'))
