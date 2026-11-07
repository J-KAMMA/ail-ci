"""D3: a list[str] built by append (str elements are views; each block moves its own into out)."""
def main():
    out: list[str] = []
    for i in par_range(0, 40):
        if i % 4 == 0:
            out.append("four")
        elif i % 2 == 0:
            out.append("two")
        else:
            out.append("odd")
    print(len(out), out[0], out[1], out[2], out[3], out[39])
main()
