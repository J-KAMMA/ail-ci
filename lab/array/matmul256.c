/* The same 256x256 f64 matmul as matmul256.py, with the fixed order of design 3.5/3.7:
   K = 256 is one block, element k goes to lane k % 16 (lanes start at -0.0), then the
   8-4-2-1 tree; the products are rounded before the add, so no FMA. The checksum is the
   row-major sequential sum of every element, the same order as the AIL program. */
#include <stdio.h>

static double a[256][256];
static double b[256][256];
static double c[256][256];

static unsigned long fill(double m[256][256], unsigned long s) {
    int i, j;
    for (i = 0; i < 256; i++) {
        for (j = 0; j < 256; j++) {
            s = (1664525UL * s + 1013904223UL) % 4294967296UL;
            m[i][j] = (double)s / 4294967296.0;
        }
    }
    return s;
}

int main(void) {
    int i, j, k, w, x;
    unsigned long s;
    double total;
    s = fill(a, 1UL);
    fill(b, s);
    for (i = 0; i < 256; i++) {
        for (j = 0; j < 256; j++) {
            double lane[16];
            for (w = 0; w < 16; w++) lane[w] = -0.0;
            for (k = 0; k < 256; k++) lane[k % 16] += a[i][k] * b[k][j];
            for (w = 8; w >= 1; w /= 2) {
                for (x = 0; x < w; x++) lane[x] += lane[x + w];
            }
            c[i][j] = lane[0];
        }
    }
    total = 0.0;
    for (i = 0; i < 256; i++) {
        for (j = 0; j < 256; j++) total += c[i][j];
    }
    printf("%.17g\n", total);
    printf("%.17g\n", c[0][0]);
    printf("%.17g\n", c[1][2]);
    printf("%.17g\n", c[255][255]);
    return 0;
}
