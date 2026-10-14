"""Native and public-check coverage for the bounded long-option parser."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import test_ail_c_objects as support

ROOT = support.ROOT


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class CliArgsTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command
    write = support.CObjectTests.write
    ail_build = support.CObjectTests.ail_build
    check_run = support.CObjectTests.check_run

    def test_standalone_library_check(self):
        result = self.command('check', ROOT / 'language_examples/cli_args.ail', '--library')
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(json.loads(result.stdout)['status'], 'passed')

    def test_values_positionals_specifications_and_errors(self):
        source = r'''use cli_args;
fn fails(args:list[str], values:list[str], switches:list[str])->int {
    try { let result=cli_parse(args,values,switches); }
    except ValueError { return 1; }
    return 0;
}
fn main()->int {
    let args:list[str]=["before","--text=a=b","--verbose","--empty=","--number","-42","--","--unknown","-","-3"];
    let values:list[str]=["text","empty","number"];
    let switches:list[str]=["verbose"];
    let parsed=cli_parse(args,values,switches);
    if len(parsed.options)!=4 or parsed.options["text"]!="a=b" or parsed.options["empty"]!="" or parsed.options["verbose"]!="" or parsed.options["number"]!="-42" { return 1; }
    if len(parsed.positional)!=4 or parsed.positional[0]!="before" or parsed.positional[1]!="--unknown" or parsed.positional[2]!="-" or parsed.positional[3]!="-3" { return 2; }
    if len(args)!=10 or args[1]!="--text=a=b" or len(values)!=3 or len(switches)!=1 { return 3; }
    let unicode=cli_parse(["--text","日本語\x00😀","--raw=--literal=tail",""],["text","raw"],[]);
    if unicode.options["text"]!="日本語\x00😀" or unicode.options["raw"]!="--literal=tail" or len(unicode.positional)!=1 or unicode.positional[0]!="" { return 4; }
    let empty=cli_parse([],[],[]);
    if len(empty.options)!=0 or len(empty.positional)!=0 { return 5; }
    let short=cli_parse(["-x","-","-7"],[],[]);
    if len(short.positional)!=3 { return 6; }
    let valid=cli_parse(["--A9_-"],["name"],["A9_-"]);
    if "A9_-" not in valid.options { return 7; }
    if fails(["--unknown"],[],[])!=1 or fails(["---"],[],[])!=1 or fails(["--=x"],[],[])!=1 { return 8; }
    if fails(["--text"],["text"],[])!=1 or fails(["--text","--"],["text"],[])!=1 or fails(["--text","--other"],["text"],[])!=1 { return 9; }
    if fails(["--s="],[],["s"])!=1 or fails(["--s","--s"],[],["s"])!=1 or fails(["--x=1","--x","2"],["x"],[])!=1 { return 10; }
    if fails([],["x","x"],[])!=1 or fails([],[],["x","x"])!=1 or fails([],["x"],["x"])!=1 { return 11; }
    for bad in ["","0x","-x","_x","a b","a=b","é","x\x00","--x"] {
        if fails([],[bad],[])!=1 or fails([],[],[bad])!=1 { return 12; }
    }
    let repeated=0;
    while repeated<100 {
        let copy=cli_parse(["--text=日本語\x00😀"],["text"],[]);
        if copy.options["text"]!="日本語\x00😀" { return 13; }
        repeated+=1;
    }
    print("ok"); return 0;
}'''
        executable = self.ail_build('cli_cases', source)
        self.check_run(executable, 'ok\n')

    def test_invalid_arguments_do_not_create_or_change_output(self):
        executable = self.ail_build('cli_output', '''use cli_args;
fn main()->int {
    let output=sys.argv[1];
    let args:list[str]=[];
    for i in range(2,len(sys.argv)) { args.append(sys.argv[i]); }
    try {
        let result=cli_parse(args,["text"],["verbose"]);
        write_bytes(output,result.options.get("text","").encode("utf-8"));
    } except ValueError { return 2; }
    return 0;
}''')
        for tokens in (["--unknown"], ["--text"], ["--text","--verbose"],
                       ["--verbose","--verbose"], ["--text=x","--text=y"], ["--verbose="]):
            with self.subTest(tokens=tokens):
                output = self.root / 'output.txt'
                for existing in (False, True):
                    if existing:
                        output.write_bytes(b'unchanged')
                    result = subprocess.run([str(executable), str(output), *tokens],
                                            capture_output=True, timeout=30)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (2, b'', b''))
                    if existing:
                        self.assertEqual(output.read_bytes(), b'unchanged')
                        output.unlink()
                    else:
                        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()