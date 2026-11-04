package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"os"
	"sort"
)

func nameOk(f []byte) bool {
	n := len(f)
	if n < 1 || n > 24 {
		return false
	}
	for _, c := range f {
		if (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
			c == ' ' || c == '.' || c == '_' || c == '-' {
			continue
		}
		return false
	}
	return true
}

func countryOk(f []byte) bool {
	return len(f) == 2 && f[0] >= 'A' && f[0] <= 'Z' && f[1] >= 'A' && f[1] <= 'Z'
}

func number(f []byte, lo, hi int64) (int64, bool) {
	if len(f) == 0 {
		return 0, false
	}
	var v int64
	for _, c := range f {
		if c < '0' || c > '9' {
			return 0, false
		}
		if v <= hi {
			v = v*10 + int64(c-'0')
		}
	}
	if v < lo || v > hi {
		return 0, false
	}
	return v, true
}

func split3(line []byte) ([3][]byte, bool) {
	var f [3][]byte
	nf := 0
	st := 0
	for i := 0; i <= len(line); i++ {
		if i == len(line) || line[i] == '\t' {
			if nf < 3 {
				f[nf] = line[st:i]
			}
			nf++
			st = i + 1
		}
	}
	return f, nf == 3
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	if len(data) == 0 {
		w.WriteString("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
		return
	}
	uidx := make(map[int64]int)
	uid := []int64{}
	uname := []string{}
	uctry := []string{}
	uamt := []int64{}
	unum := []int64{}
	cidx := make(map[string]int)
	cname := []string{}
	camt := []int64{}
	cnum := []int64{}
	var goodUsers, goodOrders, bad, unmatched int64
	sec := 0
	foundUsers := false
	foundOrders := false
	pos := 0
	for pos < len(data) {
		e := bytes.IndexByte(data[pos:], '\n')
		end := len(data)
		if e >= 0 {
			end = pos + e
		}
		line := data[pos:end]
		switch {
		case sec == 0 && bytes.Equal(line, []byte("#users")):
			sec = 1
			foundUsers = true
		case sec == 1 && bytes.Equal(line, []byte("#orders")):
			sec = 2
			foundOrders = true
		case sec == 1:
			ok := false
			if f, three := split3(line); three && len(f[0]) > 0 && len(f[1]) > 0 && len(f[2]) > 0 {
				id, okq := number(f[0], 1, 2000000000)
				if okq && nameOk(f[1]) && countryOk(f[2]) {
					if _, dup := uidx[id]; !dup {
						uidx[id] = len(uid)
						uid = append(uid, id)
						uname = append(uname, string(f[1]))
						uctry = append(uctry, string(f[2]))
						uamt = append(uamt, 0)
						unum = append(unum, 0)
						goodUsers++
						ok = true
					}
				}
			}
			if !ok {
				bad++
			}
		case sec == 2:
			ok := false
			if f, three := split3(line); three && len(f[0]) > 0 && len(f[1]) > 0 && len(f[2]) > 0 {
				_, ok1 := number(f[0], 1, 2000000000)
				id, ok2 := number(f[1], 1, 2000000000)
				amt, ok3 := number(f[2], 0, 100000000)
				if ok1 && ok2 && ok3 {
					goodOrders++
					ui, found := uidx[id]
					if !found {
						unmatched++
					} else {
						uamt[ui] += amt
						unum[ui]++
						cc := uctry[ui]
						ci, have := cidx[cc]
						if !have {
							ci = len(cname)
							cidx[cc] = ci
							cname = append(cname, cc)
							camt = append(camt, 0)
							cnum = append(cnum, 0)
						}
						camt[ci] += amt
						cnum[ci]++
					}
					ok = true
				}
			}
			if !ok {
				bad++
			}
		}
		if end < len(data) {
			pos = end + 1
		} else {
			pos = len(data)
		}
	}
	if !foundUsers || !foundOrders {
		w.WriteString("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n")
		return
	}
	fmt.Fprintf(w, "users %d orders %d bad %d unmatched %d\n", goodUsers, goodOrders, bad, unmatched)
	corder := make([]int, len(cname))
	for i := range corder {
		corder[i] = i
	}
	sort.Slice(corder, func(a, b int) bool {
		x, y := corder[a], corder[b]
		if camt[x] != camt[y] {
			return camt[x] > camt[y]
		}
		return cname[x] < cname[y]
	})
	for _, i := range corder {
		fmt.Fprintf(w, "country %s orders %d amount %d\n", cname[i], cnum[i], camt[i])
	}
	uorder := make([]int, 0, len(uid))
	for i := range uid {
		if unum[i] > 0 {
			uorder = append(uorder, i)
		}
	}
	sort.Slice(uorder, func(a, b int) bool {
		x, y := uorder[a], uorder[b]
		if uamt[x] != uamt[y] {
			return uamt[x] > uamt[y]
		}
		return uid[x] < uid[y]
	})
	m := len(uorder)
	if m > 10 {
		m = 10
	}
	for _, i := range uorder[:m] {
		fmt.Fprintf(w, "user %d %s %d\n", uid[i], uname[i], uamt[i])
	}
	var total int64
	for _, v := range uamt {
		total += v
	}
	fmt.Fprintf(w, "total %d\n", total)
}
