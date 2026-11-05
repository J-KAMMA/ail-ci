import os

a = os.stat("data/a.txt")
b = os.stat("data/a.txt")
print(a.st_mtime_ns == b.st_mtime_ns)
print(a.st_size == b.st_size)
print(a.st_mtime_ns > 0)
print(a.st_mtime_ns >= 0, a.st_atime_ns >= 0, a.st_ctime_ns >= 0)
print(a.st_mtime_ns == b.st_mtime_ns)
