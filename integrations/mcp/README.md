# AIL MCP server

A minimal stdio MCP server for the AIL compiler. It has no network access and uses only the Python
standard library; the optional `mcp` package is imported lazily and is not required.

## Tools

| tool | what it does |
| --- | --- |
| `ailc_check(path)` | Runs `ail_chatgpt.py check` and returns its `ail.check/1` JSON diagnostics. No C build. |
| `ailc_build(path)` | Runs `ail_chatgpt.py compile --json`. Returns the artifact path, or the diagnostics and `agent_diagnostics` when the build fails. |
| `ailc_explain(path, function)` | Runs `ail_chatgpt.py build --cpython` and returns whether the function was accelerated; if not, the `rejected` reason. |

## Run

```sh
python3 integrations/mcp/ailc_mcp.py
```

The compiler defaults to `AIL_CURRENT/ail_chatgpt.py` in this checkout. Override it with
`AILC_COMPILER=/path/to/ail_chatgpt.py` or `AIL_SDK_DIR=/path/to/AIL_CURRENT`.

`AILC_MCP_NO_SDK=1` forces the built-in stdlib JSON-RPC loop, even when `mcp` is installed.

## Test

The tests are in `AIL_CURRENT/test_ail_agent_integrations.py` and run the tools on the three files
under `integrations/mcp/examples/`: `typed.py`, `mutates.py`, and `refused.py`.
