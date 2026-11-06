# Rust twins

The `regex` crate is **not available offline** on this runner.  `~/.cargo/registry` does not
exist (the only entry under `~/.cargo` is `bin/`) and there is no vendored copy under
`lab/regex/rust/vendor` or `vendor/` in the repository.  Fetching it requires network access
and is an owner decision, so, as sub-step 2 of the brief says, this step stops here and the
Rust column of `RESULTS.md` is marked unavailable.

`run.py` repeats that check (`rust_offline`) so a future run with a vendored crate is not
silently reported as unavailable.  To enable the twins, populate one of those locations and
add one binary here (or one binary taking a workload argument) that prints the same digest
lines as `w1_literal.py` ... `w8_fullmatch.py`, then extend `run.py` to build and run it.
