"""D3: more workers than items (10 items, run at 16 threads): blocks are single iterations."""
def main():
    out = []
    for i in par_range(0, 10):
        out.append(i * i)
    print(len(out), out[0], out[9])
main()
