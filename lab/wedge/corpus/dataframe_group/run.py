"""Driver for dataframe_group: group, sum and filter a generated frame."""
import dataframe_group as m

N = 2500000
GROUPS = 64


def build() -> m.Frame:
    key = []
    a = []
    b = []
    for i in range(N):
        key.append((i * 7 + 3) % GROUPS)
        a.append((i * 13) % 1000)
        b.append(i % 97)
    return m.Frame(key, a, b)


def main() -> None:
    f = build()
    sums = m.group_sum(f.key, f.a, GROUPS)
    counts = m.group_count(f.key, GROUPS)
    total = m.total_of(sums)
    filt = m.filter_sum(f.a, 100, 900)
    wsum = m.weighted_sum(f.a, f.b, 3)
    biggest = m.max_group_count(counts)
    scaled = m.scaled_total(f.b, 5, 7)
    print("rows", f.rows())
    print("groups", len(sums))
    print("total", total)
    print("filter", filt)
    print("weighted", wsum)
    print("biggest", biggest)
    print("scaled", scaled)


main()
