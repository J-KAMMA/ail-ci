"""D3: two appends in one iteration, both unconditional, then one that is skipped for odd i."""
def main():
    out = []
    for i in par_range(0, 100):
        out.append(i)
        out.append(-i)
        if i % 2 == 0:
            out.append(i + 1000)
    print(len(out), out[0], out[1], out[2], out[len(out) - 1])
main()
