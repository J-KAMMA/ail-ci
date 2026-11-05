import quopri

high = bytes(range(0x7f, 0x100))
enc = quopri.encodestring(high)
print(len(enc))
print(repr(enc[:80]))
print(repr(enc[-80:]))
dec = quopri.decodestring(enc)
print(repr(dec[:40]))
print(dec == high)

for b in (0x7f, 0x80, 0xff):
    one = bytes((b,))
    print(b, repr(quopri.encodestring(one)), repr(quopri.decodestring(quopri.encodestring(one))))
