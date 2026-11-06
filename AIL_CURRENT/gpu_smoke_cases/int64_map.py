n = 4096
xs = [0] * n
for i in range(n):
    xs[i] = i * 3 - 5000
out = [0] * n
# ail: gpu
for i in range(n):
    out[i] = xs[i] * 2 - 7
acc = 0
for i in range(n):
    acc = acc + out[i]
print(out[0], out[1234], out[4095])
print(acc)
