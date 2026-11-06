"""feinf2: the byte-level BPE tokenizer in `lab/infer/bpe.py`.

The committed `bpe_cases/tiny` vocabulary was trained with Hugging Face
`tokenizers` on `lab/infer/tok_corpus.txt`; `expected_ids.json` is its ids for
every corpus line.  The default build, the forced general build
(`AIL_UNIFIED_FORCE=1`) and CPython must all produce exactly those ids, and
`roundtrip` must recover the corpus bytes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CHATGPT = ROOT / "ail_chatgpt.py"
BPE = REPO / "lab/infer/bpe.py"
CORPUS = REPO / "lab/infer/tok_corpus.txt"
CASE = ROOT / "bpe_cases/tiny"
HAVE_CC = shutil.which("cc") is not None or shutil.which("gcc") is not None


def clean_env(**extra):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("AIL_"):
            env.pop(key)
    env.update(extra)
    return env


def parse_rows(text):
    rows = []
    for line in text.splitlines():
        rows.append([int(x) for x in line.split()] if line else [])
    return rows


@unittest.skipUnless(HAVE_CC, "installed C compiler required")
class BpeNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        directory = Path(cls.tmp.name)
        cls.exe = {}
        for name, extra in (("default", {}), ("unified", {"AIL_UNIFIED_FORCE": "1"})):
            output = directory / ("bpe_" + name)
            subprocess.run(
                [sys.executable, "-B", str(CHATGPT), "compile", str(BPE), "-o", str(output)],
                cwd=REPO, env=clean_env(**extra), check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            cls.exe[name] = output
        cls.expected = json.loads((CASE / "expected_ids.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cpython(self, command):
        env = clean_env(PYTHONPATH=str(ROOT))
        return subprocess.run(
            [sys.executable, "-B", str(BPE), command, str(CASE), str(CORPUS)],
            cwd=REPO, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def run_ail(self, name, command):
        return subprocess.run(
            [str(self.exe[name]), command, str(CASE), str(CORPUS)],
            cwd=REPO, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_encode_ids_match_expected_in_all_three(self):
        cpython = parse_rows(self.run_cpython("encode").stdout.decode())
        self.assertEqual(cpython, self.expected)
        for name in ("default", "unified"):
            with self.subTest(build=name):
                got = parse_rows(self.run_ail(name, "encode").stdout.decode())
                self.assertEqual(got, self.expected)

    def test_roundtrip_recovers_corpus_bytes(self):
        want = CORPUS.read_bytes()
        self.assertEqual(self.run_cpython("roundtrip").stdout, want)
        for name in ("default", "unified"):
            with self.subTest(build=name):
                self.assertEqual(self.run_ail(name, "roundtrip").stdout, want)

    def test_both_builds_print_the_same_bytes(self):
        for command in ("encode", "roundtrip"):
            with self.subTest(command=command):
                self.assertEqual(self.run_ail("default", command).stdout,
                                 self.run_ail("unified", command).stdout)


if __name__ == "__main__":
    unittest.main()
