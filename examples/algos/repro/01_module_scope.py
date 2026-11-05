"""Reproducer: a module-level call returning non-numeric data is refused as a module constant."""


def build(n):
    result = []
    for index in range(n):
        result.append((index, index + 1))
    return result


edges = build(4)
print(edges[0][0])
