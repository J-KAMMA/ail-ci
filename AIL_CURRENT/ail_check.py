"""Run the selected source regression suite, sequentially, without discovery."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
MODULES = (
    'test_ail_sdk', 'test_ail_sdk_environment', 'test_ail_packaging', 'test_ail_platforms', 'test_ail_fuzz_findings', 'test_ail_corpus_findings', 'test_ail_corpus_findings2', 'test_ail_spec_fixes', 'test_ail_quirks', 'test_ail_doctor', 'test_ail_integer_codec', 'test_ail_bytearray_decimal', 'test_ail_modconst', 'test_ail_sets_general',
    'test_ail_handle_lists', 'test_ail_filesystem_mutation', 'test_ail_stdout_mixed',
    'test_ail_stdout_mixed_resources', 'test_ail_tcp_poll', 'test_ail_tcp_poll_resources',
    'test_ail_tcp_json_lines_poll_resources', 'test_ail_csv_writer', 'test_ail_csv_reference', 'test_ail_monotonic',
    'test_ail_tcp_json_deadlines', 'test_ail_csv_rewrite_stream',
    'test_ail_csv_rewrite_stream_resources', 'test_ail_source_check', 'test_ail_type_details', 'test_ail_argument_type_details', 'test_ail_owned_type_details', 'test_ail_owned_type_repair', 'test_ail_list_expression_extend', 'test_ail_string_field_mutation', 'test_ail_float_argument_widening', 'test_ail_check_repair_context', 'test_ail_exception_context', 'test_ail_exception_values_core', 'test_ail_exception_aggregate_objects', 'test_ail_exception_values_app', 'test_ail_empty_blocks', 'test_ail_source_edit', 'test_ail_edit_check_report', 'test_ail_batch_edit', 'test_ail_try_locals', 'test_ail_str_iter_fast', 'test_ail_builder_locals', 'test_ail_scan_spec_modes', 'test_ail_local_count_repeat', 'test_ail_field_index_inplace', 'test_ail_overflow_error', 'test_ail_struct_list_inplace', 'test_ail_borrowed_owner', 'test_ail_memory_shapes', 'test_ail_bytearray_loops', 'test_ail_refusal_hints', 'test_ail_optional_structs', 'test_ail_stdin_read_until', 'test_ail_for_bytes_expr', 'test_ail_numeric_loops', 'test_ail_frontend_speed', 'test_ail_instruction_gap', 'test_ail_span_cache', 'test_ail_field_views', 'test_ail_parallel_for', 'test_ail_numeric_loop_arena', 'test_ail_source_context', 'test_ail_api_contracts', 'test_ail_builtin_api', 'test_ail_builtin_contracts', 'test_ail_api_profiles', 'test_ail_scalar_list_mutations', 'test_ail_numeric_bindings', 'test_ail_numeric_binding_boundaries', 'test_ail_numeric_profiles', 'test_ail_numeric_profiles_native', 'test_ail_record_initializers', 'test_ail_builtin_maps', 'test_ail_builtin_syntax_forms', 'test_ail_str_find_alias', 'test_ail_str_rfind', 'test_ail_str_predicates', 'test_ail_sort_keys', 'test_ail_build_reports', 'test_ail_native_diagnostics', 'test_ail_c_keyword_functions', 'test_ail_libc_names', 'test_ail_builtin_shadowing', 'test_ail_c_api_exception_values', 'test_c_api_bridge', 'test_ail_context_imports', 'test_ail_edit_dependencies', 'test_ail_ordinary_join_return', 'test_ail_owned_join_take', 'test_ail_string_repeat_fusion', 'test_ail_typed_locals', 'test_ail_bytes_list_fields', 'test_ail_grid_return', 'test_ail_grid_calls', 'test_ail_pool_iter_capture', 'test_ail_pool_row_arguments', 'test_ail_argv_slices', 'test_ail_cli_args', 'test_integer_row_stream', 'test_json_pointer_batch', 'test_json_pointer_scan', 'test_json_query_cli', 'test_json_query_file', 'test_json_document_library', 'test_json_kv', 'test_json_kv_tcp', 'test_csv_column_stats_cli', 'test_csv_column_stats_value', 'test_csv_column_stats_stream', 'test_csv_group_scan', 'test_ail_reference_examples', 'test_ail_dict_upsert', 'test_ail_field_str_append', 'test_ail_list_ops', 'test_ail_check', 'test_ail_dict_delete', 'test_ail_ctor_move', 'test_ail_int_dict_set', 'test_ail_arg_borrow', 'test_ail_stdin_list_batch', 'test_ail_heapq_bisect', 'test_ail_short_style_traps', 'test_ail_text_lines', 'test_ail_swap_rebinding', 'test_ail_nested_lists', 'test_ail_field_store_cost', 'test_ail_lang_gaps', 'test_ail_text_views', 'test_ail_slow_patterns', 'test_ail_python_syntax', 'test_ail_element_views', 'test_ail_range_checks', 'test_ail_hot_ops', 'test_ail_ir_s0', 'test_ail_ir_s1', 'test_ail_ir_s2', 'test_ail_ir_s3', 'test_ail_ir_s3b', 'test_ail_stdlib_batch1', 'test_ail_re', 'test_ail_collections', 'test_ail_ir_s4a', 'test_ail_tuples', 'test_ail_stdlib_batch3', 'test_ail_json_fast', 'test_ail_ir_rulex', 'test_ail_ir_s4c1', 'test_ail_fallback_note', 'test_ail_refusal_messages', 'test_ail_ir_s3c1', 'test_ail_ir_s3c2', 'test_ail_ir_s3c3', 'test_ail_ir_s3d1', 'test_ail_modules', 'test_ail_loss_paths', 'test_ail_stdlib_batch4', 'test_ail_try_hoist', 'test_ail_rep5_idioms', 'test_ail_files', 'test_ail_ffi', 'test_ail_zlib', 'test_ail_http', 'test_ail_subprocess', 'test_ail_clock', 'test_ail_build_cache', 'test_ail_ir_f1', 'test_ail_field_pop', 'test_ail_int_sort', 'test_ail_obj_refs', 'test_ail_bytearray_refs', 'test_ail_borrowed_elements', 'test_ail_str_comprehension_move', 'test_ail_ir_specsel', 'test_ail_pathlib', 'test_ail_sqlite', 'test_ail_ir_cover', 'test_ail_excfix', 'test_ail_exc_str', 'test_ail_globals', 'test_ail_threads', 'test_ail_virtual_dispatch', 'test_ail_typed_inherit', 'test_ail_boolfield', 'test_ail_stdlib5', 'test_ail_dunders', 'test_ail_silent5', 'test_ail_silent6', 'test_ail_typed_blockers', 'test_ail_genlib', 'test_ail_crypto',
    'test_ail_nested_functions', 'test_ail_match', 'test_ail_raise_from', 'test_ail_optional_locals',
    'test_ail_safetynet',
    'test_ail_strict', 'test_ail_cratebridge', 'test_ail_typed_parallel', 'test_ail_freestanding', 'test_ail_freestanding2',
    'test_ail_flush_exit', 'test_ail_mixed_bounds', 'test_ail_typed_submit', 'test_ail_typed_tuples',
    'test_ail_lsp', 'test_ail_project', 'test_ail_debug', 'test_ail_debug_lines', 'test_ail_debug_flush',
    'test_ail_typed_blockers2',
    'test_ail_c_export',
    'test_ail_unified',
    'test_ail_ir_gridbounds',
    'test_ail_bugs7',
    'test_ail_unbound',
    'test_ail_gcfix',
    'test_ail_gcstress',
    'test_ail_gcroots',
    'test_ail_deqctr',
    'test_ail_gaps_api1',
    'test_ail_gaps_api2',
    'test_ail_silent1',
    'test_ail_silent2',
    'test_ail_nonecrash',
    'test_ail_fuzz1',
    'test_ail_fuzz22',
    'test_ail_fuzz3',
    'test_ail_fuzz3n',
    'test_ail_fuzz20',
    'test_ail_c169',
    'test_ail_fuzz21',
    'test_ail_fuzz23',
    'test_ail_fuzz24',
    'test_ail_fuzz27',
    'test_ail_fuzz30',
    'test_ail_fuzz31',
    'test_ail_fuzz32',
    'test_ail_fuzz33',
    'test_ail_fuzz46',
    'test_ail_fuzz47',
    'test_ail_fuzz48',
    'test_ail_fuzz51',
    'test_ail_fuzz36',
    'test_ail_fuzz37',
    'test_ail_fuzz38',
    'test_ail_fuzz39',
    'test_ail_fuzz41',
    'test_ail_fuzz66',
    'test_ail_fuzz70',
    'test_ail_fuzz74',
    'test_ail_fuzz76',
    'test_ail_fuzz77',
    'test_ail_fuzz8',
    'test_ail_fuzz80',
    'test_ail_fuzz82',
    'test_ail_fuzz60',
    'test_ail_fuzz61',
    'test_ail_fuzz62',
    'test_ail_fuzz65',
    'test_ail_fuzz55',
    'test_ail_fuzz56',
    'test_ail_fuzz83',
    'test_ail_fuzz86',
    'test_ail_fuzz87',
    'test_ail_fuzz89',
    'test_ail_pre18',
    'test_ail_pre96',
    'test_ail_pre97',
    'test_ail_pre98',
    'test_ail_pre109',
    'test_ail_pre110',
    'test_ail_pre128',
    'test_ail_pre130',
    'test_ail_pre132',
    'test_ail_pre133',
)


SUPPORT = (
    'ail_check.py', 'test_ail_struct_lifetimes.py', 'test_ail_text_find_search.py', 'test_ail_float64_codec.py', 'test_ail_callable_owned_results.py', 'test_ail_callable_values.py', 'test_ail_finally.py', 'language_examples/numeric_pipeline_allocator.c', 'test_ail_binary_cursor_cli.py', 'test_csv_column_stats_bytes_value_candidate.py', 'test_csv_column_stats_stream_candidate.py', 'test_csv_column_stats_bytes_candidate.py', 'test_csv_column_stats_skip_candidate.py', 'test_ail_c_objects.py', 'test_ail_exception_resources.py',
    'test_ail_map_fields.py', 'test_ail_bytearray_receiver.py', 'language_examples/bytearray_method_r616.baseline', 'test_ail_tcp_json_lines.py', 'test_ail_tcp_json_lines_poll.py',
    'test_ail_tcp_listener.py', 'test_integer_column_stats_cli.py', 'test_json_query_cli.py',
    'freestanding/ring.py', 'freestanding/pagealloc.py', 'freestanding/crc32.py', 'freestanding/vga.py', 'freestanding/kernel_main.py', 'freestanding/harness.c',
    'freestanding/kernel/boot.S', 'freestanding/kernel/linker.ld', 'freestanding/kernel/build.py', 'freestanding/kernel/console.py', 'freestanding/kernel/idt.py', 'freestanding/kernel/kmain.py', 'freestanding/kernel/harness_kernel.c',
)

def preflight(root):
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10 or newer is required')
    if not shutil.which('gcc'):
        raise ValueError('gcc must be available on PATH')
    compiler = os.environ.get('PIPE_CC', '')
    if compiler and not shutil.which(compiler):
        raise ValueError(f'PIPE_CC does not resolve: {compiler}')
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    selected = manifest.get('sdk_files')
    pins = manifest.get('sha256')
    if not isinstance(selected, list) or not selected or not isinstance(pins, dict):
        raise ValueError('MANIFEST requires sdk_files and sha256')
    for name in dict.fromkeys(selected + list(SUPPORT) + [f'{module}.py' for module in MODULES]):
        if not isinstance(name, str):
            raise ValueError('invalid manifest path')
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f'missing or unsafe selected file: {name}')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if pins.get(name) != digest:
            raise ValueError(f'hash mismatch: {name}')
    probe = subprocess.run(
        [sys.executable, '-B', str(root / 'ail_chatgpt.py'), 'doctor', '--check'],
        cwd=root, capture_output=True, timeout=150,
    )
    report = json.loads(probe.stdout)
    check = report.get('build_check', {})
    if probe.returncode or probe.stderr or check.get('status') != 'passed' or check.get('phase') != 'run':
        raise ValueError(f'doctor --check failed: {check}')


def load_suite(root):
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in MODULES:
        module = importlib.import_module(name)
        if Path(module.__file__).resolve() != (root / f'{name}.py').resolve():
            raise ValueError(f'test imported outside source root: {name}')
        tests = loader.loadTestsFromModule(module)
        count = tests.countTestCases()
        if loader.errors or not count:
            raise ValueError(f'no valid tests loaded: {name}: {loader.errors}')
        print(f'{name}: {count} tests')
        suite.addTests(tests)
    return suite


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='list exact test IDs without probes')
    args = parser.parse_args(argv)
    os.environ.setdefault('AIL_NO_CACHE', '1')   # tests that exercise the build cache set their own AIL_CACHE
    # The suite's builds turn a wrong-struct helper call (GCC 13 only warns) into an error; users' builds are unchanged.
    os.environ.setdefault('AIL_EXTRA_CFLAGS', '-Werror=incompatible-pointer-types')
    old_cwd, old_path = Path.cwd(), sys.path[:]
    try:
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        if not args.list:
            preflight(ROOT)
        suite = load_suite(ROOT)
        if not suite.countTestCases():
            raise ValueError('no selected tests loaded')
        print(f'Total: {suite.countTestCases()} tests', flush=True)
        if args.list:
            print('\n'.join(test_ids(suite)))
            return 0
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        for test, reason in result.skipped:
            print(f'UNVERIFIED SKIP {test.id()}: {reason}')
        if result.testsRun == len(result.skipped):
            print('No selected test was verified', file=sys.stderr)
            return 1
        return 0 if result.wasSuccessful() else 1
    except Exception as error:
        print(f'Configuration/probe/import failure: {error}', file=sys.stderr)
        return 2
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path


if __name__ == '__main__':
    raise SystemExit(main())