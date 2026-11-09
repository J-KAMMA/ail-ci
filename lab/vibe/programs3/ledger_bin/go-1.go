package main

import (
	"fmt"
	"os"
	"sort"
)

type parseError struct {
	offset int
	kind   string
}

type record struct {
	op     byte
	id     uint32
	from   uint32
	to     uint32
	amount uint32
	name   string
	start  int
}

func parseVar(data []byte, pos *int, start int) (uint32, *parseError) {
	var value uint64
	var shift uint
	n := 0
	var last byte
	for {
		if *pos >= len(data) {
			return 0, &parseError{start, "truncated"}
		}
		last = data[*pos]
		*pos = *pos + 1
		n++
		if n == 5 && last&0x80 != 0 {
			return 0, &parseError{start, "varint"}
		}
		value |= uint64(last&0x7F) << shift
		shift += 7
		if last&0x80 == 0 {
			break
		}
	}
	if n >= 2 && last == 0 {
		return 0, &parseError{start, "varint"}
	}
	if value > 4294967295 {
		return 0, &parseError{start, "varint"}
	}
	return uint32(value), nil
}

func parse(data []byte) ([]record, bool, *parseError) {
	if len(data) < 6 || data[0] != 0xC7 || data[1] != 'L' || data[2] != 'X' || data[3] != 'F' || data[4] != 0x02 || data[5]&0xFE != 0 {
		return nil, false, &parseError{offset: 0, kind: "header"}
	}
	strict := data[5]&0x01 == 1
	pos := 6
	recs := []record{}
	for pos < len(data) {
		start := pos
		op := data[pos]
		pos++
		if op < 0x01 || op > 0x05 {
			return nil, strict, &parseError{start, "opcode"}
		}
		r := record{op: op, start: start}
		switch op {
		case 0x01:
			id, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			if pos >= len(data) {
				return nil, strict, &parseError{start, "truncated"}
			}
			nl := data[pos]
			pos++
			if nl < 1 || nl > 32 {
				return nil, strict, &parseError{start, "name"}
			}
			nb := make([]byte, int(nl))
			for i := 0; i < int(nl); i++ {
				if pos >= len(data) {
					return nil, strict, &parseError{start, "truncated"}
				}
				c := data[pos]
				pos++
				if c < 0x21 || c > 0x7E {
					return nil, strict, &parseError{start, "name"}
				}
				nb[i] = c
			}
			init, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			r.id = id
			r.name = string(nb)
			r.amount = init
		case 0x02:
			f, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			t, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			a, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			r.from, r.to, r.amount = f, t, a
		case 0x03:
			id, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			r.id = id
		case 0x04:
			id, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			a, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			r.id, r.amount = id, a
		case 0x05:
			l, e := parseVar(data, &pos, start)
			if e != nil {
				return nil, strict, e
			}
			if uint64(l) > uint64(len(data)-pos) {
				return nil, strict, &parseError{start, "truncated"}
			}
			pos += int(l)
		}
		if pos >= len(data) {
			return nil, strict, &parseError{start, "truncated"}
		}
		ck := data[pos]
		pos++
		c := 0
		for i := start; i < pos-1; i++ {
			c = (c*31 + int(data[i])) % 251
		}
		if int(ck) != c {
			return nil, strict, &parseError{start, "check"}
		}
		recs = append(recs, r)
	}
	return recs, strict, nil
}

type account struct {
	name    string
	balance int64
	shut    bool
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	recs, strict, perr := parse(data)
	if perr != nil {
		fmt.Printf("error at offset %d: %s\n", perr.offset, perr.kind)
		os.Exit(2)
	}

	accounts := make(map[uint32]*account)
	dup, unk, shr, slf, fnd := 0, 0, 0, 0, 0

	reject := func(r record, reason string) {
		switch reason {
		case "dup":
			dup++
		case "unknown":
			unk++
		case "shut":
			shr++
		case "self":
			slf++
		case "funds":
			fnd++
		}
		if strict {
			fmt.Printf("rejected at offset %d: %s\n", r.start, reason)
			os.Exit(3)
		}
	}

	for _, r := range recs {
		switch r.op {
		case 0x01:
			if _, ok := accounts[r.id]; ok {
				reject(r, "dup")
				continue
			}
			accounts[r.id] = &account{name: r.name, balance: int64(r.amount)}
		case 0x02:
			f, ok := accounts[r.from]
			if !ok {
				reject(r, "unknown")
				continue
			}
			t, ok := accounts[r.to]
			if !ok {
				reject(r, "unknown")
				continue
			}
			if f.shut {
				reject(r, "shut")
				continue
			}
			if t.shut {
				reject(r, "shut")
				continue
			}
			if r.from == r.to {
				reject(r, "self")
				continue
			}
			if int64(r.amount) > f.balance {
				reject(r, "funds")
				continue
			}
			f.balance -= int64(r.amount)
			t.balance += int64(r.amount)
		case 0x03:
			a, ok := accounts[r.id]
			if !ok {
				reject(r, "unknown")
				continue
			}
			if a.shut {
				reject(r, "shut")
				continue
			}
			a.shut = true
		case 0x04:
			a, ok := accounts[r.id]
			if !ok {
				reject(r, "unknown")
				continue
			}
			if a.shut {
				reject(r, "shut")
				continue
			}
			a.balance += int64(r.amount)
		case 0x05:
		}
	}

	ids := make([]uint32, 0, len(accounts))
	for id := range accounts {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })

	var openCount, shutCount int
	var total int64
	for _, id := range ids {
		a := accounts[id]
		if a.shut {
			shutCount++
		} else {
			openCount++
		}
		total += a.balance
	}

	type topEntry struct {
		id      uint32
		name    string
		balance int64
	}
	top := []topEntry{}
	for _, id := range ids {
		a := accounts[id]
		if !a.shut {
			top = append(top, topEntry{id, a.name, a.balance})
		}
	}
	sort.Slice(top, func(i, j int) bool {
		if top[i].balance != top[j].balance {
			return top[i].balance > top[j].balance
		}
		return top[i].id < top[j].id
	})
	if len(top) > 5 {
		top = top[:5]
	}

	var g int64
	for _, id := range ids {
		a := accounts[id]
		g = (g*1000003 + int64(id)*7 + a.balance) % 1000000007
	}

	fmt.Printf("records: %d\n", len(recs))
	fmt.Printf("accounts: %d open, %d shut\n", openCount, shutCount)
	fmt.Printf("rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n", dup, unk, shr, slf, fnd)
	fmt.Printf("total: %d\n", total)
	for _, t := range top {
		fmt.Printf("top: %d %s %d\n", t.id, t.name, t.balance)
	}
	fmt.Printf("digest: %d\n", g)
}
