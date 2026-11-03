"""Direct decimal bytearray extension: independent formatting and effect order."""
import hashlib
import subprocess
import sys
import unittest

from ail_syntax import translate
import test_ail_c_objects as support
from test_ail_bytearray_receiver import oracle
from test_ail_map_fields import build

SOURCE = "from ail import write_stdout_bytes\nclass Box:\n\n    def __init__(self, data: bytearray, trace: str, calls: int):\n        self.data = data\n        self.trace = trace\n        self.calls = calls\n\ndef receiver(box: Box) -> bytearray:\n    box.trace += 'R'\n    return box.data\n\ndef argument(box: Box, action: int) -> int:\n    box.trace += 'A'\n    box.calls += 1\n    if action == 0:\n        box.data = bytearray(b'new')\n    elif action == 1:\n        box.data.clear()\n    else:\n        raise ValueError\n    return -9223372036854775808\n\ndef run(n: int) -> int:\n    output = bytearray()\n    values: list[int] = [0, 1, -1, 9, -9, 10, -10, 99, -99, 100, -100, 999, -999, 1000, -1000, 999999999999999999, -999999999999999999, 1000000000000000000, -1000000000000000000, 9223372036854775807, -9223372036854775808]\n    for value in values:\n        output.extend(str(value).encode(encoding='UTF_8', errors='strict'))\n        output.append(44)\n    power: int = 1\n    for digit in range(19):\n        output.extend(str(power - 1).encode())\n        output.append(44)\n        output.extend(str(power).encode())\n        output.append(44)\n        output.extend(str(-power).encode())\n        output.append(44)\n        if digit < 18:\n            power *= 10\n    for i in range(n):\n        value: int = i * 1000003 - 123456789\n        output.extend(str(value).encode('utf8', 'strict'))\n        output.append(44)\n    write_stdout_bytes(bytes(output))\n    for action in range(3):\n        box = Box(bytearray(b'old'), '', 0)\n        held = box.data\n        try:\n            receiver(box).extend(str(argument(box, action)).encode())\n        except ValueError:\n            write_stdout_bytes(b'caught')\n        write_stdout_bytes(box.trace.encode())\n        write_stdout_bytes(str(box.calls).encode())\n        write_stdout_bytes(bytes(held))\n        write_stdout_bytes(bytes(box.data))\n    write_stdout_bytes(b':continued')\n    return 0\n"
SHADOW = "from ail import write_stdout_bytes\ndef str(value: int) -> str:\n    return 'shadow'\n\ndef run(n: int) -> int:\n    output = bytearray()\n    output.extend(str(n).encode())\n    write_stdout_bytes(bytes(output))\n    return 0\n"
CALLABLE = "from ail import write_stdout_bytes\ndef format(value: int) -> str:\n    return 'callable'\n\ndef run(n: int) -> int:\n    str: Callable[[int], str] = format\n    output = bytearray()\n    output.extend(str(n).encode())\n    write_stdout_bytes(bytes(output))\n    return 0\n"
FLOAT = 'from ail import write_stdout_bytes\ndef run(n: int) -> int:\n    output = bytearray()\n    output.extend(str(1.5).encode())\n    write_stdout_bytes(bytes(output))\n    return 0\n'

class BytearrayDecimalTests(unittest.TestCase):
    setUp=support.CObjectTests.setUp
    command=support.CObjectTests.command
    write=support.CObjectTests.write

    def compare(self,executable,source,n):
        value,expected=oracle(source,n)
        result=subprocess.run([str(executable),str(n)],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,value,result.stderr[:2000].decode(errors='replace'))
        self.assertEqual(result.stderr,b'')
        if result.stdout!=expected:
            offset=next((i for i,(a,b) in enumerate(zip(result.stdout,expected)) if a!=b),
                        min(len(result.stdout),len(expected)))
            self.fail(f'first difference={offset}, sizes={len(result.stdout)}/{len(expected)}, '
                      f'sha256={hashlib.sha256(result.stdout).hexdigest()}/{hashlib.sha256(expected).hexdigest()}')

    def test_decimal_boundaries_many_values_receiver_effect_order_and_continuation(self):
        executable=build(self,'decimal',SOURCE+'import sys\n\ndef main() -> int:\n    return run(int(sys.argv[1]))\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
        for n in (0,1,8193):
            with self.subTest(n=n): self.compare(executable,SOURCE,n)

    def supported_by_baseline_and_candidate(self,source):
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            import pyfunc
            original=pyfunc._bytearray_method
            baseline=support.ROOT/'language_examples/bytearray_method_r616.baseline'
            namespace={}
            exec(compile(baseline.read_text(encoding='utf8'),str(baseline),'exec'),pyfunc.__dict__,namespace)
            messages=[]
            try:
                for method in (namespace['_bytearray_method'],original):
                    pyfunc._bytearray_method=method
                    try:
                        pyfunc.to_c(source,name='run',strict=True)
                    except pyfunc.Unsupported as error:
                        messages.append(str(error))
                    else:
                        messages.append(None)
            finally:
                pyfunc._bytearray_method=original
            self.assertEqual(messages[1],messages[0],'candidate/baseline support or refusal differs')
            return messages[0] is None
        finally:
            sys.path.pop(0)

    def test_shadowed_function_and_float_fallback(self):
        for name,source in (('shadow',SHADOW),('float',FLOAT)):
            with self.subTest(name=name):
                if not self.supported_by_baseline_and_candidate(source): continue
                executable=build(self,name,source+'import sys\n\ndef main() -> int:\n    return run(int(sys.argv[1]))\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
                self.compare(executable,source,17)

    def test_strict_codec_errors(self):
        expressions=('str(value).encode("ascii")','str(value).encode(errors="ignore")',
                     'str(value).encode("utf8","strict","extra")',
                     'str(value).encode("utf8",encoding="utf8")',
                     'str(value).encode(unknown="utf8")','str(value).encode(1)',
                     'str(value).encode(codec)')
        sources=[f'fn run(value:int)->int {{ let codec="utf8"; let output=bytearray(); output.extend({expression}); return 0; }}'
                 for expression in expressions]
        sys.path.insert(0,str(support.ROOT/'python/pkg-v12'))
        try:
            from pyfunc import to_c,Unsupported
            for source in sources:
                with self.subTest(source=source):
                    with self.assertRaises(Unsupported):
                        to_c(source,name='run',strict=True)
        finally:
            sys.path.pop(0)

    def test_callable_str_shadow_or_equal_existing_refusal(self):
        if not self.supported_by_baseline_and_candidate(CALLABLE): return
        executable=build(self,'callable',CALLABLE+'import sys\n\ndef main() -> int:\n    return run(int(sys.argv[1]))\n\nif __name__ == "__main__":\n    sys.exit(main())\n')
        self.compare(executable,CALLABLE,17)

if __name__=='__main__':
    unittest.main()
