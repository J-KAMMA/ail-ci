def collatz_len(n):
    steps = 0
    m = n
    while m != 1:
        if m % 2 == 0:
            m = m // 2
        else:
            m = 3 * m + 1
        steps += 1
    return steps


def sieve(limit):
    flags = [True] * (limit + 1)
    flags[0] = False
    flags[1] = False
    i = 2
    while i * i <= limit:
        if flags[i]:
            j = i * i
            while j <= limit:
                flags[j] = False
                j += i
        i += 1
    count = 0
    for f in flags:
        if f:
            count += 1
    return count


def main():
    best = 0
    arg = 0
    for i in range(1, 300000):
        s = collatz_len(i)
        if s > best:
            best = s
            arg = i
    print(best, arg)
    print(sieve(3000000))
    total = 0
    for i in range(20000000):
        total += (i * 7) % 13
    print(total)


main()
