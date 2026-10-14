"""requires/ensures clauses: checked at entry and at every exit, failing with a named message.

`requires c;` and `ensures c;` are the first statements of a function body. `requires` is checked
on entry; `ensures` before every return (and at the end of a function without a result), with
`result` naming the returned value. A violated clause stops the program with exit status 1 and
"<requires|ensures> failed in <function>: <condition>" on stderr.
"""
import subprocess
import sys
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''struct Account { balance: int; }
impl Account {
    fn withdraw(self, amount: int) -> int {
        requires amount > 0;
        ensures result >= 0;
        self.balance = self.balance - amount;
        return self.balance;
    }
}
fn isqrt(n: int) -> int {
    requires n >= 0;
    ensures result * result <= n;
    ensures (result + 1) * (result + 1) > n;
    let result: int = 0;
    while (result + 1) * (result + 1) <= n { result += 1; }
    if n == 99 { return result + 1; }
    return result;
}
fn note(x: int, out: list[int]) -> void {
    requires x != 0;
    ensures x > -100;
    if x < 0 { return; }
    print(x);
}
fn main() -> int {
    let mode = sys.argv[1];
    let n = int(sys.argv[2]);
    if mode == "isqrt" { print(isqrt(n)); }
    elif mode == "note" { note(n, [1]); print("done"); }
    elif mode == "withdraw" { let a = Account(10); print(a.withdraw(n)); }
    return 0;
}'''


class ContractTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def run_case(self, program, *args):
        result = subprocess.run([str(program), *args], capture_output=True, timeout=30)
        return result.returncode, result.stdout.decode(), result.stderr.decode()

    def test_clauses_pass_and_fail(self):
        program = build(self, 'contracts', SOURCE)
        self.assertEqual(self.run_case(program, 'isqrt', '10'), (0, '3\n', ''))
        self.assertEqual(self.run_case(program, 'isqrt', '0'), (0, '0\n', ''))
        code, out, err = self.run_case(program, 'isqrt', '99')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('ensures failed in isqrt: result * result <= n', err)
        code, out, err = self.run_case(program, 'isqrt', '-4')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('requires failed in isqrt: n >= 0', err)
        self.assertEqual(self.run_case(program, 'note', '5'), (0, '5\ndone\n', ''))
        self.assertEqual(self.run_case(program, 'note', '-5'), (0, 'done\n', ''))
        code, out, err = self.run_case(program, 'note', '-200')
        self.assertEqual((code, out), (1, ''))
        self.assertIn('ensures failed in note: x > -100', err)
        self.assertEqual(self.run_case(program, 'withdraw', '4'), (0, '6\n', ''))
        code, out, err = self.run_case(program, 'withdraw', '12')
        self.assertEqual(code, 1)
        self.assertIn('ensures failed in Account.withdraw: result >= 0', err)
        code, out, err = self.run_case(program, 'withdraw', '0')
        self.assertIn('requires failed in Account.withdraw: amount > 0', err)

    def test_misplaced_or_invalid_clauses_are_refused(self):
        cases = {
            'late': 'fn f(x: int) -> int { let y = x; requires x > 0; return y; }',
            'result_in_requires': 'fn f(x: int) -> int { requires result > 0; return x; }',
            'result_without_result': 'fn f(x: int) -> void { ensures result > 0; print(x); }',
            'nested': 'fn f(x: int) -> int { if x > 0 { requires x > 1; } return x; }',
        }
        for name, body in cases.items():
            with self.subTest(name):
                path = self.write(name + '.ail', body + '\nfn main() -> int { return f(1); }\n')
                result = self.command('compile', path, '-o', self.root / name)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr + result.stdout, rb'requires|ensures')


if __name__ == '__main__':
    unittest.main()
