def mix(rounds):
    state = 12345
    acc = 0
    for i in range(rounds):
        state = (state * 1103515245 + 12345) % 2147483648
        acc = (acc * 31 + state) % 1000000007
    return acc

print(mix(5000000))
