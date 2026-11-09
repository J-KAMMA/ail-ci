package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
)

type account struct {
	name string
	bal  int64
	open bool
}

type record struct {
	op      byte
	off     int
	id      uint32
	from    uint32
	to      uint32
	amount  uint32
	initial uint32
	name    string
}

func readVar(data []byte, pos *int) (uint32, string) {
	var buf [5]byte
	n := 0
	for i := 0; i < 5; i++ {
		if *pos >= len(data) {
			return 0, "truncated"
		}
		b := data[*pos]
		*pos++
		buf[i] = b
		n = i + 1
		if b&0x80 == 0 {
			break
		}
		if i == 4 {
			return 0, "varint"
		}
	}
	if n >= 2 && buf[n-1] == 0 {
		return 0, "varint"
	}
	var v uint64
	for i := 0; i < n; i++ {
		v |= uint64(buf[i]&0x7f) << (7 * uint(i))
	}
	if v > 4294967295 {
		return 0, "varint"
	}
	return uint32(v), ""
}

func parse(data []byte) ([]record, string, int) {
	if len(data) < 6 {
		return nil, "header", 0
	}
	if data[0] != 0xC7 || data[1] != 0x4C || data[2] != 0x58 || data[3] != 0x46 ||
		data[4] != 0x02 || data[5]&^byte(1) != 0 {
		return nil, "header", 0
	}
	pos := 6
	var recs []record
	for pos < len(data) {
		off := pos
		op := data[pos]
		pos++
		var r record
		r.op = op
		r.off = off
		switch op {
		case 0x01:
			id, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			r.id = id
			if pos >= len(data) {
				return nil, "truncated", off
			}
			nl := data[pos]
			pos++
			if nl < 1 || nl > 32 {
				return nil, "name", off
			}
			nb := make([]byte, 0, nl)
			for i := 0; i < int(nl); i++ {
				if pos >= len(data) {
					return nil, "truncated", off
				}
				b := data[pos]
				pos++
				if b < 0x21 || b > 0x7E {
					return nil, "name", off
				}
				nb = append(nb, b)
			}
			r.name = string(nb)
			ini, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			r.initial = ini
		case 0x02:
			from, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			to, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			amount, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			r.from, r.to, r.amount = from, to, amount
		case 0x03:
			id, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			r.id = id
		case 0x04:
			id, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			amount, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			r.id, r.amount = id, amount
		case 0x05:
			l, k := readVar(data, &pos)
			if k != "" {
				return nil, k, off
			}
			if uint64(len(data)-pos) < uint64(l) {
				return nil, "truncated", off
			}
			pos += int(l)
		default:
			return nil, "opcode", off
		}
		if pos >= len(data) {
			return nil, "truncated", off
		}
		var c int64
		for i := off; i < pos; i++ {
			c = (c*31 + int64(data[i])) % 251
		}
		if byte(c) != data[pos] {
			return nil, "check", off
		}
		pos++
		recs = append(recs, r)
	}
	return recs, "", 0
}

type entry struct {
	id  uint32
	bal int64
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	recs, kind, off := parse(data)
	if kind != "" {
		fmt.Printf("error at offset %d: %s\n", off, kind)
		os.Exit(2)
	}
	strict := data[5]&1 == 1

	accounts := make(map[uint32]*account)
	var cntDup, cntUnknown, cntShut, cntSelf, cntFunds int

	for _, r := range recs {
		reason := ""
		switch r.op {
		case 0x01:
			if _, ok := accounts[r.id]; ok {
				reason = "dup"
			}
		case 0x02:
			a, aok := accounts[r.from]
			b, bok := accounts[r.to]
			if !aok {
				reason = "unknown"
			} else if !bok {
				reason = "unknown"
			} else if !a.open {
				reason = "shut"
			} else if !b.open {
				reason = "shut"
			} else if r.from == r.to {
				reason = "self"
			} else if int64(r.amount) > a.bal {
				reason = "funds"
			}
		case 0x03:
			a, ok := accounts[r.id]
			if !ok {
				reason = "unknown"
			} else if !a.open {
				reason = "shut"
			}
		case 0x04:
			a, ok := accounts[r.id]
			if !ok {
				reason = "unknown"
			} else if !a.open {
				reason = "shut"
			}
		}
		if reason != "" {
			if strict {
				fmt.Printf("rejected at offset %d: %s\n", r.off, reason)
				os.Exit(3)
			}
			switch reason {
			case "dup":
				cntDup++
			case "unknown":
				cntUnknown++
			case "shut":
				cntShut++
			case "self":
				cntSelf++
			case "funds":
				cntFunds++
			}
			continue
		}
		switch r.op {
		case 0x01:
			accounts[r.id] = &account{name: r.name, bal: int64(r.initial), open: true}
		case 0x02:
			accounts[r.from].bal -= int64(r.amount)
			accounts[r.to].bal += int64(r.amount)
		case 0x03:
			accounts[r.id].open = false
		case 0x04:
			accounts[r.id].bal += int64(r.amount)
		}
	}

	var openCount, shutCount int
	var total int64
	var ent []entry
	for id, a := range accounts {
		total += a.bal
		if a.open {
			openCount++
			ent = append(ent, entry{id, a.bal})
		} else {
			shutCount++
		}
	}
	sort.Slice(ent, func(i, j int) bool {
		if ent[i].bal != ent[j].bal {
			return ent[i].bal > ent[j].bal
		}
		return ent[i].id < ent[j].id
	})

	ids := make([]uint32, 0, len(accounts))
	for id := range accounts {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	var g int64
	for _, id := range ids {
		g = (g*1000003 + int64(id)*7 + accounts[id].bal) % 1000000007
	}

	w := bufio.NewWriter(os.Stdout)
	fmt.Fprintf(w, "records: %d\n", len(recs))
	fmt.Fprintf(w, "accounts: %d open, %d shut\n", openCount, shutCount)
	fmt.Fprintf(w, "rejected: dup=%d unknown=%d shut=%d self=%d funds=%d\n",
		cntDup, cntUnknown, cntShut, cntSelf, cntFunds)
	fmt.Fprintf(w, "total: %d\n", total)
	for i := 0; i < len(ent) && i < 5; i++ {
		fmt.Fprintf(w, "top: %d %s %d\n", ent[i].id, accounts[ent[i].id].name, ent[i].bal)
	}
	fmt.Fprintf(w, "digest: %d\n", g)
	w.Flush()
}
