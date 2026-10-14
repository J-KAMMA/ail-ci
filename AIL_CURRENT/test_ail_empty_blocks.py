"""Empty code blocks preserve checks, source positions, and observable evaluation."""
import ast
import os
import shutil
import unittest

import ail_syntax
import test_ail_c_objects as native_support
import test_ail_source_check as check_support


class EmptyBlockTests(unittest.TestCase):
    setUp = check_support.SourceCheckTests.setUp
    source = check_support.SourceCheckTests.source
    check = check_support.SourceCheckTests.check

    def test_empty_control_blocks_and_void_function_are_checked(self):
        source = self.source('''fn helper()->void {}
fn main()->int {
 helper();
 if 0 {} elif 0 {} else {}
 while 0 {}
 for item in range(0) {}
 try {} except ValueError {} else {} finally {}
 return 0;
}''')
        status, report = self.check(source)
        self.assertEqual(status, 0, report)
        tree = ast.parse(ail_syntax.translate(source.read_text(encoding='utf8')))
        self.assertEqual(sum(isinstance(node, ast.Pass) for node in ast.walk(tree)), 10)

    def test_comment_crlf_unicode_empty_block_source_positions(self):
        text = '# 日本語 😀\r\nfn helper()->void { # 空本文 }\r\n  # { コメント\r\n}\r\nfn main()->int {helper();return 0;}\r\n'
        positions = {}
        translated = ail_syntax.translate(text, source_map=positions)
        tree = ast.parse(translated)
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'helper')
        self.assertEqual(len(helper.body), 1)
        self.assertIsInstance(helper.body[0], ast.Pass)
        self.assertEqual(positions[helper.body[0].lineno], (4, 1))
        self.assertEqual(positions[helper.lineno], (2, 1))
        status, report = self.check(self.source(text))
        self.assertEqual(status, 0, report)

    def test_nonvoid_missing_return_still_rejected(self):
        # main itself may fall off its end (it exits 0, as sys.exit(None) does); see
        # test_main_falls_off_end below.
        for text in ('fn helper()->int {} fn main()->int {return 0;}',
                     'fn helper()->str {} fn main()->int {return 0;}',
                     'fn helper()->int {} fn main()->int {return helper();}'):
            with self.subTest(text=text):
                status, report = self.check(self.source(text))
                self.assertNotEqual(status, 0, report)
                self.assertEqual(report['status'], 'failed')

    def test_main_falls_off_end(self):
        status, report = self.check(self.source('fn main()->int {}'))
        self.assertEqual(status, 0, report)

    def test_empty_dict_is_expression_and_invalid_containers_and_semicolon_rejected(self):
        translated = ail_syntax.translate('fn main()->int {let values:dict[str,int]={};return len(values);}')
        tree = ast.parse(translated)
        self.assertEqual(sum(isinstance(node, ast.Dict) for node in ast.walk(tree)), 1)
        self.assertEqual(sum(isinstance(node, ast.Pass) for node in ast.walk(tree)), 0)
        for text in ('struct Box {} fn main()->int {return 0;}',
                     'struct Box {x:int;} impl Box {} fn main()->int {return 0;}',
                     'fn main()->int {return 0}',
                     'fn main()->int {let value=1; if 0 {value=2} return 0;}'):
            with self.subTest(text=text), self.assertRaises(ail_syntax.SyntaxErrorAIL):
                ail_syntax.translate(text)


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class EmptyBlockNativeTests(unittest.TestCase):
    setUp = native_support.CObjectTests.setUp
    write = native_support.CObjectTests.write
    command = native_support.CObjectTests.command
    ail_build = native_support.CObjectTests.ail_build
    check_run = native_support.CObjectTests.check_run

    def test_empty_blocks_preserve_side_effects_and_exception_finally(self):
        executable = self.ail_build('empty_blocks', '''struct Box {value:int;}
impl Box {fn noop(self)->void {}}
fn helper()->void {}
fn mark(label:int,value:int)->int {print(label);return value;}
fn items()->list[int] {print(40);return [7,8];}
fn main()->int {
 helper(); let box=Box(5); box.noop();
 if mark(10,1) {} elif mark(11,1) {} else {}
 if mark(20,0) {} elif mark(21,1) {} else {}
 while mark(30,0) {}
 for item in items() {}
 try {} except ValueError {} else {} finally {print(50);}
 try {raise ValueError;} except ValueError {} finally {print(60);}
 print(box.value);return 0;
}''')
        self.check_run(executable, '10\n20\n21\n30\n40\n50\n60\n5\n')


if __name__ == '__main__':
    unittest.main()