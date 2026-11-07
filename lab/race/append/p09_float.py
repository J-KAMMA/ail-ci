"""D3: a list[float] built by append (doubles, one buffer kind per block)."""
def main():
    out: list[float] = []
    for i in par_range(0, 50):
        out.append(i * 0.25)
        if i % 10 == 0:
            out.append(-1.5)
    print(len(out), out[0], out[1], out[len(out) - 1])
main()
