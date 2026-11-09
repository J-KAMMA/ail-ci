package main

import (
	"bufio"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

type ident struct {
	num bool
	n   int64
	s   string
}

type version struct {
	line   string
	maj    int64
	min    int64
	pat    int64
	hasPre bool
	pre    []ident
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func parseNum(s string) (int64, bool) {
	if !isDigits(s) {
		return 0, false
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func validIdentChar(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-'
}

// parseIdents validates a dot-separated identifier list and returns the parsed identifiers.
func parseIdents(s string) ([]ident, bool) {
	parts := strings.Split(s, ".")
	res := make([]ident, 0, len(parts))
	for _, p := range parts {
		if p == "" {
			return nil, false
		}
		for i := 0; i < len(p); i++ {
			if !validIdentChar(p[i]) {
				return nil, false
			}
		}
		if isDigits(p) {
			v, ok := parseNum(p)
			if !ok {
				return nil, false
			}
			res = append(res, ident{num: true, n: v})
		} else {
			res = append(res, ident{num: false, s: p})
		}
	}
	return res, true
}

func parseVersion(line string) (version, bool) {
	var v version
	v.line = line
	main := line
	if i := strings.IndexByte(line, '+'); i >= 0 {
		main = line[:i]
		build := line[i+1:]
		if _, ok := parseIdents(build); !ok {
			return v, false
		}
	}
	core := main
	if i := strings.IndexByte(main, '-'); i >= 0 {
		core = main[:i]
		pre := main[i+1:]
		ids, ok := parseIdents(pre)
		if !ok {
			return v, false
		}
		v.hasPre = true
		v.pre = ids
	}
	parts := strings.Split(core, ".")
	if len(parts) != 3 {
		return v, false
	}
	var ok bool
	if v.maj, ok = parseNum(parts[0]); !ok {
		return v, false
	}
	if v.min, ok = parseNum(parts[1]); !ok {
		return v, false
	}
	if v.pat, ok = parseNum(parts[2]); !ok {
		return v, false
	}
	return v, true
}

func cmpPre(a, b []ident) int {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		x, y := a[i], b[i]
		var c int
		switch {
		case x.num && y.num:
			if x.n < y.n {
				c = -1
			} else if x.n > y.n {
				c = 1
			}
		case x.num:
			c = -1
		case y.num:
			c = 1
		default:
			c = strings.Compare(x.s, y.s)
		}
		if c != 0 {
			return c
		}
	}
	switch {
	case len(a) < len(b):
		return -1
	case len(a) > len(b):
		return 1
	}
	return 0
}

func cmpVersion(a, b version) int {
	if a.maj != b.maj {
		if a.maj < b.maj {
			return -1
		}
		return 1
	}
	if a.min != b.min {
		if a.min < b.min {
			return -1
		}
		return 1
	}
	if a.pat != b.pat {
		if a.pat < b.pat {
			return -1
		}
		return 1
	}
	switch {
	case !a.hasPre && !b.hasPre:
		return 0
	case !a.hasPre:
		return 1
	case !b.hasPre:
		return -1
	}
	return cmpPre(a.pre, b.pre)
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	var versions []version
	bad := 0
	for _, raw := range lines {
		line := raw
		if strings.HasSuffix(line, "\r") {
			line = line[:len(line)-1]
		}
		if line == "" {
			continue
		}
		v, ok := parseVersion(line)
		if !ok {
			bad++
			continue
		}
		versions = append(versions, v)
	}

	sort.SliceStable(versions, func(i, j int) bool {
		c := cmpVersion(versions[i], versions[j])
		if c != 0 {
			return c < 0
		}
		return versions[i].line < versions[j].line
	})

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	w.WriteString("bad " + strconv.Itoa(bad) + " sorted " + strconv.Itoa(len(versions)) + "\n")
	for _, v := range versions {
		w.WriteString(v.line)
		w.WriteString("\n")
	}
}
