package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
)

type gkey struct {
	r string
	p string
}

func nameOk(f []byte) bool {
	n := len(f)
	if n < 1 || n > 16 {
		return false
	}
	for _, c := range f {
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_') {
			return false
		}
	}
	return true
}

func number(f []byte, allowNeg bool) (int64, bool) {
	i := 0
	neg := false
	if allowNeg && i < len(f) && f[i] == '-' {
		neg = true
		i = 1
	}
	if i >= len(f) {
		return 0, false
	}
	var v int64
	for ; i < len(f); i++ {
		c := f[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		if v <= 10000001 {
			v = v*10 + int64(c-'0')
		}
	}
	if neg {
		v = -v
	}
	return v, true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	if len(data) == 0 {
		w.WriteString("rows 0 bad 0 groups 0\ntotal 0\n")
		return
	}
	groups := make(map[gkey]int)
	greg := []string{}
	gprod := []string{}
	gqty := []int64{}
	grev := []int64{}
	regions := make(map[string]int64)
	var good, bad int64
	pos := 0
	first := true
	for pos < len(data) {
		e := bytes.IndexByte(data[pos:], '\n')
		end := len(data)
		if e >= 0 {
			end = pos + e
		}
		line := data[pos:end]
		if first {
			first = false
		} else {
			var fs [4][]byte
			nf := 0
			st := 0
			for i := 0; i <= len(line); i++ {
				if i == len(line) || line[i] == ',' {
					if nf < 4 {
						fs[nf] = line[st:i]
					}
					nf++
					st = i + 1
				}
			}
			if nf != 4 {
				bad++
			} else {
				reg, prod, qf, pf := fs[0], fs[1], fs[2], fs[3]
				if !nameOk(reg) || !nameOk(prod) || len(qf) == 0 || len(pf) == 0 {
					bad++
				} else {
					q, okq := number(qf, true)
					p, okp := number(pf, false)
					if !okq || !okp || q < -1000 || q > 1000 || p < 0 || p > 10000000 {
						bad++
					} else {
						rev := q * p
						r := string(reg)
						pr := string(prod)
						k := gkey{r, pr}
						gi, found := groups[k]
						if !found {
							gi = len(greg)
							groups[k] = gi
							greg = append(greg, r)
							gprod = append(gprod, pr)
							gqty = append(gqty, 0)
							grev = append(grev, 0)
						}
						gqty[gi] += q
						grev[gi] += rev
						regions[r] += rev
						good++
					}
				}
			}
		}
		if end < len(data) {
			pos = end + 1
		} else {
			pos = len(data)
		}
	}
	fmt.Fprintf(w, "rows %d bad %d groups %d\n", good, bad, len(greg))
	idx := make([]int, len(greg))
	for i := range idx {
		idx[i] = i
	}
	sort.Slice(idx, func(i, j int) bool {
		a, b := idx[i], idx[j]
		if grev[a] != grev[b] {
			return grev[a] > grev[b]
		}
		if greg[a] != greg[b] {
			return greg[a] < greg[b]
		}
		return gprod[a] < gprod[b]
	})
	m := len(idx)
	if m > 10 {
		m = 10
	}
	for _, i := range idx[:m] {
		fmt.Fprintf(w, "%s %s %d %d\n", greg[i], gprod[i], gqty[i], grev[i])
	}
	rn := make([]string, 0, len(regions))
	for r := range regions {
		rn = append(rn, r)
	}
	sort.Strings(rn)
	var total int64
	for _, r := range rn {
		v := regions[r]
		fmt.Fprintf(w, "region %s revenue %d\n", r, v)
		total += v
	}
	fmt.Fprintf(w, "total %d\n", total)
}
