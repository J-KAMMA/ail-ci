import quopri

print(repr(quopri.encodestring(b"a=b")))
print(repr(quopri.encodestring(b"==")))
print(repr(quopri.decodestring(b"a=3Db")))
print(repr(quopri.decodestring(b"=3D=3D")))

controls = bytes(range(0x00, 0x20))
enc = quopri.encodestring(controls)
print(repr(enc))
print(repr(quopri.decodestring(enc)))
print(quopri.decodestring(enc) == controls)
