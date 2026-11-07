"""The agent-actionable machine form of a compiler diagnostic.

The human text is unchanged (it is the byte-for-byte `message`); this module adds the stable code,
the one-sentence cause and the literal edit an agent can apply.  Data follows
docs/design/AGENT_ERRORS.md: AIL0101..AIL0116, one family per refusal or fallback note.
"""
import re


FAMILIES = (
    dict(code='AIL0101', pattern='sys.stdin.buffer.readline', cause="`sys.stdin.buffer.readline` is saved in `read`, but this compiler accepts `sys.stdin.buffer.readline()` only as a direct call; the saved method fails at run time with `'...' object has no attribute 'readline'`.", replace='read = sys.stdin.buffer.readline\nprint(read().decode().strip())',
         **{'with': 'print(sys.stdin.readline().strip())'}),
    dict(code='AIL0102', pattern='_ail_l1l', cause='`b = heapq.heappop(fh)` pops a berth number from a 1-field free list, while `entry = heapq.heappop(wait1)` pops a 5-field job row; the compiler captures both pops in one temporary and a captured row must have one width.', replace='                b = heapq.heappop(fh)',
         **{'with': '                fh.sort()\n                b = fh.pop(0)'}),
    dict(code='AIL0103', pattern='comparing a str with a number', cause='`s` is a str and `1` is a number; a str is never equal to a number, so `s == 1` is always False.', replace='if s == 1:',
         **{'with': 'if s == "1":'}),
    dict(code='AIL0104', pattern='d.get(k) with one argument', cause='`d.get(k)` gives None for a missing key, and this compiler has no None for an int value.', replace='v = d.get(k)',
         **{'with': 'v = d.get(k, -1)'}),
    dict(code='AIL0105', pattern='dict of containers', cause='`accounts` is a dict whose values are lists; a typed dict holds int, float, str or bytes, not a list.', replace='accounts[rid] = [name, initial, True]\nprint(accounts[rid][0], accounts[rid][1])',
         **{'with': 'class Account:\n    def __init__(self, name: str, initial: int, active: bool) -> None:\n        self.name = name\n        self.initial = initial\n        self.active = active\n\naccounts: dict[int, Account] = {}\naccounts[rid] = Account(name, initial, True)\nprint(accounts[rid].name, accounts[rid].initial)'}),
    dict(code='AIL0106', pattern='class list comprehensions', cause='`[P(x) for x in xs]` is a list comprehension that builds class instances; this compiler builds comprehensions of numbers, strings and bytes only.', replace='    return [P(x) for x in xs]',
         **{'with': '    out: list[P] = []\n    for x in xs:\n        out.append(P(x))\n    return out'}),
    dict(code='AIL0107', pattern='mixes bools and numbers', cause="this dict literal puts an int (`'line': 3`) and a bool (`'has_else': False`) in the same dict; an AIL dict has one value type. Writing `0` / `1` to match the int would change what prints (`0` instead of `False`).", replace="d = {'type': 'when', 'line': 3, 'body': [], 'has_else': False}\nprint(d['line'], d['has_else'])",
         **{'with': "class Node:\n    def __init__(self, kind: str, line: int, has_else: bool) -> None:\n        self.kind = kind\n        self.line = line\n        self.has_else = has_else\n\nd = Node('when', 3, False)\nprint(d.line, d.has_else)"}),
    dict(code='AIL0108', pattern='returns bytes on one path and a number', cause='`make_term` returns `bytes` on the first path and the number `0` on the second; one function has one return type.', replace='    return 0',
         **{'with': '    return b"0"'}),
    dict(code='AIL0109', pattern='while-else is unsupported', cause='`while ... else:` is not supported; here the loop has no `break`, so the `else` body always runs and can move after the loop.', replace='while i < 3:\n    i += 1\nelse:\n    print("done", i)',
         **{'with': 'while i < 3:\n    i += 1\nprint("done", i)'}),
    dict(code='AIL0110', pattern='nested annotation', cause='`records: list[dict[str, str]]` is two levels deep (a list of dicts); the typed path recognises one level of rows, `list[SomeClass]`.', replace='def sizes(records: list[dict[str, str]]) -> list[int]:\n    out = []\n    for r in records:\n        out.append(len(r))\n    return out\n\nprint(sizes([{"a": "1"}, {"b": "2", "c": "3"}]))',
         **{'with': 'class Row:\n    def __init__(self, a: str, b: str) -> None:\n        self.a = a\n        self.b = b\n\ndef sizes(records: list[Row]) -> list[int]:\n    out: list[int] = []\n    for r in records:\n        n = 1\n        if r.b:\n            n = 2\n        out.append(n)\n    return out\n\nprint(sizes([Row("1", ""), Row("2", "3")]))'}),
    dict(code='AIL0111', pattern='dunder method Fraction.__float__', cause='`float(x)` needs `Fraction.__float__`, which this compiler does not build. Importing `fractions` at all prints this note; the old note pointed at line 235 of the standard-library prelude, not at your 3-line file.', replace='from fractions import Fraction\nx = Fraction(1, 2)\nprint(float(x))',
         **{'with': 'print(1 / 2)'}),
    dict(code='AIL0112', pattern='format spec on a Decimal', cause='a format spec on a `Decimal` needs `Decimal.__format__`; this compiler applies format specs to int, float and str only. The old note pointed at line 1687 of the `decimal` prelude, not at your 4-line file.', replace='print(f"{d:.2f}")',
         **{'with': 'print(f"{float(d):.2f}")'}),
    dict(code='AIL0113', pattern='yield: this language has no generators', cause='`yield` makes a generator, and this compiler has no generators.', replace='def gen(n: int):\n    for i in range(n):\n        yield i',
         **{'with': 'def gen(n: int) -> list[int]:\n    out: list[int] = []\n    for i in range(n):\n        out.append(i)\n    return out'}),
    dict(code='AIL0114', pattern='a tuple used where a single value is needed', cause='the comprehension builds a list of 2-field tuples in one expression; this compiler needs the list named, then pairs appended to it.', replace='    return [(m, pow(base, -1, m)) for m in moduli]',
         **{'with': '    out: list[tuple[int, int]] = []\n    for m in moduli:\n        out.append((m, pow(base, -1, m)))\n    return out'}),
    dict(code='AIL0115', pattern='is a list parameter, which is read-only', cause="`arr` is a `list[int]` parameter and parameters are read-only, so `arr[0] = 1` cannot change the caller's list.", replace='def fill(arr: list[int]) -> None:\n    arr[0] = 1\n\nxs = [0, 0]\nfill(xs)',
         **{'with': 'def fill(arr: list[int]) -> list[int]:\n    out: list[int] = []\n    for x in arr:\n        out.append(x)\n    out[0] = 1\n    return out\n\nxs = [0, 0]\nxs = fill(xs)'}),
    dict(code='AIL0116', pattern='cannot tell the type of element', cause='the tuple element is an empty list or an unknown value; name its type.', replace='t = ([], n)',
         **{'with': 'xs: list[int] = []\nt = (xs, n)'}),
)


