"""Research-only state checkpoints plus four-digit decimal formatting."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys

import row_locals_compare as compare
import row_codec_controls as controls
import row_decimal_quad as quad

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / 'integer_row_stream_checkpoint_candidate.ail'
PRICE = json.loads("{\"run\":37912208329,\"counts\":{\"reference\":974,\"state_loop\":623,\"decimal\":736,\"total\":4681,\"cpu_wall\":0.8167732809229639},\"combined_wall_share_estimate\":0.4070779885480185,\"ideal_zero_cost_amdahl\":1.686562449505193,\"half_cost_amdahl\":1.2555542491229426,\"required_total_time_reduction_vs_rust\":0.28467459712010135,\"required_phase_reduction_vs_rust\":0.699312183730419,\"physical_roof_measured\":false,\"assumed_physical_roof_fraction\":null,\"achieved_physical_roof_fraction\":null}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    watched = [Path(__file__), Path(quad.__file__), Path(controls.__file__), Path(compare.__file__)]
    before = {str(path): compare.row.pin(path) for path in watched}
    original_generated, original_private, original_argv = compare.row.generated, compare.private_controls, sys.argv[:]
    records = []
    def generated(path, *positional, **keywords):
        original = original_generated(path, *positional, **keywords)
        candidate = Path(path).parent.name == 'candidate_sources'
        code = quad.patch_generated(original, require_decimal=Path(path).name in
                                    ('row_reduce_stream_main.ail', 'codec_controls.ail')) if candidate else original
        records.append(dict(source=str(path), candidate=candidate,
                            original_c_sha256=compare.digest(original.encode()),
                            generated_c_sha256=compare.digest(code.encode())))
        return code
    def private(work, variants, gcc, rustc, report):
        original_private(work, variants, gcc, rustc, report)
        controls.controls(work, variants, gcc, rustc, report, generated)
    try:
        compare.row.generated, compare.private_controls = generated, private
        sys.argv = [str(Path(__file__)), '--output', str(args.output), '--candidate', str(CANDIDATE)]
        with redirect_stdout(io.StringIO()):
            status = compare.main()
    finally:
        compare.row.generated, compare.private_controls, sys.argv = original_generated, original_private, original_argv
    report = json.loads(args.output.read_text(encoding='utf8'))
    after = {str(path): compare.row.pin(path) for path in watched}
    report.update(research='checkpoint scalar state at prefix ValueError and normal completion; four-digit decimal chunks',
                  declared_profile='single-thread typed internal state; no custom allocator callback mutating state; headroom for baseline temporary retains',
                  unqualified_profiles=['unsafe ABI headers', 'heap state observed after fatal _Exit', 'concurrent or signal mutation'],
                  prior_sample_price=PRICE, generated_c_records=records,
                  research_pins_before=before, research_pins_after=after)
    if before != after:
        report.update(status='FAILED', quality_passed=False, beats_c_and_rust=False,
                      failure='research scripts changed')
        report.pop('paired_summary', None)
        status = 1
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: report[key] for key in ('status', 'quality_passed', 'beats_c_and_rust')}))
    return status

if __name__ == '__main__':
    raise SystemExit(main())
