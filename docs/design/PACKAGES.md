# Packages: `ail add`, vendored PyPI wheels pinned by hash

Status: design + census, 2026-11-06 (ffpkg0). No compiler or CLI change is in this commit.

The goal is one command that makes a pure-Python PyPI package available to an AIL program
without a virtualenv, pip at build time, or a runtime Python:

```
ail add tabulate==0.9.0     # fetch, verify, vendor, pin
ail build                   # the project finds it through AIL_PATH
```

The rule stays "AIL may be faster than CPython, never different": vendoring only changes where
the source is read from at build time. It does not change the compiler's semantics, the search
order inside `ail_modules.py`, or the generated executable's dependency on any Python runtime.

## 0. Census result

`lab/pkg/census.py` classifies 30 popular, pure-Python wheels listed with exact versions in
`lab/pkg/packages.txt`. The full table and every first refusal are in `lab/pkg/RESULTS.md`.

- **built typed: 0**
- **built general: 0**
- **refused: 30**
- **output differs: 0**
- **classified: 30 / 30**

Every wheel is `*-none-any` (`pip download --no-deps --only-binary=:all:`); each was unpacked
into its own empty directory and never imported by the census. The probe is a short program
that imports the package and calls one function. AIL got the package root (plus `six` for
`python-dateutil` and `mdurl` for `markdown-it-py`) on `AIL_PATH`; CPython got the same roots on
`PYTHONPATH`. Both ran with `-S`, so the machine's site-packages could not hide a missing
dependency. A build counted as typed or general from the compiler's own fallback note; stdout
and the exit status were compared with CPython.

The result is 0/30, not a handful of near misses. The first blockers spread over the whole
language surface rather than one missing module:

| first blockers (examples) | packages |
| --- | --- |
| import merge / module-name binding | `wcwidth`, `art`, `markdown-it-py`, `six`, `toolz`, `rich`, `pytz`, `funcy`, `defusedxml`, `pyparsing` |
| unmodelled library or runtime call | `tabulate`, `toml`, `boltons`, `humanize`, `texttable`, `mdurl`, `idna`, `appdirs`, `pyfiglet`, `json5` |
| subset cut in a function shape | `more-itertools`, `semver`, `tomli`, `tomli-w`, `xmltodict`, `packaging` |
| import-time shape / decorator | `colorama`, `click`, `python-dateutil`, `pygments` |

No program printed something different from CPython; all 30 stopped at compile time, so the
census stop rule was not triggered. The table in `RESULTS.md` contains the complete first line
for each package, its wheel file name and its SHA-256.

