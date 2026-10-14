"""Scalar local list mutation with independent Python values and allocation accounting."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from ail_syntax import translate
sys.path.insert(0,str(Path(__file__).resolve().parent/'python/pkg-v12'))
from pyfunc import to_c
from pyfront import Unsupported
import cruntime
import test_ail_c_objects as support
import test_ail_struct_lifetimes as resources
from test_ail_callable_values import oracle_source
from test_ail_text_find_search import HEADERS

WHOLE=r'''
fn retained()->str {
 let words:list[str]=["old"+str(1),"日本語\0😀"+str(2)];
 let result=words.pop();words.clear();words=["replacement"];return result;
}
fn index()->int {print("index");return -2;}
fn main()->int {
 let ints:list[int]=[-9223372036854775808,0,9223372036854775807];ints.reverse();
 for integer_item in ints {print(integer_item);}ints.reverse();print(ints[0]);
 let floats:list[float]=[1.5,-0.0,2.5];floats.reverse();for float_item in floats {print(float_item);}
 let words:list[str]=["first","日本語\0😀","last"];words.reverse();
 let saved=words.pop(index());words.clear();words=["new"];print(saved);print(retained());
 let empty:list[str]=[];empty.reverse();let singleton:list[int]=[7];singleton.reverse();print(singleton[0]);
 try {empty.pop();}except IndexError {print("empty");}finally {singleton.reverse();}
 let remaining:list[str]=["a","b"];print(remaining.pop(-1));print(remaining.pop(0));
 try {remaining.pop(-9223372036854775808);}except IndexError {print("min");}
 let present:list[str]=["x"];
 try {present.pop(9223372036854775807);}except IndexError {print("max");}
 return 0;
}
'''

# Original failing source is retained independently; future numeric-binding work must pass it.
MIXED_ITERATOR_WHOLE=WHOLE.replace('integer_item','item').replace('float_item','item')
ORIGINAL_FUNCTION_SCOPE_RESOURCE='''
def run(n: int) -> int:
    total = 0
    for i in range(n):
        words: list[str] = ["old" + str(i), "日本語\\0😀" + str(i)]
        words.reverse()
        saved = words.pop(0)
        words.clear()
        words = ["new"]
        total += len(saved)
        try:
            words.pop(9223372036854775807)
        except IndexError:
            total += 1
        finally:
            words.reverse()
    return total
'''
RESOURCE='''
def step(i: int) -> int:
    words: list[str] = ["old" + str(i), "日本語\\0😀" + str(i)]
    words.reverse()
    saved = words.pop(0)
    words.clear()
    words = ["new"]
    total = len(saved)
    try:
        words.pop(9223372036854775807)
    except IndexError:
        total += 1
    finally:
        words.reverse()
    return total

def run(n: int) -> int:
    total = 0
    for i in range(n):
        total += step(i % 10)
    return total
'''

class ScalarListMutationTypeTests(unittest.TestCase):
    def test_whole_and_allocator_workloads_compile(self):
        to_c(translate(WHOLE),strict=True)
        to_c(RESOURCE,name='run',strict=True,library=True)

    def test_borrowed_parameters_bad_indices_and_float_sort_refused(self):
        for kind,call in [('int','xs.reverse()'),('float','xs.reverse()'),('str','xs.reverse()'),('str','xs.pop()')]:
            with self.subTest(kind=kind,call=call),self.assertRaises(Unsupported):
                to_c(translate('fn probe(xs:list['+kind+'])->void {'+call+';}',module=True),strict=True,library=True)
        for expr in ('xs.pop(1.5)','xs.pop(b"x")','xs.pop(index=0)','xs.pop(0,1)','xs.reverse(0)'):
            with self.subTest(expr=expr),self.assertRaises(Unsupported):
                to_c(translate('fn main()->int {let xs:list[str]=["x"];'+expr+';return 0;}'),strict=True)
        with self.assertRaises(Unsupported):
            to_c(translate('fn probe(xs:list[float])->void {xs.sort();}',module=True),strict=True,library=True)

    def test_nested_and_record_lists_do_not_enter_scalar_reverse(self):
        from test_ail_grid_return import GRID
        cases=[
            GRID+'fn main()->int {let values=grid(2,2);values.reverse();return 0;}',
            'fn main()->int {let outer=[];let row=[];row.append(1);outer.append(row);outer.reverse();return 0;}',
            'fn main()->int {let values=[];values.append((1,2));values.reverse();return values[0][0];}',
        ]
        for source in cases:
            with self.subTest(source=source),self.assertRaisesRegex(Unsupported,'scalar list reverse requires scalar elements'):
                to_c(translate(source),strict=True)
        # Struct lists already have reference-aware reverse; preserve that dispatch.
        code=to_c(translate('struct Item {value:int;} fn main()->int {let values:list[Item]=[Item(1),Item(2)];values.reverse();return 0;}'),strict=True)
        self.assertRegex(code,r'ail_olist_reverse\(v__t\d+\)')
        self.assertNotIn('ail_list_reverse(&v_values)',code)
    def test_existing_field_slot_mutation_remains_supported(self):
        to_c(translate('struct Box {ints:list[int];floats:list[float];words:list[str];} fn main()->int {let box=Box([1,2],[1.5,2.5],["a","b"]);box.ints.reverse();box.floats.reverse();box.words.reverse();let saved=box.words.pop();box.words.clear();print(saved);return 0;}'),strict=True)

@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),'installed C compiler required')
class ScalarListMutationNativeTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    write=support.CObjectTests.write
    command=support.CObjectTests.command
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run
    check_lifetimes=resources.StructLifetimeTests.check_lifetimes

    def test_whole_output_independent_python_oracle(self):
        namespace={};exec(oracle_source(translate(WHOLE)).removesuffix('\nsys.exit(main())'),namespace)
        output=io.StringIO()
        with contextlib.redirect_stdout(output):namespace['main']()
        self.check_run(self.ail_build('scalar_mutation',WHOLE),output.getvalue())

    def test_owned_pop_escape_finally_errors_zero_live(self):
        self.check_lifetimes(RESOURCE,sizes=(1,32,1024))

    def test_numeric_only_programs_include_required_bounds(self):
        for kind,values,expected in [('int','[3,2,1]','1\n'),('float','[1.5,2.5]','2.5\n')]:
            with self.subTest(kind=kind):
                program='fn main()->int {let values:list['+kind+']='+values+';values.reverse();print(values[0]);return 0;}'
                self.check_run(self.ail_build('numeric_only_'+kind,program),expected)
    def test_runtime_invalid_spine_and_int64_capacity_guards(self):
        host=r'''
int main(int argc,char **argv) {
 int mode=argc>1?atoi(argv[1]):0;int64_t i=1;double f=1;ail_str s={0};
 ail_list ints={&i,1,1};ail_flist floats={&f,1,1};ail_slist words={&s,1,1};
 switch(mode) {
 case 1:ints.n=-1;ail_list_reverse(&ints);break;
 case 2:floats.cap=0;ail_flist_reverse(&floats);break;
 case 3:words.p=NULL;ail_slist_reverse(&words);break;
 case 4:ints.cap=INT64_MAX;ail_list_reverse(&ints);break;
 case 5:floats.cap=INT64_MAX;ail_flist_reverse(&floats);break;
 case 6:words.cap=INT64_MAX;ail_slist_reverse(&words);break;
 case 7:words.n=-1;ail_sarena arena={0};ail_slist_pop(&arena,&words,0);break;
 case 8:s.n=INT64_MAX;ail_sarena arena2={0};ail_slist_pop(&arena2,&words,0);break;
 default:return 0;
 }
 return 91;
}
'''
        compiler=os.environ.get('PIPE_CC') or shutil.which('gcc') or shutil.which('cc')
        path=self.write('scalar_guards.c',HEADERS+cruntime.emit({'LIST','FLIST','SLIST'})+host)
        binary=self.root/('scalar_guards.exe' if os.name=='nt' else 'scalar_guards')
        result=subprocess.run([compiler,'-std=c11','-O2',str(path),'-lm','-o',str(binary)],capture_output=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        self.check_run(binary,'')
        for mode in range(1,9):
            with self.subTest(mode=mode):
                result=subprocess.run([str(binary),str(mode)],capture_output=True,timeout=30)
                self.assertNotEqual(result.returncode,0);self.assertNotEqual(result.returncode,91)

if __name__=='__main__':unittest.main()