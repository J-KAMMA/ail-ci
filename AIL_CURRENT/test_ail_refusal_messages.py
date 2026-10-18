"""Compile-time refusals are written for an LLM author: they say what is not supported, where
(file:line:col) and exactly what to write instead (a `write instead:` line), in at most three lines.

Each case is a small program an LLM plausibly writes, the position the refusal must name, and the
phrases that keep the check meaningful (the construct is named; the rewrite is given). The
programs are compiled with the general path off (`AIL_NO_GENERAL=1`, as the other refusal tests do),
so the message is the typed path's. Nothing here changes which programs are accepted.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (name, syntax, source, "line:col" the refusal must name, phrases the message must contain)
CASES = [
    ('main_not_called', 'python',
     'def main() -> None:\n    print("hi")\n',
     '1:1', ['main() is defined but never called', 'add `main()` as the last line']),
    ('float_into_int_param', 'ail',
     'fn collatz(n: int) -> int {\n    if n == 1 { return 0; }\n    if n % 2 == 0 { return 1 + collatz(n / 2); }\n'
     '    return 1 + collatz(3 * n + 1);\n}\nfn main() { print(collatz(27)); }\n',
     '3:', ['passing a float to collatz()', 'no implicit truncation', 'collatz(n // 2)']),
    ('float_into_int_param_signature', 'ail',
     'fn collatz(n: int) -> int { return n; }\nfn main() { print(collatz(27 / 2)); }\n',
     '1:', ["'n' is annotated int in the source, but the caller also supplies float",
            'pass `int(x)` at the call']),
    ('str_param_used_like_bytes', 'ail',
     'const ALPHA = "abc";\nfn pos(ch: str) -> int { return ALPHA.find(ch); }\n'
     'fn main() { print(pos("b")); }\n',
     '2:', ["'ch' is annotated str but the body uses it like bytes", 'let alpha: str = TABLE;']),
    ('dict_of_bool', 'ail',
     'fn main() { let seen: dict[int,bool] = {}; print(len(seen)); }\n',
     '1:', ['`let seen: dict[int,bool]`', 'not bool', 'let seen: dict[int, int] = {};']),
    ('optional_int', 'python',
     'def find(d: dict[int, int], k: int) -> int | None:\n    return d.get(k)\n\n\n'
     'def main() -> None:\n    print(find({1: 2}, 1))\n\n\nmain()\n',
     '1:', ['int | None: only a class type can be None', 'return a sentinel']),
    ('dict_get_one_argument', 'python',
     'def main() -> None:\n    d = {"a": 1}\n    v = d.get("b")\n    print(v)\n\n\nmain()\n',
     '3:', ['d.get(k) with one argument', '`d.get(k, -1)`']),
    ('staticmethod', 'python',
     'class M:\n    @staticmethod\n    def sq(x: int) -> int:\n        return x * x\n\n\n'
     'def main() -> None:\n    print(M.sq(3))\n\n\nmain()\n',
     '3:', ['a decorator on M.sq', 'a top-level `def sq(x: int) -> int`']),
    ('global_loop_variable', 'python',
     'count = 0\n\n\ndef inc() -> None:\n    global count\n    for count in range(3):\n        pass\n\n\n'
     'def main() -> None:\n    inc()\n    print(count)\n\n\nmain()\n',
     '6:', ['module variable', 'compute the value into a local']),
    ('global_list', 'python',
     'items = [1]\n\n\ndef reset() -> None:\n    global items\n    items = [2]\n\n\n'
     'def main() -> None:\n    reset()\n    print(items[0])\n\n\nmain()\n',
     '', ['`global`', 'pass the value in as a parameter']),
    ('nonlocal_statement', 'python',
     'def main() -> None:\n    total = 0\n\n    def add(n: int) -> None:\n        nonlocal total\n'
     '        total += n\n\n    add(3)\n    print(total)\n\n\nmain()\n',
     '5:', ['nonlocal', 'return the new one']),
    ('generator', 'python',
     'def gen(n: int):\n    for i in range(n):\n        yield i\n\n\n'
     'def main() -> None:\n    for x in gen(3):\n        print(x)\n\n\nmain()\n',
     '3:', ['yield: this language has no generators', 'out.append(x)']),
    ('walrus', 'python',
     'def main() -> None:\n    xs = [1, 2, 3]\n    if (n := len(xs)) > 2:\n        print(n)\n\n\nmain()\n',
     '3:', ['the walrus operator', 'n = len(xs)']),
    ('match_statement', 'python',
     'def main() -> None:\n    x = 3\n    match x:\n        case 1:\n            print("one")\n'
     '        case _:\n            print("other")\n\n\nmain()\n',
     '3:', ['a `match` statement', 'if` / `elif` / `else` chain']),
    ('while_else', 'python',
     'def main() -> None:\n    i = 0\n    while i < 3:\n        i += 1\n    else:\n        print("done")\n\n\nmain()\n',
     '3:', ['while-else is unsupported', 'a flag set before the loop']),
    ('print_a_list', 'python',
     'def main() -> None:\n    xs = [1, 2, 3]\n    print(xs)\n\n\nmain()\n',
     '3:', ['print() given a list[int]', 'for x in xs: print(x)']),
    ('enumerate_with_start', 'python',
     'def main() -> None:\n    for i, x in enumerate(["a", "b"], 1):\n        print(i, x)\n\n\nmain()\n',
     '2:', ['a tuple target over a sequence', 'for i in range(len(xs))']),
    ('nested_format_spec', 'python',
     'def main() -> None:\n    w = 8\n    x = 3.14159\n    print(f"{x:{w}.2f}")\n\n\nmain()\n',
     '4:', ['a nested format spec', 'a literal spec']),
    ('star_args', 'python',
     'def f(*args: int) -> int:\n    return sum(args)\n\n\ndef main() -> None:\n    print(f(1, 2, 3))\n\n\nmain()\n',
     '1:', ['plain positional arguments', 'list every parameter by name']),
    ('mutable_default', 'python',
     'def f(x: int, acc: list[int] = []) -> int:\n    acc.append(x)\n    return len(acc)\n\n\n'
     'def main() -> None:\n    print(f(1), f(2))\n\n\nmain()\n',
     '1:', ["the default for 'acc'", 'drop the default']),
    ('dict_of_lists_annotation', 'python',
     'def main() -> None:\n    d: dict[str, list[int]] = {}\n    print(len(d))\n\n\nmain()\n',
     '2:', ['unsupported local annotation dict[str, list[int]]', 'keep other values in parallel lists']),
    ('typevar_generic', 'python',
     'from typing import TypeVar, List\nT = TypeVar("T")\n\n\ndef first(xs: List[T]) -> T:\n    return xs[0]\n\n\n'
     'def main() -> None:\n    print(first([1, 2]))\n\n\nmain()\n',
     '5:', ["'xs' is annotated list[T]", 'no generics']),
    ('import_numpy', 'python',
     'import numpy as np\n\n\ndef main() -> None:\n    print(np.zeros(3))\n\n\nmain()\n',
     '1:', ["import of 'numpy'", 'write what you need by hand']),
    ('str_plus_bytes', 'python',
     'def main() -> None:\n    s = "abc"\n    b = s.encode()\n    print(s + b)\n\n\nmain()\n',
     '4:', ['concatenating a str with bytes', '`data.decode()`']),
    ('float_assigned_to_int', 'python',
     'def main() -> None:\n    x: int = 7\n    y: int = x / 2\n    print(y)\n\n\nmain()\n',
     '3:', ["'y' is declared int; assigning float", 'y: int = int(x / 2)']),
    ('second_name_for_a_list', 'python',
     'def main() -> None:\n    a = [1, 2]\n    b = a\n    b.append(3)\n    print(len(a))\n\n\nmain()\n',
     '3:', ['makes a second name for the same container', '`b = a.copy()`']),
    ('append_to_list_parameter', 'ail',
     'fn f(xs: list[int]) -> void { xs.append(1); }\nfn main() { let a = [1]; f(a); print(a[0]); }\n',
     '1:', ['is a list parameter, which is read-only', 'keep the list in a struct field']),
    ('function_without_output', 'python',
     'def main() -> None:\n    x = 3\n\n\nmain()\n',
     '1:', ['no parameters and no print()', 'print the result inside the function']),
    ('invalid_fn_header', 'ail',
     'fn f(a: int): int { return a; }\nfn main() { print(f(1)); }\n',
     '1:', ['this `fn` header is not of the form', 'the result type follows `->`']),
    ('statement_outside_function', 'ail',
     'let x = 1;\nfn main() { print(x); }\n',
     '1:', ['a statement outside any function', 'move the statement into `fn main()']),
    ('increment_operator', 'ail',
     'fn main() { let i = 0; i++; print(i); }\n',
     '1:', ['is not valid here', 'there is no `x++`']),
    ('inheritance', 'python',
     'class A:\n    def __init__(self) -> None:\n        self.x = 1\n\n\n'
     'class B(A):\n    def __init__(self) -> None:\n        self.x = 2\n\n\n'
     'def main() -> None:\n    print(B().x)\n\n\nmain()\n',
     '6:', ["class 'B' names a base class", 'no base class']),
    ('class_without_init', 'python',
     'class A:\n    def f(self) -> int:\n        return 1\n\n\ndef main() -> None:\n    print(A().f())\n\n\nmain()\n',
     '1:', ["class 'A' has no __init__", '`@dataclass` with annotated fields']),
    ('str_in_bytes_literal', 'python',
     'import sys\n\n\ndef main() -> None:\n    data = sys.stdin.buffer.read()\n    for b in data:\n'
     '        if b == "a":\n            print("hit")\n\n\nmain()\n',
     '7:', ['comparing a str with', 'is an int (`b == 97`']),
    ('exit_call', 'python',
     'def main() -> None:\n    exit(0)\n\n\nmain()\n',
     '2:', ['call to exit()', '`sys.exit(0)`']),
    ('key_lambda_index', 'ail',
     'struct Item { name: str; value: int; }\n'
     'fn main() { let items: list[Item] = []; items.append(Item("a", 1));\n'
     '  items.sort(key=lambda i: (-items[i].value, items[i].name)); print(len(items)); }\n',
     '3:', ['a reference list item requires an integer index', 'key=lambda it: (-it.value, it.name)']),
]


def compile_case(directory, syntax, source):
    path = Path(directory, 'prog.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_GENERAL='1')
    return subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile', 'prog.ail',
                           '--syntax', syntax, '-o', 'prog'], cwd=directory, capture_output=True,
                          text=True, timeout=600, env=env)


class RefusalMessageForm(unittest.TestCase):
    def test_every_case_has_the_three_part_form(self):
        for name, syntax, source, where, phrases in CASES:
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built = compile_case(directory, syntax, source)
                text = built.stderr
                self.assertIn(built.returncode, (2, 3), built.stdout + text)
                self.assertFalse(Path(directory, 'prog').exists(), name)
                lines = [line for line in text.splitlines() if line and not line.startswith('note:')]
                # (2) where: file:line:col first, optionally narrowed to the line the case expects
                self.assertRegex(lines[0], r'^prog\.ail:\d+:\d+: ', text)
                if where:
                    self.assertTrue(lines[0].startswith('prog.ail:' + where), text)
                # (1) what is not supported, and (3) what to write instead, in at most three lines
                self.assertTrue(any(line.startswith('  write instead: ') for line in lines), text)
                self.assertLessEqual(len(lines), 3, text)
                self.assertNotIn('usage:', text)
                for phrase in phrases:
                    self.assertIn(phrase, text)

    def test_case_names_are_unique(self):
        names = [case[0] for case in CASES]
        self.assertEqual(len(names), len(set(names)))

    def test_unlocated_refusals_are_read_off_the_source(self):
        # the type check cannot map these to a statement; the position comes from the source text
        for name, syntax, source, where, _ in CASES:
            if name not in ('optional_int', 'star_args', 'typevar_generic', 'mutable_default'):
                continue
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built = compile_case(directory, syntax, source)
                self.assertRegex(built.stderr, r'^prog\.ail:\d+:\d+: ')


if __name__ == '__main__':
    unittest.main()
