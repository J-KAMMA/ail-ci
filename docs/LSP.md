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
| `textDocument/hover` | On a diagnostic: its `write instead:` rewrite. Elsewhere: the type of a name the front end can name, or a function signature. |

Diagnostics carry the compiler message and its `write instead:` text. A source that does not load,
parse or type-check is an **Error**. A program the typed path refuses but the general path builds is
a **Warning** starting with `runs on the slow general path because ...` (this split needs a C
compiler). With `strict = true` in `ail.toml`, every typed-path blocker is an **Error**. Advisory
slow-pattern findings are **Information**.

The server checks the buffer through `ail check`, so unsaved edits get up-to-date diagnostics.
Imports, the project file and relative paths keep working because the buffer is checked beside the
real file. Hover types come from annotations and obvious initialisers (`x = 1`, `names = ["a"]`,
`total = value + 4`); the server does not invent a type when the front end cannot tell one.

## Prerequisites

Make sure the `ail` command is on `PATH`:

```sh
ail --version
ail lsp        # speaks LSP on stdin/stdout; run it from an editor, not a terminal
```

From a source checkout, use the module and point it at the SDK:

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
  "version": "0.1.0",
  "engines": { "vscode": "^1.80.0" },
  "activationEvents": ["onLanguage:python"],
  "main": "./extension.js",
  "dependencies": { "vscode-languageclient": "^9.0.0" }
}
```

`extension.js`:

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

```sh
export PYTHONPATH=/path/to/repo/packaging
export AIL_SDK_DIR=/path/to/repo/AIL_CURRENT
```

then use `cmd = { "python3", "-m", "ail_lang", "lsp" }`.

## Notes and troubleshooting

- The server is intentionally small: open/change/save/close, diagnostics and hover. It does not
  provide completion, definitions, formatting or code actions.
- Diagnostics for an imported module are published on that module's file, not only on the entry
  file.
- If nothing appears, check the server log of your editor and run `ail check path/to/file.py`
  manually. That is the same check the server runs.
- A file with no `main()` call, or a program that uses a construct outside the typed path, gets the
  compiler's own explanation and rewrite rather than a generic parser message.
