package main

import (
	"fmt"
	"os"
	"sort"
)

var data []byte
var pos int

func fail(off int, kind string) {
	fmt.Printf("error at offset %d: %s\n", off, kind)
	os.Exit(2)
}

func readVar(start int) uint64 {
	var val uint64
	n := 0
	for {
		if pos >= len(data) {
			fail(start, "truncated")
		}
		b := data[pos]
		pos++
		n++
		val |= uint64(b&0x7f) << (7 * uint(n-1))
		if b&0x80 == 0 {
			if n >= 2 && b == 0 {
				fail(start, "varint")
			}
			break
		}
		if n == 5 {
			fail(start, "varint")
		}
	}
	if val > 4294967295 {
		fail(start, "varint")
	}
	return val
}

type rec struct {
	off    int
	op     byte
	id     uint64
	from   uint64
	to     uint64
	amount uint64
	name   string
}

type acct struct {
	id   uint64
	name string
	bal  int64
	open bool
}

const MOD = 1000000007

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	b, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	data = b

	if len(data) < 6 || data[0] != 0xC7 || data[1] != 'L' || data[2] != 'X' || data[3] != 'F' || data[4] != 2 || data[5]&^1 != 0 {
		fail(0, "header")
	}
	strict := data[5]&1 == 1

	pos = 6
	recs := []rec{}
	for pos < len(data) {
		start := pos
		op := data[pos]
		pos++
		r := rec{off: start, op: op}
		switch op {
		case 1:
			r.id = readVar(start)
			if pos >= len(data) {
				fail(start, "truncated")
			}
			nl := data[pos]
			pos++
			if nl < 1 || nl > 32 {
				fail(start, "name")
			}
			name := make([]byte, 0, nl)
			for i := 0; i < int(nl); i++ {
				if pos >= len(data) {
					fail(start, "truncated")
				}
				c := data[pos]
				pos++
				if c < 0x21 || c > 0x7e {
					fail(start, "name")
				}
				name = append(name, c)
			}
			r.name = string(name)
			r.amount = readVar(start)
		case 2:
			r.from = readVar(start)
			r.to = readVar(start)
			r.amount = readVar(start)
		case 3:
			r.id = readVar(start)
		case 4:
			r.id = readVar(start)
			r.amount = readVar(start)
		case 5:
			l := readVar(start)
			if uint64(len(data)-pos) < l {
				fail(start, "truncated")
			}
			pos += int(l)
		default:
			fail(start, "opcode")
		}
		if pos >= len(data) {
			fail(start, "truncated")
		}
		var c int = 0
		for i := start; i < pos; i++ {
			c = (c*31 + int(data[i])) % 251
		}
		if int(data[pos]) != c {
			fail(start, "check")
		}
		pos++
		recs = append(recs, r)
	}

	accts := map[uint64]*acct{}
	counts := map[string]int{}
	for _, r := range recs {
		reason := ""
		switch r.op {
		case 1:
			if _, ok := accts[r.id]; ok {
				reason = "dup"
			} else {
				accts[r.id] = &acct{id: r.id, name: r.name, bal: int64(r.amount), open: true}
			}
		case 2:
			from, fok := accts[r.from]
			to, tok := accts[r.to]
			if !fok || !tok {
				reason = "unknown"
			} else if !from.open || !to.open {
				reason = "shut"
			} else if r.from == r.to {
				reason = "self"
			} else if int64(r.amount) > from.bal {
				reason = "funds"
			} else {
				from.bal -= int64(r.amount)
				to.bal += int64(r.amount)
			}
		case 3:
			a, ok := accts[r.id]
			if !ok {
				reason = "unknown"
			} else if !a.open {
				reason = "shut"
			} else {
				a.open = false
			}
		case 4:
			a, ok := accts[r.id]
			if !ok {
				reason = "unknown"
			} else if !a.open {
				reason = "shut"
			} else {
				a.bal += int64(r.amount)
			}
		}
		if reason != "" {
			if strict {
				fmt.Printf("rejected at offset %d: %s\n", r.off, reason)
				os.Exit(3)
			}
			counts[reason]++
		}
	}

	all := make([]*acct, 0, len(accts))
	for _, a := range accts {
		all = append(all, a)
	}
	sort.Slice(all, func(i, j int) bool { return all[i].id < all[j].id })

	openN, shutN := 0, 0
	var total int64 = 0
	open := []*acct{}
	for _, a := range all {
		total += a.bal
		if a.open {
			openN++
			open = append(open, a)
		} else {
			shutN++
		}
	}
	sort.Slice(open, func(i, j int) bool {
		if open[i].bal != open[j].bal {
			return open[i].bal > open[j].bal
		}
		return open[i].id < open[j].id
	})

	var g int64 = 0
	for _, a := range all {
		g = (g*1000003 + (int64(a.id)*7)%MOD + a.bal%MOD) % MOD
	}

	fmt.Printf("records: %d\n", len(recs))
	fmt.Printf("accounts: %d open, %d shut\n", openN, shutN)
	fmt.Printf("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n",
		counts["dup"], counts["unknown"], counts["shut"], counts["self"], counts["funds"])
	fmt.Printf("total: %d\n", total)
	for i := 0; i < len(open) && i < 5; i++ {
		a := open[i]
		fmt.Printf("top: %d %s %d\n", a.id, a.name, a.bal)
	}
	fmt.Printf("digest: %d\n", g)
}
