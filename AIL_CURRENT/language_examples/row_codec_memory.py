"""Independent helper allocation/RSS evidence; instrumented jobs are never timed.

Requested peak excludes allocator headers, libc-internal allocations, static
storage, .rodata, and RSS. Realloc requests count full new capacity, not growth.
RSS is a separate per-process page-based observation, not a speed or causal claim.
"""
import argparse
import array
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import row_codec_compare as codec

compare, row = codec.compare, codec.compare.row
HERE, ROOT = codec.HERE, codec.compare.ROOT
sys.path.insert(0, str(ROOT))
from test_ail_exception_resources import ALLOCATOR

TAIL = r'''
#undef main
static void heap_report(void) {
 DRAIN
 fprintf(stderr,"HEAP {\"live\":%zu,\"bytes\":%zu,\"peak\":%zu}\n",live,live_bytes,peak_bytes);
}
int main(int argc,char **argv) {if(atexit(heap_report))return 123;return tracked_main(argc,argv);}
'''


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError('allocation observer anchor changed: ' + anchor[:100])
    return text.replace(anchor, replacement, 1)


def counted(code):
    allocator = ALLOCATOR
    declaration = 'static size_t live, live_bytes, peak_bytes;'
    extra = r'''
static size_t request_calls, requested_bytes, request_kinds[3];
static void count_request(size_t size, unsigned kind) {
    if (request_calls == SIZE_MAX || requested_bytes > SIZE_MAX - size || request_kinds[kind] == SIZE_MAX) abort();
    request_calls++; requested_bytes += size; request_kinds[kind]++;
}
'''
    allocator = replace_once(allocator, declaration, declaration + extra)
    allocator = replace_once(allocator, 'static void *count_malloc(size_t size) {',
                              'static void *raw_malloc(size_t size) {')
    allocator = replace_once(allocator, 'static void count_free(void *ptr) {', r'''static void *count_malloc(size_t size) {
    count_request(size, 0); return raw_malloc(size);
}
static void count_free(void *ptr) {''')
    allocator = replace_once(allocator, '    void *p = count_malloc(n * size);',
                              '    count_request(n * size, 1);\n    void *p = raw_malloc(n * size);')
    allocator = replace_once(allocator, 'static void *count_realloc(void *ptr, size_t size) {',
                              'static void *count_realloc(void *ptr, size_t size) {\n    count_request(size, 2);')
    allocator = replace_once(allocator, '    if (!ptr) return count_malloc(size);',
                              '    if (!ptr) return raw_malloc(size);')
    # Caller workloads are bounded; original calloc overflow rejection is preserved.
    # Zero-size realloc-to-free counts as one request of zero bytes.
    drain = ('for(int64_t i=0;i<ail__blk_cache_n;i++)free(ail__blk_cache[i].p);'
             'ail__blk_cache_n=0;ail__blk_cache_bytes=0;') if 'ail__blk_cache[AIL_BLK_CACHE_MAX]' in code else ''
    drain += ('for(int j=0;j<ail__ba_cache_n;j++){free(ail__ba_cache[j]->p);free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in code else '')  # parked bytearrays (cruntime ail__ba_cache)
    tail = TAIL.replace('DRAIN', drain)
    anchor = r' fprintf(stderr,"HEAP {\"live\":%zu,\"bytes\":%zu,\"peak\":%zu}\n",live,live_bytes,peak_bytes);'
    replacement = r''' fprintf(stderr,"HEAP {\"live\":%zu,\"bytes\":%zu,\"peak\":%zu,\"request_calls\":%zu,\"requested_bytes\":%zu,\"malloc_calls\":%zu,\"calloc_calls\":%zu,\"realloc_calls\":%zu}\n",live,live_bytes,peak_bytes,request_calls,requested_bytes,request_kinds[0],request_kinds[1],request_kinds[2]);'''
    tail = replace_once(tail, anchor, replacement)
    return '#include <stdint.h>\n' + allocator + '\n#define main tracked_main\n' + code + tail


def command(argv, report, name):
    item = dict(command=list(map(str, argv)), status='STARTED')
    report['operations'][name] = item
    result = subprocess.run(argv, capture_output=True, timeout=180)
    item.update(status='RETURNED', actual=compare.observed(result))
    if result.returncode:
        raise ValueError('operation failed: ' + name)
    return result


def build(work, label, code, gcc, report):
    source = work / (label + '.c')
    binary = work / (label + ('.exe' if os.name == 'nt' else ''))
    source.write_text(code, encoding='utf8')
    before = row.pin(source)
    command([str(gcc), *row.FLAGS, str(source), '-lm', '-o', str(binary)], report, 'build_' + label)
    report['builds'][label] = dict(source_before=before, binary_before=row.pin(binary))
    return binary, source


def input_case(work, name, values, cols, *, tail=b'', expect_error=False):
    words = array.array('q', values)
    if words.itemsize != 8:
        raise ValueError('8-byte array q required')
    if sys.byteorder != 'little':
        words.byteswap()
    data = words.tobytes() + tail
    expected = b'' if expect_error else row.oracle(values, cols, 1)
    source, oracle = work / (name + '.bin'), work / (name + '.expected')
    source.write_bytes(data)
    oracle.write_bytes(expected)
    return dict(name=name, input=source, expected_path=oracle, cols=cols, expected=expected,
                returncode=2 if expect_error else 0, input_before=row.pin(source), expected_before=row.pin(oracle))


def observe(binary, case, report, *, heap=False, time_tool=None, cycle=None, position=None, variant=None):
    item = dict(variant=variant, binary=str(binary), case=case['name'], cycle=cycle, position=position,
                passed=False, status='STARTED', input_before=case['input_before'],
                expected_before=case['expected_before'], binary_before=row.pin(binary))
    report['heap_runs' if heap else 'rss_runs'].append(item)
    argv = [str(binary), str(case['input']), str(case['cols']), '1']
    if time_tool is not None:
        argv = [str(time_tool), '-f', 'RSS_KIB=%M', *argv]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=180)
        item.update(status='RETURNED', actual=compare.observed(result),
                    output_verified=result.stdout == case['expected'])
        if result.returncode != case['returncode'] or result.stdout != case['expected']:
            raise ValueError('whole output/status differs: ' + case['name'])
        if heap:
            match = re.fullmatch(rb'HEAP (\{[^\r\n]+\})\r?\n', result.stderr)
            if not match:
                raise ValueError('single exact heap record required')
            stats = json.loads(match[1])
            names = ('live', 'bytes', 'peak', 'request_calls', 'requested_bytes',
                     'malloc_calls', 'calloc_calls', 'realloc_calls')
            if set(stats) != set(names) or any(type(stats[key]) is not int or stats[key] < 0 for key in names):
                raise ValueError('invalid heap counters')
            item['heap'] = stats
            if stats['live'] or stats['bytes']:
                raise ValueError('requested native allocations remain live')
            if stats['request_calls'] <= 0 or not 0 < stats['peak'] <= stats['requested_bytes']:
                raise ValueError('allocation observer lacks valid nonzero evidence')
            if stats['request_calls'] != sum(stats[key] for key in names[-3:]):
                raise ValueError('request family counts differ')
        else:
            match = re.fullmatch(rb'RSS_KIB=(\d+)\r?\n', result.stderr)
            if not match or int(match[1]) <= 0:
                raise ValueError('positive GNU time per-process RSS record required')
            item['peak_rss_kib'] = int(match[1])
        item['passed'] = True
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        item.update(error=str(error))
        raise
    finally:
        item.update(input_after=row.pin(case['input']), expected_after=row.pin(case['expected_path']),
                    binary_after=row.pin(binary))
        item['data_unchanged'] = (item['input_before'] == item['input_after']
            and item['expected_before'] == item['expected_after'] and item['binary_before'] == item['binary_after'])
        if not item['data_unchanged']:
            item['passed'] = False
            raise ValueError('input/oracle/binary changed')
    return item


