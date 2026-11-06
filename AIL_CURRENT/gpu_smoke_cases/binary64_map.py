n = 4096
a = [0.0] * n
b = [0.0] * n
for i in range(n):
    a[i] = float(i) * 0.5 - 1000.0
    b[i] = float(i % 37) / 8.0 + 0.25
out = [0.0] * n
# ail: gpu
for i in range(n):
    t = a[i] * b[i] - a[i]
    out[i] = abs(t) + (b[i] if b[i] > 0.5 else 0.5)
acc = 0.0
for i in range(n):
    acc = acc + out[i]
print(out[0], out[2048], out[4095])
print(acc)
