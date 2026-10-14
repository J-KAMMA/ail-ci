"""Research-only row integer decoding and decimal formatting; no adoption claim."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys

import row_locals_compare as compare

HERE = Path(__file__).resolve().parent
CURRENT = HERE / 'integer_row_stream.ail'

DECODE_ORIGINAL = r'''static ail_list ail_integer_decode(ail_bytes data, int64_t width, int64_t order) {
    if (width != 1 && width != 2 && width != 4 && width != 8)
        ail_raise_named(AIL_EXC_VALUE);
    if (order != 0 && order != 1) ail_raise_named(AIL_EXC_VALUE);
    if (data.n < 0 || (uintmax_t)data.n > SIZE_MAX ||
            (uintmax_t)data.n > PTRDIFF_MAX || (data.n && !data.p))
        ail_die("invalid bytes span");
    if (data.n % width) ail_raise_named(AIL_EXC_VALUE);
    int64_t count = data.n / width;
    if (count > INT64_MAX / sizeof(int64_t) ||
            (uintmax_t)count > SIZE_MAX / sizeof(int64_t) ||
            (uintmax_t)count > PTRDIFF_MAX / sizeof(int64_t))
        ail_die("integer list too long");
    ail_list result = {0};
    if (!count) return result;
    result.p = (int64_t *)ail_alloc((size_t)count * sizeof *result.p);
    result.n = result.cap = count;
    for (int64_t i = 0; i < count; ++i) {
        uint64_t bits = 0;
        const unsigned char *p = data.p + (size_t)i * (size_t)width;
        for (int64_t k = 0; k < width; ++k)
            bits |= (uint64_t)p[k] << ((order ? width - 1 - k : k) * 8);
        result.p[i] = width == 8 && (bits & (UINT64_C(1) << 63))
            ? -1 - (int64_t)(UINT64_MAX - bits) : (int64_t)bits;
    }
    return result;
}'''

DECIMAL_ORIGINAL = r'''static void ail_bytearray_extend_int(ail_bytearray *output, int64_t value) {
    unsigned char buffer[24];
    int position = sizeof buffer;
    uint64_t magnitude = value < 0 ? (uint64_t)0 - (uint64_t)value : (uint64_t)value;
    do { buffer[--position] = (unsigned char)('0' + magnitude % 10); magnitude /= 10; }
    while (magnitude);
    if (value < 0) buffer[--position] = '-';
    ail_bytearray_extend(output, (ail_bytes){buffer + position, (int64_t)sizeof buffer - position});
}'''

DECODE_FAST = DECODE_ORIGINAL.replace('    result.n = result.cap = count;\n', '''    result.n = result.cap = count;
#if CHAR_BIT == 8 && defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    if (width == 8 && order == 0) {
        memcpy(result.p, data.p, (size_t)data.n);
        return result;
    }
#endif
''', 1)
DIGIT_PAIRS = ''.join(f'{value:02d}' for value in range(100))
DECIMAL_FAST = '''static void ail_bytearray_extend_int(ail_bytearray *output, int64_t value) {
    static const unsigned char digit_pairs[] = "''' + DIGIT_PAIRS + '''";
    unsigned char buffer[24];
    int position = sizeof buffer;
    uint64_t magnitude = value < 0 ? (uint64_t)0 - (uint64_t)value : (uint64_t)value;
    while (magnitude >= 100) {
        unsigned pair = (unsigned)(magnitude % 100);
        magnitude /= 100;
        buffer[--position] = digit_pairs[pair * 2 + 1];
        buffer[--position] = digit_pairs[pair * 2];
    }
    if (magnitude < 10) {
        buffer[--position] = (unsigned char)('0' + magnitude);
    } else {
        unsigned pair = (unsigned)magnitude;
        buffer[--position] = digit_pairs[pair * 2 + 1];
        buffer[--position] = digit_pairs[pair * 2];
    }
    if (value < 0) buffer[--position] = '-';
    ail_bytearray_extend(output, (ail_bytes){buffer + position, (int64_t)sizeof buffer - position});
}'''
PATCHES = {'integer_decode': (DECODE_ORIGINAL, DECODE_FAST), 'decimal_extend': (DECIMAL_ORIGINAL, DECIMAL_FAST)}


def helper_counts(code):
    return {name: dict(original=code.count(original), candidate=code.count(candidate))
            for name, (original, candidate) in PATCHES.items()}


def patch_generated(code, *, require_all=False):
    """Exact guarded helper replacement; unrelated generated C remains untouched."""
    for name, (original, candidate) in PATCHES.items():
        signature = original.partition('\n')[0]
        signatures = code.count(signature)
        if signatures > 1 or signatures and code.count(original) != 1:
            raise ValueError('codec helper source changed: ' + name)
        if require_all and signatures != 1:
            raise ValueError('required codec helper missing: ' + name)
        if signatures:
            code = code.replace(original, candidate, 1)
    return '#include <limits.h>\n' + code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    watched = [Path(__file__), Path(compare.__file__)]
    before = {str(path): compare.row.pin(path) for path in watched}
    original_generated, original_private, original_argv = compare.row.generated, compare.private_controls, sys.argv[:]
    generated_records, validation_pins = [], {}
    def generated(path, *positional, **keywords):
        code = original_generated(path, *positional, **keywords)
        original = code
        candidate = Path(path).parent.name == 'candidate_sources'
        if candidate:
            code = patch_generated(code, require_all=Path(path).name == 'row_reduce_stream_main.ail')
        generated_records.append(dict(source=str(path), candidate=candidate,
                                      before=helper_counts(original), after=helper_counts(code),
                                      original_c_sha256=compare.digest(original.encode()), generated_c_sha256=compare.digest(code.encode())))
        return code
    def private(work, variants, gcc, rustc, report):
        original_private(work, variants, gcc, rustc, report)
        import row_codec_controls as validation
        path = Path(validation.__file__)
        validation_pins['before'] = compare.row.pin(path)
        validation.controls(work, variants, gcc, rustc, report, generated)
        validation_pins['after'] = compare.row.pin(path)
        if validation_pins['before'] != validation_pins['after']:
            raise ValueError('codec validation source changed')
    try:
        compare.row.generated, compare.private_controls = generated, private
        sys.argv = [str(Path(__file__)), '--output', str(args.output), '--candidate', str(CURRENT)]
        with redirect_stdout(io.StringIO()):
            status = compare.main()
    finally:
        compare.row.generated, compare.private_controls, sys.argv = original_generated, original_private, original_argv
    report = json.loads(args.output.read_text(encoding='utf8'))
    pin_error = None
    after = {}
    try:
        after = {str(path): compare.row.pin(path) for path in watched}
        if 'before' in validation_pins:
            validation_pins['after'] = compare.row.pin(Path(validation_pins['before']['path']))
    except OSError as error:
        pin_error = str(error)
    report.update(research='width8 little-endian memcpy after original guards; MIN-safe digit-pair decimal formatter',
                  source_profile='identical current standard module and main for both variants; candidate generated C helpers only',
                  generated_c_records=generated_records, helper_patch_totals={name: sum(item['after'][name]['candidate']
                      for item in generated_records if item['candidate']) for name in PATCHES},
                  validation_module_pins=validation_pins,
                  codec_script_pins_before=before, codec_script_pins_after=after,
                  prior_sample_price=dict(run='37899484159', status='QUALIFIED', rows=65537, cols=17,
                      estimated_decode_wall_share=0.175304, estimated_int_decimal_wall_share=0.114518,
                      estimated_combined_wall_share=0.289821, ideal_zero_cost_amdahl=1.4081,
                      baseline_over_c=1.2171, baseline_over_rust=1.3059,
                      achieved_empirical_c_fraction=0.8217, achieved_empirical_rust_fraction=0.7658,
                      assumed_empirical_reference_fraction=1, physical_roof_measured=False,
                      assumed_physical_roof_fraction=None, scope='sampled CPU attribution scaled by CPU/wall; not a causal wall-time guarantee'))
    if pin_error or before != after or ('before' in validation_pins and validation_pins.get('after') != validation_pins['before']):
        report.update(status='FAILED', quality_passed=False, beats_c_and_rust=False, failure=pin_error or 'codec comparison/validation source changed')
        report.pop('paired_summary', None)
        status = 1
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: report[key] for key in ('status', 'quality_passed', 'beats_c_and_rust', 'memory_measurement')}))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
