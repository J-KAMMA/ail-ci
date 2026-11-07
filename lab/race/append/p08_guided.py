"""D3: a heavy body so the guided schedule (AIL_PAR_SCHED=guided) takes over; blocks are contiguous
but of different sizes, and the join still puts them back in iteration order."""
def main():
    out = []
    for i in par_range(0, 3000):
        n = i + 1
        c = 0
        while n != 1:
            if n % 2 == 0:
                n = n // 2
            else:
                n = 3 * n + 1
            c += 1
        if c % 2 == 1:
            out.append(i)
    print(len(out), out[0], out[len(out) - 1])
main()
