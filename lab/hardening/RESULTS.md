# Binary hardening of AIL executables

Measured 2026-11-05 on the GitHub Actions runner (Ubuntu 24.04, x86-64).

Tools:

- `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`
- `GNU readelf (GNU Binutils for Ubuntu) 2.42`
- Rust: **n/a** - `rustc` on PATH is only the rustup shim and no toolchain is installed
  (`error: rustup could not choose a version of rustc to run, because one wasn't specified explicitly,
  and no default is configured.`), so the Rust columns below are `n/a`.

The six properties come from `tools/hardening_check.py`, which uses `readelf -h/-l/-d/-s/-S` only.
`pie` = ELF type `DYN` plus `PIE` in `DT_FLAGS_1`; `nx` = `GNU_STACK` present and not executable;
`relro` = `full` with `GNU_RELRO` and `BIND_NOW`; `canary` = dynamic symbol `__stack_chk_fail`;
`fortify` = number of distinct dynamic `__*_chk` symbols.

Corpus (`lab/hardening/`): `csv_sum` (CSV of ints), `word_count`, `rec_tree` (recursive walk of a
parent array), `str_build` (2000 rows joined), `dict_count` (word frequencies, insertion sort).
Each `.py` is AIL source and is also valid CPython; each `.c` is the same algorithm. All ten binaries
produced byte-identical stdout and exit status on the fixtures (`lab/hardening/measure.py`).

## AIL vs C, same five programs

