"""The fixed-order float sum (D2 option b, `docs/design/PAR_REDUCE.md`).

With `AIL_PAR_FSUM=fixed`, `acc += e` on a float `acc` in a parallel body sums in fixed chunks of
4096 iterations.  A chunk's layout depends only on the iteration count: chunk c is
`[lo + c*4096, min(lo + (c+1)*4096, hi))`.  Each chunk is summed left to right starting at `-0.0`
(the IEEE identity: `-0.0 + x == x` for every `x`, including `+0.0` and `-0.0`); afterwards `acc`
adds the chunk sums left to right in chunk order, starting from its value before the loop.

`fixed_sum` below is that order, written in ordinary Python.  It is the reference every probe in
this directory is measured against.
"""
import importlib.util
import pathlib

CHUNK = 4096
HERE = pathlib.Path(__file__).resolve().parent


def fixed_sum(values, start=0.0):
    """The fixed order over `values`, with `acc` starting at `start`."""
    acc = start
    for begin in range(0, len(values), CHUNK):
        s = -0.0
        for x in values[begin:begin + CHUNK]:
            s = s + x
        acc = acc + s
    return acc


def load(path):
    """Import a probe module without running its `main()` (each guards it with `__main__`)."""
    path = pathlib.Path(path)
    spec = importlib.util.spec_from_file_location('fsum_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probes():
    """The probe files, sorted."""
    return sorted(HERE.glob('f*.py'))


def expected(path):
    """The reference output for one probe: `fixed_sum` over its `values()` from its `START`."""
    module = load(path)
    return fixed_sum(module.values(), module.START)


if __name__ == '__main__':
    for probe in probes():
        print('%s\t%s' % (probe.name, repr(expected(probe))))
