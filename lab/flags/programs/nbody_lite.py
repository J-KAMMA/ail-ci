def energy(steps):
    x = 1.0
    v = 0.0
    k = 0.5
    dt = 0.0001
    total = 0.0
    for i in range(steps):
        a = 0.0 - k * x
        v += a * dt
        x += v * dt
        total += 0.5 * v * v + 0.5 * k * x * x
    return total

print(round(energy(3000000), 6))
