import copy

def main() -> None:
    ring = []
    ring.append(ring)
    ring.append({"back": ring})

    clone = copy.deepcopy(ring)
    print(len(clone))
    print(clone[0] is clone)
    print(clone[1]["back"] is clone)
    clone[0].append("tail")
    print(len(ring), len(clone))
    print(ring[0] is ring)

    left = []
    right = [left]
    left.append(right)
    pair = copy.deepcopy(left)
    print(pair[0][0] is pair)

main()