AIL builds: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict]`.
C builds: `gcc -O2 -o OUT SRC.c`.

| binary | pie | nx | relro | canary | fortify | stripped | bytes |
|---|---|---|---|---|---|---|---|
| `ail/csv_sum` | yes | yes | full | yes | 1 | no | 22416 |
| `ail/word_count` | yes | yes | full | yes | 1 | no | 22016 |
| `ail/rec_tree` | yes | yes | full | yes | 1 | no | 21776 |
| `ail/str_build` | yes | yes | full | yes | 0 | no | 25904 |
| `ail/dict_count` | yes | yes | full | yes | 2 | no | 35008 |
| `ail-strict/csv_sum` | yes | yes | full | yes | 1 | no | 22416 |
| `ail-strict/word_count` | yes | yes | full | yes | 1 | no | 22016 |
| `ail-strict/rec_tree` | yes | yes | full | yes | 1 | no | 21776 |
| `ail-strict/str_build` | yes | yes | full | yes | 0 | no | 25904 |
| `ail-strict/dict_count` | yes | yes | full | yes | 2 | no | 35008 |
| `c/csv_sum` | yes | yes | full | no | 1 | no | 16056 |
| `c/word_count` | yes | yes | full | no | 1 | no | 16056 |
| `c/rec_tree` | yes | yes | full | no | 1 | no | 16144 |
| `c/str_build` | yes | yes | full | no | 4 | no | 16248 |
| `c/dict_count` | yes | yes | full | yes | 4 | no | 16360 |

All five AIL programs build on the typed path (`--strict` accepts every one), and the strict binary is
byte-identical to the default binary (same SHA-256).

### Reading the table

- **AIL is already PIE, NX and full RELRO, and has a stack canary.** It does not pass any hardening
  flag itself: it invokes plain `cc -O2`, and Ubuntu 24.04's gcc 13 defaults (`--enable-default-pie`,
  default `-fstack-protector-strong`, default `-z relro -z now`) supply all four. The property is a
  property of the distro toolchain, not of the AIL build system.
- **C built bare with `gcc -O2` keeps PIE, NX and full RELRO from the same distro defaults, but has
  no canary** for these programs: GCC 13 in this configuration gives the plain `-fstack-protector`,
  which only instruments functions with a local array or an address-taken local, and none of these
  small `main`s needs it. (AIL's generated `main` plus runtime helpers do trigger it.)
- **`fortify` differs**: Ubuntu's gcc already defines `_FORTIFY_SOURCE=3` at `-O2`. AIL's larger
  generated code calls `memcpy`/`memset` on known-size objects and picks up `__memcpy_chk` /
  `__memset_chk`; the two-line C programs mostly do not. AIL `str_build` gets none.
- Nothing is stripped: AIL keeps `.symtab` (and any debug info in it).

## Rust

`rustc` on PATH is the rustup shim, and `rustup toolchain list` says `no installed toolchains`;
with no default toolchain, `rustc` fails with
`error: rustup could not choose a version of rustc to run, because one wasn't specified explicitly,
and no default is configured.` The ten `lab/compare/src/*/main.rs` programs were not built (no
toolchain was downloaded), so every Rust row is `n/a`:

| binary | pie | nx | relro | canary | fortify | stripped | bytes |
|---|---|---|---|---|---|---|---|
| `rust/berth_sim` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/chain_relax` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/echo_pack` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/ledger_bin` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/rail_transfer` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/scar_life` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/tally_lang` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/term_rank` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/ticket_audit` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| `rust/tree_fold` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Proposal

Rebuild the generated C by hand (`--debug-dir DIR` -> `DIR/program.c`) with the flags AIL uses, then
the same plus `-fstack-protector-strong -D_FORTIFY_SOURCE=2 -Wl,-z,relro,-z,now`.

The exact AIL command, confirmed by reproducing the AIL binary byte for byte (SHA-256 identical,
same size) before adding anything:

```
cc -O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd \
   -Werror=implicit-function-declaration -Werror=implicit-int -Werror=incompatible-pointer-types \
   -fno-asynchronous-unwind-tables -o OUT DIR/program.c -lm
```

(`cc` = `gcc`; `link_flags()` is empty on Linux, `-lm` is the link tail. Flags from
`pipeline.opt_flags()`/`CFLAGS_TUNE` and `pyc.py`; read, not edited.)

Proposed:

```
cc -O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd \
   -Werror=implicit-function-declaration -Werror=implicit-int -Werror=incompatible-pointer-types \
   -fno-asynchronous-unwind-tables \
   -fstack-protector-strong -D_FORTIFY_SOURCE=2 -Wl,-z,relro,-z,now \
   -o OUT DIR/program.c -lm
```

| program | pie | nx | relro | canary | fortify | stripped bytes | instructions run (icount) | instructions in `.text` |
|---|---|---|---|---|---|---|---|---|
| `csv_sum` before | yes | yes | full | yes | 1 | 18648 | n/a | 1760 |
| `csv_sum` after | yes | yes | full | yes | 0 | 18648 | n/a | 1743 |
| `dict_count` before | yes | yes | full | yes | 2 | 30936 | n/a | 3825 |
| `dict_count` after | yes | yes | full | yes | 0 | 30936 | n/a | 3760 |

- **Output is unchanged** for both programs: byte-identical stdout and exit status on the fixtures,
  and the rebuilt binaries run normally.
- **Nothing improves.** PIE, NX, full RELRO and the canary were already there from the distro
  defaults; the three added flags add nothing.
- **`-D_FORTIFY_SOURCE=2` is a regression on this toolchain.** Ubuntu's gcc 13 already defines
  `_FORTIFY_SOURCE=3` at `-O2`; redefining it to 2 drops `__memcpy_chk` (`csv_sum`) and
  `__memcpy_chk`/`__memset_chk` (`dict_count`), so the counted `__*_chk` symbols go 1 -> 0 and
  2 -> 0. `__stack_chk_fail` stays.
- **File size does not move after `strip`** (18648 / 30936 both before and after), and unstripped
  the hardened binaries are 48 and 144 bytes smaller. `.text` is 48 and 192 bytes smaller; the
  difference is absorbed by section alignment in the stripped files.
- **Executed instruction counts are unavailable on this runner.** `tools/icount.c` builds, but
  `perf_event_open` returns `EACCES` (`perf_event_open: Permission denied`) because
  `/proc/sys/kernel/perf_event_paranoid` is 4 and the runner user cannot lower it (uid 1001, no
  sudo); `valgrind` and `qemu-x86_64` are not installed, so there is no fallback counter. The
  counts are reported as `n/a` rather than guessed.
  As a substitute, the static instruction count of `.text`
  (`objdump -d --no-show-raw-insn | count instruction lines`) is 1760 -> 1743 for `csv_sum` and
  3825 -> 3760 for `dict_count`: the hardened builds are *smaller* because the `__memcpy_chk` /
  `__memset_chk` call sites became plain `memcpy` / `memset`. A static count is not a run count and
  is not comparable across programs; it is here only to show the direction of the code-size change.

### What would actually be worth doing

1. **Nothing for PIE / NX / RELRO / canary**, as long as builds run on a distro whose gcc defaults
   are enabled. A runner or cross toolchain without them (Alpine/musl `gcc`, some minimal
   containers) would silently lose all four. If AIL wants this guaranteed rather than inherited, the
   flags to add are `-fPIE -pie -fstack-protector-strong -Wl,-z,relro,-z,now` - and that is a build
   change, out of scope here (this job only measures).
2. **Do not add `-D_FORTIFY_SOURCE=2`.** The default is already 3, which is strictly stronger.
   If a flag is wanted, it is `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3` to pin the level against a
   toolchain that defaults lower; cost 0 bytes, since 3 is what the binaries already get.
3. **`-fstack-protector-strong` explicitly** is the one cheap, portable insurance: it costs the
   `__stack_chk_fail` import and a few instructions per protected function and matches what the
   distro already does.
4. **Stripping** is an orthogonal size win (`strip`: 22416 -> 18648, 35008 -> 30936 bytes here),
   with no effect on these properties.

Costs: all four properties are already present, so the proposed flags buy nothing. The stripped file
size is unchanged (18648 / 30936 bytes) and `.text` shrinks by 48 and 192 bytes, entirely because
`-D_FORTIFY_SOURCE=2` removed the `__*_chk` call sites; that is the one measurable effect, and it is
a loss of fortification, not a gain. Executed instruction counts could not be taken on this runner.
