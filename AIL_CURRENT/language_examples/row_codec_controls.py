"""Independent whole-output codec controls; no heap/peak-memory claim.

Widths 1/2/4 decode unsigned, zero-extended octets; width 8 decodes signed
int64. Public valid buffers only; no fabricated invalid C pointers or spans.
"""
from pathlib import Path
import random
import struct
import subprocess

import row_locals_compare as compare

row = compare.row
SOURCE = r'''fn main()->int {
 let input=bytearray(read_bytes(sys.argv[1]));
 let data:bytes=bytes(input);
 let width:int=int(sys.argv[2]);let order:int=int(sys.argv[3]);
 let offset:int=int(sys.argv[4]);
 let payload:bytes=data;
 if offset==1 {payload=data[1:-1];}
 try {
  let first:list[int]=integer_decode(payload,width,order);
  let peer:list[int]=integer_decode(payload,width,order);
  if len(first)!=len(peer) {return 3;}
  if len(peer)>0 {
   let original:int=peer[0];
   let octet:int=data[offset];
   input[offset]=(octet+1)%256;
   if data[offset]!=octet or input[offset]!=(octet+1)%256 {return 4;}
   let changed:bytes=bytes(input);
   if original!=0 {first[0]=0;} else {first[0]=1;}
   if peer[0]!=original or data[offset]!=octet {return 5;}
   if bytes(input)!=changed {return 8;}
  }
  let fresh:list[int]=integer_decode(payload,width,order);
  if len(fresh)!=len(peer) {return 6;}
  for i in range(len(peer)) {if fresh[i]!=peer[i] {return 7;}}
  let output=bytearray();
  for value in peer {output.extend(str(value).encode());output.append(10);}
  write_stdout_bytes(bytes(output));return 0;
 } except ValueError {return 2;}
}'''


def decoded(data, width, order):
    """Python byte-domain oracle, independent of generated C and AIL codecs."""
    if width not in (1, 2, 4, 8) or order not in (0, 1) or len(data) % width:
        raise ValueError('invalid public integer codec input')
    return [int.from_bytes(data[start:start + width], 'big' if order else 'little', signed=width == 8)
            for start in range(0, len(data), width)]


def cases():
    maximum, minimum = (1 << 63) - 1, -(1 << 63)
    for width in (1, 2, 4, 8):
        values = ([minimum, maximum, -(1 << 53) - 1, -1, 0, 1, (1 << 53) + 1]
                  if width == 8 else [0, 1, (1 << (width * 8 - 1)) - 1,
                                     1 << (width * 8 - 1), (1 << (width * 8)) - 2, (1 << (width * 8)) - 1])
        for order in (0, 1):
            data = b''.join(value.to_bytes(width, 'big' if order else 'little', signed=width == 8)
                            for value in values)
            for offset in (0, 1):
                yield f'width{width}_order{order}_offset{offset}', data, width, order, offset
            yield f'empty_width{width}_order{order}', b'', width, order, 1
    for width in (0, 3, 9, -1):
        for data in (b'', b'\x01\x02\x03\x04\x05\x06\x07\x08'):
            yield f'bad_width{width}_bytes{len(data)}', data, width, 0, 1
    for order in (-1, 2):
        for width in (1, 2, 4, 8):
            for data in (b'', b'\xff' * width):
                yield f'bad_order{order}_width{width}_bytes{len(data)}', data, width, order, 1
    for width in (2, 4, 8):
        for order in (0, 1):
            for length in (width - 1, width + 1):
                yield f'partial_width{width}_order{order}_bytes{length}', bytes(range(length)), width, order, 1
    edges = [minimum, maximum, 0, -1, 1, -9, 9, -10, 10, -99, 99,
             -100, 100, -999, 999, -1000, 1000]
    adjacent = [sign * (10 ** power + delta) for power in range(19)
                for delta in (-1, 0, 1) for sign in (-1, 1)]
    generator = random.Random(784)
    bits = [generator.getrandbits(64) for _ in range(8193)]
    values = edges + adjacent + [value if value < 1 << 63 else value - (1 << 64) for value in bits]
    data = struct.pack('<' + 'q' * len(values), *values)
    yield 'long_decimal_signed64_seed784', data, 8, 0, 1


def controls(work, variants, gcc, rustc, report, generated):
    """Compile one driver per variant, append observed cases, raise on any failure."""
    work = Path(work)
    outcomes = report.setdefault('codec_controls', [])
    report['codec_control_scope'] = __doc__.strip()
    for variant, directory in variants.items():
        driver = Path(directory) / 'codec_controls.ail'
        driver.write_text(SOURCE, encoding='utf8')
        driver_before = row.pin(driver)
        binary = compare.build(work, variant + '_codec', generated(driver), gcc, rustc, report)
        binary_before = row.pin(binary)
        for name, payload, width, order, offset in cases():
            data = b'\xa5' + payload + b'\x5a' if offset else payload
            try:
                values = decoded(payload, width, order)
                expected = b''.join(f'{value}\n'.encode('ascii') for value in values)
                code = 0
            except ValueError:
                expected, code = b'', 2
            path = work / (variant + '_' + name + '.bin')
            expected_path = work / (variant + '_' + name + '.expected')
            path.write_bytes(data)
            expected_path.write_bytes(expected)
            before = row.pin(path)
            expected_before = row.pin(expected_path)
            item = dict(variant=variant, case=name, width=width, order=order, offset=offset,
                        decoded_domain=('signed int64' if width == 8 else 'unsigned zero-extended'
                                        if width in (1, 2, 4) else 'invalid width'),
                        passed=False, status='STARTED', expected_returncode=code,
                        input_before=before, expected_before=expected_before, driver_before=driver_before,
                        binary_before=binary_before, memory_measurement='not_performed', memory_claim=False)
            outcomes.append(item)
            try:
                process = subprocess.run([str(binary), str(path), str(width), str(order), str(offset)],
                                         capture_output=True, timeout=120)
                item.update(status='RETURNED', actual=compare.observed(process),
                            output_verified=process.stdout == expected,
                            passed=(process.returncode, process.stdout, process.stderr) == (code, expected, b''))
            except (OSError, subprocess.SubprocessError) as error:
                item.update(status='ERROR', error=str(error))
                raise ValueError('codec control execution failed: ' + variant + '/' + name) from error
            finally:
                item.update(input_after=row.pin(path), expected_after=row.pin(expected_path),
                            driver_after=row.pin(driver), binary_after=row.pin(binary))
                item['data_unchanged'] = (item['input_before'] == item['input_after']
                    and item['expected_before'] == item['expected_after']
                    and item['driver_before'] == item['driver_after']
                    and item['binary_before'] == item['binary_after'])
            if not item['passed'] or not item['data_unchanged']:
                raise ValueError('codec control failed: ' + variant + '/' + name)
    return outcomes
