"""Typed borrowed numeric row arguments through public compilation paths."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_float64_codec import compiler

REDUCE = 'fn reduce(values:list[int])->int {return sum(values);}\n'
CHOOSE = 'fn choose(index:int)->int {print(index);return index;}\n'

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class PoolRowArgumentTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run
    snapshot = support.CObjectTests.snapshot

    def test_rows_aliases_empty_and_indices_evaluated_once(self):
        source = REDUCE + CHOOSE + '''fn main()->int {
 let g=[[1,2,3],[]];let row=g[0];print(reduce(row));
 print(reduce(g[choose(0)]));print(reduce(g[choose(-1)]));
 try {print(reduce(g[choose(2)]));} except IndexError {print("index");}
 try {print(reduce(g[choose(-3)]));} except IndexError {print("index");}
 try {print(reduce(g[choose(-9223372036854775807-1)]));} except IndexError {print("index");}
 return 0;
}'''
        self.check_run(self.ail_build('row_indices', source),
                       '6\n0\n6\n-1\n0\n2\nindex\n-3\nindex\n-9223372036854775808\nindex\n')

    def test_integer_key_dictionary_rows(self):
        source=REDUCE+CHOOSE+'''fn main()->int {
 let rows={};rows[7]=[];rows[7].append(1);rows[7].append(2);rows[7].append(3);rows[9]=[];
 print(reduce(rows[choose(7)]));print(reduce(rows[choose(9)]));
 try {print(reduce(rows[choose(11)]));} except KeyError {print("missing");}
 return 0;
}'''
        self.check_run(self.ail_build('dict_rows',source),'7\n6\n9\n0\n11\nmissing\n')
    def test_positional_and_keyword_arguments_keep_evaluation_order(self):
        source = CHOOSE + '''fn combine(left:list[int],right:list[int],tail:int)->int {
 return sum(left)*100+sum(right)*10+tail;
}
fn main()->int {
 let g=[[1],[2]];
 print(combine(g[choose(0)],g[choose(1)],choose(3)));
 print(combine(tail=choose(4),right=g[choose(1)],left=g[choose(0)]));
 return 0;
}'''
        self.check_run(self.ail_build('row_order', source), '0\n1\n3\n123\n4\n1\n0\n124\n')

    def test_returned_list_owns_values_after_row_mutation(self):
        source='''fn copy_row(values:list[int])->list {return values;}
fn main()->int {let g=[[1,2,3]];let result=copy_row(g[0]);
 let row=g[0];row.append(9);print(len(result));print(len(row));print(result[-1]);print(row[-1]);return 0;}'''
        self.check_run(self.ail_build('row_return_copy',source),'3\n4\n3\n9\n')
    def test_borrowed_row_parameter_mutation_is_refused(self):
        source = self.write('row_mutation.ail', '''fn change(xs:list[int])->int {
 xs[0]=71;return xs[-1];}
fn main()->int {let g=[[1,2,3]];print(change(g[0]));return 0;}''')
        output = self.root / 'row_mutation'
        result = self.command('compile', source, '-o', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'list parameter', result.stderr)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + '.exe').exists())

    def test_full_wide_row_output_matches_independent_python_values(self):
        values = [(1 << 53) + 1, -(1 << 53) - 1, (1 << 63) - 1, -(1 << 63), 17]
        source = '''fn output(xs:list[int])->int {for value in xs {print(value);}return len(xs);}
fn main()->int {let g=[[''' + ','.join(map(str, values)) + ''']];
 print(output(g[0]));return 0;}'''
        self.check_run(self.ail_build('row_wide', source),
                       ''.join(f'{value}\n' for value in values) + f'{len(values)}\n')

    def test_callee_index_empty_fold_and_strict_sum_overflow(self):
        source = REDUCE + '''fn first(xs:list[int])->int {return xs[0];}
fn smallest(xs:list[int])->int {return min(xs);}
fn main()->int {let g=[[]];print(reduce(g[0]));
 try {print(first(g[0]));} except IndexError {print("index");}
 try {print(smallest(g[0]));} except ValueError {print("empty");}
 return 0;}'''
        self.check_run(self.ail_build('row_empty', source), '0\nindex\nempty\n')
        executable = self.ail_build('row_overflow', REDUCE + '''fn main()->int {
 let g=[[9223372036854775807,1,-1]];print(reduce(g[0]));return 0;}''')
        result = subprocess.run([str(executable)], capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'integer overflow', result.stderr)

    def test_separate_and_relocated_source_free_module(self):
        helper = self.write('row_helper.ail', REDUCE)
        entry = self.write('row_entry.ail', 'use row_helper;\n' + CHOOSE + '''fn main()->int {
 let g=[[1,2,3]];print(reduce(g[choose(0)]));return 0;}''')
        output = self.root / 'separate'
        result = self.command('compile', entry, '--separate', '-o', output)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.check_run(output if output.is_file() else Path(str(output) + '.exe'), '0\n6\n')
        obj = self.ail_build('row_module', REDUCE, library=True)
        relocated = self.root / 'relocated objects'; relocated.mkdir()
        moved = relocated / obj.name
        obj.rename(moved); Path(str(obj) + '.json').rename(Path(str(moved) + '.json'))
        helper.unlink(); entry.unlink()
        before = self.snapshot(moved)
        executable = self.ail_build('source_free', CHOOSE + '''fn main()->int {
 let g=[[1,2,3]];print(reduce(g[choose(0)]));return 0;}''', moved)
        self.check_run(executable, '0\n6\n')
        self.assertEqual(self.snapshot(moved), before)

    def test_shadowed_sum_keeps_user_function_binding(self):
        source = '''fn sum(xs:list[int])->int {return xs[0]+40;}
fn main()->int {let g=[[2]];print(sum(g[0]));return 0;}'''
        self.check_run(self.ail_build('row_shadow', source), '42\n')

class PoolRowArgumentRefusalTests(unittest.TestCase):
    def test_wrong_shapes_are_refused(self):
        to_c, unsupported = compiler()
        prefix = 'def reduce(values:list[int])->int:\n return sum(values)\n'
        for setup, value in (('g=[[1,2]]', '1'), ('g=[[1,2]]', 'g'),
                             ('g=[(1,2)]', 'g[0]'), ('g=[[1.0,2.0]]', 'g[0]'),
                             ('g=[["a","b"]]', 'g[0]'), ('g=[[[1]]]', 'g[0]')):
            with self.subTest(setup=setup, value=value), self.assertRaises(unsupported):
                to_c(prefix + f'def run()->int:\n {setup}\n return reduce({value})\n',
                     name='run', strict=True)

    def test_nested_record_rows_are_refused(self):
        to_c, unsupported = compiler()
        source = '''class Record:
 def __init__(self,value:int):
  self.value=value
def reduce(values:list[int])->int:
 return sum(values)
def run()->int:
 g=[[Record(1)]]
 return reduce(g[0])
'''
        with self.assertRaises(unsupported):
            to_c(source, name='run', strict=True)

if __name__ == '__main__':
    unittest.main()