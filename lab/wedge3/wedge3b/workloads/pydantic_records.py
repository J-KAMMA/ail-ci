"""Validate a large batch of nested records with pydantic (v1 pure Python or v2 Rust core).

The output is deliberately library-version independent: only field values are aggregated, never
the representation of a model, and money is summed in integer cents.  Run this file with either
`pydantic<2` (pure Python) or `pydantic>=2` (pydantic-core); stdout is byte identical.
"""
from typing import Optional

from pydantic import BaseModel

N_ORDERS = 20000
N_LINES = 6
CITIES = ('Amsterdam', 'Berlin', 'Lisbon', 'Oslo', 'Prague', 'Rome')


class Address(BaseModel):
    street: str
    city: str
    zipcode: int


class Line(BaseModel):
    sku: str
    qty: int
    price: float


class Order(BaseModel):
    id: int
    customer: str
    address: Address
    lines: list[Line]
    note: Optional[str] = None


def source_data():
    for i in range(N_ORDERS):
        lines = []
        for j in range(N_LINES):
            lines.append({
                'sku': 'SKU-%04d-%02d' % (i % 997, j),
                'qty': (i + j) % 9 + 1,
                'price': ((i * 37 + j * 101) % 5000) / 100.0,
            })
        yield {
            'id': i,
            'customer': 'customer-%d' % (i % 500),
            'address': {
                'street': '%d Main Street' % (i % 300),
                'city': CITIES[i % len(CITIES)],
                'zipcode': 10000 + (i % 900),
            },
            'lines': lines,
            'note': None if i % 7 else 'note-%d' % i,
        }


def main():
    cents = 0
    qty_total = 0
    per_city = {city: 0 for city in CITIES}
    max_line = 0
    note_count = 0
    sku_hash = 1469598103934665603
    for raw in source_data():
        order = Order(**raw)
        local = 0
        for line in order.lines:
            value = int(round(line.qty * line.price * 100))
            local += value
            qty_total += line.qty
            if value > max_line:
                max_line = value
            for ch in line.sku:
                sku_hash = ((sku_hash ^ ord(ch)) * 1099511628211) & ((1 << 64) - 1)
        cents += local
        per_city[order.address.city] += local
        if order.note is not None:
            note_count += 1
        cents += order.address.zipcode % 10
    print('orders', N_ORDERS)
    print('lines', N_ORDERS * N_LINES)
    print('cents', cents)
    print('qty', qty_total)
    print('max_line', max_line)
    print('notes', note_count)
    print('sku_hash', sku_hash)
    for city in CITIES:
        print('city', city, per_city[city])


if __name__ == '__main__':
    main()
