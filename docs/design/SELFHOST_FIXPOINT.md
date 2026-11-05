# Self-hosting fixpoint check

Status: design (2026-11-05). No compiler file is edited by this document; the measurement it
rests on is `lab/selfhost/DETERMINISM.md` and `tools/c_determinism.py`.

The goal is a check that the AIL compiler, rewritten in AIL, reproduces itself exactly. "Exactly"
means **the generated C bytes**, not the binaries: C is what the compiler produces, and two
builds of the same bytes by the same `cc` are the same program. Comparing binaries would make the
check depend on the linker, the C library and the build directory, which are not the compiler.

## 1. Stages

| stage | what runs | what it produces | what is compared |
|-------|-----------|------------------|------------------|
| 0 | `cc` on the committed seed (`selfhost/seed/program.c`) | seed compiler binary | seed C bytes vs. stage-2 C bytes |
| 1 | CPython 3.12 running the AIL-written compiler source (`selfhost/compiler.ail`) | `C1 = compiler(P)`, then a stage-1 binary | `C1` vs. `C2` |
| 2 | the stage-1 binary compiling the same compiler source | `C2 = compiler(P)` | `C2` vs. `C1`, and `C2` vs. seed |
| 2' | the stage-2 binary compiling the compiler source again | `C3` | `C3` vs. `C2` (the fixpoint) |

`P` is the compiler source for the self-host check and one named module for the small first
fixpoint (section 4). At every arrow only `program.c` is compared, byte for byte with `cmp` or a
SHA-256 over the file; the linked binary is built only because stage 2 needs a compiler to run.

Stage 0 exists so the chain is not circular: the seed was produced by a named compiler version and
is checked in, and CI only verifies that the seed still equals what stage 2 emits. A change to the
compiler necessarily changes stage 2's output and therefore fails the seed comparison; regenerating
the seed is a separate, explicit commit (section 2).

Stage 1 must run under CPython with `AIL_NO_CACHE=1`, `PYTHONDONTWRITEBYTECODE=1` and a fixed
`PYTHONHASHSEED`; otherwise a stage-1/stage-2 difference could come from the host process rather
than from the compiler. Stage 2 runs in the same working directory with the same environment
except that the compiler is a binary; the `--debug-dir` and `-o` paths differ (the harness checks
that they are not embedded in the C; see rule D2 below).

## 2. The seed

Committed files, all produced by one command and never edited by hand:

- `selfhost/seed/compiler.c` — the C that stage 2 emitted for `selfhost/compiler.ail`;
- `selfhost/seed/compiler.c.sha256` — its digest, so a one-line diff shows when the seed moves;
- `selfhost/seed/PROVENANCE.md` — the compiler commit, the command and the date that produced it.

Regeneration is explicit and never part of a normal build:

```
python3 tools/selfhost_fixpoint.py --update-seed
```

`--update-seed` runs stages 1 and 2, requires `C1 == C2` (an unfixed compiler may not move the
seed), then writes the three files above and prints the new digest. CI never passes
`--update-seed`; the flag exists for a human on a branch, and the resulting seed change is reviewed
like any other generated file.

CI proves the committed seed equals stage 2 by running the check without `--update-seed`:

```
python3 tools/selfhost_fixpoint.py --check-seed
```

which fails when `sha256(selfhost/seed/compiler.c) != sha256(C2)` and prints the first differing
line of the two files.

## 3. Determinism rules the compiler must keep

The check is worthless if the compiler already emits different C for the same source from run to
run. `lab/selfhost/DETERMINISM.md` measured the current compiler over 30 programs, three builds
each, varying `PYTHONHASHSEED`, the output directory and the working directory: **26 of 30 programs
and 34 of 34 comparable program-mode pairs were identical, and no difference of any class was
observed.** The rules below are therefore preconditions for the fixpoint, not fixes for measured
findings; each is stated so the probe's class names map onto a rule the day one appears.

- **D1 — hash order.** Emit anything derived from a set or dict of strings only after sorting it
  (`sorted(...)`) or after walking a list that was built in source order. Two runs with different
  `PYTHONHASHSEED` must produce the same emitter order. *Class: hash order.*
- **D2 — absolute paths.** Generated C must not contain the source path, the `--debug-dir`, the
  `-o` path or the current working directory. Diagnostics may name a path on stderr; `program.c`
  may name only the source file's basename, if anything. *Class: absolute path.*
- **D3 — temporary names.** No `tempfile` name, PID or random suffix may reach `program.c`.
  Emitted symbol names are derived from source names and a counter that is reset per compilation.
  *Class: temporary name.*
