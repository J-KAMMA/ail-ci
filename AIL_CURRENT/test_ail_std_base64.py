"""Standard-library base64 batch: the programs in lab/stdlib/base64, compared with CPython 3.12.

The built programs cover b64encode / b64decode (bytes and ASCII str, altchars, validate), the
standard_* and urlsafe_* forms, encodebytes / decodebytes, b16encode / b16decode and b32encode /
b32decode. Each one is compiled in the default mode on both AIL_IR values and must print what
CPython prints, byte for byte, with the same exit code. The two programs that need a feature this
compiler does not have (b85/a85 and the legacy base64.encode / base64.decode stream API) stay
named compile-time refusals.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "base64"

BUILT = [
    "basic_roundtrip.py",
    "basic_auth.py",
    "url_token.py",
    "json_payload.py",
    "altchars_filesystem.py",
    "mime_lines.py",
    "hex_codec.py",
    "base32_ids.py",
    "strict_validation.py",
    "chunked_stream.py",
]

REFUSED = {
    "b85_vectors.py": "base64.b85encode is not built",
    "legacy_stream_api.py": "base64.encode is not built",
}


def build(directory, source, exe, env_extra):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(env_extra)
    return subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                           "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                          text=True, timeout=900, env=env)


class StdlibBase64Tests(unittest.TestCase):
    def test_built_programs_match_cpython_on_both_ir_builds(self):
        for name in BUILT:
            for env in ({"AIL_IR": "0"}, {"AIL_IR": "1"}):
                with self.subTest(program=name, env=env):
                    with tempfile.TemporaryDirectory() as directory:
                        shutil.copy2(PROGRAMS / name, Path(directory) / name)
                        source = Path(directory) / name
                        expected = subprocess.run([sys.executable, "-B", str(source)], capture_output=True,
                                                  timeout=120)
                        exe = Path(directory) / ("prog_" + env["AIL_IR"])
                        built = build(directory, source, exe, env)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr[-2000:])
                        ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                        self.assertEqual(ran.returncode, expected.returncode, ran.stderr[-500:])
                        self.assertEqual(ran.stdout, expected.stdout, ran.stderr[-500:])

    def test_unsupported_programs_are_refused_by_name(self):
        for name, needle in REFUSED.items():
            with self.subTest(program=name):
                with tempfile.TemporaryDirectory() as directory:
                    shutil.copy2(PROGRAMS / name, Path(directory) / name)
                    source = Path(directory) / name
                    exe = Path(directory) / "prog"
                    built = build(directory, source, exe, {})
                    self.assertNotEqual(built.returncode, 0, built.stdout)
                    self.assertIn(needle, built.stderr)
                    self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
