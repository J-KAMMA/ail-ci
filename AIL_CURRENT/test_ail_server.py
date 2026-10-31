"""The resident compile server (ail_server.py, opt-in with AIL_SERVER=1): the same builds, errors and exit codes as the
normal path, and the process rules around it.

Every build here runs twice, once the normal way and once with AIL_SERVER=1 in a private runtime directory, each with a
fresh AIL_CACHE and TMPDIR and a recording C compiler wrapper, and the two are compared: exit code, stdout, stderr and
every C file handed to the C compiler.  Tests that change the compiler run on a copy of the source tree.
"""
import concurrent.futures
import itertools
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ail_server  # noqa: E402

REPO = ROOT.parent
LAB = REPO / 'lab' / 'compare' / 'src'
CORPUS = REPO / 'lab' / 'corpus' / 'programs'
REAL_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') or shutil.which('cc')
HELLO = 'def main() -> None:\n    print("hello")\n\nmain()\n'
CC_WRAPPER = '#!/bin/sh\nfor a in "$@"; do case "$a" in *.c) n=$(ls "$CC_SAVE" | wc -l); cp "$a" "$CC_SAVE/$n.c";; esac; done\nexec %s "$@"\n'
PATCH = '''    import os as _o
    _t = _o.environ.get('AIL_TEST_PYC')
    if _t == 'crash':
        raise RuntimeError('boom from pyc')
    if _t == 'exit':
        sys.exit('exit text from pyc')
    if _t == 'segv':
        import signal as _s
        _o.kill(_o.getpid(), _s.SIGSEGV)
    if _t and _t.startswith('sleep:'):
        open(_t[6:], 'w').write(str(_o.getpid()))
        import time as _tm
        _tm.sleep(600)
'''


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        return Path('/proc/%d/stat' % pid).read_text().split(')')[-1].split()[0] != 'Z'
    except OSError:
        return False


def wait_for(condition, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


@unittest.skipUnless(REAL_CC and ail_server.supported(), 'Linux with a C compiler required')
class ServerBase(unittest.TestCase):
    tree = ROOT

    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix='ails-work-'))
        cls.runtime = Path(tempfile.mkdtemp(prefix='ails'))        # short: a socket path is limited to about 100 bytes
        cls.counter = itertools.count(1)
        wrapper = cls.work / 'cc.sh'
        wrapper.write_text(CC_WRAPPER % REAL_CC)
        wrapper.chmod(0o755)
        cls.wrapper = wrapper

    @classmethod
    def tearDownClass(cls):
        for path in cls.runtime.glob('*.sock'):
            path.unlink()                       # a server whose socket file is gone exits
        time.sleep(1.5)
        shutil.rmtree(cls.runtime, ignore_errors=True)
        shutil.rmtree(cls.work, ignore_errors=True)

    @classmethod
    def environment(cls, server, extra=None, runtime=None):
        base = cls.work / ('run%d' % next(cls.counter))
        for name in ('cache', 'tmp', 'cc'):
            (base / name).mkdir(parents=True)
        env = {key: value for key, value in os.environ.items() if not key.startswith('AIL_')}
        env.update(AIL_CACHE=str(base / 'cache'), TMPDIR=str(base / 'tmp'), PIPE_CC=str(cls.wrapper), CC_SAVE=str(base / 'cc'),
                   AIL_SERVER_DIR=str(runtime or cls.runtime), AIL_SERVER_IDLE='120')
        if server:
            env['AIL_SERVER'] = '1'
        env.update(extra or {})
        return env, base

    @classmethod
    def command(cls, *args, tree=None):
        return [sys.executable, '-X', 'utf8', '-B', str(Path(tree or cls.tree) / 'ail_chatgpt.py'), *map(str, args)]

    @classmethod
    def build(cls, args, server, extra=None, cwd=None, tree=None, runtime=None, timeout=600):
        """(returncode, stdout, stderr, [C files]) with temporary paths normalised."""
        env, base = cls.environment(server, extra, runtime)
        args = [str(base / 'prog') if arg == '{OUT}' else arg for arg in args]
        done = subprocess.run(cls.command(*args, tree=tree), capture_output=True, text=True, env=env, cwd=cwd or cls.work,
                              timeout=timeout)
        def clean(text):
            text = text.replace(str(base), '<RUN>')
            return re.sub(r'ailc?-[A-Za-z0-9_]{6,}', 'ail-TMP', text)
        sources = [clean((base / 'cc' / name).read_text(errors='replace')) for name in sorted(os.listdir(base / 'cc'), key=lambda name: int(name[:-2]))]
        return done.returncode, clean(done.stdout), clean(done.stderr), sources

    def same(self, args, extra=None, cwd=None, tree=None, expect=None):
        plain = self.build(args, False, extra, cwd, tree)
        served = self.build(args, True, extra, cwd, tree)
        self.assertEqual(plain[:3], served[:3])
        self.assertEqual(plain[3], served[3])
        if expect is not None:
            self.assertEqual(plain[0], expect)
        return plain, served

    @classmethod
    def describe(cls):
        return [(path.name, path.with_name(path.name + '.log').read_text()) for path in cls.sockets()]

    @classmethod
    def sockets(cls, runtime=None):
        return sorted((runtime or cls.runtime).glob('*.sock'))


