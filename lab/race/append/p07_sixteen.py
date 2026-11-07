"""D3: 1024 iterations (many blocks), run at 1, 2, 4 and 16 threads."""
def main():
    out = []
    for i in par_range(0, 1024):
        out.append(i * 7 + 1)
    print(len(out), out[0], out[1023])
main()
