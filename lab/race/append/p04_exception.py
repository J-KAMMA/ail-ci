"""D3: an exception halfway. The list holds the blocks before the failing one plus the failing
block's buffer up to the raise, exactly the state the sequential loop leaves. Both builds stop at
i == 37 with the same stdout and exit status; the exception text is compared separately."""
def main():
    out = []
    for i in par_range(0, 100):
        out.append(i)
        if i == 37:
            out.append(1 // (i - 37))
    print(len(out), out[len(out) - 1])
main()
