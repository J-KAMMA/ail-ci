import quopri

samples = [
    b"Hello, world!",
    b"The quick brown fox jumps over the lazy dog.",
    b"plain ASCII text with punctuation: ;,.:!?()[]{}",
    b"",
]

for s in samples:
    enc = quopri.encodestring(s)
    dec = quopri.decodestring(enc)
    print(repr(s))
    print(repr(enc))
    print(repr(dec))
    print(dec == s)
