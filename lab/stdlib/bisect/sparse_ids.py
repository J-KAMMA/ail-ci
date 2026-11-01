from bisect import bisect_left, insort_left


def main():
    ids = []
    for value in [104, 101, 108, 103, 102, 110, 105]:
        insort_left(ids, value)
    print("ids", ids)
    for probe in [100, 103, 106, 111]:
        pos = bisect_left(ids, probe)
        exists = pos < len(ids) and ids[pos] == probe
        print(probe, pos, exists)
    insort_left(ids, 106)
    print("new", ids)
    print("dup", bisect_left(ids, 106))
    print("last", bisect_left(ids, 110), bisect_left(ids, 200))


main()
