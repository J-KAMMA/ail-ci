import quopri

exact = b"a" * 76
print(len(exact))
enc76 = quopri.encodestring(exact)
print(repr(enc76))
print(len(enc76))
print(quopri.decodestring(enc76) == exact)

long = b"b" * 100
enc100 = quopri.encodestring(long)
print(repr(enc100))
print(len(enc100))
print(enc100.count(b"=\n"))
print(quopri.decodestring(enc100) == long)

line = b"x" * 75 + b"="
print(repr(quopri.encodestring(line)))
print(quopri.decodestring(quopri.encodestring(line)) == line)
