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
note: AIL_CURRENT/stdlib/cmd.py:386:5: built on the general path (about 20x slower) because
class attribute cmd.Cmd.intro = None; a class attribute here is an int, float, str or bool
literal; run with --strict to see why
```

## How the module dispatches

`AIL_CURRENT/stdlib/cmd.py` is CPython 3.12's `Lib/cmd.py` as AIL source, found by
`import cmd` through `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`). It keeps `Cmd`,
`cmdloop`, `precmd`, `postcmd`, `preloop`, `postloop`, `parseline`, `onecmd`, `emptyline`,
`default`, `completedefault`, `completenames`, `get_names`, `do_help`, `print_topics`,
`columnize`, and the documented class attributes. `sys.stdin`/`sys.stdout` are not stored as
fields; input uses `input()` or `sys.stdin.readline()` at the call site and output uses
`sys.stdout.write()`. Readline completion is a `complete()` stub returning `None`.

The dispatch avoids the two things this compiler does not model -- `dir()`/`__dict__` and a
method as a value -- with the two things it does model:

* `hasattr(obj, name)` accepts a computed `name`; the compiler answers by matching it
  against the methods of every class in the program, including overrides. This is exact.
* An attribute call on a *parameter with no static type* (`o.do_x(arg)` in a module-level
  helper) is compiled to a run-time check against every class that defines `do_x`, so it
  calls the subclass's implementation.

A private `_Stubs` class (not a base of `Cmd`, never instantiated) gives the compiler a
definition for each command name the module can spell; `onecmd()` and `parseline()` call
the matching helper only after `hasattr()` says the instance really implements the name.
That makes the previously wrong cases behave like CPython:

* an unimplemented command falls through to `default()` (`*** Unknown syntax: ...`) instead
  of being silently swallowed by a base-class stub;
* `parseline('!ls')` returns `(None, None, '!ls')` when the subclass has no `do_shell`, and
  `('shell', 'ls', 'shell ls')` when it does;
* `hasattr(shell, 'do_add')` is False for a subclass that does not define `do_add`;
* `get_names()` returns the base API names plus the subclass commands that really exist.

## Self-check probes

Compiled and run in both builds (default and `AIL_UNIFIED_FORCE=1`) and compared with
`python3` (stdout and exit status). `r*` probes are the reviewer's.

| probe | covers | result |
| --- | --- | --- |
| `r1_vocab.py` | unimplemented `echo`/`add`/`!ls`, unknown command, `help` | dispatch lines match; the help table differs (see below) |
| `r2_outside.py` | a `do_baz` outside the command table | differs: not dispatched or listed (see below) |
| `r3_parse.py` | `parseline('!ls')`, `'?'`, `'x?'`, `'!'` with no `do_shell` | matches both builds |
| `r4_empty.py` | `emptyline()` repetition with an unimplemented `ping` | matches both builds |
| `r5_attr.py` | `hasattr(..., 'do_add')`, `get_names()` | `hasattr` and `get_names()` match; help table differs |
| `r6_dyn.py` | computed `getattr` in the program, `type(s) is G` | matches both builds |
| `r7_lab01.py` | replica of `01_hello_commands.py` with `help` queued | matches both builds |
| `p_cmd_loop.py` | prompt, intro, arg/no-arg, multiple spaces, `default()`, `do_EOF` | matches |
| `p_cmd_empty.py` | default `emptyline()`, overridden `emptyline()`, unknown command | matches |
| `p_cmd_hooks.py` | `preloop`/`postloop`, `precmd` rewriting, `postcmd` stopping | matches |
| `p_cmd_int.py` | `int()` on `42`, `0`, `-1`, `-9223372036854775808`, `9223372036854775807`, sums at the boundaries | matches |
| `p_cmd_parse.py` | `parseline()` on `?x`, `!ls`, spaced args, empty, tabs | matches with and without `do_shell` |
| `p_cmd_help.py` | help table, `help` via `help_*`, `help unknown` | `help_*` and `help unknown` match; docstring-only help differs |

### Remaining differences (need compiler features)

Both were reproduced on this commit in both builds:

1. **A method's `__doc__` cannot be read.** `self.do_x` as a value is refused
   (`the method .do_x() (on a instance:C)` / `field 'do_x' requires a class instance`), and
   `getattr(self, 'do_x')` as a value is refused by name. CPython's `do_help` uses
   `getattr(self, name).__doc__` to split documented from undocumented commands and to
   print `help <name>` for a docstring-only command. The module therefore lists every
   `do_*` command as documented and prints `*** No help on <name>` when there is no
   `help_<name>` method. `lab/stdlib/cmd/05_help.py` and `10_aliases.py` use docstrings on
   every command, so their tables match; a subclass that mixes documented and undocumented
   commands (the reviewer's `r1`/`r5`) shows the difference.
2. **Commands outside `_COMMAND_NAMES` are not dispatched.** A call with a name computed at
   run time cannot find a method: `getattr(o, name)(...)` reaches
   `AttributeError: 'C' object has no attribute 'do_baz'` even when `hasattr(o, name)` is
   true (verified with the reviewer's `r2_outside.py`). The compiler needs a `dir()`-like
   method list (or a runtime method dispatch by name) for a general `onecmd`. The ten lab
   programs only use names in the table, so all of them dispatch correctly.

## Follow-ups (out of scope: compiler features)

* The typed path refuses a `None` class attribute and method default arguments, so every
  program uses the general path. Exact note above.
* This compiler has no `dir()` and an AIL class exposes neither `__dict__` nor `__mro__`
  (`the name 'dir' is not a known function/class/builtin`; `type object 'A' has no attribute
  '__mro__'`). `get_names()` stands in their place with the fixed base-name list and
  `hasattr()` over the command table.
* `getattr(obj, name)` with a name only known at run time cannot call a method
  (`AttributeError: 'X' object has no attribute 'do_x'` even when `hasattr` is true);
  `getattr(obj, 'do_x')` as a literal value is accepted only as `getattr(obj, 'do_x')(...)`,
  which the compiler rewrites to `obj.do_x(...)` and resolves statically. This is why the
  module spells one helper per name rather than writing CPython's single
  `func = getattr(self, 'do_' + cmd)` line.
