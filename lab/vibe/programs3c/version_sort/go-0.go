package main

import (
	"fmt"
	"io"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

var versionRe = regexp.MustCompile(`^([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$`)

type ident struct {
	numeric bool
	num     int64
	s       string
}

type version struct {
	major, minor, patch int64
	pre                 []ident
	line                string
}

func allDigits(s string) bool {
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
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func parseVersion(line string) (version, bool) {
	m := versionRe.FindStringSubmatch(line)
	if m == nil {
		return version{}, false
	}
	var v version
	var ok bool
	if v.major, ok = parseNum(m[1]); !ok {
		return version{}, false
	}
	if v.minor, ok = parseNum(m[2]); !ok {
		return version{}, false
	}
	if v.patch, ok = parseNum(m[3]); !ok {
		return version{}, false
	}
	v.line = line
	if m[4] != "" {
		for _, p := range strings.Split(m[4], ".") {
			if allDigits(p) {
				n, ok := parseNum(p)
				if !ok {
					return version{}, false
				}
				v.pre = append(v.pre, ident{numeric: true, num: n, s: p})
			} else {
				v.pre = append(v.pre, ident{numeric: false, s: p})
			}
		}
	}
	if m[5] != "" {
		for _, p := range strings.Split(m[5], ".") {
			if allDigits(p) {
				if _, ok := parseNum(p); !ok {
					return version{}, false
				}
			}
		}
	}
	return v, true
}

func cmpInt(a, b int64) int {
	if a < b {
		return -1
	}
	if a > b {
		return 1
	}
	return 0
}

func cmpIdent(x, y ident) int {
	switch {
	case x.numeric && y.numeric:
		return cmpInt(x.num, y.num)
	case x.numeric:
		return -1
	case y.numeric:
		return 1
	default:
		return strings.Compare(x.s, y.s)
	}
}

func cmpVersion(a, b version) int {
	if c := cmpInt(a.major, b.major); c != 0 {
		return c
	}
	if c := cmpInt(a.minor, b.minor); c != 0 {
		return c
	}
	if c := cmpInt(a.patch, b.patch); c != 0 {
		return c
	}
	ap, bp := len(a.pre) == 0, len(b.pre) == 0
	switch {
	case ap && bp:
		return 0
	case ap:
		return 1
	case bp:
		return -1
	}
	n := len(a.pre)
	if len(b.pre) < n {
		n = len(b.pre)
	}
	for i := 0; i < n; i++ {
		if c := cmpIdent(a.pre[i], b.pre[i]); c != 0 {
			return c
		}
	}
	return cmpInt(int64(len(a.pre)), int64(len(b.pre)))
}

func isBlank(s string) bool {
	return strings.Trim(s, " \t") == ""
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	var vs []version
	bad := 0
	for _, l := range lines {
		l = strings.TrimSuffix(l, "\r")
		if isBlank(l) {
			continue
		}
		v, ok := parseVersion(l)
		if !ok {
			bad++
			continue
		}
		vs = append(vs, v)
	}

	sort.Slice(vs, func(i, j int) bool {
		c := cmpVersion(vs[i], vs[j])
		if c != 0 {
			return c < 0
		}
		return vs[i].line < vs[j].line
	})

	var sb strings.Builder
	fmt.Fprintf(&sb, "bad %d sorted %d\n", bad, len(vs))
	for _, v := range vs {
		sb.WriteString(v.line)
		sb.WriteString("\n")
	}
	os.Stdout.WriteString(sb.String())
}
