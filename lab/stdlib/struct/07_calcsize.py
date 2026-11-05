"""calcsize across prefixes, alignment, counts and whitespace."""
import struct

formats = ["@b", "@h", "@i", "@l", "@q", "@f", "@d", "@e", "@c", "@?", "@s", "@p", "@n", "@N",
           "=b", "=h", "=i", "=l", "=q", "<i", ">i", "!i", "<q", ">q"]
for f in formats:
    print(f, struct.calcsize(f))
print(struct.calcsize("@?h"), struct.calcsize("@?i"), struct.calcsize("@?q"), struct.calcsize("@?d"))
print(struct.calcsize("@3s"), struct.calcsize("@3p"), struct.calcsize("@2b"), struct.calcsize("@2h"))
print(struct.calcsize("@bh"), struct.calcsize("@hb"), struct.calcsize("@bhi"), struct.calcsize("@ib"))
print(struct.calcsize("@db"), struct.calcsize("@bd"), struct.calcsize("@fh"))
print(struct.calcsize("i i"), struct.calcsize("I I"), struct.calcsize("0x"), struct.calcsize(""))
