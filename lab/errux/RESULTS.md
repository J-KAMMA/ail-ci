# errux: a scored corpus of refusal messages

- Date: 2026-11-04
- Base: `origin/integ`; corpus commit: `b228f88`
- Programs: `lab/errux/progs/` (40, one distinct refusal each)
- Scorer: `lab/errux/score.py`; baseline: `lab/errux/baseline.json`
- Total: **117 / 160** over 40 programs (max 4 each)

## Scoring rules

Each program begins with two header comments: `# line: N` (the line CPython or a reader
would blame) and `# names: TEXT` (a short substring naming the construct). The first
non-`note:` stderr line of the default build scores one point for each of:

1. **clean refusal status** — the compile exits 2 (syntax error) or 3 (subset refusal),
   not 1 with a Python traceback and not a C compiler error;
2. **location** — the line starts with `<file>.py:N:` where `<file>` is the program's own
   file name and `N` is the header line;
3. **construct named** — the line contains the `names` text (case-insensitive);
4. **rewrite hint** — the line contains one of `write instead`, `use `, `did you mean`,
   `rename`, `instead` (the exact list is `HINT_WORDS` in `score.py`).

A program that now builds is reported as `builds now`; it is a regression only if CPython
rejects it. `python3 lab/errux/score.py --write-baseline` records `{program: score}`;
`--check` exits 1 and names every program below its baseline.

## Table

`CPython` is 3.12's verdict: `rejects` when it exits non-zero (often at run time, before
the construct AIL refuses). `trimmed first stderr line` is cut to 160 characters.

