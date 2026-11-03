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
        source='import sys\n\ndef bound(value: int) -> int:\n    print(value)\n    return value\n\ndef emit(args: list[str]) -> None:\n    for value in args:\n        print(value.encode(\'utf-8\').hex())\n\ndef main() -> int:\n    args: list[str] = sys.argv[1:]\n    emit(args)\n    saved: list[str] = sys.argv[-2:]\n    args.clear()\n    emit(saved)\n    emit(sys.argv[bound(1):bound(3)])\n    emit(sys.argv[9223372036854775807:])\n    emit(sys.argv[-9223372036854775808:0])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'
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