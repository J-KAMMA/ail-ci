import quopri

data = bytes(range(256))
enc = quopri.encodestring(data)
dec = quopri.decodestring(enc)
print(len(data), len(enc))
print(dec == data)
print(dec[:30])
print(dec[120:140])
print(dec[-20:])

header_enc = quopri.encodestring(data, header=True)
header_dec = quopri.decodestring(header_enc, header=True)
print(header_dec == data)
print(len(header_enc))
