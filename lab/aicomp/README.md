# AI-compute measurement (`aicomp1`)

`bench.py` generates the same workload in AIL, NumPy, PyTorch CPU, plain C and (for the
smallest f64 rows) pure CPython, runs each process five times, and writes `results.json`
and `RESULTS.md`. The generated sources are kept in a temporary directory; nothing outside
`lab/aicomp/` is modified.

```
python3 -m venv /tmp/ai-bench-venv
/tmp/ai-bench-venv/bin/pip install numpy torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
python3 lab/aicomp/bench.py --venv /tmp/ai-bench-venv
python3 lab/aicomp/probes.py          # small AIL programs vs CPython, both builds
```

The columns run single-threaded. AIL is built with `--strict`, so a fallback to the general
path fails the run instead of being measured. The value formula and the size of every case
are in `bench.py`; `RESULTS.md` records the runner, start-up floors, errors and gaps.

No compiler, runtime or test module is touched by this lane.
