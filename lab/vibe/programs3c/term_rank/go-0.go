package main

import (
	"bufio"
	"bytes"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

var stopWords = map[string]bool{}

func init() {
	list := "an and are as at be but by for from had has have he her his in into is it its not of on or " +
		"our she so than that the their them then there these they this to was we were which will with " +
		"you your"
	for _, w := range strings.Fields(list) {
		stopWords[w] = true
	}
}

func isWord(b byte) bool {
	return (b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') || (b >= '0' && b <= '9') || b >= 0x80
}

func normalize(tok []byte) (string, bool) {
	buf := make([]byte, 0, len(tok))
	for _, b := range tok {
		if b == '\'' {
			continue
		}
		if b >= 'A' && b <= 'Z' {
			b += 32
		}
		buf = append(buf, b)
	}
	allDigits := len(buf) > 0
	for _, b := range buf {
		if b < '0' || b > '9' {
			allDigits = false
			break
		}
	}
	if allDigits {
		buf = []byte("#" + strconv.Itoa(len(buf)))
	}
	if len(buf) < 2 {
		return "", false
	}
	if stopWords[string(buf)] {
		return "", false
	}
	n := len(buf)
	if n >= 5 && string(buf[n-3:]) == "ing" {
		buf = buf[:n-3]
	} else if n >= 4 && buf[n-1] == 's' && buf[n-2] != 's' {
		buf = buf[:n-1]
	}
	return string(buf), true
}

func termsOfLine(line []byte, fn func(string)) {
	n := len(line)
	i := 0
	for i < n {
		if !isWord(line[i]) {
			i++
			continue
		}
		j := i + 1
		for j < n {
			c := line[j]
			if isWord(c) {
				j++
				continue
			}
			if (c == '\'' || c == '-') && j+1 < n && isWord(line[j+1]) {
				j++
				continue
			}
			break
		}
		if t, ok := normalize(line[i:j]); ok {
			fn(t)
		}
		i = j
	}
}

func parseK(s string) (int, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	t := strings.TrimLeft(s, "0")
	if len(t) == 0 || len(t) > 4 {
		return 0, false
	}
	v, err := strconv.Atoi(t)
	if err != nil || v < 1 || v > 1000 {
		return 0, false
	}
	return v, true
}

type item struct {
	t string
	s int64
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	k, ok := parseK(os.Args[1])
	if !ok {
		os.Exit(1)
	}

	data, _ := io.ReadAll(os.Stdin)

	var lines [][]byte
	if len(data) > 0 {
		parts := bytes.Split(data, []byte("\n"))
		if len(parts) > 0 && len(parts[len(parts)-1]) == 0 {
			parts = parts[:len(parts)-1]
		}
		lines = parts
	}

	docs := [][][]byte{{}}
	for _, line := range lines {
		s := string(line)
		if s == "%%" || s == "%%\r" {
			docs = append(docs, [][]byte{})
		} else {
			last := len(docs) - 1
			docs[last] = append(docs[last], line)
		}
	}

	N := len(docs)
	docTF := make([]map[string]int64, N)
	total := map[string]int64{}
	df := map[string]int64{}

	for d, dl := range docs {
		m := map[string]int64{}
		for _, line := range dl {
			termsOfLine(line, func(t string) {
				m[t]++
			})
		}
		docTF[d] = m
		for t, c := range m {
			df[t]++
			total[t] += c
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	less := func(items []item) func(i, j int) bool {
		return func(i, j int) bool {
			if items[i].s != items[j].s {
				return items[i].s > items[j].s
			}
			return items[i].t < items[j].t
		}
	}

	for d := 0; d < N; d++ {
		m := docTF[d]
		items := make([]item, 0, len(m))
		for t, tf := range m {
			num := tf * 1000 * int64(N+1)
			den := df[t] * (tf + 2)
			items = append(items, item{t, num / den})
		}
		sort.Slice(items, less(items))
		if len(items) > k {
			items = items[:k]
		}
		w.WriteString("doc ")
		w.WriteString(strconv.Itoa(d + 1))
		w.WriteString(":")
		for _, it := range items {
			w.WriteString(" ")
			w.WriteString(it.t)
			w.WriteString("=")
			w.WriteString(strconv.FormatInt(it.s, 10))
		}
		w.WriteString("\n")
	}

	all := make([]item, 0, len(total))
	for t, c := range total {
		all = append(all, item{t, c})
	}
	sort.Slice(all, less(all))
	if len(all) > k {
		all = all[:k]
	}
	w.WriteString("all:")
	for _, it := range all {
		w.WriteString(" ")
		w.WriteString(it.t)
		w.WriteString("=")
		w.WriteString(strconv.FormatInt(it.s, 10))
	}
	w.WriteString("\n")
}
