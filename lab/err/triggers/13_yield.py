def gen(n: int):
    for i in range(n):
        yield i

print(list(gen(3)))