class SameBuilds(ServerBase):
    def test_compare_lab_tasks(self):
        tasks = sorted(path for path in LAB.iterdir() if (path / 'main.ail').is_file()) if LAB.is_dir() else []
        if not tasks:
            self.skipTest('lab/compare is not part of this tree')
        for task in tasks:
            with self.subTest(task=task.name):
                plain, served = self.same(['compile', task / 'main.ail', '-o', '{OUT}'], expect=0)
                self.assertTrue(plain[3] and served[3])
        self.assertEqual(len(self.sockets()), 1)

    def test_python_syntax_corpus_sample(self):
        names = sorted(path for path in CORPUS.glob('*/t0*.py'))[:5] if CORPUS.is_dir() else []
        if not names:
            self.skipTest('lab/corpus is not part of this tree')
        for name in names:
            with self.subTest(program=name.name):
                self.same(['compile', name, '--syntax', 'python', '-o', '{OUT}'])

    def test_per_build_environment(self):
        source = LAB / 'chain_relax' / 'main.ail'
        if not source.is_file():
            self.skipTest('lab/compare is not part of this tree')
        forced = self.same(['compile', source, '-o', '{OUT}'], extra={'AIL_UNIFIED_FORCE': '1'})
        default = self.same(['compile', source, '-o', '{OUT}'], expect=0)
        self.same(['compile', source, '-o', '{OUT}'], extra={'AIL_UNIFIED_FORCE': '1', 'AIL_NO_GENERAL': '1'})
        self.assertNotEqual(forced[0][:2], default[0][:2])   # the variable changes the build, and the server followed it
        self.assertEqual(len(self.sockets()), 1, self.describe())             # one server answered every one of them

    def test_errors_and_usage(self):
        (self.work / 'bad.ail').write_text('fn main() -> int {\n    return nope(\n')
        (self.work / 'hello.py').write_text(HELLO)
        cases = ([['compile', 'missing.ail', '-o', '{OUT}'], 2], [['compile'], 2], [['compile', 'bad.ail', '-o', '{OUT}'], None],
                 [['compile', 'hello.py', '--syntax', 'ail', '-o', '{OUT}'], None], [['check', 'bad.ail'], None],
                 [['check', 'hello.py', '--json'], None], [['check', '-h'], 0], [['compile', '--no-such-option'], 2])
        for args, code in cases:
            with self.subTest(args=args):
                plain, served = self.same(args)
                if code is not None:
                    self.assertEqual(plain[0], code)
                self.assertTrue(plain[1] or plain[2], 'no output at all')
        self.assertNotEqual(self.build(['compile', 'bad.ail', '-o', '{OUT}'], True)[0], 0)

    def test_unserved_commands_run_normally(self):
        self.assertEqual(self.build(['cache', '--help'], True)[:3], self.build(['cache', '--help'], False)[:3])

    def test_concurrent_requests(self):
        source = LAB / 'chain_relax' / 'main.ail'
        if not source.is_file():
            self.skipTest('lab/compare is not part of this tree')
        (self.work / 'hello.py').write_text(HELLO)
        jobs = [['compile', source, '-o', '{OUT}'], ['compile', 'hello.py', '-o', '{OUT}'], ['check', 'hello.py'],
                ['compile', source, '-o', '{OUT}'], ['compile', 'hello.py', '-o', '{OUT}'], ['check', source]]
        expected = [self.build(job, False) for job in jobs]
        with concurrent.futures.ThreadPoolExecutor(len(jobs)) as pool:
            got = list(pool.map(lambda job: self.build(job, True), jobs))
        self.assertEqual(expected, got)
        self.assertEqual(len(self.sockets()), 1)

    def test_fallback_when_the_server_cannot_start(self):
        (self.work / 'hello.py').write_text(HELLO)
        blocked = self.work / 'not-a-directory'
        blocked.write_text('x')
        plain = self.build(['compile', 'hello.py', '-o', '{OUT}'], False)
        for runtime in (blocked, blocked / 'inside'):
            with self.subTest(runtime=runtime.name):
                self.assertEqual(plain, self.build(['compile', 'hello.py', '-o', '{OUT}'], True, runtime=runtime))
        # a server that dies while it starts: the build still runs, the normal way
        broken = self.work / 'broken'
        broken.mkdir()
        (broken / 'sitecustomize.py').write_text('import sys\nif "serve" in sys.argv:\n    raise SystemExit(3)\n')
        self.assertEqual(plain, self.build(['compile', 'hello.py', '-o', '{OUT}'], True, extra={'PYTHONPATH': str(broken)},
                                           runtime=self.work / 'rt-broken'))


