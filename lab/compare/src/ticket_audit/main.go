package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
)

func fail(n int, cat string, code int) {
	fmt.Printf("line %d: %s\n", n, cat)
	os.Exit(code)
}

func isDigits(s string, lo, hi int) bool {
	if len(s) < lo || len(s) > hi {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func isUpper(c byte) bool { return c >= 'A' && c <= 'Z' }

func synVenue(s string) bool {
	if len(s) != 3 {
		return false
	}
	for i := 0; i < 3; i++ {
		if !isUpper(s[i]) {
			return false
		}
	}
	return true
}

func synName(s string) bool {
	if len(s) < 1 || len(s) > 40 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < 0x20 || s[i] > 0x7e || s[i] == '|' {
			return false
		}
	}
	return s[0] != ' ' && s[len(s)-1] != ' '
}

func synDate(s string) bool {
	return len(s) == 10 && s[4] == '-' && s[7] == '-' && isDigits(s[:4], 4, 4) && isDigits(s[5:7], 2, 2) && isDigits(s[8:], 2, 2)
}

func synTime(s string) bool {
	return len(s) == 5 && s[2] == ':' && isDigits(s[:2], 2, 2) && isDigits(s[3:], 2, 2)
}

func synPrice(s string) bool {
	i := strings.IndexByte(s, '.')
	if i < 0 {
		return false
	}
	return isDigits(s[:i], 1, 4) && isDigits(s[i+1:], 2, 2)
}

func synSeat(s string) bool {
	return len(s) >= 2 && isUpper(s[0]) && isDigits(s[1:], 1, 3)
}

func synBuyer(s string) bool {
	if len(s) < 4 || len(s) > 12 {
		return false
	}
	if s[0] < 'a' || s[0] > 'z' {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
			return false
		}
	}
	return true
}

func num(s string) int {
	n := 0
	for i := 0; i < len(s); i++ {
		n = n*10 + int(s[i]-'0')
	}
	return n
}

func valCap(s string) bool {
	if s[0] == '0' {
		return false
	}
	n := num(s)
	return n >= 1 && n <= 100000
}

func valEvent(s string) bool {
	d := func(i int) int { return int(s[i] - '0') }
	return (3*d(0)+d(1)+3*d(2)+d(3)+3*d(4)+d(5))%10 == 0
}

func valDate(s string) bool {
	y, m, d := num(s[:4]), num(s[5:7]), num(s[8:])
	if y < 2000 || y > 2099 || m < 1 || m > 12 || d < 1 {
		return false
	}
	days := []int{31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}
	if y%4 == 0 {
		days[1] = 29
	}
	return d <= days[m-1]
}

func valTime(s string) bool {
	return num(s[:2]) <= 23 && num(s[3:]) <= 59
}

func priceCents(s string) int {
	i := strings.IndexByte(s, '.')
	return num(s[:i])*100 + num(s[i+1:])
}

func valPrice(s string) bool {
	i := strings.IndexByte(s, '.')
	if i > 1 && s[0] == '0' {
		return false
	}
	return priceCents(s)%5 == 0
}

func valSeat(s string) bool { return s[1] != '0' }

func valCount(s string) bool { return len(s) == 1 || s[0] != '0' }

func money(c int) string { return fmt.Sprintf("%d.%02d", c/100, c%100) }

