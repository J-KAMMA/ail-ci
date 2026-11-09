package main

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

type venue struct {
	capacity int64
}

type event struct {
	venue     string
	price     int64
	sold      map[string]bool
	soldCount int64
}

var (
	venues    = map[string]*venue{}
	events    = map[string]*event{}
	nS, nR    int64
	nRecords  int64
	revenue   int64
)

func fail(line int, cat string, status int) {
	fmt.Printf("line %d: %s\n", line, cat)
	os.Exit(status)
}

func splitLines(data []byte) []string {
	if len(data) == 0 {
		return nil
	}
	parts := strings.Split(string(data), "\n")
	if parts[len(parts)-1] == "" {
		parts = parts[:len(parts)-1]
	}
	return parts
}

func allDigits(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func digitsLen(s string, lo, hi int) bool {
	return len(s) >= lo && len(s) <= hi && allDigits(s)
}

func num(s string) int {
	n, _ := strconv.Atoi(s)
	return n
}

func validCode(s string) bool {
	if len(s) != 3 {
		return false
	}
	for i := 0; i < 3; i++ {
		if s[i] < 'A' || s[i] > 'Z' {
			return false
		}
	}
	return true
}

func validName(s string) bool {
	if len(s) < 1 || len(s) > 40 {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < 0x20 || c > 0x7E || c == '|' {
			return false
		}
	}
	return s[0] != ' ' && s[len(s)-1] != ' '
}

func isEventSyn(s string) bool {
	return len(s) == 6 && allDigits(s)
}

func eventChecksum(s string) bool {
	d := func(i int) int { return int(s[i] - '0') }
	sum := 3*d(0) + d(1) + 3*d(2) + d(3) + 3*d(4) + d(5)
	return sum%10 == 0
}

func isDateSyn(s string) bool {
	if len(s) != 10 || s[4] != '-' || s[7] != '-' {
		return false
	}
	return allDigits(s[0:4]) && allDigits(s[5:7]) && allDigits(s[8:10])
}

func dateValid(s string) bool {
	y := num(s[0:4])
	m := num(s[5:7])
	d := num(s[8:10])
	if y < 2000 || y > 2099 {
		return false
	}
	if m < 1 || m > 12 {
		return false
	}
	days := []int{31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}[m-1]
	if m == 2 && y%4 == 0 {
		days = 29
	}
	return d >= 1 && d <= days
}

func isTimeSyn(s string) bool {
	if len(s) != 5 || s[2] != ':' {
		return false
	}
	return allDigits(s[0:2]) && allDigits(s[3:5])
}

func timeValid(s string) bool {
	return num(s[0:2]) <= 23 && num(s[3:5]) <= 59
}

func isPriceSyn(s string) bool {
	idx := strings.IndexByte(s, '.')
	if idx < 1 || idx > 4 {
		return false
	}
	if len(s)-idx-1 != 2 {
		return false
	}
	return allDigits(s[:idx]) && allDigits(s[idx+1:])
}

// priceValue returns cents and whether the value rule holds.
func priceValue(s string) (int64, bool) {
	idx := strings.IndexByte(s, '.')
	ip := s[:idx]
	fp := s[idx+1:]
	if len(ip) > 1 && ip[0] == '0' {
		return 0, false
	}
	cents := int64(num(ip))*100 + int64(num(fp))
	if cents%5 != 0 {
		return 0, false
	}
	return cents, true
}

func isSeatSyn(s string) bool {
	if len(s) < 2 || len(s) > 4 {
		return false
	}
	if s[0] < 'A' || s[0] > 'Z' {
		return false
	}
	return digitsLen(s[1:], 1, 3)
}

func isBuyerSyn(s string) bool {
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

func money(c int64) string {
	return fmt.Sprintf("%d.%02d", c/100, c%100)
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}

	lines := splitLines(data)
	if len(lines) == 0 || lines[0] != "TKT/1" {
		fail(1, "header", 2)
	}

	endSeen := false
	for i := 1; i < len(lines); i++ {
		ln := i + 1
		line := lines[i]
		if endSeen {
			fail(ln, "summary", 8)
		}
		f := strings.Split(line, "|")
		typ := f[0]
		switch typ {
		case "V":
			if len(f) != 4 {
				fail(ln, "syntax", 3)
			}
			code, name, capS := f[1], f[2], f[3]
			if !validCode(code) || !validName(name) || !digitsLen(capS, 1, 6) {
				fail(ln, "syntax", 3)
			}
			if capS[0] == '0' || num(capS) > 100000 {
				fail(ln, "value", 4)
			}
			if venues[code] != nil {
				fail(ln, "duplicate", 6)
			}
			venues[code] = &venue{capacity: int64(num(capS))}
			nRecords++

		case "E":
			if len(f) != 6 {
				fail(ln, "syntax", 3)
			}
			evt, vc, date, tm, price := f[1], f[2], f[3], f[4], f[5]
			if !isEventSyn(evt) || !validCode(vc) || !isDateSyn(date) ||
				!isTimeSyn(tm) || !isPriceSyn(price) {
				fail(ln, "syntax", 3)
			}
			pc, pok := priceValue(price)
			if !eventChecksum(evt) || !dateValid(date) || !timeValid(tm) || !pok {
				fail(ln, "value", 4)
			}
			if venues[vc] == nil {
				fail(ln, "reference", 5)
			}
			if events[evt] != nil {
				fail(ln, "duplicate", 6)
			}
			events[evt] = &event{venue: vc, price: pc, sold: map[string]bool{}}
			nRecords++

		case "S":
			if len(f) != 4 {
				fail(ln, "syntax", 3)
			}
			evt, seat, buyer := f[1], f[2], f[3]
			if !isEventSyn(evt) || !isSeatSyn(seat) || !isBuyerSyn(buyer) {
				fail(ln, "syntax", 3)
			}
			if !eventChecksum(evt) || seat[1] == '0' {
				fail(ln, "value", 4)
			}
			ev := events[evt]
			if ev == nil {
				fail(ln, "reference", 5)
			}
			if ev.sold[seat] {
				fail(ln, "duplicate", 6)
			}
			if ev.soldCount >= venues[ev.venue].capacity {
				fail(ln, "capacity", 7)
			}
			ev.sold[seat] = true
			ev.soldCount++
			revenue += ev.price
			nS++
			nRecords++

		case "R":
			if len(f) != 3 {
				fail(ln, "syntax", 3)
			}
			evt, seat := f[1], f[2]
			if !isEventSyn(evt) || !isSeatSyn(seat) {
				fail(ln, "syntax", 3)
			}
			if !eventChecksum(evt) || seat[1] == '0' {
				fail(ln, "value", 4)
			}
			ev := events[evt]
			if ev == nil || !ev.sold[seat] {
				fail(ln, "reference", 5)
			}
			delete(ev.sold, seat)
			ev.soldCount--
			revenue -= ev.price
			nR++
			nRecords++

		case "END":
			if len(f) != 3 {
				fail(ln, "syntax", 3)
			}
			cs, cc := f[1], f[2]
			if !digitsLen(cs, 1, 9) || !digitsLen(cc, 1, 12) {
				fail(ln, "syntax", 3)
			}
			if (len(cs) > 1 && cs[0] == '0') || (len(cc) > 1 && cc[0] == '0') {
				fail(ln, "value", 4)
			}
			count, _ := strconv.ParseInt(cs, 10, 64)
			cents, _ := strconv.ParseInt(cc, 10, 64)
			if count != nRecords || cents != revenue {
				fail(ln, "summary", 8)
			}
			endSeen = true

		default:
			fail(ln, "syntax", 3)
		}
	}

	if !endSeen {
		fail(len(lines)+1, "summary", 8)
	}

	fmt.Printf("venues %d events %d sold %d refunds %d\n", len(venues), len(events), nS, nR)
	fmt.Printf("revenue %s\n", money(revenue))

	type agg struct {
		n, t, rev int64
	}
	aggs := map[string]*agg{}
	codes := make([]string, 0, len(venues))
	for code := range venues {
		aggs[code] = &agg{}
		codes = append(codes, code)
	}
	for _, ev := range events {
		a := aggs[ev.venue]
		a.n++
		a.t += ev.soldCount
		a.rev += ev.price * ev.soldCount
	}
	sort.Strings(codes)
	for _, c := range codes {
		a := aggs[c]
		fmt.Printf("%s events=%d tickets=%d revenue=%s\n", c, a.n, a.t, money(a.rev))
	}

	ids := make([]string, 0, len(events))
	for id := range events {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool {
		a, b := events[ids[i]], events[ids[j]]
		if a.soldCount != b.soldCount {
			return a.soldCount > b.soldCount
		}
		return ids[i] < ids[j]
	})
	k := len(ids)
	if k > 3 {
		k = 3
	}
	for i := 0; i < k; i++ {
		fmt.Printf("top %s %d\n", ids[i], events[ids[i]].soldCount)
	}
	os.Exit(0)
}
