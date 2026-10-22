# Differences from CPython

Rows are found by probing the compiled program against CPython (`bash ~/tools/cmp.sh`).  A row that the
compiler *refuses by name* is not a silent difference: the build stops and the `note:` line says what to
write instead.

| id | area | CPython | this compiler | status |
|----|------|---------|---------------|--------|
| C?-job-resub2-10220600-1 | `re.sub` / `re.subn` / `Pattern.sub` with a bound method as `repl` (`re.sub(P, obj.m, s)`) | the method is called with each Match | refused at build time: `a bound method (fmt) as the replacement is not built: a method is not a value in this program; write \`lambda m: obj.fmt(m)\` instead` -- a method is not a value anywhere in this language (`f = obj.m` fails at run time too) | refused by name, not silent |
| C?-job-resub2-10220600-2 | the same, where the name of the method is also a field of some class in the program | as above | the surface cannot tell a method from a field of the same name, so the value keeps the string-replacement lowering and fails at run time (`TypeError: argument of type 'function' is not iterable`) instead of being refused | silent (conservative: refusing would break a str field of that name) |
| C?-job-resub2-10220600-3 | a function reaching `repl` through an *unannotated* parameter whose call sites mix functions and strings (`def f(repl, s): return re.sub(P, repl, s)`, called once with a def and once with a str) | both work | the one lowering is chosen for the whole source position: it is the string one, so the call site that passes a function fails at run time (`TypeError`) | silent (annotate the parameter `Callable[...]`, or pass a lambda) |