_LOCATION = re.compile(r'^(?:note|error): (?P<path>.+):(?P<line>\d+):(?P<col>\d+): ')
_BARE_LOCATION = re.compile(r'^(?P<path>.+):(?P<line>\d+):(?P<col>\d+): ')


def family(message):
    """The family a human diagnostic belongs to, or None for a message not in the table."""
    text = str(message or '')
    for item in FAMILIES:
        if item['pattern'] in text:
            return item
    return None


def _lines(source):
    return str(source or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _find(source, block):
    """(first_line, last_line, column) of a literal block in source, 1-based, or None."""
    if not source or not block:
        return None
    lines, wanted = _lines(source), block.split('\n')
    for index in range(len(lines) - len(wanted) + 1):
        if lines[index:index + len(wanted)] == wanted:
            first = wanted[0]
            return index + 1, index + len(wanted), len(first) - len(first.lstrip()) + 1
    return None


def _position(text):
    for pattern in (_LOCATION, _BARE_LOCATION):
        found = pattern.match(str(text or ''))
        if found:
            return found.group('path'), int(found.group('line')), int(found.group('col'))
    return None


def diagnostic(message, source_text=None, path=None, line=None, col=None):
    """The JSON-ready object for one diagnostic, or None when the message is not in the table.

    `message` is copied byte for byte.  A location that names a prelude, or no location at all,
    is replaced by the line of the literal edit when that edit is found in the user's source.
    """
    text = str(message or '')
    item = family(text)
    if item is None:
        return None
    found = _position(text)
    if found:
        parsed_path, parsed_line, parsed_col = found
        path = parsed_path if path is None else path
        line = parsed_line if line is None else line
        col = parsed_col if col is None else col
    fix = None
    where = _find(source_text, item['replace'])
    if where is not None:
        start, end, column = where
        fix = {'replace_range': [start, end], 'with': item['with']}
        source_lines = _lines(source_text) if source_text is not None else []
        if not found:
            line, col = start, column
        elif source_lines and line is not None and line > len(source_lines):
            line, col = end, len(item['replace'].split('\n')[-1]) - len(item['replace'].split('\n')[-1].lstrip()) + 1
    severity = 'error' if text.startswith('error:') or 'not in the subset:' in text else 'note'
    result = dict(code=item['code'], severity=severity, file=None if path is None else str(path),
                  line=line, col=col, cause=item['cause'], message=text)
    if fix is not None:
        result['fix'] = fix
    return result
