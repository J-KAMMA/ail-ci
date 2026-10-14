"""Pooled row sources execute once and survive pool relocation."""
import subprocess
import unittest
import test_ail_c_objects as support

CHOOSE='fn choose(index:int)->int {print("choose");return index;}\n'

class PoolIterCaptureTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run

    def test_folds_empty_early_exit_and_lazy_contexts(self):
        program=CHOOSE+'''fn main()->int {
 let g=[[1,2,3],[0,9],[]];
 print(sum(g[choose(0)]));print(max(g[choose(0)]));print(min(g[choose(0)]));
 if any(g[choose(0)]) {print(1);} else {print(0);}
 if all(g[choose(1)]) {print(1);} else {print(0);}
 for value in g[choose(0)] {print(value);}
 print(sum(value for value in g[choose(0)]));
 print(sum(g[choose(2)]));
 if any(g[choose(2)]) {print(1);} else {print(0);}
 if all(g[choose(2)]) {print(1);} else {print(0);}
 try {print(max(g[choose(2)]));} except ValueError {print("empty");}
 if False and sum(g[choose(0)])>0 {print("bad");}
 print(sum(g[choose(0)]) if False else 41);
 print(sum(g[choose(0)]) if True else 42);
 return 0;
}'''
        expected=('choose\n6\nchoose\n3\nchoose\n1\nchoose\n1\nchoose\n0\n'
                  'choose\n1\n2\n3\nchoose\n6\nchoose\n0\nchoose\n0\n'
                  'choose\n1\nchoose\nempty\n41\nchoose\n6\n')
        self.check_run(self.ail_build('pool_fold_capture',program),expected)

    def test_negative_and_invalid_indices_once(self):
        program=CHOOSE+'''fn main()->int {
 let g=[[1,2,3]];print(sum(g[choose(-1)]));
 try {print(sum(g[choose(1)]));} except IndexError {print("index");}
 try {for value in g[choose(-2)] {print(value);}} except IndexError {print("index");}
 return 0;
}'''
        self.check_run(self.ail_build('pool_capture_indices',program),
                       'choose\n6\nchoose\nindex\nchoose\nindex\n')

    def test_original_row_survives_replacement_and_growth(self):
        program=CHOOSE+'''fn main()->int {
 let g=[[1,2,3],[99]];
 for value in g[choose(0)] {
  print(value);g[0]=g[1];for index in range(65) {g.append([]);}
 }
 print(g[0][0]);return 0;
}'''
        self.check_run(self.ail_build('pool_capture_growth',program),'choose\n1\n2\n3\n99\n')

    def test_sum_wide_exact_values_and_intermediate_overflow(self):
        values=[(1<<53)+1,17,-9]
        literal=','.join(map(str,values))
        program=CHOOSE+f'''fn main()->int {{
 let g=[[{literal}]];print(sum(g[choose(0)]));return 0;
}}'''
        self.check_run(self.ail_build('pool_capture_wide',program),f'choose\n{sum(values)}\n')
        program='''fn main()->int {
 let g=[[9223372036854775807,1,-1]];print(sum(g[0]));return 0;
}'''
        executable=self.ail_build('pool_capture_overflow',program)
        result=subprocess.run([str(executable)],capture_output=True,timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,b'')
        self.assertIn(b'integer overflow',result.stderr)

    def test_shadowed_fold_return_types_and_two_arguments(self):
        program='''fn sum(value:int)->float {return float(value)+0.5;}
fn max(left:int,right:int)->float {return float(left)+float(right)+0.5;}
fn main()->int {print(sum(7));print(max(7,11));return 0;}'''
        self.check_run(self.ail_build('pool_capture_shadow_float',program),'7.5\n18.5\n')
    def test_separate_compiled_function_keeps_single_evaluation(self):
        library=self.write('capture_reduce.ail',CHOOSE+'''fn reduce()->int {
 let g=[[1,2,3]];return sum(g[choose(0)]);
}''')
        source=self.write('capture_caller.ail','use capture_reduce; fn main()->int {print(reduce());return 0;}')
        binary=self.root/'capture-separated.exe'
        built=self.command('compile',source,'--separate','-o',binary)
        self.assertEqual(built.returncode,0,built.stderr.decode(errors='replace'))
        self.check_run(binary,'choose\n6\n')
    def test_shadowed_sum_user_function(self):
        program=CHOOSE+'''fn sum(value:int)->int {print("user");return value+10;}
fn main()->int {print(sum(choose(7)));return 0;}'''
        self.check_run(self.ail_build('pool_capture_shadow',program),'choose\nuser\n17\n')

if __name__=='__main__':unittest.main()
