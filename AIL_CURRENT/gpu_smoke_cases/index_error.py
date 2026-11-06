n = 4096
xs = [0] * n
for i in range(n):
    xs[i] = i
out = [0] * n
# ail: gpu
for i in range(n):
    out[i] = xs[i + 1096]
print(out[0])
