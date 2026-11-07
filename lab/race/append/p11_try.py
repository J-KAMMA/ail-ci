"""D3: an exception halfway inside a `try` that prints `out`. The list must hold exactly the state the
sequential loop leaves: 38 items, the last 37. The typed build refuses this shape by name -- a
parallel loop cannot live in a function with try/except, so the partial-buffer join cannot be
observed through the caught exception -- and the probe records that refusal; the `range` twin shows
the state the join produces, printed by the `except` branch."""
def main():
    out = []
    try:
        for i in par_range(0, 100):
            out.append(i)
            if i == 37:
                out.append(1 // (i - 37))
    except ZeroDivisionError:
        pass
    print(len(out), out[len(out) - 1], out[0])
main()
