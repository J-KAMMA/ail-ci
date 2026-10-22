You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

1. **3-arg `pow()` misreports float operands** (`/tmp/rprobes/p_powfloat.py`, both builds).
`pow(2.0, 3, 5)` expected `TypeError: pow() 3rd argument not allowed unless all arguments are integers`; actual `TypeError: unsupported operand type(s) for ** or pow(): 'float', 'int', 'int'`. Same for `(3, 2.0, 5)`, `(3, 2, 5.0)` and `pow(C.A, 2.0, 5)`. Base was correct, so this is a regression.

2. **`divmod()` instance dispatch is too broad and loses divmod-specific diagnostics** (`p_divmod_err.py`, `p_mod_enum.py`, `p_divmod_more.py`).
`divmod(E.A, C.A)` expected `TypeError: unsupported operand type(s) for divmod(): 'E' and 'C'`; actual `... for //: 'E' and 'C'`. `divmod(C.A, "x")` expected `... divmod(): 'C' and 'str'`; actual `... for //` (no operand names). `divmod(C.A, 0.0)` expected `ZeroDivisionError: float divmod()`; actual `ZeroDivisionError: float floor division by zero`. A class defining only `__floordiv__`/`__mod__` (`Q`) gives `divmod(Q(), 2) == (10, 11)` where CPython raises the `divmod()` TypeError; a `__rfloordiv__`/`__rmod__` class gives `(20, 21)` for `divmod(2, R())`.

3. **3-arg `pow()` converts an enum before naming the failing operand** (`p_pow_enum.py`).
`pow(C.A, E.A, 5)` expected `TypeError: unsupported operand type(s) for ** or pow(): 'C', 'E', 'int'`; actual `'int', 'E', 'int'`. `pow(E.A, C.A, 5)` expected `'E', 'C', 'int'`; actual `'E', 'int', 'int'`.

4. **Plain Enum on the left still does not defer to the other operand** (`p_eq_custom2.py`, `p_enum_plain_ord.py`).
With `C(IntEnum).__eq__` overridden to return True, `E.A == C.A` expected `True` (and `C.__eq__` runs); actual `False` because `_AilEnum.__eq__` returns identity instead of `NotImplemented` across classes. Plain Enum ordering also still says `'instance'` and `'<'`: `E.A <= H.A` expected `TypeError: '<=' not supported between instances of 'E' and 'H'`; actual `TypeError: '<' not supported between instances of 'instance' and 'instance'`.

Probe both builds with `bash ~/tools/cmp.sh`, add each fixed case to the tests, then commit. If a finding cannot be fixed safely, refuse the construct by name at compile time instead of leaving a silent wrong answer.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