Caveat: one representative call per package. A refusal inside a specific function (for example
`humanize.datetime.now` or `xmltodict`'s `**kwargs` call) does not prove every other call is
refused; a refusal in a package's `__init__.py` or module body does. The census measures "can
this package be used for an ordinary small CLI task today", not "is every function supported".

## 1. Layout

### Config (`ail.toml` or `[tool.ail]` in `pyproject.toml`)

Add one key to the existing project table:

```toml
name = "hello"
entry = "src/main.py"
dependencies = ["tabulate==0.9.0", "click==8.1.7"]
```

`dependencies` is a list of strings. `ail add` writes exact `==` pins, so the config is already
deterministic; the lock is still authoritative because it also hashes the wheel. `project.py`
accepts the key, rejects a wrong type, and keeps `ail.toml` winning over `[tool.ail]` as today.
`ail new` writes an empty `dependencies = []` line.

**Alternative rejected:** a separate `requirements.txt` is a second source of truth and has no
project root, entry or build options. **Alternative deferred:** `pyproject.toml` dependencies
(`[project].dependencies`) would conflate AIL packages with Python packaging requirements;
AIL's vendored tree is not importable by the build interpreter.

### Vendor tree

```
ail_packages/
  tabulate/0.9.0/
    tabulate/
    tabulate-0.9.0.dist-info/       # METADATA, licenses, RECORD
  click/8.1.7/
    click/
    click-8.1.7.dist-info/
ail.lock
```

The full wheel is unpacked below `ail_packages/<canonical-name>/<version>/`; the importable
top-level names sit at that directory's root, exactly as they do in a wheel root, so
`AIL_PATH=ail_packages/tabulate/0.9.0` behaves like `PYTHONPATH` pointing at the wheel.
Keeping `.dist-info` retains the license and provenance. The version directory makes updates
and removals atomic and lets two projects' trees be audited independently.

**Alternative rejected:** one flat `ail_packages/` (a second site-packages) makes deletion and
provenance ambiguous and turns two distributions that provide the same top-level name into an
invisible ordering bug. **Alternative deferred:** a content-addressed store under
`~/.cache/ail/packages/<sha256>/` with project symlinks saves disk on many projects, but adds a
cache to trust, garbage collection and Windows symlink problems; ffpkg1 does not need it.

`ail build`, `ail run` and `ail check` prepend the locked roots to `AIL_PATH` (before the
user's existing value), so `ail_modules.py` sees them in the existing "entry directory, then
AIL_PATH, then bundled stdlib" order. No search-order change is made in `ail_modules.py`.

Two distributions that expose the same top-level module name are refused by name at add/build
time, unless the user explicitly accepts a namespace package in a later revision. Silently
letting one win is the kind of order-dependent difference this repository forbids.

### Lock (`ail.lock`)

TOML, read by `tomllib` on 3.11+ and by the existing small reader's table/array subset on 3.10:

```toml
# generated by ail add; do not edit
version = 1

[package.tabulate]
version = "0.9.0"
wheel = "tabulate-0.9.0-py3-none-any.whl"
sha256 = "024ca478df22e9340661486f85298cff5f6dcdba14f3813e8830015b9ed1948f"
size = 34272
requires_python = ">=3.7"
license = "MIT"
requires = []
tree_sha256 = "..."
```

`tree_sha256` is a deterministic digest over the sorted vendored relative paths and file bytes.
It is extra to the required wheel SHA-256 and lets `ail build` verify the tree offline after
the wheel is gone. The lock is written last, after the vendor tree is in place, and is never
edited by hand.

**Alternatives:** JSON in `ail.lock` is easy to parse but not what Python projects expect;
TOML arrays of tables (`[[package]]`) need a reader extension on 3.10; a flat custom line format
diffs well but is not a standard format. The nested `[package.<canonical-name>]` table is TOML,
needs no new parser, and keeps names from `[-_.]` canonicalization dot-free.

## 2. Source: PyPI JSON and wheels only

`ail add NAME[==VERSION]` uses only:

1. `https://pypi.org/pypi/<name>/json` (or `/pypi/<name>/<version>/json` for a pin);
2. the `urls` entries in that JSON;
3. the wheel file from `files.pythonhosted.org`, fetched over HTTPS.

For a bare name, the highest non-yanked stable version with a compatible pure wheel is chosen.
For `==` the exact release is required. `requires_python`, if present, must accept the Python
running the compiler, because the compiler parses the package with that interpreter.

The selected file must be a wheel whose name ends in `-none-any.whl`. Its SHA-256 must equal
the JSON's `digests.sha256`; then it must equal the lock's value when a lock entry already
exists. A mismatch stops before anything is written. The download lands in a private temporary
directory and is unpacked into a new directory with a traversal/symlink check; the finished
tree is moved into `ail_packages/` with `os.replace`.

**Refused by name:**

- an sdist, or a release with no pure wheel: "sdists run code at build time; AIL never does";
- a platform wheel (`cp312-…`, `manylinux…`, `win_amd64…`) or a `*-none-any` wheel that contains
  `.so`, `.pyd`, `.dll` or `.dylib` files: "requires a C extension";
- a wheel whose `Requires-Dist` names a package not already in `dependencies` when the
  direct-only resolver is in use (see decision 4 below);
- a malformed/hostile archive: absolute path, `..`, symlink, hardlink, duplicate path.

**Alternatives rejected:** `pip download` at `ail add` time makes the tool depend on pip's
resolver and its build isolation (and on pip being installed in a minimal `ailc` environment);
`https://pypi.org/simple/` HTML parsing is less stable than the JSON API; sdists with a PEP 517
build step are exactly the untrusted-code path this task forbids.

The package is never imported or executed by `ail add`. `METADATA` is read with
`email.parser`; the wheel's `RECORD` is used only for file discovery and the tree digest.

`yanked` releases are never selected for a bare name. `requires_python` may exclude the host;
the JSON `version` must be the version named in the lock, not a normalized spelling that hides
a mismatch.

## 3. Packages that need C extensions

**Decision: refuse them by name in ffpkg1.** The message names the package and the reason
(`no pure-Python wheel`, or `wheel contains extension module X`), and points at the future
hybrid path. No platform wheel is downloaded, unpacked or locked.

**Alternative (later): route to the CPython hybrid.** A `cpyhyb*` build can run the original
package inside CPython and accelerate selected pure functions; a platform wheel could then be
locked per target. That is a different build product and a different trust story (it needs a
Python runtime), so it must not be the default `ail add` behaviour. When it lands, the lock
will need a wheel tag and platform key next to the current pure-wheel entry.

**Alternative rejected:** attempt to compile the extension's C source with gcc. That is a new
build system (include paths, Python C API, ABI), not a packaging feature.

## 4. Dependency resolution

`Requires-Dist` is read from the wheel's `METADATA`. Environment markers are evaluated only
with the markers the compiler knows (`python_version`, `sys_platform`, `os_name`,
`platform_machine`); an unknown marker is a refusal by name, never a guess.

**Recommendation for ffpkg1: direct-only, closure-checked.** `ail add` vendors the named
distribution, records its non-optional `Requires-Dist` in the lock, and refuses if a requirement
is not already present in `dependencies` (the error tells the user to `ail add` it next).
`ail build` verifies that every `requires` entry of every locked package is itself locked.
This is deterministic, easy to review, and needs no PEP 440 resolver. The census's all-refused
result means a full resolver is not the critical path.

**Alternative (ffpkg2): a small resolver** over the JSON API, choosing the highest version that
satisfies every collected specifier. It needs a PEP 440 version parser and specifier matcher,
backtracking for conflicts, and a policy for extras. That is a larger, riskier component; it
should not delay the lock/vendor/hash core.

Extras requested in a requirement are refused by name in ffpkg1 (the wheel metadata's extra
requirements are not activated).

## 5. The `ail add` hook and ffpkg1 files

The only new command dispatch in `packaging/ail_lang/cli.py` is:

```python
if command == "add":
    return ail_pkg.add(rest)
```

with `ail_pkg` added to the existing relative import. Build/run/check also need the vendor
roots in `AIL_PATH`; that is one line in `_env()` calling `project.package_dirs(Path.cwd())`
(or an equivalent `project` helper). `ail add` is the only command hook in `cli.py`; the
environment line is the `AIL_PATH` integration, not a second command.

Files ffpkg1 creates:

- `packaging/ail_lang/ail_pkg.py` — PyPI JSON client, wheel selection, download/hash,
  safe extraction, `ail.lock` reader/writer, `ail add`, `ail licenses`, tree verification.
  Standard library only; no import of the vendored code.
- `AIL_CURRENT/test_ail_pkg.py` — local fake-index tests: exact pin, bare-name selection,
  yanked rejection, sdist refusal, platform/C-extension refusal, SHA-256 mismatch, traversal
  and symlink rejection, lock round trip, dependency-closure check, tree digest mismatch,
  `AIL_PATH` integration. No network: a `file://` fake index and fixture wheels in a
  temporary directory.
- `AIL_CURRENT/tests.d/test_ail_pkg.txt` — the module name for the normal test runner.
- `docs/PACKAGES.md` — user-facing `ail add` / `ail.lock` / `ail licenses` documentation.
- `examples/packages/` — a small project whose dependencies are checked in as a fixture, used
  by the wheel smoke test.

Files ffpkg1 edits:

- `packaging/ail_lang/project.py` — add the `dependencies` key, read the lock, expose
  `package_dirs()` and a verification hook.
- `packaging/ail_lang/cli.py` — the add dispatch above and the `_env()` `AIL_PATH` line.
- `packaging/README.md`, `AIL_CURRENT/test_ail_project.py` and
  `AIL_CURRENT/test_ail_packaging.py` — document and test the new project key and lock.
- Manifest files written by `tools/update_manifest.py` (never by hand).

## 6. Owner decisions

| decision | alternatives | recommendation |
| --- | --- | --- |
| **Network use by the tool** | (a) `ail build/run/check` fetch missing packages; (b) only `ail add` fetches, everything else is offline; (c) never fetch, require a user-supplied wheel | **(b)**. `ail add` is explicit network consent. `ail build/run/check` use only the lock and vendor tree and fail with "run ail add" when something is missing, so a build is reproducible and can run on a disconnected machine. Hosts are allowlisted to `pypi.org` and `files.pythonhosted.org`; package metadata URLs are never followed elsewhere. |
| **Where the lock lives** | (a) project root `ail.lock`; (b) inside `ail_packages/`; (c) only in `ail.toml` | **(a)**. One lock per project, next to `ail.toml`/`pyproject.toml`, committed with it. It is the only source of exact versions and hashes; config carries the human constraints. `ail_packages/` is derived data and may be regenerated. |
| **Licence display** | (a) only print at `ail add`; (b) only on `build`; (c) never, only copy files | **(a) plus a command**. `ail add` prints one line per package with name, version, licence and SHA-256 prefix, because that is the moment the user makes a redistribution decision. `ail licenses` lists the same for the lock and the path to the copied licence file. `ail build` prints nothing extra, so its diagnostics stay focused. Unknown metadata prints `unknown` and a warning, never a guessed licence. |
| **Transitive dependencies** | (a) direct-only with a closure check; (b) full resolver now | **(a) in ffpkg1**, **(b) later**. See decision 4. |
| **C extensions** | (a) refuse; (b) platform wheel + CPython hybrid | **(a) now**, **(b) when `cpyhyb` can make the same program observable behaviour**. |
| **Version syntax in `ail.toml`** | (a) exact `==` only; (b) PEP 440 ranges | **(a) in ffpkg1**. `ail add NAME` resolves once and writes an exact pin. Ranges can come with the resolver; a range without a lock entry is refused by name. |
| **Integrity at build time** | (a) trust the vendor tree; (b) wheel SHA-256 only; (c) wheel SHA-256 + tree digest | **(c)**. The wheel hash is required by the brief; the tree digest makes an offline build check the actual files that will be compiled. |
| **Unknown/hostile metadata** | (a) best-effort; (b) refuse | **(b)** for archive shapes, hashes, missing dependencies and unknown markers; **best-effort only** for `license` (display), where an absent field is not a security problem. |

## 7. What the census means for the roadmap

The packaging layer is not the bottleneck: even with a perfect lock and vendor tree, 0/30 of
this sample would build today. The next compiler work should come from the blockers in
`RESULTS.md`, not from a larger resolver. The most repeated, highest-leverage ones are:

1. module name binding: a submodule and a same-named attribute (`wcwidth`, `art`,
   `markdown-it-py`) and `import x` plus `x = ...` in one module (`six`, `toolz`, `rich`,
   `pytz`, `funcy`, `defusedxml`);
2. `functools.partial` with a callable instance and required keyword-only parameters (the
   `more-itertools` / `semver` / `tomli` family);
3. the `os.linesep`/`os.environ`/`datetime.now`-style general-path holes (`toml`, `humanize`);
4. nested `try: import` branch selection (`appdirs`) and `**kwargs` calls (`xmltodict`).

These are compiler/library gaps, not reasons to weaken the packaging design. The lock and
vendor tree can land first and stay useful while the compiler catches up.

## 8. Untrusted-files rule

The census and `ail add` both treat downloaded wheels as hostile data:

- each wheel is downloaded into a fresh private directory and unpacked into a new directory;
- the tool never imports or executes a package, `setup.py`, a `.pth` file or a `.data` script;
- `python3 -I` (or `-S` for the oracle, which needs `PYTHONPATH`) keeps the census interpreter
  away from the downloaded tree; the compiler is run with `-S` as well;
- extraction rejects absolute paths, `..`, symlinks, hardlinks and duplicate entries;
- only `METADATA`, `RECORD` and importable source files are read;
- the resulting `ail_packages/` tree is still untrusted source: the generated executable runs
  that code with the program's privileges. A hash proves which bytes were chosen, not that
  they are safe.

The census downloads only with `--no-deps --only-binary=:all:` and one wheel per package, and
uses a 1.5 GB address-space cap and one build at a time. It stops and records a reproducer if a
built program ever prints different output from CPython.
