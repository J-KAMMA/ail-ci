"""Command argument list slices: typed calls, bounds, lifetime and refusals."""
import unittest
import test_ail_c_objects as support

class ArgvSliceTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    ail_build=support.CObjectTests.ail_build
    check_run=support.CObjectTests.check_run
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def test_owned_slices_pass_to_functions_and_keep_bound_order(self):
        source='''fn bound(value:int)->int {print(value);return value;}
fn emit(args:list[str])->void {for value in args {print(value.encode("utf-8").hex());}}
fn main()->int {
 let args:list[str]=sys.argv[1:];emit(args);
 let saved:list[str]=sys.argv[-2:];args.clear();emit(saved);
 emit(sys.argv[bound(1):bound(3)]);
 emit(sys.argv[9223372036854775807:]);
 emit(sys.argv[-9223372036854775808:0]);return 0;
}'''
        executable=self.ail_build('argv_slices',source)
        values=['日本😀','','--flag','-1']
        encoded=[value.encode().hex()+'\n' for value in values]
        expected=''.join(encoded)+''.join(encoded[-2:])+'1\n3\n'+''.join(encoded[:2])
        self.check_run(executable,expected,*values)

    def test_float_and_step_refused_before_artifact(self):
        for i,expression in enumerate(('sys.argv[1.5:]','sys.argv[::1]','sys.argv[::-1]')):
            source=self.write(f'bad_argv_{i}.ail',f'fn main()->int {{let args:list[str]={expression};return 0;}}')
            output=self.root/f'bad_argv_{i}'
            result=self.command('compile',source,'-o',output)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn(b'Traceback',result.stderr)
            self.assertFalse(output.exists());self.assertFalse(output.with_suffix('.exe').exists())

if __name__=='__main__':unittest.main()