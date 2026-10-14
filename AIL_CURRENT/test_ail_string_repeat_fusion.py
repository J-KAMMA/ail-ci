"""Pure repeated-string loop fusion against original Python execution."""
import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

import test_ail_c_objects as support


class StringRepeatFusionTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build

    def build(self, source, stem, fused, fusion_function="run"):
        sys.path.insert(0, str(support.ROOT / 'python/pkg-v12'))
        try:
            from pyfunc import to_c
            from module_object import FLAGS
            info = {'_want_units': True, '_checked_arrays': True}
            generated = to_c(source, name='run', strict=True, library=True, info=info)
        finally:
            sys.path.pop(0)
        match = list(re.finditer(r'int64_t run\(int64_t v_n\)\s*\{', generated))
        self.assertEqual(len(match), 1, 'run entry ABI must remain scalar')
        definition = list(re.finditer(r'^[^;\n]*\b' + re.escape(fusion_function) + r'\([^;\n]*\)\s*\{', generated, re.M))
        self.assertEqual(len(definition), 1)
        body = generated[definition[0].start():]
        used = 'ail_str_repeat(' in body
        self.assertEqual(used, fused, f'{stem}: repeat call use disagrees with eligibility')
        host = r'''
int main(int argc,char **argv){
#ifdef _WIN32
 if(_setmode(1,_O_BINARY)==-1)return 8;
#endif
 if(argc!=2)return 9;return (int)run(atoll(argv[1]));
}
'''
        path = self.write(stem + '.c', generated + host)
        exe = self.root / (stem + ('.exe' if os.name == 'nt' else ''))
        cc = os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        self.assertTrue(cc, 'C compiler required')
        result = subprocess.run([cc, '-std=c11', *FLAGS, str(path), '-lm', '-o', str(exe)],
                                capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[:2500].decode(errors='replace'))
        return exe

    def compare(self, source, exe, sizes):
        oracle = self.write(exe.stem + '_oracle.py',
                            'import sys\nsys.stdout.reconfigure(encoding="utf-8",newline="\\n")\n' +
                            source + '\nraise SystemExit(run(int(sys.argv[1])))\n')
        for n in sizes:
            with self.subTest(n=n, program=exe.stem):
                expected = subprocess.run([sys.executable, '-B', str(oracle), str(n)],
                                          capture_output=True, timeout=60)
                actual = subprocess.run([str(exe), str(n)], capture_output=True, timeout=60)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((actual.returncode, actual.stderr), (0, b''))
                self.assertEqual(len(actual.stdout), len(expected.stdout))
                self.assertEqual(hashlib.sha256(actual.stdout).digest(),
                                 hashlib.sha256(expected.stdout).digest(), 'complete output mismatch')

    def test_target_counts_unicode_nul_prefix_alias_and_large_bound(self):
        patterns = ('a', '日本', '😀', '\0z')
        statements = ['def run(n:int)->int:']
        for k in (1, 4, 5, 16):
            statements += [f'    s{j}:str="prefix😀"' for j in range(k)]
            statements += ['    saved:str=s0', '    for i in range(n):']
            statements += [f'        s{j}+={patterns[j%4]!r}' for j in range(k)]
            statements += ['    print(saved)', '    print("|".join([' +
                           ','.join(f's{j}' for j in range(k)) + ']))']
        statements += ['    return 0']
        source = '\n'.join(statements)
        exe = self.build(source, 'shapes', True)
        # Large original Python oracle is linear; do not run an unfused native baseline.
        self.compare(source, exe, (-3, 0, 1, 2, 25, 2048, 65537))

    def test_parameter_snapshot_and_pure_arithmetic_bound(self):
        source = '''
def accumulate(n:int,prefix:str)->int:
    a:str=prefix
    saved:str=a
    for index in range(n+2):
        a+="é😀\\0"
    print(saved+"|"+a)
    return 0

def run(n:int)->int:
    accumulate(n,"seed日本")
    return 0
'''
        exe = self.build(source, 'parameter', False, fusion_function='accumulate')
        self.compare(source, exe, (-3, -2, -1, 0, 1, 25, 2048))
    def test_dynamic_rhs_duplicate_target_and_index_observation_fallback(self):
        source = '''
def value(i:int)->str:
    print(i)
    return "x"

def run(n:int)->int:
    a:str="p"
    b:str="q"
    suffix:str="x"
    i:int=-9
    for i in range(n):
        a+="x"
        a+="y"
    print(i)
    for j in range(n):
        b+=suffix
    print(a)
    print(b)
    return 0
'''
        exe = self.build(source, 'fallback', False)
        self.compare(source, exe, (0, 1, 2, 25))

    def test_effectful_count_once_shadow_range_and_control_flow_fallback(self):
        sources = ('''
def bound(n:int)->int:
    print(17)
    return n

def run(n:int)->int:
    a:str="p"
    for i in range(bound(n)):
        a+="x"
    print(a)
    return 0
''', '''
def range(n:int)->list[int]:
    print(19)
    return [3,1]

def run(n:int)->int:
    a:str="p"
    for i in range(n):
        a+="x"
    print(a)
    return 0
''', '''
def run(n:int)->int:
    a:str="p"
    for i in range(n):
        if i==2:
            break
        a+="x"
    print(a)
    return 0
''')
        for index, source in enumerate(sources):
            exe = self.build(source, f'effect{index}', False)
            self.compare(source, exe, (-3, 0, 1, 4))

    def test_range_target_retains_last_value_and_body_rebinding_does_not_advance_iterator(self):
        source = '''
def run(n:int)->int:
    i:int=-9
    for i in range(n):
        i+=100
        print(i)
    print(i)
    i=-9
    for i in range(3,3+n):
        i+=100
        print(i)
    print(i)
    i=-9
    for i in range(3,-n,-1):
        i+=100
        print(i)
    print(i)
    i=-9
    for i in range(n):
        if i==1:
            continue
        if i==3:
            break
    print(i)
    return 0
'''
        exe = self.build(source, 'target-values', False)
        self.compare(source, exe, (-3, 0, 1, 2, 4))

    def test_source_free_compiled_module_retains_same_results(self):
        module = '''fn expanded(n:int,prefix:str)->str {
 let a:str=prefix;let b:str="";let c:str="";let d:str="";
 for i in range(n) {a+="日本😀";b+="xy";c+="x";d+="y";}
 return a+"|"+b;
}'''
        obj = self.ail_build('builders', module, library=True)
        relocated = self.root / 'relocated'
        relocated.mkdir()
        moved = relocated / 'builders.o'
        shutil.move(str(obj), moved)
        shutil.move(str(obj)+'.json', str(moved)+'.json')
        before = [(p.read_bytes(),p.stat().st_mtime_ns) for p in (moved,Path(str(moved)+'.json'))]
        exe = self.ail_build('entry', 'fn main()->int {print(expanded(25,"seed"));return 0;}', moved)
        result = subprocess.run([str(exe)], capture_output=True, timeout=30)
        expected = ('seed'+'日本😀'*25+'|'+'xy'*25+'\n').encode('utf-8')
        if os.name == 'nt':
            expected = expected.replace(b'\n', b'\r\n')
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,expected,b''))
        self.assertEqual([(p.read_bytes(),p.stat().st_mtime_ns) for p in (moved,Path(str(moved)+'.json'))],before)


if __name__ == '__main__':
    unittest.main()