import quopri

data = b"0123456789abcdef" * 312 + b"0123456789abcdef"[:8]
print(len(data))
enc = quopri.encodestring(data)
print(len(enc))
print(enc[:40])
dec = quopri.decodestring(enc)
print(len(dec))
print(dec[:40])
print(dec == data)

long_data = bytes(range(256)) * 20
long_enc = quopri.encodestring(long_data)
print(len(long_data), len(long_enc))
print(long_enc[:40])
print(quopri.decodestring(long_enc) == long_data)
