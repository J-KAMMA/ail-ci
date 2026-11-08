# Vendoring pure-Python packages (`ail_pkg.py`)

`AIL_CURRENT/ail_pkg.py` downloads one pure-Python wheel, verifies its SHA-256, vendors the
Python sources and `.dist-info` metadata, and pins the result in `ail.lock`. It never imports
or runs the downloaded package.

The `ail` command has no `add` hook in this change yet. Run the tool with its directory on
`PYTHONPATH`, from the project root:

```
PYTHONPATH=/path/to/AIL_CURRENT python3 -m ail_pkg add tabulate==0.9.0
PYTHONPATH=/path/to/AIL_CURRENT python3 -m ail_pkg add six==1.16.0 python-dateutil==2.9.0.post0
PYTHONPATH=/path/to/AIL_CURRENT python3 -m ail_pkg list
PYTHONPATH=/path/to/AIL_CURRENT python3 -m ail_pkg sync
PYTHONPATH=/path/to/AIL_CURRENT python3 -m ail_pkg remove tabulate
```

`python3 AIL_CURRENT/ail_pkg.py add ...` works too. Only `add` and a `sync` that has to refetch
a missing wheel use the network. The index is `https://pypi.org/pypi`; `AIL_PYPI_URL` overrides
it (the test points it at a local HTTP server). Downloads are allowed only from `pypi.org` and
`files.pythonhosted.org` (plus the local host of a test index).

## Layout

```
ail_packages/tabulate/0.9.0/tabulate/...
ail_packages/tabulate/0.9.0/tabulate-0.9.0.dist-info/...
.ail-wheels/tabulate-0.9.0-py3-none-any.whl   # verified wheel cache, so sync works offline
ail.lock
```

`ail.lock` records the exact version, wheel name, wheel SHA-256, size, `requires_python`,
licence (or `unknown`), direct requirements and a digest of the vendored tree. It is written
last and is the only source of exact versions and hashes.

`sync` installs exactly the lock: it re-extracts every wheel, checks the wheel SHA-256 and the
tree digest, replaces `ail_packages/`, and removes directories the lock does not name. A
tampered cached wheel stops with the two hashes in the message; it never installs the bytes.

## Refusals by name

`add` refuses: an sdist ("sdists run code at build time; AIL never does"), a platform wheel or
a wheel containing `.so`, `.pyd`, `.dll` or `.dylib` ("requires a C extension"), a pure wheel
tagged for Python 2 only ("no pure-Python wheel for Python 3"), a SHA-256 that does not match
the index or the existing lock, an absolute path, `..`, a symlink or a duplicate archive
entry, a malformed marker or requirement, a missing direct dependency, a dependency whose
version specifier the locked version does not satisfy, and two distributions that provide the
same top-level module.

Dependencies are direct-only: add a requirement before the package that needs it. The lock
records each requirement's specifier (`require_specs`) and both `add` and `sync` enforce it.
Extras are not activated. When the vendored tree of a locked package is missing, `add` names
it and asks for `sync` instead of crashing. Only `*.py`/`*.pyi` and `.dist-info` files are vendored, so a package that needs
non-Python data files at runtime may be incomplete; this revision targets the compiler census,
where every package is still refused at compile time.

## Building

`ail build` does not prepend the vendor roots yet. Put the package root on `AIL_PATH`:

```
AIL_PATH="$PWD/ail_packages/tabulate/0.9.0${AIL_PATH:+:$AIL_PATH}" \
  python3 -B AIL_CURRENT/ail_chatgpt.py compile src/main.py -o build/app
```
