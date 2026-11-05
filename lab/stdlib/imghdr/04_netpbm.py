import imghdr

# PBM (P1/P4), PGM (P2/P5), PPM (P3/P6): magic plus one whitespace byte.
for magic in (b'P1\n', b'P4 ', b'P2\n', b'P5\t', b'P3\r', b'P6\n'):
    print(imghdr.what(None, magic + b'\x00' * 28))

# The magic is only two bytes in CPython's test, so shorter-than-32 h works.
print(imghdr.what(None, b'P1'))
print(imghdr.what(None, b'P2'))
print(imghdr.what(None, b'P3'))