class Process(ServerBase):
    def test_runtime_directory_and_socket_permissions(self):
        (self.work / 'hello.py').write_text(HELLO)
        loose = Path(tempfile.mkdtemp(prefix='ailp'))
        loose.chmod(0o755)
        self.addCleanup(shutil.rmtree, loose, True)
        self.assertEqual(self.build(['compile', 'hello.py', '-o', '{OUT}'], True, runtime=loose)[0], 0)
        self.assertEqual(stat.S_IMODE(loose.stat().st_mode), 0o700)
        sockets = self.sockets(loose)
        self.assertEqual(len(sockets), 1)
        self.assertEqual(stat.S_IMODE(sockets[0].stat().st_mode), 0o600)
        self.assertTrue(stat.S_ISSOCK(sockets[0].stat().st_mode))
        left, right = socket.socketpair()
        self.assertEqual(ail_server._peer_uid(left), os.getuid())
        left.close()
        right.close()
        for path in sockets:
            path.unlink()
        time.sleep(1.5)

    def test_idle_exit(self):
        (self.work / 'hello.py').write_text(HELLO)
        runtime = Path(tempfile.mkdtemp(prefix='ails'))
        self.addCleanup(shutil.rmtree, runtime, True)
        self.assertEqual(self.build(['compile', 'hello.py', '-o', '{OUT}'], True, {'AIL_SERVER_IDLE': '2'}, runtime=runtime)[0], 0)
        sockets = self.sockets(runtime)
        self.assertEqual(len(sockets), 1)
        self.assertTrue(wait_for(lambda: not sockets[0].exists(), 20), 'the idle server did not exit')

    def test_identity_names_what_the_template_froze(self):
        limits = ail_server.current_limits()
        env = dict(os.environ)
        key = ail_server.identity(str(ROOT), env, limits)
        self.assertEqual(key, ail_server.identity(str(ROOT), dict(env, AIL_NO_CACHE='1', AIL_UNIFIED_FORCE='1', PATH='/x'), limits))
        for name in ail_server.IMPORT_ENV + ('PYTHONHASHSEED', 'LC_ALL'):
            self.assertNotEqual(key, ail_server.identity(str(ROOT), dict(env, **{name: 'zz-test'}), limits), name)
        smaller = {name: list(value) for name, value in limits.items()}
        smaller['RLIMIT_AS'] = [1 << 40, smaller['RLIMIT_AS'][1]]
        self.assertNotEqual(key, ail_server.identity(str(ROOT), env, smaller))

    def test_import_time_environment_reads_are_all_keyed(self):
        probe = (
            'import os, sys\n'
            'seen = set()\n'
            'class Recording(type(os.environ)):\n'
            '    def __getitem__(self, key):\n'
            '        seen.add(key)\n'
            '        return super().__getitem__(key)\n'
            'os.environ.__class__ = Recording\n'
            'sys.path.insert(0, sys.argv[1])\n'
            'import ail_server\n'
            'ail_server.Template(sys.argv[1])\n'
            'print(sorted(seen))\n')
        done = subprocess.run([sys.executable, '-c', probe, str(ROOT)], capture_output=True, text=True, timeout=300,
                              env={key: value for key, value in os.environ.items() if not key.startswith('AIL_')})
        self.assertEqual(done.returncode, 0, done.stderr)
        seen = eval(done.stdout.strip().splitlines()[-1])
        ours = [name for name in seen if name.startswith(('AIL_', 'PIPE_'))]
        self.assertEqual([name for name in ours if name not in ail_server.IMPORT_ENV], [],
                         'a module reads this variable while it is imported: add it to ail_server.IMPORT_ENV')


