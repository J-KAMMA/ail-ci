"""D3: an empty range -- no block, no buffer, out stays as it was."""
def main():
    out = [7, 8]
    for i in par_range(0, 0):
        out.append(i)
    print(len(out), out[0], out[1])
main()
