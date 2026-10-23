# DEVLOG

## 2026-10-23 - fuzz84: refuse split/rsplit/splitlines arguments given twice

A keyword that CPython finds already filled by a positional was silently dropped while
processing text: `"a,b".split(",", sep="-")` printed `['a', 'b']` where CPython raises
`TypeError`, `rsplit` behaved the same for `sep`/`maxsplit` (`"a,b,c".split(",", 1,
maxsplit=2)`), and `splitlines` read the positional `keepends` and ignored a second
keyword (`"a\nb".splitlines(True, keepends=False)`). They are refused by name at compile
time now, the same treatment `expandtabs`' own `tabsize` already gets. Valid keyword forms
and the other text-processing probes still match CPython on both builds. Added
`test_ail_fuzz84.py`, which also covers the valid sep=/maxsplit=/keepends= forms.
