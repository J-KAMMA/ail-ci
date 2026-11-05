import os
import os.path

print(os.path.samefile("data/a.txt", "data/a.txt"))
print(os.path.samefile("data/a.txt", "data/link.txt"))
print(os.path.samefile("data/a.txt", "data/b.bin"))
a = os.stat("data/a.txt")
b = os.stat("data/link.txt")
c = os.stat("data/b.bin")
print(a.st_dev == b.st_dev, a.st_ino == b.st_ino)
print(a.st_dev == c.st_dev, a.st_ino == c.st_ino)
