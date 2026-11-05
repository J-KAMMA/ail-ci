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
and exits 1. The task allows the calculator shell to stop loudly there. `05_help.py` and
`10_aliases.py` call the no-argument `help` table; `get_names()` supplies CPython's fixed base
names plus the supported commands the instance defines, so both print the same table as
CPython (verified in both builds).

The default build falls back to the general path for every program because `Cmd.__init__`
has default arguments and the class has a `None` class attribute:

```
note: AIL_CURRENT/stdlib/cmd.py:319:5: built on the general path (about 20x slower) because
class attribute cmd.Cmd.identchars = cmd.IDENTCHARS; a class attribute here is an int, float,
str or bool literal. write instead: a module-level constant, or set the value in __init__
(`self.identchars = ...`); run with --strict to see why
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
* `hasattr(shell, 'do_add')` is False for a subclass that does not define `do_add`.

### `get_names()` and the help table

CPython's `get_names()` is `dir(self.__class__)`.  `dir()` is refused, so the module keeps the
fixed list of `Cmd`'s own names and finds a subclass command with the computed `hasattr()`
above, which tests exactly the classes in the program.  `help` with no argument then runs
CPython's own table algorithm over that list, and `completenames()` filters it the same way.
That is exact for every command in the supported vocabulary and for a subclass that overrides
`get_names()`, so `05_help.py` and `10_aliases.py` match CPython exactly.  A command whose
name is outside `_COMMAND_NAMES` cannot be seen this way, so it is not listed; that is the one
remaining gap and it needs a `dir()`-like enumeration in the compiler.

A method's `__doc__` also cannot be read, so a `do_*` command with no `help_<name>` topic is
listed as documented, as CPython lists it when it has a docstring.

### Refused by name instead of guessed

The compiler can only call a method whose attribute name is a literal, and it cannot read a
method's `__doc__` or enumerate a class's methods (no `dir()`, `__dict__` or `__mro__`).  The
cases that need one of those names stop with a loud `NotImplementedError` naming what is
missing, in both builds:

| program shape | result |
| --- | --- |
| `onecmd('exit now')` with a real `do_exit` outside `_COMMAND_NAMES` | `NotImplementedError: cmd.Cmd.onecmd: cannot dispatch do_exit: ...` |
| `help exit` with a `help_exit` outside `_COMMAND_NAMES` | `NotImplementedError: cmd.Cmd.do_help: cannot call help_exit ...` |
| `help zoom` where only `do_zoom` has a docstring | `NotImplementedError: cmd.Cmd.do_help: cannot read the docstring of do_zoom; ...` |
| `help help` with no `help_help` | exact CPython text (the `do_help` docstring is a literal) |
| `help <name>` with a `help_<name>` method in the vocabulary, or an unknown name | exact CPython text |
| `help` with no argument, `get_names()`, `completenames()` | exact CPython text for the base names and the vocabulary |

`lab/stdlib/cmd/05_help.py` uses `help_<name>` and an unknown topic; `10_aliases.py` uses
`help_greet`; both call the no-argument `help` and match CPython exactly.

## Self-check probes

Compiled and run in both builds (default and `AIL_UNIFIED_FORCE=1`); the first seven probes
compare stdout and exit status with `python3`, the last three check the named refusals.

| probe | covers | result |
| --- | --- | --- |
| `p_cmd_loop.py` | prompt, intro, arg/no-arg, multiple spaces, `default()`, `do_EOF` | matches |
| `p_cmd_empty.py` | default `emptyline()`, overridden `emptyline()`, unknown command | matches |
| `p_cmd_hooks.py` | `preloop`/`postloop`, `precmd` rewriting, `postcmd` stopping | matches |
| `p_cmd_int.py` | `int()` on `42`, `0`, `-1`, `-9223372036854775808`, `9223372036854775807`, sums at the boundaries | matches |
| `p_cmd_parse.py` | `parseline()` on `?x`, `!ls`, spaced args, empty, tabs | matches with and without `do_shell` |
| `p_cmd_help.py` | `help` via `help_*`, `help help`, `help unknown`, the no-argument table | matches |
| `p_cmd_names.py` | `get_names()`/`completenames()` for the supported vocabulary and a `get_names()` override | matches |
| `p_cmd_outside.py` | `do_exit` outside the vocabulary | named `NotImplementedError`, both builds |
| `p_cmd_doc.py` | `help zoom` on a docstring-only command | named `NotImplementedError`, both builds |
| `p_cmd_help_outside.py` | `help exit` with a `help_exit` outside the vocabulary | named `NotImplementedError`, both builds |

### Remaining follow-ups (need compiler features)

* The typed path refuses a `None` class attribute and method default arguments, so every
  program uses the general path. Exact note above.
* A method list and a method's docstring are not available to AIL source.  `get_names()` is
  exact for `Cmd`'s own names and the supported vocabulary; a command name outside it is not
  listed, and a docstring-only `help <name>` cannot print the docstring.  The compiler would
  need a `dir()`-like enumeration and a way to read `getattr(obj, 'do_x').__doc__` (and to
  call a method by a computed name) to close those gaps; until then the dispatch cases refuse
  by name as shown above.
* The refusals are at the first call, not at build time.  This compiler builds a bundled
  module as a whole: a `dir()`/`__dir__` anywhere in `cmd.py` (even in a function no program
  calls) makes `import cmd` itself refused for every program, so a compile-time refusal here
  would take all ten labs with it.  The run-time `NotImplementedError` is the narrowest loud
  refusal this module can make without a compiler feature.
* `getattr(obj, name)` with a name only known at run time cannot call a method
  (`AttributeError: 'X' object has no attribute 'do_x'` even when `hasattr` is true);
  `getattr(obj, 'do_x')` as a literal value is accepted only as `getattr(obj, 'do_x')(...)`,
  which the compiler rewrites to `obj.do_x(...)` and resolves statically. This is why the
  module spells one helper per name rather than writing CPython's single
  `func = getattr(self, 'do_' + cmd)` line.
