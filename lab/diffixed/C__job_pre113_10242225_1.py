# C?-job-pre113-10242225-1: constant expressions with an out-of-int64 intermediate
print((1 << 63) - 1)
print(2**65 - 2**65)
print((1 << 62) * 2 - 1)
print(2**63 - 2**62)
print(-(1 << 63))
print((2**65 - 2**65) + 7)
print((1 << 64) // (1 << 32))
