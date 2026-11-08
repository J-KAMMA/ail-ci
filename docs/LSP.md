# AIL language server (`ail lsp`)

`ail lsp` is a small Language Server Protocol server on standard input/output. It uses JSON-RPC 2.0
with `Content-Length` framing and needs only the Python standard library, so it is part of the
normal `ail` installation.

## What it does

| LSP request / notification | Behaviour |
| --- | --- |
| `initialize` / `shutdown` / `exit` | Standard lifecycle. `exit` without `shutdown` returns status 1. |
| `textDocument/didOpen` | Checks the buffer and publishes diagnostics. |
| `textDocument/didChange` | Full sync (`textDocumentSync.change = 1`); checks the edited buffer. |
| `textDocument/didSave` | Re-checks the file on disk (or the text sent with the save). |
| `textDocument/didClose` | Clears the diagnostics for the closed document. |
| `textDocument/publishDiagnostics` | Diagnostics from the same `ail check` front end that `ail build` uses. |
| `textDocument/hover` | On a diagnostic: its `write instead:` rewrite. Elsewhere: a function signature, an annotation, a certain literal type, a type the typed path inferred, or nothing. |
| `textDocument/definition` | The binding of the name at the cursor: a local, parameter, function, class, method through `self.m()` or through a local name bound to a class or an instance of a class in the same file, or a name imported from another module. Every binding of a name with several assignments is returned; when the target is not certain the answer is `null`. |

Diagnostics carry the compiler message and its `write instead:` text. A source that does not load,
parse or type-check is an **Error**. A program the typed path refuses but the general path builds is
a **Warning** starting with `runs on the slow general path because ...` (this split needs a C
compiler). With `strict = true` in `ail.toml`, every typed-path blocker is an **Error**. Advisory
slow-pattern findings are **Information**.

The server checks the buffer through `ail check`, so unsaved edits get up-to-date diagnostics.
Imports, the project file and relative paths keep working because the buffer is checked beside the
real file; in a read-only directory it is checked in a temporary directory with the real directory
first on `AIL_PATH`.

Hover shows a type when it is certain:

* a function name shows its signature as written;
* a parameter or a name with an annotation shows the annotation text;
* a name whose every assignment in its scope is a literal of one type (`int`, `float`, `str`,
  `bytes`, `bool` or `None`) shows that type;
* a name the typed path gives a local type shows `` `x`: `float` (inferred by the typed path) ``.
  The type comes from the C declarations of a `--debug` build (`int64_t` -> `int`,
  `double` -> `float`, the list, str and dict structs), and only where the C type maps to one
  Python type. A name the compiler boxes because it is assigned two different types, a numeric
  sum (`sum(...)`, which is an int or a float at run time), and an unannotated name whose C
  `int64_t` could be either `int` or `bool` show nothing. The `int64_t` disambiguation reads the
  source, so it trusts a list or dict literal's items only while nothing mutates that container:
  an item store, `del`, a method call such as `append` or `update`, a call that receives the name,
  or an alias assignment makes the item type unknown. The build is cached per document version and
  runs only after `didSave` or 1 s idle, never on every keystroke.

Every other name shows nothing, including a name on the general path (for example the `int | None`
review function), `b"a b".split()`, `range(3)`, an attribute (`obj.x`) or a keyword label
(`f(x=x)`), and any position inside a string or a comment. A wrong type is worse than no type.

Go-to-definition uses the same scope analysis. It follows the compiler's import search order (the
program's directory, then `AIL_PATH`, then the bundled `AIL_CURRENT/stdlib/`) and reads the open
buffer of every open document. A name with several assignments in one scope answers all of them; an
attribute of an unknown object, a builtin, a name inside a string or a comment, and any target that
is not certain answer `null`.

## Prerequisites

Make sure the `ail` command is on `PATH`:

<!-- docs-test: skip ail lsp is an interactive stdin/stdout server; run it from an editor -->
```sh
ail --version
ail lsp        # speaks LSP on stdin/stdout; run it from an editor, not a terminal
```

From a source checkout, use the module and point it at the SDK:

<!-- docs-test: skip starts the interactive server on stdin/stdout; an editor supplies the requests -->
```sh
python3 -m ail_lang lsp
# with PYTHONPATH=/path/to/repo/packaging and AIL_SDK_DIR=/path/to/repo/AIL_CURRENT
```

