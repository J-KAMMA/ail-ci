import os

s = os.fspath("data/a.txt")
print(s)
print(s == "data/a.txt")
b = os.fspath(b"data/a.txt")
print(b.decode())
print(b == b"data/a.txt")
print(os.fspath(b"") == b"")