type event struct {
	venue string
	price int
	seats map[string]bool
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	text := string(data)
	lines := strings.Split(text, "\n")
	if strings.HasSuffix(text, "\n") || text == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 || lines[0] != "TKT/1" {
		fail(1, "header", 2)
	}
	venues := map[string]int{} // capacity
	venueEvents := map[string]int{}
	venueTickets := map[string]int{}
	venueRev := map[string]int{}
	events := map[string]*event{}
	nV, nE, nS, nR := 0, 0, 0, 0
	records := 0
	revenue := 0
	for i := 1; i < len(lines); i++ {
		ln := i + 1
		f := strings.Split(lines[i], "|")
		var syn []func(string) bool
		var val []func(string) bool
		switch f[0] {
		case "V":
			syn = []func(string) bool{synVenue, synName, func(s string) bool { return isDigits(s, 1, 6) }}
			val = []func(string) bool{nil, nil, valCap}
		case "E":
			syn = []func(string) bool{func(s string) bool { return isDigits(s, 6, 6) }, synVenue, synDate, synTime, synPrice}
			val = []func(string) bool{valEvent, nil, valDate, valTime, valPrice}
		case "S":
			syn = []func(string) bool{func(s string) bool { return isDigits(s, 6, 6) }, synSeat, synBuyer}
			val = []func(string) bool{valEvent, valSeat, nil}
		case "R":
			syn = []func(string) bool{func(s string) bool { return isDigits(s, 6, 6) }, synSeat}
			val = []func(string) bool{valEvent, valSeat}
		case "END":
			syn = []func(string) bool{func(s string) bool { return isDigits(s, 1, 9) }, func(s string) bool { return isDigits(s, 1, 12) }}
			val = []func(string) bool{valCount, valCount}
		default:
			fail(ln, "syntax", 3)
		}
		if len(f)-1 != len(syn) {
			fail(ln, "syntax", 3)
		}
		for k := range syn {
			if !syn[k](f[k+1]) {
				fail(ln, "syntax", 3)
			}
		}
		for k := range val {
			if val[k] != nil && !val[k](f[k+1]) {
				fail(ln, "value", 4)
			}
		}
		switch f[0] {
		case "V":
			if _, ok := venues[f[1]]; ok {
				fail(ln, "duplicate", 6)
			}
			venues[f[1]] = num(f[3])
			nV++
		case "E":
			if _, ok := venues[f[2]]; !ok {
				fail(ln, "reference", 5)
			}
			if _, ok := events[f[1]]; ok {
				fail(ln, "duplicate", 6)
			}
			events[f[1]] = &event{f[2], priceCents(f[5]), map[string]bool{}}
			venueEvents[f[2]]++
			nE++
		case "S":
			e, ok := events[f[1]]
			if !ok {
				fail(ln, "reference", 5)
			}
			if e.seats[f[2]] {
				fail(ln, "duplicate", 6)
			}
			if len(e.seats) >= venues[e.venue] {
				fail(ln, "capacity", 7)
			}
			e.seats[f[2]] = true
			revenue += e.price
			venueTickets[e.venue]++
			venueRev[e.venue] += e.price
			nS++
		case "R":
			e, ok := events[f[1]]
			if !ok || !e.seats[f[2]] {
				fail(ln, "reference", 5)
			}
			delete(e.seats, f[2])
			revenue -= e.price
			venueTickets[e.venue]--
			venueRev[e.venue] -= e.price
			nR++
		case "END":
			if num(f[1]) != records || num(f[2]) != revenue {
				fail(ln, "summary", 8)
			}
			if i+1 < len(lines) {
				fail(ln+1, "summary", 8)
			}
			w := bufio.NewWriter(os.Stdout)
			defer w.Flush()
			fmt.Fprintf(w, "venues %d events %d sold %d refunds %d\n", nV, nE, nS, nR)
			fmt.Fprintf(w, "revenue %s\n", money(revenue))
			codes := make([]string, 0, len(venues))
			for c := range venues {
				codes = append(codes, c)
			}
			sort.Strings(codes)
			for _, c := range codes {
				fmt.Fprintf(w, "%s events=%d tickets=%d revenue=%s\n", c, venueEvents[c], venueTickets[c], money(venueRev[c]))
			}
			ids := make([]string, 0, len(events))
			for id := range events {
				ids = append(ids, id)
			}
			sort.Slice(ids, func(a, b int) bool {
				ca, cb := len(events[ids[a]].seats), len(events[ids[b]].seats)
				if ca != cb {
					return ca > cb
				}
				return ids[a] < ids[b]
			})
			if len(ids) > 3 {
				ids = ids[:3]
			}
			for _, id := range ids {
				fmt.Fprintf(w, "top %s %d\n", id, len(events[id].seats))
			}
			return
		}
		records++
	}
	fail(len(lines)+1, "summary", 8)
}
