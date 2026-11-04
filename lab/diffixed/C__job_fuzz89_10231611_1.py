# C?-job-fuzz89-10231611-1: bytes split with None separator and maxsplit
print(b" a ".split(None, 0))
print(b" a ".rsplit(None, 0))
print(b" a b ".split(None, 1))
print(b" a b ".rsplit(None, 1))
print(b"   ".split(None, 0))
print(b"a b c".split())
print(b"a b c".split(b" ", 1))
print(b" a b ".split(None, 0), b" a b ".rsplit(None, 0))
