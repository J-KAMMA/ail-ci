"""G5a: `import cmd` in compiled programs (bundled stdlib/cmd.py) against CPython's cmd.

The ten programs in lab/stdlib/cmd/ subclass cmd.Cmd and use the ordinary command-loop API:
prompts and intros, do_* methods with and without arguments, do_EOF, default/unknown commands,
the default and an overridden emptyline, precmd/postcmd/preloop/postloop, help tables and
help_* methods, parseline, cmdqueue and direct onecmd calls.  Each is compiled with the default
command and run beside `python3` on the same source (feeding its .in file when it has one);
stdout and the exit status must agree.  Nine programs must match exactly; the calculator stops
loudly on an int beyond int64, which the task allows.

The module cannot enumerate a class's methods or read a method's `__doc__` or call a method
whose name is only known at run time: `get_names()` returns CPython's fixed base names plus
the commands of the supported vocabulary that the instance defines, so the no-argument `help`
table and `completenames()` are exact for those names (and for a `get_names()` override).  A
command is documented in that table when it has a `help_<name>` method or when its docstring
is the literal in the module (the base `do_help`); otherwise it is listed as undocumented,
which is CPython's answer for a command with no docstring.  The cases that need the missing
compiler features stop with a named `NotImplementedError` instead of guessing: a `do_*`
command outside the vocabulary, a `help_<name>` outside it, and `help <name>` for a
docstring-only command.  The constructor's `stdin`/`stdout` are stored and used like
CPython's; only the two process streams are represented by small stand-ins, because this
compiler refuses `sys.stdin`/`sys.stdout` as values.  The tests pin the table, the streams,
the exact reflection cases and the loud stops.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "cmd"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

PASSING = [
    "01_hello_commands.py",
    "02_unknown_and_empty.py",
    "03_emptyline_override.py",
    "04_hooks.py",
    "05_help.py",
    "06_parseline.py",
    "07_cmdqueue.py",
    "08_onecmd.py",
    "10_aliases.py",
]
ALL = PASSING + ["09_calculator.py"]


def stdin_for(source):
    side = source.with_suffix(".in")
    if side.is_file():
        return side.read_bytes()
    return b""


def run_cpython(path, data):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          input=data, capture_output=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibCmdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-cmd-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual(sorted(p.name for p in PROGRAMS.glob("*.py")), sorted(ALL))

    def test_programs_match_cpython(self):
        for name in PASSING:
            source = PROGRAMS / name
            data = stdin_for(source)
            work = self.dir / source.stem
            work.mkdir(exist_ok=True)
            program = work / source.name
            shutil.copyfile(source, program)
            expected = run_cpython(program, data)
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(program=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (source.stem + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], cwd=str(work), input=data,
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_calculator_stops_loudly(self):
        source = PROGRAMS / "09_calculator.py"
        data = stdin_for(source)
        work = self.dir / source.stem
        work.mkdir(exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
            with self.subTest(build=mode):
                env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                env.pop("PYTHONPATH", None)
                exe = work / ("09_calculator." + mode + ".out")
                built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                        str(program), "-o", str(exe)],
                                       cwd=str(work), capture_output=True, text=True,
                                       timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(work), input=data,
                                     capture_output=True, timeout=120)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn(b"OverflowError", ran.stderr)

    def test_dispatch_semantics(self):
        probes = {
            "default_fallback.py": """import cmd
class D(cmd.Cmd):
    def do_echo(self, arg):
        print("echo:", arg)
    def do_EOF(self, arg):
        return True
s = D()
print("has add", hasattr(s, 'do_add'))
print("has shell", hasattr(s, 'do_shell'))
s.onecmd("echo a")
s.onecmd("")
s.onecmd("ping")
s.onecmd("")
s.onecmd("EOF")
""",
            "parseline.py": """import cmd
class C(cmd.Cmd):
    def do_EOF(self, arg):
        return True
s = C()
for line in ["!ls", "?", "x?", "!"]:
    print("parsed", repr(s.parseline(line)))
s.onecmd("!ls")
""",
            "names.py": """import cmd
class E(cmd.Cmd):
    def do_greet(self, arg):
        pass
    def do_EOF(self, arg):
        return True
s = E()
print("do_add", hasattr(s, 'do_add'))
print("do_greet", hasattr(s, 'do_greet'))
""",
        }
        for name, text in probes.items():
            work = self.dir / ("probe_" + name.replace(".py", ""))
            work.mkdir(exist_ok=True)
            program = work / name
            program.write_text(text)
            expected = run_cpython(program, b"")
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(probe=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (name.replace(".py", "") + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s\n%s%s" % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_reflection_names(self):
        probes = {
            "override.py": """import cmd