| program | score | exit | CPython | trimmed first stderr line |
|---|---:|---:|---|---|
| `01_undefined_name_nested.py` | 3 | 3 | rejects | 01_undefined_name_nested.py:5:9: not in the subset: name 'missing_name' is not defined |
| `02_unknown_function_hint.py` | 4 | 3 | rejects | 02_unknown_function_hint.py:6:1: not in the subset: the name 'greet2' is not a known function/class/builtin; did you mean 'greet'? |
| `03_missing_argument.py` | 3 | 3 | rejects | 03_missing_argument.py:6:1: not in the subset: add() called without a required argument b |
| `04_method_without_self.py` | 3 | 3 | rejects | 04_method_without_self.py:7:1: not in the subset: C.hi() takes 0 positional arguments but 1 was given |
| `05_unknown_str_method.py` | 3 | 3 | rejects | 05_unknown_str_method.py:4:1: not in the subset: the method .uppr() (on a str) |
| `06_dict_view_kept.py` | 3 | 3 | accepts | 06_dict_view_kept.py:4:1: not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 4): a view follows its dict in CPython, |
| `07_unknown_list_method.py` | 3 | 3 | rejects | 07_unknown_list_method.py:4:1: not in the subset: the method .push() (on a list) |
| `08_math_name_not_published.py` | 3 | 3 | rejects | 08_math_name_not_published.py:4:1: not in the subset: math.sqr (not yet published in NAMES_library.json) |
| `09_too_many_arguments.py` | 3 | 3 | rejects | 09_too_many_arguments.py:6:1: not in the subset: f() called with too many positional arguments |
| `10_os_system_not_built.py` | 4 | 3 | accepts | 10_os_system_not_built.py:4:1: not in the subset: os.system is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace geten |
| `11_io_not_built.py` | 4 | 3 | accepts | 11_io_not_built.py:4:1: not in the subset: io used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv en |
| `12_math_shadowed_constant.py` | 4 | 3 | accepts | 12_math_shadowed_constant.py:4:1: not in the subset: AIL constant 'math' shadows the built-in name math; math.* functions are reached through this name, so it c |
| `13_module_as_value.py` | 3 | 3 | accepts | 13_module_as_value.py:5:5: not in the subset: the module math used as a plain value |
| `14_super_without_base.py` | 3 | 3 | accepts | 14_super_without_base.py:5:9: not in the subset: super() in a class with no base class |
| `15_isinstance_non_name_type.py` | 3 | 3 | rejects | 15_isinstance_non_name_type.py:4:1: not in the subset: isinstance() with a non-name type argument |
| `16_stdin_as_value.py` | 3 | 3 | accepts | 16_stdin_as_value.py:4:1: not in the subset: sys.stdin used as a plain value |
| `17_open_non_literal_mode.py` | 3 | 3 | rejects | 17_open_non_literal_mode.py:5:1: not in the subset: open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the pro |
| `18_caught_exception_attribute.py` | 3 | 3 | accepts | 18_caught_exception_attribute.py:4:1: not in the subset: a caught exception type Attribute (only builtin or user Exception subclasses are supported) |
| `19_unknown_keyword_argument.py` | 3 | 3 | rejects | 19_unknown_keyword_argument.py:5:1: not in the subset: f() called with an unknown keyword argument y |
| `20_starred_call_argument.py` | 3 | 3 | rejects | 20_starred_call_argument.py:6:1: not in the subset: a starred (*args) call argument (only print(*xs), zip(*rows), and a call to a def f(*args) or a fixed-arity  |
| `21_async_def.py` | 3 | 3 | accepts | 21_async_def.py:3:1: not in the subset: async def: this language has no coroutines or event loop. |
| `22_nested_class.py` | 3 | 3 | accepts | 22_nested_class.py:4:5: not in the subset: a nested class definition (C) |
| `23_missing_module.py` | 3 | 2 | rejects | 23_missing_module.py:3:1: import of 'nonexistent_module_xyz' is not available: it is not part of the standard library and no module of that name is on the searc |
| `24_missing_colon.py` | 3 | 2 | rejects | 24_missing_colon.py:3:18: expected ':' |
| `25_unclosed_bracket.py` | 3 | 2 | rejects | 25_unclosed_bracket.py:3:5: '[' was never closed |
| `26_unclosed_paren.py` | 3 | 2 | rejects | 26_unclosed_paren.py:3:6: '(' was never closed |
| `27_assign_to_literal.py` | 3 | 2 | rejects | 27_assign_to_literal.py:3:5: cannot assign to literal |
| `28_missing_indented_block.py` | 3 | 2 | rejects | 28_missing_indented_block.py:4:1: expected an indented block after function definition on line 3 |
| `29_tabs_and_spaces.py` | 4 | 2 | rejects | 29_tabs_and_spaces.py:5:1: inconsistent use of tabs and spaces in indentation |
| `30_module_without_name.py` | 3 | 2 | accepts | 30_module_without_name.py:4:7: module 'zlib' has no top-level name 'compressobj' (it defines: DEFLATED, DEF_BUF_SIZE, DEF_MEM_LEVEL, MAX_WBITS, Z_BEST_COMPRESSI |
| `31_duplicate_name.py` | 3 | 2 | accepts | 31_duplicate_name.py:9:1: duplicate AIL name: C (`def C` / `class C` is bound a second time at module level; a function here has one definition, which also rule |
| `32_int64_constant_out_of_range.py` | 3 | 2 | accepts | 32_int64_constant_out_of_range.py:3:5: int64 constant expression out of range: 9223372036854775808 |
| `33_class_body_statement.py` | 2 | 3 | accepts | not in the subset: a class body statement other than def/assignment/pass/docstring in C |
| `34_non_name_base_class.py` | 2 | 3 | rejects | not in the subset: a non-name base class in class B |
| `35_encode_error_handler.py` | 2 | 3 | accepts | not in the subset: str.encode() with the error handler 'xmlcharrefreplace' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace) |
| `36_generator_with_threads.py` | 2 | 3 | accepts | not in the subset: a generator function in a program with threads (the general path runs a generator on a stack of its own, which the thread lock does not follo |
| `37_keyword_only_required.py` | 2 | 3 | accepts | not in the subset: a required keyword-only parameter a in def f (this cut requires every keyword-only parameter to have a default) |
| `38_multiple_inheritance.py` | 2 | 3 | accepts | not in the subset: multiple inheritance in class C |
| `39_is_tuple_constant.py` | 2 | 3 | accepts | not in the subset: `is` with a tuple constant (line 5, DIFFERENCES C175): CPython merges equal tuple constants of a code object (`a = (); b = (); a is b` is Tru |
| `40_yield_outside_function.py` | 2 | 3 | rejects | not in the subset: not a Python expression: invalid syntax (<unknown>, line 3) |

**Total: 117 / 160.** 32 messages name the location (rule 2), 40 name the construct
(rule 3), 5 give a rewrite hint (02, 10, 11, 12, 29; rule 4), and all 40 use a clean
status (rule 1). Note that 29 earns the hint point from the substring `use` inside
"inconsistent use of tabs and spaces", not from actual guidance; the hint rule is a
string test, so that is a false positive worth tightening later.

## Follow-ups

The 10 lowest scores, ties broken by file name. "Missing" names the scoring rules the
first line does not satisfy.

1. `33_class_body_statement.py` — score 2.
   Message: `not in the subset: a class body statement other than def/assignment/pass/docstring in C`
   Missing: no `<file>.py:N:` prefix (rule 2) and no rewrite hint (rule 4).
2. `34_non_name_base_class.py` — score 2.
   Message: `not in the subset: a non-name base class in class B`
   Missing: no location prefix and no rewrite hint; it also does not say which expression formed the base.
3. `35_encode_error_handler.py` — score 2.
   Message: `not in the subset: str.encode() with the error handler 'xmlcharrefreplace' on the general path (built: utf-8, ascii, latin-1; errors strict, ignore, replace)`
   Missing: no location prefix and no rewrite hint (`built:` is not one of the hint words).
4. `36_generator_with_threads.py` — score 2.
   Message: `not in the subset: a generator function in a program with threads (the general path runs a generator on a stack of its own, which the thread lock does not follow)`
   Missing: no location prefix and no rewrite hint; it does not name the `def` that holds the `yield`.
5. `37_keyword_only_required.py` — score 2.
   Message: `not in the subset: a required keyword-only parameter a in def f (this cut requires every keyword-only parameter to have a default)`
   Missing: no location prefix and no rewrite hint.
6. `38_multiple_inheritance.py` — score 2.
   Message: `not in the subset: multiple inheritance in class C`
   Missing: no location prefix and no rewrite hint.
7. `39_is_tuple_constant.py` — score 2.
   Message: `not in the subset: \`is\` with a tuple constant (line 5, DIFFERENCES C175): CPython merges equal tuple constants of a code object (\`a = (); b = (); a is b\` is True; \`()\` is a singleton) and here each tuple display is a value of its own; compare with \`==\``
   Missing: the line number is parenthetical (`(line 5, ...)`), not the `<file>.py:N:` prefix (rule 2), and there is no hint word (rule 4) even though `compare with ==` is close.
8. `40_yield_outside_function.py` — score 2.
   Message: `not in the subset: not a Python expression: invalid syntax (<unknown>, line 3)`
   Missing: no location prefix (the parser's `<unknown>` is the compiler's wrapper, not the program) and no rewrite hint. This is a syntactically valid Python program, so it is not a syntax error in CPython; CPython rejects it at run time with `SyntaxError: 'yield' outside function`.
9. `01_undefined_name_nested.py` — score 3.
   Message: `01_undefined_name_nested.py:5:9: not in the subset: name 'missing_name' is not defined`
   Missing: no rewrite hint (rule 4); the location is correct.
10. `03_missing_argument.py` — score 3.
    Message: `03_missing_argument.py:6:1: not in the subset: add() called without a required argument b`
    Missing: no rewrite hint (rule 4); the location is correct.

## Findings not in the corpus

Three beginner mistakes do not produce a clean refusal and were left out of the 40 because
the gate forbids C compiler text in stderr. They are recorded here rather than fixed:

- `return` outside a function — `def f() -> None: return 1` followed by a module-level
  `return 2`: exit 4, `the C compiler rejected this (general path):` and
  `program.c: ... error: 'out' undeclared`.
- `break` outside a loop — exit 4, `program.c: ... error: break statement not within loop or switch`.
- duplicate parameter name — `def f(a, a)`: exit 4, `program.c: ... error: redefinition of parameter 'v_a'`.

`x = None; print(x.value)` builds (exit 0) and is not in the corpus.
