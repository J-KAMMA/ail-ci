import copy

def main() -> None:
    shared = [1]
    source = [shared, shared]
    memo = {}
    first = copy.deepcopy(source, memo)
    print(first[0] is first[1])
    print(len(memo))
    same = copy.deepcopy(source, memo=memo)
    print(same[0] is same[1])
    print(len(memo) >= 3)
    print(first[0] is same[0])
    first[0].append(2)
    print(shared, first[1], same[0])

main()
