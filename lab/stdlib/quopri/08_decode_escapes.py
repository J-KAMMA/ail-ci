import quopri

print(repr(quopri.decodestring(b"abc=\ndef")))
print(repr(quopri.decodestring(b"one =\ntwo =\nthree")))
print(repr(quopri.decodestring(b"3d")))
print(repr(quopri.decodestring(b"=3d")))
print(repr(quopri.decodestring(b"=3D")))
print(repr(quopri.decodestring(b"=ZZ")))
print(repr(quopri.decodestring(b"a=ZZb")))
print(repr(quopri.decodestring(b"trailing=")))
print(repr(quopri.decodestring(b"trailing=\n")))
print(repr(quopri.decodestring(b"=41=42=43")))
