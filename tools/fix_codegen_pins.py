"""Rewrite the codegen-pin hashes after an intended runtime/codegen change.

    python3 tools/codegen_diff.py        # first: check the generated-C diff is only the intended change
    python3 tools/fix_codegen_pins.py    # then: replace each failing pin with the hash now produced

Runs the two codegen-pin test modules and replaces every "'actual' != 'expected'" SHA-256 pair they
report in those test files, repeating until they pass (each assertion stops at its first mismatch).
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'AIL_CURRENT'
MODULES = ('test_ail_record_initializers', 'test_ail_numeric_bindings')


def main():
    files = [ROOT / (name + '.py') for name in MODULES]
    for _ in range(10):
        result = subprocess.run([sys.executable, '-m', 'unittest', *MODULES], cwd=ROOT, capture_output=True, text=True)
        pairs = re.findall(r"AssertionError: '([0-9a-f]{64})' != '([0-9a-f]{64})'", result.stderr)
        if not pairs:
            print('pins pass' if result.returncode == 0 else result.stderr[-2000:])
            return result.returncode
        for actual, expected in pairs:
            for path in files:
                text = path.read_text()
                if expected in text:
                    path.write_text(text.replace(expected, actual))
                    print('%s: %s -> %s' % (path.name, expected[:12], actual[:12]))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
