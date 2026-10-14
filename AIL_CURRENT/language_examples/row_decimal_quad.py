"""Research-only four-digit decimal formatting; no adoption claim."""
from row_codec_compare import DECIMAL_FAST


DECIMAL_QUAD = DECIMAL_FAST.replace('    while (magnitude >= 100) {', '''    while (magnitude >= 10000) {
        uint32_t quad = (uint32_t)(magnitude % 10000);
        magnitude /= 10000;
        uint32_t low = quad % 100;
        uint32_t high = quad / 100;
        buffer[--position] = digit_pairs[low * 2 + 1];
        buffer[--position] = digit_pairs[low * 2];
        buffer[--position] = digit_pairs[high * 2 + 1];
        buffer[--position] = digit_pairs[high * 2];
    }
    while (magnitude >= 100) {''', 1)


def patch_generated(code, *, require_decimal=False):
    """Replace exactly one unchanged digit-pair helper, or reject source drift."""
    signature = DECIMAL_FAST.partition('\n')[0]
    signatures = code.count(signature)
    if signatures > 1 or signatures and code.count(DECIMAL_FAST) != 1:
        raise ValueError('decimal helper source changed')
    if require_decimal and signatures != 1:
        raise ValueError('required decimal helper missing')
    return code.replace(DECIMAL_FAST, DECIMAL_QUAD, 1) if signatures else code
