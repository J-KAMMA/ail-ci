package main

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

var exitCodes = map[string]int{
	"header":    2,
	"syntax":    3,
	"value":     4,
	"reference": 5,
	"duplicate": 6,
	"capacity":  7,
	"summary":   8,
}

func fail(n int, cat string) {
	fmt.Printf("line %d: %s\n", n, cat)
	os.Exit(exitCodes[cat])
}

func isDigits(s string) bool {
	if len(s) == 0 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func digitsN(s string, k int) bool {
	return len(s) == k && isDigits(s)
}

func isUpper(c byte) bool { return c >= 'A' && c <= 'Z' }

func isUpper3(s string) bool {
	return len(s) == 3 && isUpper(s[0]) && isUpper(s[1]) && isUpper(s[2])
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

func dateSyntax(s string) bool {
	return len(s) == 10 && s[4] == '-' && s[7] == '-' &&
		isDigits(s[0:4]) && isDigits(s[5:7]) && isDigits(s[8:10])
}

func timeSyntax(s string) bool {
	return len(s) == 5 && s[2] == ':' && isDigits(s[0:2]) && isDigits(s[3:5])
}

func priceParts(s string) (string, string, bool) {
	p := strings.IndexByte(s, '.')
	if p < 1 || p > 4 {
		return "", "", false
	}
	ip, fp := s[:p], s[p+1:]
	if !isDigits(ip) || len(fp) != 2 || !isDigits(fp) {
		return "", "", false
	}
	return ip, fp, true
}

func validSeat(s string) bool {
	if len(s) < 2 || len(s) > 4 {
		return false
	}
	if !isUpper(s[0]) {
		return false
	}
	return isDigits(s[1:])
}

func validBuyer(s string) bool {
	if len(s) < 4 || len(s) > 12 {
		return false
	}
	if !(s[0] >= 'a' && s[0] <= 'z') {
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

func checksumOK(s string) bool {
	d := func(i int) int64 { return int64(s[i] - '0') }
	return (3*d(0)+d(1)+3*d(2)+d(3)+3*d(4)+d(5))%10 == 0
}

func dateValueOK(s string) bool {
	y, _ := strconv.Atoi(s[0:4])
	m, _ := strconv.Atoi(s[5:7])
	d, _ := strconv.Atoi(s[8:10])
	if y < 2000 || y > 2099 || m < 1 || m > 12 {
		return false
	}
	var dim int
	switch m {
	case 4, 6, 9, 11:
		dim = 30
	case 2:
		if y%4 == 0 {
			dim = 29
		} else {
			dim = 28
		}
	default:
		dim = 31
	}
	return d >= 1 && d <= dim
}

func timeValueOK(s string) bool {
	h, _ := strconv.Atoi(s[0:2])
	m, _ := strconv.Atoi(s[3:5])
	return h <= 23 && m <= 59
}

// noLeadingZero: no leading zero unless the string is exactly "0".
func noLeadingZero(s string) bool {
	return len(s) == 1 || s[0] != '0'
}

func money(c int64) string {
	return fmt.Sprintf("%d.%02d", c/100, c%100)
}

type venue struct {
	capacity int64
}

type event struct {
	venue     string
	price     int64
	sold      map[string]bool
	soldCount int64
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	data, err := io.ReadAll(f)
	f.Close()
	if err != nil {
		os.Exit(1)
	}

	s := string(data)
	var lines []string
	if len(s) > 0 {
		lines = strings.Split(s, "\n")
		if s[len(s)-1] == '\n' {
			lines = lines[:len(lines)-1]
		}
	}
	if len(lines) == 0 || lines[0] != "TKT/1" {
		fail(1, "header")
	}

	venues := map[string]*venue{}
	events := map[string]*event{}
	var revenue, nS, nR, nRecs int64
	ended := false

	for i := 1; i < len(lines); i++ {
		n := i + 1
		if ended {
			fail(n, "summary")
		}
		fl := strings.Split(lines[i], "|")
		want := 0
		switch fl[0] {
		case "V":
			want = 4
		case "E":
			want = 6
		case "S":
			want = 4
		case "R":
			want = 3
		case "END":
			want = 3
		default:
			fail(n, "syntax")
		}
		if len(fl) != want {
			fail(n, "syntax")
		}

		switch fl[0] {
		case "V":
			code, name, capS := fl[1], fl[2], fl[3]
			if !isUpper3(code) || !validName(name) || len(capS) < 1 || len(capS) > 6 || !isDigits(capS) {
				fail(n, "syntax")
			}
			if !noLeadingZero(capS) {
				fail(n, "value")
			}
			capv, _ := strconv.ParseInt(capS, 10, 64)
			if capv < 1 || capv > 100000 {
				fail(n, "value")
			}
			if venues[code] != nil {
				fail(n, "duplicate")
			}
			venues[code] = &venue{capacity: capv}
			nRecs++

		case "E":
			ev, vc, date, tm, price := fl[1], fl[2], fl[3], fl[4], fl[5]
			ip, fp, pok := priceParts(price)
			if !digitsN(ev, 6) || !isUpper3(vc) || !dateSyntax(date) || !timeSyntax(tm) || !pok {
				fail(n, "syntax")
			}
			if !checksumOK(ev) || !dateValueOK(date) || !timeValueOK(tm) {
				fail(n, "value")
			}
			if !noLeadingZero(ip) {
				fail(n, "value")
			}
			iv, _ := strconv.ParseInt(ip, 10, 64)
			fv, _ := strconv.ParseInt(fp, 10, 64)
			cents := iv*100 + fv
			if cents%5 != 0 {
				fail(n, "value")
			}
			if venues[vc] == nil {
				fail(n, "reference")
			}
			if events[ev] != nil {
				fail(n, "duplicate")
			}
			events[ev] = &event{venue: vc, price: cents, sold: map[string]bool{}}
			nRecs++

		case "S":
			ev, seat, buyer := fl[1], fl[2], fl[3]
			if !digitsN(ev, 6) || !validSeat(seat) || !validBuyer(buyer) {
				fail(n, "syntax")
			}
			if !checksumOK(ev) || seat[1] == '0' {
				fail(n, "value")
			}
			e := events[ev]
			if e == nil {
				fail(n, "reference")
			}
			if e.sold[seat] {
				fail(n, "duplicate")
			}
			if e.soldCount >= venues[e.venue].capacity {
				fail(n, "capacity")
			}
			e.sold[seat] = true
			e.soldCount++
			revenue += e.price
			nS++
			nRecs++

		case "R":
			ev, seat := fl[1], fl[2]
			if !digitsN(ev, 6) || !validSeat(seat) {
				fail(n, "syntax")
			}
			if !checksumOK(ev) || seat[1] == '0' {
				fail(n, "value")
			}
			e := events[ev]
			if e == nil || !e.sold[seat] {
				fail(n, "reference")
			}
			delete(e.sold, seat)
			e.soldCount--
			revenue -= e.price
			nR++
			nRecs++

		case "END":
			cnt, cents := fl[1], fl[2]
			if len(cnt) < 1 || len(cnt) > 9 || !isDigits(cnt) ||
				len(cents) < 1 || len(cents) > 12 || !isDigits(cents) {
				fail(n, "syntax")
			}
			if !noLeadingZero(cnt) || !noLeadingZero(cents) {
				fail(n, "value")
			}
			cn, _ := strconv.ParseInt(cnt, 10, 64)
			cv, _ := strconv.ParseInt(cents, 10, 64)
			if cn != nRecs || cv != revenue {
				fail(n, "summary")
			}
			ended = true
		}
	}

	if !ended {
		fail(len(lines)+1, "summary")
	}

	codes := make([]string, 0, len(venues))
	for c := range venues {
		codes = append(codes, c)
	}
	sort.Strings(codes)

	evIDs := make([]string, 0, len(events))
	for id := range events {
		evIDs = append(evIDs, id)
	}
	sort.Strings(evIDs)

	fmt.Printf("venues %d events %d sold %d refunds %d\n", len(venues), len(events), nS, nR)
	fmt.Printf("revenue %s\n", money(revenue))
	for _, c := range codes {
		var ne, tk, rv int64
		for _, id := range evIDs {
			e := events[id]
			if e.venue == c {
				ne++
				tk += e.soldCount
				rv += e.soldCount * e.price
			}
		}
		fmt.Printf("%s events=%d tickets=%d revenue=%s\n", c, ne, tk, money(rv))
	}

	sort.Slice(evIDs, func(a, b int) bool {
		ea, eb := events[evIDs[a]], events[evIDs[b]]
		if ea.soldCount != eb.soldCount {
			return ea.soldCount > eb.soldCount
		}
		return evIDs[a] < evIDs[b]
	})
	for i := 0; i < len(evIDs) && i < 3; i++ {
		fmt.Printf("top %s %d\n", evIDs[i], events[evIDs[i]].soldCount)
	}
	os.Exit(0)
}
