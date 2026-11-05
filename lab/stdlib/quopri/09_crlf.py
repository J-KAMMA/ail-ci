import quopri

data = b"line one\r\nline two\r\nline three"
enc = quopri.encodestring(data)
print(repr(enc))
dec = quopri.decodestring(enc)
print(repr(dec))

print(repr(quopri.decodestring(b"a\r\nb\r\nc")))
print(repr(quopri.decodestring(b"a=0D=0Ab")))
print(repr(quopri.encodestring(b"ends with crlf\r\n")))
print(repr(quopri.decodestring(quopri.encodestring(b"ends with crlf\r\n"))))
