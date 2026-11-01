# `random` real-program coverage

Date: 2026-11-01. Build command for every row:

```
AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/random/<name>.py --syntax python -o /tmp/<name>
```

"typed" means the default build stayed on the typed path; "general" means the default build fell back to
the general path (the compiler prints its fallback note on stderr). Every built program was run and its
stdout and exit code were compared with CPython 3.12; all 11 match. Each was also built with
`AIL_UNIFIED_FORCE=1` (general path) and with `AIL_NO_GENERAL=1` where the program builds there, and both
builds match CPython as well.

| Program | Default result | CPython stdout / exit |
| --- | --- | --- |
| `card_deck.py` | general | match / 0 |
| `cumulative_raffle.py` | general | match / 0 |
| `dice_stats.py` | typed | match / 0 |
| `lottery_ticket.py` | general | match / 0 |
| `monte_carlo_pi.py` | typed | match / 0 |
| `password_generator.py` | general | match / 0 |
| `pin_generator.py` | typed | match / 0 |
| `random_walk.py` | typed | match / 0 |
| `rng_class.py` | general | match / 0 |
| `sampling_errors.py` | general | match / 0 |
| `secure_token.py` | refused | -- |
| `weighted_raffle.py` | general | match / 0 |

Result: **11 of 12 build**, all 11 print CPython's stdout and exit code.

## Refusal

`secure_token.py` (the only refused program) fails at its first `random.SystemRandom` use:

```
lab/stdlib/random/secure_token.py:5:5: not in the subset: random.SystemRandom is not built; random is built for seed(<int>), random, randint, randrange, uniform, gauss, normalvariate, getrandbits, choice (a list), shuffle (a list) and sample (a list): CPython 3.12's MT19937, bit for bit (the general path could not build this program either); general path: random.SystemRandom (not yet published in NAMES_library.json)
```

Follow-up (out of scope here): `random.SystemRandom` needs an OS-entropy source and its own method set on
both paths. No program was changed to avoid it.

## Other known limits (not exercised by these programs)

* `getrandbits(k)` with `k > 63` stops with `RuntimeError: getrandbits: more than 63 bits needs integers
  beyond 64 bits`; CPython returns an unbounded int. A negative `k` matches CPython's `ValueError`. `getrandbits(63)` matches CPython (2^63-1 fits int64).
* `random.choices` with `weights` / `cum_weights` is built on the general path; the typed path names its
  refusal and falls back.

## Checks

* The generated C of the 10 `lab/compare/src/*/main.ail` tasks was built before and after this branch's
  compiler changes (`--debug-dir`, `program.c`); all 10 are byte-identical.
* `lab/stdlib/random` programs were not edited.
* `test_ail_std_random.py` builds the 11 passing programs in the default mode and compares stdout and the
  exit code with CPython. It also covers the new `getrandbits` / `normalvariate` / `choices(cum_weights=...)`
  paths on both builds.
