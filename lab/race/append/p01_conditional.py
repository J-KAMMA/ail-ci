"""D3: a conditional append into a list defined before the loop; the sequential twin builds the
same list with `range`, and the outputs must agree at every thread count."""
def main():
    out = []
    for i in par_range(0, 200):
        if i % 3 == 0:
            out.append(i)
        else:
            out.append(i * 10)
    print(len(out), out[0], out[1], out[199])
main()
