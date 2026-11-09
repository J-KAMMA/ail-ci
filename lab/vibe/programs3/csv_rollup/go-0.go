package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
)

type key struct {
	region  string
	product string
}

type group struct {
	region  string
	product string
	qty     int64
	revenue int64
}

func validName(b []byte) bool {
	if len(b) < 1 || len(b) > 16 {
		return false
	}
	for _, c := range b {
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_') {
			return false
		}
	}
	return true
}

func parseQty(b []byte) (int64, bool) {
	if len(b) == 0 {
		return 0, false
	}
	i := 0
	neg := false
	if b[0] == '-' {
		neg = true
		i = 1
		if len(b) == 1 {
			return 0, false
		}
	}
	var v int64
	over := false
	for ; i < len(b); i++ {
		c := b[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		if !over {
			v = v*10 + int64(c-'0')
			if v > 1000 {
				over = true
			}
		}
	}
	if over {
		return 0, false
	}
	if neg {
		v = -v
	}
	return v, true
}

func parsePrice(b []byte) (int64, bool) {
	if len(b) == 0 {
		return 0, false
	}
	var v int64
	over := false
	for _, c := range b {
		if c < '0' || c > '9' {
			return 0, false
		}
		if !over {
			v = v*10 + int64(c-'0')
			if v > 10000000 {
				over = true
			}
		}
	}
	if over {
		return 0, false
	}
	return v, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	if len(data) == 0 {
		fmt.Fprint(out, "rows 0 bad 0 groups 0\n")
		fmt.Fprint(out, "total 0\n")
		return
	}

	// Drop the first line (the header).
	if i := bytes.IndexByte(data, '\n'); i >= 0 {
		data = data[i+1:]
	} else {
		data = nil
	}

	groups := make(map[key]*group)
	regions := make(map[string]int64)
	var good, bad int64

	for len(data) > 0 {
		var line []byte
		if i := bytes.IndexByte(data, '\n'); i >= 0 {
			line = data[:i]
			data = data[i+1:]
		} else {
			line = data
			data = nil
		}

		fields := bytes.Split(line, []byte{','})
		if len(fields) != 4 {
			bad++
			continue
		}
		if !validName(fields[0]) || !validName(fields[1]) {
			bad++
			continue
		}
		qty, ok := parseQty(fields[2])
		if !ok {
			bad++
			continue
		}
		price, ok := parsePrice(fields[3])
		if !ok {
			bad++
			continue
		}

		good++
		k := key{region: string(fields[0]), product: string(fields[1])}
		g := groups[k]
		if g == nil {
			g = &group{region: k.region, product: k.product}
			groups[k] = g
		}
		g.qty += qty
		rev := qty * price
		g.revenue += rev
		regions[k.region] += rev
	}

	fmt.Fprintf(out, "rows %d bad %d groups %d\n", good, bad, len(groups))

	list := make([]*group, 0, len(groups))
	var total int64
	for _, g := range groups {
		list = append(list, g)
		total += g.revenue
	}

	sort.Slice(list, func(i, j int) bool {
		if list[i].revenue != list[j].revenue {
			return list[i].revenue > list[j].revenue
		}
		if list[i].region != list[j].region {
			return list[i].region < list[j].region
		}
		return list[i].product < list[j].product
	})

	n := len(list)
	if n > 10 {
		n = 10
	}
	for i := 0; i < n; i++ {
		g := list[i]
		fmt.Fprintf(out, "%s %s %d %d\n", g.region, g.product, g.qty, g.revenue)
	}

	names := make([]string, 0, len(regions))
	for r := range regions {
		names = append(names, r)
	}
	sort.Strings(names)
	for _, r := range names {
		fmt.Fprintf(out, "region %s revenue %d\n", r, regions[r])
	}

	fmt.Fprintf(out, "total %d\n", total)
}