- **D4 — time.** No timestamp, date or elapsed time in the C, including in banners and comments.
  A version banner may carry a hand-maintained constant. *Class: time.*
- **D5 — counters.** Any generated name numbered by a counter must be assigned in a traversal
  order that is independent of hash order and of process identity (the counter itself is fine; an
  order that changes is not). *Class: counter.*
- **D6 — everything else.** A difference not in D1–D5 is treated as a bug until classified; the
  check reports the class so the fix can add a rule here. *Class: other.*

## 4. First fixpoint: one small module

`lab/selfhost/CENSUS.md` names compiler files by accepted-function count, not a leaf module that
builds whole with no refusals. The smallest stdlib module that does build whole under `--strict`
with no refusal note is `AIL_CURRENT/stdlib/keyword.py` (verified 2026-11-05: exit 0, no `note:`
line, `program.c` 15,880 bytes). It is the first target:

```
# stage 1: CPython running the AIL compiler, emitted C for the module
python3 -B AIL_CURRENT/ail_chatgpt.py compile AIL_CURRENT/stdlib/keyword.py \
    -o /tmp/fx/s1/kw --strict --debug-dir /tmp/fx/s1/dbg
# C1 = /tmp/fx/s1/dbg/program.c

# stage 2: the same compiler built by AIL, emitting C for the same module
/tmp/fx/s1/kw compile AIL_CURRENT/stdlib/keyword.py \
    -o /tmp/fx/s2/kw --strict --debug-dir /tmp/fx/s2/dbg
# C2 = /tmp/fx/s2/dbg/program.c

cmp /tmp/fx/s1/dbg/program.c /tmp/fx/s2/dbg/program.c
```

The first command is the existing compiler today; the second command is the same command with a
compiled compiler, so the second step turns on only when `selfhost/compiler.ail` can build itself.
Until then the harness runs the same two commands with the CPython-hosted compiler on both sides:
that is a determinism dry run, not a fixpoint, and it is labelled as such in the report.

Expected cost: one `keyword.py` build measured at 2.5 s and 165 MB peak RSS, two stages plus a
`cc` link of the seed take under 10 s. In CI that is **0.2 minutes** on one shard, well under the
existing shard weights; the full compiler fixpoint (section 1) is four compiler builds, budget
**5 CI minutes** and no more than 1.5 GB RSS (`ulimit -v 1500000`).

## 5. What happens when a diff appears

- The check fails, exits non-zero, and prints the **first differing line** of `C1` and `C2` with
  its number, plus the SHA-256 of both files and the `tools/c_determinism.py` class of the
  difference. It never prints a thousand-line diff.
- It never updates the seed, rewrites `selfhost/seed/`, or writes into the source tree. The only
  writable directories are the CI temporary directories, removed afterwards.
- A stage-1/stage-2 difference is a compiler finding: the branch that changed the compiler owns
  it. A seed-only difference (stage 1 == stage 2 but the committed seed differs) means the seed is
  stale and must be regenerated in its own commit with `--update-seed`.
- A determinism failure inside one stage (the same stage run twice differs) is reported separately
  and blocks the fixpoint verdict, because stage 2's C cannot be compared to a moving target.
- The check never skips on a missing `cc`: it fails loudly (a fixpoint without a C compiler is not
  a fixpoint), unlike the ratchet test in section 6.

## 6. The ratchet in the test suite

`AIL_CURRENT/test_ail_c_determinism.py` is the cheap, always-on half. It builds three small
programs twice with `PYTHONHASHSEED=0` and `1` and asserts byte-identical `program.c` **only for
the programs `lab/selfhost/DETERMINISM.md` lists as identical**. Programs listed with a difference
class are not asserted, so the test never fails for known, recorded nondeterminism; when a fix
lands, the new identical row must be added to the document and the ratchet tightens. The test
skips without a C compiler.

## 7. Open questions for the owner

1. Which compiler commit is authoritative for the first seed — the base of this branch, or the
   first commit where `selfhost/compiler.ail` builds itself? The document assumes the latter.
2. Should the seed live in the repository (large, binary-ish blob) or be fetched from a release
   artifact pinned by digest? The former is simpler; the latter keeps the tree small.
3. Is `keyword.py` the right first module, or is a module with accepted functions in
   `lab/selfhost/CENSUS.md` (`prelude_array.py`) a better signal even though it still has refusals?
4. May the fixpoint check require a specific `cc` and C library version, or must C be compared
   only (which is version-independent) and the binary build be best-effort?
5. Should a stage-1/stage-2 difference fail the whole PR or only a non-blocking job until the
   compiler is fully self-hosting?
