# ail-lang

AIL is a Python-like language that compiles to standalone C executables.

    pip install ail-lang
    ail run prog.py            # compile to a temporary executable and run it
    ail build prog.py -o prog  # compile to an executable
    ail check prog.py          # type check only (no C compiler needed)
    ail doctor                 # which Python, which C compiler

`run` and `build` need a C compiler at run time: `cc`, `clang`, `gcc`, or `zig cc` (set `PIPE_CC` or
`AIL_ZIG` to choose one). The build cache is per user (`$AIL_CACHE`, else the platform cache
directory); `ail cache stats|path|clear` manages it.

The package carries the AIL compiler sources (the SDK export, `ail_sdk.py`) in `ail_lang/sdk`.

    ail new NAME               # a project: NAME/ail.toml, NAME/src/main.py
    ail build                  # inside a project: build/NAME (ail.toml, or [tool.ail] in pyproject.toml)
    ail build --debug          # -g -O0 with #line directives back to the source, for gdb
    ail lsp                    # language server on stdio: diagnostics and hover
