# argparse programs: build and CPython comparison

Built with `python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python -o X`
(default mode, no `--strict`, no `--exact-int`), from the repository root.

| program | result | CPython stdout / exit code |
| --- | --- | --- |
| backup.py | general | same (test_ail_std_argparse) |
| calc.py | general | same (test_ail_std_argparse) |
| config.py | general | same (test_ail_std_argparse) |
| errtool.py | refused | follow-up 1 |
| greet.py | general | same (test_ail_std_argparse) |
| helpfmt.py | general | same (test_ail_std_argparse) |
| scan.py | general | same (test_ail_std_argparse) |
| search.py | general | same (test_ail_std_argparse) |
| server.py | general | same (test_ail_std_argparse) |
| subcmd.py | refused | follow-up 2 |
| tag.py | general | same (test_ail_std_argparse) |
| words.py | general | same (test_ail_std_argparse) |

10 of 12 build. The ten building programs are compared with CPython 3.12 on the default build and on
the forced general path (`AIL_UNIFIED_FORCE=1`) by `AIL_CURRENT/test_ail_std_argparse.py`, including
defaults, `nargs`, `append` / `append_const` / `count` / `store_const`, `choices`, `type=int/float/str`,
mutually exclusive groups, help / version and the error exits. Stdout and exit code match everywhere;
stderr also matches for every successful run. The programs are not modified.

All ten build on the general path (not typed) because `argparse.Namespace._ail_set()` receives bools,
ints, strings and lists through one parameter. That is a speed note, not a refusal: the general path
builds and the output is identical.

## Follow-ups (exact first refusal text)

### 1. errtool.py: a program that catches `SystemExit`

```
AIL_CURRENT/stdlib/argparse.py:173:5: not in the subset: parameter `value` of argparse.Namespace._ail_set() gets a bool from some calls and a number from others; Python keeps each value's own type and a number would print as 1 / 0 (the general path could not build this program either); general path: a caught exception type SystemExit (only builtin or user Exception subclasses are supported)
  write instead: pass the same kind everywhere (`int(flag)` or a comparison)
```

The root cause is the `except SystemExit` in the program: catching a `BaseException` subclass is a new
feature (the general path only builds caught builtin or user `Exception` subclasses). `SystemExit` from
`parser.error()` / `--help` is the natural argparse error path, so this is the most valuable follow-up.
The program itself is left unchanged.

### 2. subcmd.py: subcommands

```
AIL_CURRENT/stdlib/argparse.py:173:5: not in the subset: parameter `value` of argparse.Namespace._ail_set() gets a bool from some calls and a number from others; Python keeps each value's own type and a number would print as 1 / 0 (the general path could not build this program either); general path: the method .add_subparsers() (on a instance:argparse.ArgumentParser)
  write instead: pass the same kind everywhere (`int(flag)` or a comparison)
```

The root cause is `ArgumentParser.add_subparsers()` (subparsers, their own parsers, `dest` and
`required`): a new feature, out of scope here. The program itself is left unchanged.