class S(cmd.Cmd):
    def do_echo(self, arg):
        "Echo it."
    def do_EOF(self, arg):
        "Exit."
        return True
    def help_echo(self):
        return None
    def help_EOF(self):
        return None
    def get_names(self):
        return ['do_echo', 'do_EOF', 'do_help', 'help_echo', 'help_EOF']
S().onecmd("help")
""",
            "empty_override.py": """import cmd
class S(cmd.Cmd):
    def get_names(self):
        return []
S().onecmd("help")
print("done")
""",
            "vocabulary.py": """import cmd
class S(cmd.Cmd):
    def do_echo(self, arg):
        pass
    def do_EOF(self, arg):
        return True
s = S()
print(s.get_names())
print(s.completenames("e"))
""",
        }
        for name, text in probes.items():
            work = self.dir / ("reflect_" + name.replace(".py", ""))
            work.mkdir(exist_ok=True)
            program = work / name
            program.write_text(text)
            expected = run_cpython(program, b"")
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(probe=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (name.replace(".py", "") + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s\n%s%s" % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_help_table_classification(self):
        probes = {
            "undoc.py": """import cmd
class S(cmd.Cmd):
    def do_echo(self, arg):
        pass
    def do_EOF(self, arg):
        return True
S().onecmd("help")
""",
            "documented.py": """import cmd
class S(cmd.Cmd):
    def do_echo(self, arg):
        pass
    def help_echo(self):
        return None
    def do_EOF(self, arg):
        return True
    def help_EOF(self):
        return None
S().onecmd("help")
""",
        }
        for name, text in probes.items():
            work = self.dir / ("table_" + name.replace(".py", ""))
            work.mkdir(exist_ok=True)
            program = work / name
            program.write_text(text)
            expected = run_cpython(program, b"")
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(probe=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (name.replace(".py", "") + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s\n%s%s" % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_streams(self):
        probes = {
            "attr.py": """import cmd
class S(cmd.Cmd):
    def do_EOF(self, arg):
        return True
s = S()
print(s.stdin is None, s.stdout is None)
f = open("file.txt", "w")
cmd.Cmd(stdout=f).onecmd("help")
f.close()
print("file:", repr(open("file.txt").read()))
""",
            "stream.py": """import cmd
w = open("cmds.txt", "w")
w.write("echo hi\\nEOF\\n")
w.close()
class S(cmd.Cmd):
    use_rawinput = False
    def do_echo(self, arg):
        print("echo", arg)
    def do_EOF(self, arg):
        print("done")
        return True
S(stdin=open("cmds.txt")).cmdloop()
""",
        }
        for name, text in probes.items():
            work = self.dir / ("stream_" + name.replace(".py", ""))
            work.mkdir(exist_ok=True)
            program = work / name
            program.write_text(text)
            expected = run_cpython(program, b"")
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(probe=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (name.replace(".py", "") + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s\n%s%s" % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), input=b"",
                                         capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_unsupported_is_refused(self):
        probes = {
            "outside.py": ("""import cmd
class S(cmd.Cmd):
    def do_exit(self, arg):
        print("exit", arg)
    def do_EOF(self, arg):
        return True
S().onecmd("exit now")
""", b"cmd.Cmd.onecmd: cannot dispatch do_exit"),
            "help_outside.py": ("""import cmd
class S(cmd.Cmd):
    def help_exit(self):
        print("exit help")
    def do_EOF(self, arg):
        return True
S().onecmd("help exit")
""", b"cmd.Cmd.do_help: cannot call help_exit"),
            "topic.py": ("""import cmd
class S(cmd.Cmd):
    def do_zoom(self, arg):
        'Zoom the view.'
    def do_EOF(self, arg):
        return True
S().onecmd("help zoom")
""", b"cmd.Cmd.do_help: cannot read the docstring of do_zoom"),
        }
        for name, (text, message) in probes.items():
            work = self.dir / ("refuse_" + name.replace(".py", ""))
            work.mkdir(exist_ok=True)
            program = work / name
            program.write_text(text)
            for mode, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(probe=name, build=mode):
                    env = dict(os.environ, AIL_NO_CACHE="1", **extra)
                    env.pop("PYTHONPATH", None)
                    exe = work / (name.replace(".py", "") + "." + mode + ".out")
                    built = subprocess.run([sys.executable, "-B", CLI, "compile",
                                            str(program), "-o", str(exe)],
                                           cwd=str(work), capture_output=True, text=True,
                                           timeout=600, env=env)
                    self.assertEqual(built.returncode, 0,
                                     "%s %s\n%s%s" % (name, mode, built.stdout, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(work), input=b"",
                                         capture_output=True, timeout=120)
                    self.assertNotEqual(ran.returncode, 0, "%s %s" % (name, mode))
                    self.assertIn(message, ran.stderr, "%s %s" % (name, mode))


if __name__ == "__main__":
    unittest.main()
