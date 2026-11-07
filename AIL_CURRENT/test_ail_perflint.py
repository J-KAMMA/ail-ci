"""`ail check --perf` (packaging/ail_lang/perflint.py, docs/CLI.md): static slow-algorithm advice.

One positive and one negative case per rule (the same call outside a loop, on a set, on a
loop-variant list, or an index-loop dynamic program), the --json object shape, the text line shape,
the --strict exit code (5) and a program with no hits printing nothing.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
PACKAGING = ROOT.parent / "packaging"


def setUpModule():
    if not (PACKAGING / "ail_lang" / "perflint.py").is_file():
        raise unittest.SkipTest("packaging/ail_lang is not beside AIL_CURRENT")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-perflint-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, text, name="prog.py"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def ail(self, *args):
        environment = dict(os.environ, PYTHONPATH=str(PACKAGING), AIL_SDK_DIR=str(ROOT),
                           PYTHONUTF8="1")
        return subprocess.run([sys.executable, "-B", "-m", "ail_lang", *map(str, args)],
                              cwd=self.dir, env=environment, capture_output=True, timeout=120)

    def hits(self, text):
        program = self.write(text)
        done = self.ail("check", "--perf", "--json", program)
        self.assertEqual(done.returncode, 0, done.stderr)
        return [json.loads(line) for line in done.stdout.decode("utf-8").splitlines() if line]

    def rules(self, text):
        return sorted(hit["rule"] for hit in self.hits(text))


P1 = '''\
def main() -> None:
    words: list[str] = ["alpha", "beta"]
    for probe in ["alpha", "gamma"]:
        if probe in words:
            print(probe)
        words.index(probe)
        words.count(probe)


main()
'''

P1_NEGATIVE = '''\
def main() -> None:
    words: list[str] = ["alpha", "beta"]
    if "alpha" in words:
        print(words.index("alpha"))
    known = {"alpha", "beta"}
    seen: list[str] = []
    for probe in ["alpha", "gamma"]:
        if probe in known:
            print(probe)
        if probe in seen:
            print(probe)
        seen.append(probe)


main()
'''

P2 = '''\
def main() -> None:
    xs: list[int] = [1, 2, 3]
    for _ in range(3):
        xs.pop(0)
        xs.insert(0, 9)
        del xs[0]


main()
'''

P2_NEGATIVE = '''\
def main() -> None:
    xs: list[int] = [1, 2, 3]
    xs.pop(0)
    xs.insert(0, 9)
    del xs[0]
    values = {1, 2, 3}
    for _ in range(3):
        values.pop()


main()
'''

P3 = '''\
def main() -> None:
    text = ""
    for piece in ["a", "b", "c"]:
        text += piece
    print(text)


main()
'''

P3_NEGATIVE = '''\
def main() -> None:
    text = ""
    text += "outside"
    total = 0
    for number in [1, 2, 3]:
        total += number
    print(text, total)


main()
'''

P4 = '''\
def main() -> None:
    xs: list[int] = [3, 1, 2]
    for _ in range(3):
        ordered = sorted(xs)
        print(ordered, min(xs), max(xs), sum(xs))
    for _ in range(3):
        xs.sort()


main()
'''

P4_NEGATIVE = '''\
def main() -> None:
    xs: list[int] = [3, 1, 2]
    ordered = sorted(xs)
    print(ordered, min(xs), max(xs), sum(xs))
    for value in [1]:
        xs.append(value)
        print(sorted(xs))
    wanted = {3, 1}
    for _ in range(2):
        print(min(wanted))


main()
'''

P5 = '''\
def main() -> None:
    left = [{"id": 1}, {"id": 2}]
    right = [{"id": 2}, {"id": 3}]
    for one in left:
        for two in right:
            if one["id"] == two["id"]:
                print(one)


main()
'''

P5_NEGATIVE = '''\
def main() -> None:
    table = [1, 2, 3]
    for i in range(3):
        for j in range(3):
            if table[i] == table[j]:
                print(i, j)
    left = [{"id": 1}]
    right = [{"id": 2}]
    for one in left:
        for two in right:
            if one["id"] == 0:
                print(two)


main()
'''

P6 = '''\
def main() -> None:
    values: list[int] = []
    for number in [1, 2, 3]:
        values = values + [number]
        values = [*values, number]


main()
'''

P6_NEGATIVE = '''\
def main() -> None:
    values: list[int] = []
    values = values + [1]
    for number in [1, 2, 3]:
        other = values + values
        values.append(number)


main()
'''

P3_RESET = '''\
def main() -> None:
    for i in range(5):
        s = ""
        s += str(i)
        print(s)
    for s in ["a", "b"]:
        s += "!"
        print(s)


main()
'''

P4_KEYVAR = '''\
def main() -> None:
    rows = [[3, 1], [2, 4]]
    for k in range(2):
        print(sorted(rows, key=lambda row: row[k]))
        print(min(rows, key=lambda row: row[k]))
        rows.sort(key=lambda row: row[k])
    flags = [True, False]
    for flag in flags:
        print(sorted(rows, key=lambda row: row[0], reverse=flag))
    print(rows)


main()
'''

P4_CONSTKEY = '''\
def main() -> None:
    rows = [[3, 1], [2, 4]]
    for _ in range(2):
        print(sorted(rows, key=lambda row: row[0]))
        print(min(rows, key=lambda row: row[0]))
    print(rows)


main()
'''

P6_RESET = '''\
def main() -> None:
    for i in range(5):
        values: list[int] = []
        values = values + [i]
        print(values)
    for values in [[1], [2]]:
        values = values + [3]
        print(values)


main()
'''

NO_HITS = '''\
def main() -> None:
    total = 0
    known = {1, 2, 3}
    for number in [1, 2, 3]:
        if number in known:
            total += number
    print(total)


main()
'''


class RuleTests(Base):
    def test_p1_list_membership_index_count_inside_a_loop(self):
        program = self.write(P1)
        done = self.ail("check", "--perf", "--json", program)
        self.assertEqual(done.returncode, 0, done.stderr)
        report = [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]
        self.assertEqual([one["rule"] for one in report], ["P1", "P1", "P1"])
        self.assertEqual([one["line"] for one in report], [4, 6, 7])

    def test_p1_negative_outside_a_loop_on_a_set_and_on_a_loop_variant_list(self):
        self.assertEqual(self.rules(P1_NEGATIVE), [])

    def test_p2_pop_insert_del_inside_a_loop(self):
        self.assertEqual(self.rules(P2), ["P2", "P2", "P2"])

    def test_p2_negative_outside_a_loop(self):
        self.assertEqual(self.rules(P2_NEGATIVE), [])

    def test_p3_string_concatenation_inside_a_loop(self):
        self.assertEqual(self.rules(P3), ["P3"])

    def test_p3_negative_outside_a_loop_and_numeric_addition(self):
        self.assertEqual(self.rules(P3_NEGATIVE), [])

    def test_p3_not_reported_when_the_string_is_reset_or_is_the_loop_target(self):
        self.assertEqual(self.rules(P3_RESET), [])

    def test_p4_sort_and_reductions_inside_a_loop(self):
        self.assertEqual(self.rules(P4), ["P4", "P4", "P4", "P4", "P4"])

    def test_p4_negative_outside_a_loop_on_a_set_and_on_a_loop_variant_list(self):
        self.assertEqual(self.rules(P4_NEGATIVE), [])

    def test_p4_not_reported_when_the_key_or_reverse_depends_on_the_loop(self):
        self.assertEqual(self.rules(P4_KEYVAR), [])

    def test_p4_still_reported_for_a_constant_key(self):
        self.assertEqual(self.rules(P4_CONSTKEY), ["P4", "P4"])

    def test_p5_nested_loop_pairing_by_key(self):
        self.assertEqual(self.rules(P5), ["P5"])

    def test_p5_negative_index_loop_and_a_comparison_without_the_inner_item(self):
        self.assertEqual(self.rules(P5_NEGATIVE), [])

    def test_p6_list_rebuild_inside_a_loop(self):
        self.assertEqual(self.rules(P6), ["P6", "P6"])

    def test_p6_negative_outside_a_loop_and_a_returned_list(self):
        self.assertEqual(self.rules(P6_NEGATIVE), [])

    def test_p6_not_reported_when_the_list_is_reset_or_is_the_loop_target(self):
        self.assertEqual(self.rules(P6_RESET), [])


class CliTests(Base):
    def test_json_shape(self):
        program = self.write(P1)
        done = self.ail("check", "--perf", "--json", program)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, b"")
        report = json.loads(done.stdout.decode("utf-8").splitlines()[0])
        self.assertEqual(sorted(report), ["col", "file", "fix", "line", "loop_line", "message", "rule"])
        self.assertEqual(report["rule"], "P1")
        self.assertEqual(report["file"], str(program))
        self.assertEqual(report["line"], 4)
        self.assertIsInstance(report["col"], int)
        self.assertGreaterEqual(report["col"], 1)
        self.assertEqual(report["loop_line"], 3)
        self.assertIn("membership test", report["message"])
        self.assertIn("set", report["fix"])

    def test_text_line_shape(self):
        program = self.write(P1)
        done = self.ail("check", "--perf", program)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, b"")
        lines = done.stderr.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        pattern = re.compile(r"^%s:4:\d+: perf P1: .*; fix: .*$" % re.escape(str(program)))
        self.assertTrue(pattern.match(lines[0]), lines[0])
        self.assertNotIn("perf P", done.stdout.decode("utf-8"))

    def test_strict_exit_code_is_5_for_a_hit_and_0_without_one(self):
        program = self.write(P1)
        done = self.ail("check", "--perf", "--strict", program)
        self.assertEqual(done.returncode, 5, done.stderr)
        clean = self.write(NO_HITS, "clean.py")
        done = self.ail("check", "--perf", "--strict", clean)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_program_with_no_hits_prints_nothing(self):
        program = self.write(NO_HITS)
        for extra in ([], ["--json"]):
            with self.subTest(extra=extra):
                done = self.ail("check", "--perf", *extra, program)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout, b"")
                self.assertEqual(done.stderr, b"")

    def test_an_unreadable_or_unparseable_source_is_an_error(self):
        broken = self.write("def main(:\n", "broken.py")
        done = self.ail("check", "--perf", broken)
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout, b"")
        self.assertIn(b"broken.py", done.stderr)


if __name__ == "__main__":
    unittest.main()
