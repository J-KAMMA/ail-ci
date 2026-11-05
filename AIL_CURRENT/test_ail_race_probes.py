"""The lab/race probe suite: racy probes must not be silent races, safe probes must match CPython.

`lab/race/run.py` measures both builds and writes RESULTS.md; this module is the CI gate. A racy
probe is a silent race when it builds on the lock-free typed parallel path, prints anything other
than CPython, or a ThreadSanitizer build reports on it. A safe probe must print CPython's stdout
and exit status at AIL_THREADS 1, 2, 4 and 16.

The probes that fail today are named in EXPECTED_FAILURES and marked with unittest.expectedFailure.
A probe that starts passing then reports an unexpected success, which is the signal to remove it
from that set.
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RACE = ROOT.parent / "lab" / "race"
RUNNER = RACE / "run.py"

_spec = importlib.util.spec_from_file_location("ail_race_run", RUNNER)
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

EXPECTED_FAILURES = {
    # AIL computes 2**63 in an int64 worker and stops loudly (exit 1, OverflowError). The task
    # allows "print the same or stop loudly", but this probe is not a safe match today.
    "int_beyond_int64",
}


def _load(src, kind):
    with tempfile.TemporaryDirectory(prefix="ail-race-test-") as tmp:
        work = Path(tmp)
        want = run.cpython_run(src)
        build = run.compile_probe(src, work, force=False)
        if build["path"] == "refused":
            return {"path": "refused", "note": build["note"], "match": False,
                    "want": want, "runs": {}}
        got = {"path": build["path"], "note": build["note"], "match": True,
               "want": want, "runs": {}}
        for threads in run.THREADS:
            runs = run.program_run(build["exe"], threads, runs=1)
            got["runs"][threads] = runs
            if not all(run.matches(want, r) for r in runs):
                got["match"] = False
        return got


def _check(self, src, kind):
    if not RUNNER.is_file():
        self.skipTest("lab/race/run.py is absent")
    got = _load(src, kind)
    if kind == "racy":
        self.assertNotEqual(got["path"], "typed parallel",
                            "%s runs GIL-free with a shared write" % src.name)
        if got["path"] != "refused":
            self.assertTrue(got["match"], "%s prints something other than CPython" % src.name)
        return
    self.assertEqual(got["path"] != "refused", True,
                     "%s is refused: %s" % (src.name, got.get("note", "")))
    self.assertTrue(got["match"], "%s does not match CPython at %s"
                    % (src.name, ", ".join(str(t) for t in run.THREADS)))


def _make(src, kind):
    def test(self):
        _check(self, src, kind)

    test.__name__ = "test_%s_%s" % (kind, src.stem)
    if src.stem in EXPECTED_FAILURES:
        test = unittest.expectedFailure(test)
    return test


@unittest.skipUnless(shutil.which("gcc"), "probes need a C compiler")
class RaceProbes(unittest.TestCase):
    """One test per probe, named by the probe file."""


for _kind, _dir in (("racy", RACE / "racy"), ("safe", RACE / "safe")):
    for _src in sorted(_dir.glob("*.py")):
        setattr(RaceProbes, "test_%s_%s" % (_kind, _src.stem), _make(_src, _kind))


if __name__ == "__main__":
    unittest.main()