def sections(work, binaries, objcopy, report):
    if objcopy is None:
        report['binary_sections'] = dict(status='NOT_PERFORMED', reason='objcopy unavailable')
        return []
    artifacts = []
    report['binary_sections'] = dict(status='STARTED', variants={})
    for label, binary in binaries.items():
        text, rodata, copied = (work / (label + suffix) for suffix in ('.text', '.rodata', '.section-copy'))
        command([str(objcopy), '--dump-section', '.text=' + str(text), '--dump-section', '.rodata=' + str(rodata),
                 str(binary), str(copied)], report, 'sections_' + label)
        if not text.is_file():
            raise ValueError('plain .text section missing')
        report['binary_sections']['variants'][label] = dict(binary=row.pin(binary), text=row.pin(text),
            rodata=row.pin(rodata) if rodata.is_file() else dict(status='NOT_PRESENT', reason='object format has no .rodata section'))
        artifacts.extend(path for path in (text, rodata, copied) if path.is_file())
    report['binary_sections']['status'] = 'MEASURED'
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', choices=('codec', 'local-store', 'row-quad'), default='codec')
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    if args.candidate == 'row-quad':
        import row_decimal_quad as candidate_module
        patch = lambda code: candidate_module.patch_generated(code, require_decimal=True)
    elif args.candidate == 'local-store':
        import row_store_identity_compare as candidate_module
        patch = candidate_module.patch_local_stores
    else:
        candidate_module = codec
        patch = lambda code: codec.patch_generated(code, require_all=True)
    report = dict(schema='ail.row-helper-memory/1', candidate_profile=args.candidate,
                  status='UNVERIFIED', output_verified=False,
                  timing_qualified=False, optimization_adopted=False, physical_roof_measured=False,
                  heap_scope=__doc__.strip(), heap_accounting='one payload request per count_malloc/count_calloc/count_realloc invocation; delegates counted once; zero-size realloc free requests included; calloc overflow returns NULL before accounting',
                  rss=dict(status='NOT_PERFORMED', reason='not started'), operations={}, builds={},
                  heap_runs=[], rss_runs=[], pins_before={})
    watched = [Path(__file__), Path(codec.__file__), Path(candidate_module.__file__), Path(compare.__file__), Path(row.__file__),
               ROOT / 'test_ail_exception_resources.py', HERE / 'integer_row_stream.ail', HERE / 'row_reduce_stream_main.ail',
               ROOT / 'ail_chatgpt.py', ROOT / 'ail_syntax.py', ROOT / 'MANIFEST.json',
               *sorted((ROOT / 'python/pkg-v12').glob('*.py'))]
    if args.candidate == 'row-quad':
        watched.append(HERE / 'integer_row_stream_checkpoint_candidate.ail')
    try:
        gcc_path = shutil.which('gcc')
        if not gcc_path:
            raise ValueError('gcc required')
        gcc = Path(gcc_path).absolute()
        objcopy = Path(shutil.which('objcopy')).absolute() if shutil.which('objcopy') else None
        time_tool = Path('/usr/bin/time') if sys.platform == 'linux' and Path('/usr/bin/time').is_file() else None
        watched += [gcc, *([objcopy] if objcopy else []), *([time_tool] if time_tool else [])]
        report['pins_before'] = {str(path): row.pin(path) for path in watched}
        report['compiler_version'] = command([str(gcc), '--version'], report, 'gcc_version').stdout.decode(errors='replace')
        if time_tool is not None:
            version = subprocess.run([str(time_tool), '--version'], capture_output=True, timeout=30)
            report['operations']['time_version'] = dict(command=[str(time_tool), '--version'], actual=compare.observed(version))
            if version.returncode or b'GNU' not in version.stdout:
                time_tool = None
                report['rss'] = dict(status='NOT_PERFORMED', reason='installed time is not GNU time')
        else:
            report['rss'] = dict(status='NOT_PERFORMED', reason='GNU time unavailable or platform is not Linux')
        with tempfile.TemporaryDirectory(prefix='ail-row-codec-memory-') as directory:
            work = Path(directory)
            plain, tracked, artifacts = {}, {}, []
            base = row.generated(HERE / 'row_reduce_stream_main.ail')
            if args.candidate == 'row-quad':
                directory = work / 'candidate_sources'
                directory.mkdir()
                for source, name in ((HERE / 'integer_row_stream_checkpoint_candidate.ail', 'integer_row_stream.ail'),
                                     (HERE / 'row_reduce_stream_main.ail', 'row_reduce_stream_main.ail')):
                    target = directory / name
                    target.write_bytes(source.read_bytes())
                    if target.read_bytes() != source.read_bytes():
                        raise ValueError('candidate source copy changed')
                    artifacts.append(target)
                candidate = patch(row.generated(directory / 'row_reduce_stream_main.ail'))
            else:
                candidate = patch(base)
            codes = dict(baseline=base, candidate=candidate)
            report['generated_c_hashes'] = {label: compare.digest(code.encode()) for label, code in codes.items()}
            for label, code in codes.items():
                for mode, body, binaries in (('plain', code, plain), ('heap', counted(code), tracked)):
                    binary, source = build(work, label + '_' + mode, body, gcc, report)
                    binaries[label] = binary
                    artifacts.extend((binary, source))
            artifacts += sections(work, plain, objcopy, report)
            report['artifacts_before'] = {str(path): row.pin(path) for path in artifacts}
            try:
                values = array.array('q', ((-1 if i % 2 else 1) * ((1 << 53) + 37 * i + 19) for i in range(65537 * 17)))
                whole = input_case(work, 'whole_65537x17', values, 17)
                del values
                maximum, minimum = (1 << 63) - 1, -(1 << 63)
                cases = [whole, input_case(work, 'signed_edges', [minimum, maximum, maximum, -maximum], 2),
                         input_case(work, 'empty', [], 3),
                         input_case(work, 'partial_bytes', [7, -7], 2, tail=b'x', expect_error=True),
                         input_case(work, 'partial_row', [7], 2, expect_error=True),
                         input_case(work, 'positive_prefix_error', [7, -7, maximum, 1], 2, expect_error=True),
                         input_case(work, 'negative_prefix_error', [7, -7, minimum, -1], 2, expect_error=True)]
                for label, binary in tracked.items():
                    for case in cases:
                        observe(binary, case, report, heap=True, variant=label)
                if time_tool is not None:
                    report['rss'] = dict(status='STARTED', scope='GNU time per-process maximum RSS; includes libc/static/.rodata/pages; not requested payload; page noise unquantified',
                                         protocol='five runs per variant, alternating pair order AB/BA/AB/BA/AB; sample counts balanced, first-position counts3/2')
                    for cycle in range(5):
                        order = ('baseline', 'candidate') if cycle % 2 == 0 else ('candidate', 'baseline')
                        for position, label in enumerate(order):
                            observe(plain[label], whole, report, time_tool=time_tool, cycle=cycle,
                                    position=position, variant=label)
                    report['rss']['status'] = 'MEASURED'
                    report['rss']['values_kib'] = {label: [item['peak_rss_kib'] for item in report['rss_runs'] if item['variant'] == label]
                                                  for label in plain}
            finally:
                report['artifacts_after'] = {str(path): row.pin(path) for path in artifacts}
                report['artifacts_unchanged'] = report['artifacts_before'] == report['artifacts_after']
                if not report['artifacts_unchanged']:
                    raise ValueError('generated code/binary/section changed')
        report.update(status='MEMORY_MEASURED_OUTPUT_VERIFIED', output_verified=True)
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        report.update(status='FAILED', output_verified=False, failure=str(error))
    finally:
        try:
            report['pins_after'] = {str(path): row.pin(path) for path in watched}
            if report['pins_before'] != report['pins_after']:
                report.update(status='FAILED', output_verified=False, pin_failure='source/compiler changed')
        except OSError as error:
            report.update(status='FAILED', output_verified=False, pin_failure=str(error))
        with args.output.open('x', encoding='utf8') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
    print(json.dumps(dict(status=report['status'], output_verified=report['output_verified'],
                          heap_runs=len(report['heap_runs']), rss=report['rss']['status'])))
    return 0 if report['output_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
