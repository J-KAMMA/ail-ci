"""fbpmap2: `AIL_PAR_SCHED=guided` hands out contiguous blocks in index order and keeps the result.

Each program is built once and run with the variable unset and set to `guided`, at several thread
counts, against the sequential loop. The outputs must be identical. The trap of the block a
sequential loop reaches first must still be the one raised, at 16 threads, whichever block it is in.
The reduction runtime keeps its own chunks and is exact under both schedules.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
import cruntime  # noqa: E402

THREADS = (1, 2, 4, 16)
SCHEDULES = ("", "guided")

PROGRAM = """
fn mix(v: int, k: int) -> int {
    while k > 0 { v = (v * 5 + 7) % 1073741823; k -= 1; }
    return v;
}

fn work(n: int) -> list[int] {
    let xs: list[int] = [0] * n;
    parallel for i in range(0, n) { xs[i] = mix(i * 3 + 1, i % 400); }
    return xs;
}

fn main() {
    let n = 20000;
    let xs = work(n);
    let t = 0;
    for i in range(0, n) { t += xs[i] % 1000; }
    print(n, t, xs[0], xs[n - 1]);
}
"""

TRAPS = """
fn work(n: int, big: int, mode: int) -> int {
    let xs: list[int] = [0] * n;
    let ys: list[int] = [1, 2, 3];
    parallel for i in range(0, n) {
        let t = i;
        if mode == 0 and i == 3 { t = ys[10]; }
        if mode == 0 and i == 90000 { t = big + i; }
        if mode == 1 and i == 200 { t = big + i; }
        if mode == 1 and i == 90000 { t = ys[10]; }
        xs[i] = t;
    }
    return xs[5];
}
fn main() {
    try { print(work(100000, 9223372036854775807, 0)); }
    except OverflowError as e { print("caught overflow"); }
    except IndexError as e { print("caught index"); }
    try { print(work(100000, 9223372036854775807, 1)); }
    except OverflowError as e { print("caught overflow"); }
    except IndexError as e { print("caught index"); }
}
"""

SMALL = """
fn main() {
    let three = [0, 0, 0];
    parallel for i in range(0, 3) { three[i] = i * i + 1; }
    print(three[0], three[1], three[2]);
    let one = [0];
    parallel for i in range(0, 1) { one[i] = 41 + i; }
    print(one[0]);
    let two = [0, 0];
    parallel for i in range(0, 2) { two[i] = 10 - i; }
    print(two[0], two[1]);
}
"""

REDUCE = r"""
#include <stdio.h>
static int64_t term(int64_t i) { return (i % 7) - 3; }
static void r_rerun(void **args, int64_t lo, int64_t hi, int64_t *acc) {
    (void)args;
    for (int64_t i = lo; i < hi; i++) acc[0] += term(i);
}
static void r_fn(void **args, int64_t lo, int64_t hi, ail_red_part *p) {
    (void)args;
    __int128 s = 0, mx = 0, mn = 0;
    for (int64_t i = lo; i < hi; i++) { s += term(i); if (s > mx) mx = s; if (s < mn) mn = s; }
    p[0] = (ail_red_part){s, mx, mn};
}
int main(int argc, char **argv) {
    int64_t n = 200000, acc[1] = {0};
    void *args[1] = {0};
    static ail_par_site site;
    if (argc > 1) ail_par_reduce_run(r_fn, args, 0, n, &site, 0, 1, acc, r_rerun);
    else r_rerun(args, 0, n, acc);
    printf("%lld\n", (long long)acc[0]);
    return 0;
}
"""


def build(directory, name, source):
    path, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "_c")
    path.write_text(source)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                            "-o", str(exe), "--debug-dir", str(debug)], capture_output=True, text=True, timeout=600)
    return built, exe, debug


def run(exe, threads, sched):
    env = dict(os.environ, AIL_THREADS=str(threads))
    if sched:
        env["AIL_PAR_SCHED"] = sched
    else:
        env.pop("AIL_PAR_SCHED", None)
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, env=env)


class ParSchedTests(unittest.TestCase):
    def test_guided_gives_the_sequential_result_at_every_thread_count(self):
        with tempfile.TemporaryDirectory() as directory:
            built, par, debug = build(directory, "par", PROGRAM)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn("ail_par_work_guided", (debug / "program.c").read_text())
            built, seq, _ = build(directory, "seq", PROGRAM.replace("parallel for", "for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            expected = run(seq, 1, "")
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for threads in THREADS:
                for sched in SCHEDULES:
                    got = run(par, threads, sched)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout),
                                     "AIL_THREADS=%d AIL_PAR_SCHED=%r" % (threads, sched))

    def test_the_first_failing_iteration_wins_at_16_threads(self):
        with tempfile.TemporaryDirectory() as directory:
            built, par, _ = build(directory, "par", TRAPS)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            built, seq, _ = build(directory, "seq", TRAPS.replace("parallel for", "for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            expected = run(seq, 1, "")
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(expected.stdout, "caught index\ncaught overflow\n")
            for threads in (1, 16):
                for sched in SCHEDULES:
                    got = run(par, threads, sched)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout),
                                     "AIL_THREADS=%d AIL_PAR_SCHED=%r" % (threads, sched))

    def test_one_iteration_and_more_threads_than_iterations(self):
        with tempfile.TemporaryDirectory() as directory:
            built, par, _ = build(directory, "par", SMALL)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            built, seq, _ = build(directory, "seq", SMALL.replace("parallel for", "for"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            expected = run(seq, 1, "")
            for threads in THREADS:
                for sched in SCHEDULES:
                    got = run(par, threads, sched)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout),
                                     "AIL_THREADS=%d AIL_PAR_SCHED=%r" % (threads, sched))

    def test_the_reduction_stays_exact_with_guided_chunks(self):
        text = cruntime.emit(["PARRED"])
        self.assertIn("ail_par_reduce_run", text)
        source = "#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n" + text + REDUCE
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory, "red.c")
            exe = Path(directory, "red")
            src.write_text(source)
            built = subprocess.run(["cc", "-O2", "-w", "-pthread", "-o", str(exe), str(src)],
                                   capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            expected = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300,
                                      env={k: v for k, v in os.environ.items() if k != "AIL_PAR_SCHED"})
            for threads in THREADS:
                for sched in SCHEDULES:
                    env = dict(os.environ, AIL_THREADS=str(threads))
                    if sched:
                        env["AIL_PAR_SCHED"] = sched
                    got = subprocess.run([str(exe), "p"], capture_output=True, text=True, timeout=300, env=env)
                    self.assertEqual((got.returncode, got.stdout), (0, expected.stdout),
                                     "AIL_THREADS=%d AIL_PAR_SCHED=%r" % (threads, sched))


if __name__ == "__main__":
    unittest.main()
