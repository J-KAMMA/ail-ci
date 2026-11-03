def count_primes(n):
    flags = [1] * (n + 1)
    flags[0] = 0
    flags[1] = 0
    i = 2
    while i * i <= n:
        if flags[i] == 1:
            j = i * i
            while j <= n:
                flags[j] = 0
                j += i
        i += 1
    total = 0
    for k in range(n + 1):
        total += flags[k]
    return total

print(count_primes(5000000))
