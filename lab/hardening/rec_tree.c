#include <stdio.h>
#include <stdlib.h>

static long long subtree(int node, const int *parent, const long long *weight, int n, int depth) {
    long long total = weight[node] * (depth + 1);
    int i;
    for (i = 0; i < n; i++) {
        if (parent[i] == node) total += subtree(i, parent, weight, n, depth + 1);
    }
    return total;
}

static int maxdepth(int node, const int *parent, int n, int depth) {
    int best = depth, i;
    for (i = 0; i < n; i++) {
        if (parent[i] == node) {
            int d = maxdepth(i, parent, n, depth + 1);
            if (d > best) best = d;
        }
    }
    return best;
}

int main(void) {
    int n = 500, i;
    int *parent = malloc(sizeof(int) * (size_t)n);
    long long *weight = malloc(sizeof(long long) * (size_t)n);
    for (i = 0; i < n; i++) {
        weight[i] = i % 7 + 1;
        parent[i] = i == 0 ? -1 : (i - 1) / 3;
    }
    printf("nodes=%d sum=%lld depth=%d\n", n, subtree(0, parent, weight, n, 0), maxdepth(0, parent, n, 0));
    free(parent);
    free(weight);
    return 0;
}