`ail check` needs no C compiler. The Warning/Error split for a typed-path refusal builds the
program once, so it needs `cc`, `clang`, `gcc`, or Zig; without one the server emits a Warning that
says it cannot tell whether the general path builds the program.

## VS Code (generic LSP client)

VS Code does not launch arbitrary language servers by itself, so use a generic LSP client extension
or a tiny extension of your own. A minimal extension with `vscode-languageclient` is:

`package.json`:

```json
{
  "name": "ail-lsp",
  "version": "0.1.0.dev0",
  "engines": { "vscode": "^1.80.0" },
  "activationEvents": ["onLanguage:python"],
  "main": "./extension.js",
  "dependencies": { "vscode-languageclient": "^9.0.0" }
}
```

`extension.js`:

<!-- docs-test: skip VS Code extension source; it needs VS Code and its extension host to run -->
```js
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;

function activate(context) {
  const server = {
    command: "ail",
    args: ["lsp"],
    transport: TransportKind.stdio,
  };
  client = new LanguageClient("ail", "AIL Language Server", server, {
    documentSelector: [{ scheme: "file", language: "python" }],
  });
  context.subscriptions.push(client.start());
}

function deactivate() {
  return client ? client.stop() : undefined;
}

module.exports = { activate, deactivate };
```

Install the dependency (`npm install`) and press F5 in the extension folder to open an Extension
Development Host. Open a folder containing the `.py` file (and optionally `ail.toml`); diagnostics
appear after the first open or save, and hover works over names. If `ail` is not on the `PATH` seen
by VS Code, set `command` to the absolute path of the executable. A source checkout can use:

<!-- docs-test: skip client-side VS Code configuration fragment; it needs VS Code to run -->
```js
const server = {
  command: "python3",
  args: ["-m", "ail_lang", "lsp"],
  transport: TransportKind.stdio,
  options: {
    cwd: "/path/to/repo",
    env: { ...process.env, PYTHONPATH: "/path/to/repo/packaging",
           AIL_SDK_DIR: "/path/to/repo/AIL_CURRENT" },
  },
};
```

Generic LSP-client extensions work too: configure the server command as `ail` with argument `lsp`,
transport **stdio**, and the document selector `python`.

## Neovim (`vim.lsp.start`)

Neovim 0.10 or newer can start the server directly. Add this to `init.lua`:

<!-- docs-test: skip Neovim configuration; it needs Neovim and starts an editor -->
```lua
local function ail_root()
  local found = vim.fs.find({ "ail.toml", "pyproject.toml" }, { upward = true })[1]
  return found and vim.fs.dirname(found) or vim.fn.getcwd()
end

vim.api.nvim_create_autocmd("FileType", {
  pattern = "python",
  callback = function()
    vim.lsp.start({
      name = "ail",
      cmd = { "ail", "lsp" },
      root_dir = ail_root(),
      capabilities = vim.lsp.protocol.make_client_capabilities(),
    })
  end,
})
```

`vim.lsp.start` attaches to the current buffer and reuses one client per `root_dir`. Diagnostics
are in `vim.diagnostic` (see `:lua vim.diagnostic.open_float()`), and hover is available with
`K` (`vim.lsp.buf.hover()`).

For a source checkout, point the command at the module and set the environment before starting
Neovim, for example:

<!-- docs-test: skip environment setup for an editor with placeholder paths; not a command sequence -->
```sh
export PYTHONPATH=/path/to/repo/packaging
export AIL_SDK_DIR=/path/to/repo/AIL_CURRENT
```

then use `cmd = { "python3", "-m", "ail_lang", "lsp" }`.

## Notes and troubleshooting

- The server is intentionally small: open/change/save/close, diagnostics, hover and definitions. It
  does not provide completion, formatting or code actions.
- Diagnostics for an imported module are published on that module's file, not only on the entry
  file.
- If nothing appears, check the server log of your editor and run `ail check path/to/file.py`
  manually. That is the same check the server runs.
- A file with no `main()` call, or a program that uses a construct outside the typed path, gets the
  compiler's own explanation and rewrite rather than a generic parser message.
