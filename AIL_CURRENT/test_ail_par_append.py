"""D3: `out.append(v)` in a map-like parallel body (owner decision 2026-11-06).

Every program is built from one source twice: with `par_range` and with the `range` it stands for.
The outputs and the exit status must agree at AIL_THREADS 1, 2, 4 and 16 (three runs each), with
AIL_PAR_SCHED unset and with `guided`. Each block appends into its own buffer of the list's element
kind (int, float, str), in its own iteration order; after the region the buffers are appended to
`out` in block order, which is the sequential order. A failing iteration keeps every block before it
plus its own block's buffer up to the raise.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THREADS = (1, 2, 4, 16)
RUNS = 3

INT = ("def main():\n    out = []\n    for i in %s(0, 100):\n        out.append(i * 3)\n"
       "    print(len(out), out[0], out[99])\nmain()\n")
COND = ("def main():\n    out = []\n    for i in %s(0, 200):\n        if i %% 3 == 0:\n"
        "            out.append(i)\n        else:\n            out.append(i * 10)\n"
        "    print(len(out), out[0], out[1], out[199])\nmain()\n")
TWO = ("def main():\n    out = []\n    for i in %s(0, 100):\n        out.append(i)\n"
       "        out.append(-i)\n        if i %% 2 == 0:\n            out.append(i + 1000)\n"
       "    print(len(out), out[0], out[1], out[2], out[len(out) - 1])\nmain()\n")
FLOAT = ("def main():\n    out: list[float] = []\n    for i in %s(0, 50):\n"
         "        out.append(i * 0.25)\n        if i %% 10 == 0:\n            out.append(-1.5)\n"
         "    print(len(out), out[0], out[1], out[len(out) - 1])\nmain()\n")
STR = ("def main():\n    out: list[str] = []\n    for i in %s(0, 40):\n"
       "        if i %% 4 == 0:\n            out.append(\"four\")\n        elif i %% 2 == 0:\n"
       "            out.append(\"two\")\n        else:\n            out.append(\"odd\")\n"
       "    print(len(out), out[0], out[1], out[2], out[3], out[39])\nmain()\n")
EMPTY = ("def main():\n    out = [7, 8]\n    for i in %s(0, 0):\n        out.append(i)\n"
         "    print(len(out), out[0], out[1])\nmain()\n")
MANY = ("def main():\n    out = []\n    for i in %s(0, 10):\n        out.append(i * i)\n"
        "    print(len(out), out[0], out[9])\nmain()\n")
SIXTEEN = ("def main():\n    out = []\n    for i in %s(0, 1024):\n        out.append(i * 7 + 1)\n"
           "    print(len(out), out[0], out[1023])\nmain()\n")
EXC = ("def main():\n    out = []\n    for i in %s(0, 100):\n        out.append(i)\n"
       "        if i == 37:\n            out.append(1 // (i - 37))\n"
       "    print(len(out), out[len(out) - 1])\nmain()\n")
GUIDED = ("def main():\n    out = []\n    for i in %s(0, 3000):\n        n = i + 1\n        c = 0\n"
          "        while n != 1:\n            if n %% 2 == 0:\n                n = n // 2\n"
          "            else:\n                n = 3 * n + 1\n            c += 1\n"
          "        if c %% 2 == 1:\n            out.append(i)\n"
          "    print(len(out), out[0], out[len(out) - 1])\nmain()\n")
CASES = {"int": INT, "conditional": COND, "two appends": TWO, "float": FLOAT, "str": STR,
         "empty": EMPTY, "more workers than items": MANY, "1024 items": SIXTEEN,
         "exception halfway": EXC, "guided": GUIDED}

REFUSED = {
    "two lists": ("def main():\n    a = []\n    b = []\n    for i in par_range(0, 10):\n"
                  "        a.append(i)\n        b.append(i)\n    print(len(a), len(b))\nmain()\n",
                  "two lists"),
    "read of the appended list": ("def main():\n    out = []\n    for i in par_range(0, 10):\n"
                                  "        out.append(i)\n        x = out[0]\n    print(x)\nmain()\n",
                                  "only use"),
    "a list of objects": ("def main():\n    out = []\n    for i in par_range(0, 10):\n"
                          "        out.append([i])\n    print(len(out))\nmain()\n",
                          "not allowed"),
    "write before the first append": ("def main():\n    out = [0, 0]\n    for i in par_range(0, 4):\n"
                                     "        out[i] = i * 10\n        out.append(i)\n"
                                     "    print(len(out))\nmain()\n",
                                     "only use"),
    "read before the first append": ("def main():\n    out = [7, 8]\n    for i in par_range(0, 4):\n"
                                    "        x = out[i]\n        out.append(x + 100)\n"
                                    "    print(len(out))\nmain()\n",
                                    "only use"),
    "len before the first append": ("def main():\n    out = []\n    for i in par_range(0, 8):\n"
                                   "        n = len(out)\n        out.append(i)\n"
                                   "    print(n, len(out))\nmain()\n",
                                   "only use"),
    "reduce and append": ("def main():\n    acc = 0\n    out = []\n    for i in par_range(0, 10):\n"
                          "        acc += i\n        out.append(i)\n    print(acc, len(out))\nmain()\n",
                          "reduces"),
    "try around the loop": ("def main():\n    out = []\n    try:\n"
                            "        for i in par_range(0, 10):\n            out.append(i)\n"
                            "        x = 1 // 0\n    except ZeroDivisionError:\n        pass\n"
                            "    print(len(out))\nmain()\n",
                            "cannot be inside try"),
}


def build(directory, name, source):
    path, exe = Path(directory, name + ".py"), Path(directory, name)
    path.write_text(source)
    got = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                          "--syntax", "python", "-o", str(exe)], capture_output=True, text=True,
                         timeout=300)
    return got, exe


def run(exe, threads, sched):
    env = dict(os.environ)
    env.pop("AIL_UNIFIED_FORCE", None)
    env["AIL_THREADS"] = str(threads)
    env["AIL_NO_CACHE"] = "1"
    env.pop("AIL_PAR_SCHED", None)
    if sched:
        env["AIL_PAR_SCHED"] = sched
    return subprocess.run([str(exe)], capture_output=True, env=env, timeout=300)


class ParAppendTest(unittest.TestCase):
    def test_shapes(self):
        with tempfile.TemporaryDirectory(prefix="ail-append-") as tmp:
            for label, source in CASES.items():
                with self.subTest(label):
                    par, pexe = build(tmp, label.replace(" ", "_"), source % "par_range")
                    self.assertEqual(par.returncode, 0, par.stderr[-800:])
                    self.assertNotIn("general path", par.stderr)
                    seq, sexe = build(tmp, label.replace(" ", "_") + "_seq", source % "range")
                    self.assertEqual(seq.returncode, 0, seq.stderr[-800:])
                    for sched in (None, "guided"):
                        for threads in THREADS:
                            for _ in range(RUNS):
                                a, b = run(pexe, threads, sched), run(sexe, threads, sched)
                                self.assertEqual(a.returncode, b.returncode,
                                                 (label, threads, sched, a.stderr[-400:]))
                                self.assertEqual(a.stdout, b.stdout, (label, threads, sched))
                                if label == "exception halfway":
                                    self.assertEqual(a.stderr.splitlines()[-1:],
                                                     b.stderr.splitlines()[-1:])

    def test_refused(self):
        with tempfile.TemporaryDirectory(prefix="ail-append-") as tmp:
            for label, (source, needle) in REFUSED.items():
                with self.subTest(label):
                    got, _ = build(tmp, label.replace(" ", "_"), source)
                    self.assertNotEqual(got.returncode, 0, got.stderr[-400:])
                    self.assertIn(needle, got.stderr)


if __name__ == "__main__":
    unittest.main()
