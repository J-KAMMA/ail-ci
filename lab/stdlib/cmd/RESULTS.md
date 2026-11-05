# `cmd` coverage results

Build command for every program:

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/cmd/<program>.py -o <output>
```

The oracle is `python3 <program>.py`, with the matching `.in` file on stdin when there is one
(CPython 3.12.3). Every listed program is compared by stdout and exit status on the default
build and again with `AIL_UNIFIED_FORCE=1`.

## Before

All ten programs were refused at the import. The common first-refusal prefix `P` was:

```
not in the subset: import of 'cmd' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general
path could not build this program either); general path: a non-name base class in class
```

| program | default build | first refusal before the fix |
| --- | --- | --- |
| `01_hello_commands.py` | refused | `P Greeter` |
| `02_unknown_and_empty.py` | refused | `P EchoShell` |
| `03_emptyline_override.py` | refused | `P QuietShell` |
| `04_hooks.py` | refused | `P HookShell` |
| `05_help.py` | refused | `P HelpShell` |
| `06_parseline.py` | refused | `P ParseShell` |
| `07_cmdqueue.py` | refused | `P CountShell` |
| `08_onecmd.py` | refused | `P DirectShell` |
| `09_calculator.py` | refused | `P Calculator` |
| `10_aliases.py` | refused | `P AliasShell` |

Result: **0 built, 0 typed, 10 refused**.

## After

| program | default build | `AIL_UNIFIED_FORCE=1` | CPython stdout + exit |
| --- | --- | --- | --- |
| `01_hello_commands.py` | general, matches | general, matches | same, exit 0 |
| `02_unknown_and_empty.py` | general, matches | general, matches | same, exit 0 |
| `03_emptyline_override.py` | general, matches | general, matches | same, exit 0 |
| `04_hooks.py` | general, matches | general, matches | same, exit 0 |
| `05_help.py` | general, matches | general, matches | same, exit 0 |
| `06_parseline.py` | general, matches | general, matches | same, exit 0 |
| `07_cmdqueue.py` | general, matches | general, matches | same, exit 0 |
| `08_onecmd.py` | general, matches | general, matches | same, exit 0 |
| `09_calculator.py` | general, stops loudly | general, stops loudly | CPython prints the value and continues, exit 0 |
| `10_aliases.py` | general, matches | general, matches | same, exit 0 |

Result: **9 built and matching, 0 typed, 0 refused, 1 loud stop** (9/10, required 7).
`09_calculator.py` reaches `99999999999999999999`, which is beyond int64; AIL prints
`OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)`
and exits 1. The task allows the calculator shell to stop loudly there.

The default build falls back to the general path for every program because `Cmd.__init__`
has default arguments and the class has a `None` class attribute:

```
note: AIL_CURRENT/stdlib/cmd.py:61:5: built on the general path (about 20x slower) because
class attribute cmd.Cmd.intro = None; a class attribute here is an int, float, str or bool
literal; run with --strict to see why
```

## What was added

`AIL_CURRENT/stdlib/cmd.py` is CPython 3.12's `Lib/cmd.py` as AIL source, found by
`import cmd` through `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`). It keeps `Cmd`,
`cmdloop`, `precmd`, `postcmd`, `preloop`, `postloop`, `parseline`, `onecmd`, `emptyline`,
`default`, `completedefault`, `completenames`, `get_names`, `do_help`, `print_topics`,
`columnize`, and the documented class attributes. `sys.stdin`/`sys.stdout` are not stored as
fields; input uses `input()` or `sys.stdin.readline()` at the call site and output uses
`sys.stdout.write()`. Readline completion is a `complete()` stub returning `None`.

## Follow-ups (out of scope: compiler features)

* The typed path refuses a `None` class attribute and method default arguments, so every
  program uses the general path. Exact note above.
* This compiler has no `dir()` and an AIL class exposes neither `__dict__` nor `__mro__`
  (`the name 'dir' is not a known function/class/builtin`; `type object 'A' has no attribute
  '__mro__'`). `get_names()` therefore probes a fixed command vocabulary with `hasattr()`
  and sorts it, and `do_help()` treats every `do_*` command as documented. A subclass whose
  commands are outside that vocabulary will not list them.
* `getattr(self, name)` with a name only known at run time cannot call a method here
  (`AttributeError: 'X' object has no attribute 'do_x'` even when `hasattr` is true), and
  `getattr(self, 'do_x')` as a value is refused (`getattr() of the method do_x as a value`).
  Dispatch therefore uses literal `getattr(self, 'do_name')` calls for the same fixed
  vocabulary, and the module declares `do_*`/`help_*` stubs for it.
* A method's `__doc__` cannot be read through `getattr()` here, so detailed help for a
  command without a `help_*` method prints `*** No help on <name>`; the help table still
  matches because every command in the test programs is documented.