@unittest.skipUnless(REAL_CC and ail_server.supported(), 'Linux with a C compiler required')
class CopiedTree(ServerBase):
    """The compiler is changed on a copy: a crash, a string exit, a signal, a timeout, a stuck compiler."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree = cls.work / 'tree'
        shutil.copytree(ROOT, cls.tree, ignore=shutil.ignore_patterns('test_*.py', '__pycache__', 'docs', 'language_examples',
                                                                      'array_t2_cases', 'bigint_cases', 'tests.d', 'tests'))
        (cls.work / 'hello.py').write_text(HELLO)
        cls.first = cls.build(['compile', 'hello.py', '-o', '{OUT}'], True)       # starts the server of the unmodified copy
        cls.sockets_before = cls.sockets()
        pyc = cls.tree / 'python/pkg-v12/pyc.py'
        text = pyc.read_text(encoding='utf-8')
        pyc.write_text(text.replace('def main(argv=None):\n', 'def main(argv=None):\n' + PATCH, 1), encoding='utf-8')
        chat = cls.tree / 'ail_chatgpt.py'
        chat.write_text(chat.read_text(encoding='utf-8').replace(
            'timeout=660, env=environment', 'timeout=float(os.environ.get("AIL_TEST_TIMEOUT", "660")), env=environment'), encoding='utf-8')

    def test_0_unmodified_copy_was_served(self):
        self.assertEqual(self.first[0], 0)
        self.assertEqual(len(self.sockets_before), 1)

    def test_source_change_means_a_new_server(self):
        self.assertEqual(self.build(['compile', 'hello.py', '-o', '{OUT}'], True)[0], 0)
        self.assertEqual(len(self.sockets()), 2)
        self.assertNotEqual(self.sockets()[0], self.sockets()[1])
        # and the new one runs the new code
        plain, _ = self.same(['compile', 'hello.py', '-o', '{OUT}'], extra={'AIL_TEST_PYC': 'crash'})
        self.assertEqual(len(self.sockets()), 2)
        self.assertNotEqual(plain[0], 0)

    def test_crashes_report_the_same(self):
        for mode in ('crash', 'exit', 'segv'):
            with self.subTest(mode=mode):
                plain, served = self.same(['compile', 'hello.py', '-o', '{OUT}'], extra={'AIL_TEST_PYC': mode})
                self.assertNotEqual(plain[0], 0)
                self.assertTrue(served[2], 'no error text')
        plain = self.build(['compile', 'hello.py', '-o', '{OUT}'], False, {'AIL_TEST_PYC': 'crash'})
        self.assertIn('boom from pyc', plain[2])
        self.assertIn('line', plain[2])

    def test_a_crash_does_not_end_the_server(self):
        self.same(['compile', 'hello.py', '-o', '{OUT}'], extra={'AIL_TEST_PYC': 'crash'})
        self.assertEqual(self.build(['compile', 'hello.py', '-o', '{OUT}'], True)[0], 0)

    def test_timeout(self):
        marker = self.work / 'sleeper'
        extra = {'AIL_TEST_PYC': 'sleep:%s' % marker, 'AIL_TEST_TIMEOUT': '3'}
        plain = self.build(['compile', 'hello.py', '-o', '{OUT}'], False, extra)
        served = self.build(['compile', 'hello.py', '-o', '{OUT}'], True, extra)
        # the traceback of the uncaught subprocess.TimeoutExpired differs inside subprocess.py; its last line does not
        self.assertEqual(plain[0], served[0])
        self.assertEqual(plain[2].strip().splitlines()[-1], served[2].strip().splitlines()[-1])
        self.assertIn('timed out after 3', served[2])
        pid = int(marker.read_text())
        self.assertTrue(wait_for(lambda: not alive(pid), 10), 'the timed-out compiler still runs')

    def start(self, mode, marker, server=True):
        env, base = self.environment(server, {'AIL_TEST_PYC': 'sleep:%s' % marker})
        if marker.exists():
            marker.unlink()
        process = subprocess.Popen(self.command('compile', 'hello.py', '-o', '{OUT}'), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=env, cwd=self.work, start_new_session=True)
        self.assertTrue(wait_for(lambda: marker.exists() and marker.read_text(), 120), 'the compiler never started')
        return process, int(marker.read_text())

    def test_interrupt_is_forwarded(self):
        results = []
        for server in (False, True):
            process, pid = self.start('sleep', self.work / ('int%d' % server), server)
            self.assertTrue(alive(pid))
            process.send_signal(signal.SIGINT)
            out, err = process.communicate(timeout=60)
            results.append(process.returncode)
            self.assertTrue(wait_for(lambda: not alive(pid), 15), 'the compiler survived the interrupt (server=%s)' % server)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], -signal.SIGINT)

    def test_terminate_is_forwarded(self):
        process, pid = self.start('sleep', self.work / 'term', True)
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=60)
        self.assertEqual(process.returncode, -signal.SIGTERM)
        self.assertTrue(wait_for(lambda: not alive(pid), 15))

    def test_client_death_ends_the_build(self):
        process, pid = self.start('sleep', self.work / 'kill', True)
        process.kill()
        process.communicate(timeout=60)
        self.assertTrue(wait_for(lambda: not alive(pid), 15), 'the compiler outlived its client')
        self.assertEqual(self.build(['compile', 'hello.py', '-o', '{OUT}'], True)[0], 0)      # and the server is fine


if __name__ == '__main__':
    unittest.main()
