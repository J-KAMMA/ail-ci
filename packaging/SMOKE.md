# Install smoke test: the `ailc` wheel on clean Linux images

Run it with:

    python3 tools/install_smoke.py                 # the 8 pinned images plus the no-compiler case
    python3 tools/install_smoke.py --images python:3.12-slim-bookworm
    python3 tools/install_smoke.py --engine podman --keep

The script builds the wheel once on the host (`pip wheel . --no-deps --no-build-isolation`), then starts each
image with `docker run --rm --memory=1500m` (or podman), a fresh venv in `/tmp`, `pip install --no-index
/w/*.whl`, and the checks. Each image has a 10-minute timeout; pulls are allowed. A check prints one
`CHECK name PASS|FAIL first-error-line` line, the script parses those lines, prints the table, and exits 0 only
when every check passes. The checkout is mounted read-only at `/src` for the tutorial check.

Date: 2026-11-04
Commit under test: `2a97c41` (tools/install_smoke.py; the wheel was built from that working tree)
Runner: GitHub Actions Linux runner, Docker 28.0.4, glibc host.

## Results

Checks: `version` = `ail --version`, `doctor` = `ail doctor --check`, `hello` = `ail run` of hello world compared
with the image's `python3`, `typed` = typed `fib` plus `print(2**62 + 2**62 - 1)` compared with the image's
`python3`, `tutorial` = `/tmp/v/bin/python /src/AIL_CURRENT/test_ail_tutorial.py` with
`AIL_TUTORIAL_AIL=/tmp/v/bin/ail`.

| image | Python | libc | version | doctor | hello | typed | tutorial | wall s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| python:3.10-slim-bookworm | 3.10.22 | ldd (Debian GLIBC 2.36) | PASS | PASS | PASS | PASS | PASS | 19.9 |
| python:3.11-slim-bookworm | 3.11.18 | ldd (Debian GLIBC 2.36) | PASS | PASS | PASS | PASS | PASS | 19.6 |
| python:3.12-slim-bookworm | 3.12.16 | ldd (Debian GLIBC 2.36) | PASS | PASS | PASS | PASS | PASS | 19.4 |
| python:3.13-slim-bookworm | 3.13.18 | ldd (Debian GLIBC 2.36) | PASS | PASS | PASS | PASS | PASS | 21.2 |
| debian:12 | 3.11.2 | ldd (Debian GLIBC 2.36) | PASS | PASS | PASS | PASS | PASS | 24.7 |
| ubuntu:24.04 | 3.12.3 | ldd (Ubuntu GLIBC 2.39) | PASS | PASS | PASS | PASS | PASS | 27.9 |
| fedora:41 | 3.13.9 | ldd (GNU libc) 2.40 | PASS | PASS | PASS | PASS | PASS | 26.9 |
| alpine:3.20 | 3.12.13 | musl libc (x86_64) | PASS | PASS | PASS | PASS | PASS | 21.6 |
| nocc (python:3.12-slim-bookworm, nothing installed) | 3.12.16 | ldd (Debian GLIBC 2.36) | PASS | PASS* | PASS* | SKIP | SKIP | 4.4 |

The musl image (`alpine:3.20`) passes all five checks, including the typed path and the int64 edge.

`nocc` is the expected-failure case, so its columns mean: `doctor` PASS = `ail doctor --check` exited non-zero
and named the missing C compiler; `hello` PASS = `ail run /c/hello.py` failed with a message and no traceback.
The exact output is below.

## Findings

No image failed a packaging check. There is no packaging bug to record.

No-compiler case (`python:3.12-slim-bookworm`, no `gcc`/`cc`/`clang`/`zig`):

* `ail doctor --check` exits 2 and its JSON report has `"c_compiler": null`, `"c_compiler_available": false`,
  and `"build_check": {"status": "failed", "phase": "configuration",
  "message": "C compiler is unavailable: None"}`.
* `ail run /c/hello.py` exits 2; stderr begins with exactly:

      ail: no C compiler found.

      AIL compiles programs to C, so `ail run` and `ail build` need one of: cc, clang, gcc, zig cc.
      Looked for them on PATH (and for zig via $AIL_ZIG or PATH).

  It then prints the install hints and ends with `` `ail check` does not need a C compiler. ``. There is no
  Python traceback.

Harness note, not a packaging failure: the first Fedora 41 run reported `hello` and `typed` as `FAIL stdout
differs from CPython` even though both outputs were byte-identical. Fedora's `coreutils` does not ship `cmp`
(it is in `diffutils`), and the check script had used `cmp -s`. The script now compares the two files with the
image's own `python3`; Fedora then passed. No package was added to the image, so the pin list in the script
still matches the task's package list.
