import os
import stat

p = "data/link.txt"
a = os.stat(p)
b = os.lstat(p)
print(a.st_size, b.st_size)
print(stat.S_ISLNK(b.st_mode), stat.S_ISLNK(a.st_mode))
print(stat.S_ISREG(a.st_mode), stat.S_ISREG(b.st_mode))
print(a.st_ino == b.st_ino)
