#include <stddef.h>
#include <stdint.h>

struct Bag;

struct Bag *wordbag_new(void);
void wordbag_add(struct Bag *bag, const uint8_t *p, size_t n);
void wordbag_bump(struct Bag *bag, const uint8_t *p, size_t n, uint64_t k);
void wordbag_seed(struct Bag *bag, const uint8_t *p, size_t n);
uint64_t wordbag_count(const struct Bag *bag, const uint8_t *p, size_t n);
void wordbag_free(struct Bag *bag);
