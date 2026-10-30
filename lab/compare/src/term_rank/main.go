package main

import (
	"bufio"
	"bytes"
	"io"
	"os"
	"sort"
	"strconv"
)

var stop = map[string]bool{}

func isWord(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c >= 0x80
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	a := os.Args[1]
	if len(a) == 0 {
		os.Exit(1)
	}
	k := 0
	for i := 0; i < len(a); i++ {
		if a[i] < '0' || a[i] > '9' {
			os.Exit(1)
		}
		k = k*10 + int(a[i]-'0')
		if k > 100000 {
			k = 100000
		}
	}
	if k < 1 || k > 1000 {
		os.Exit(1)
	}
	for _, w := range bytes.Fields([]byte("an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your")) {
		stop[string(w)] = true
	}
	data, _ := io.ReadAll(os.Stdin)
	var lines [][]byte
	if len(data) > 0 {
		lines = bytes.Split(data, []byte("\n"))
		if data[len(data)-1] == '\n' {
			lines = lines[:len(lines)-1]
		}
	}
	docs := []map[string]int{{}}
	for _, ln := range lines {
		if string(ln) == "%%" || string(ln) == "%%\r" {
			docs = append(docs, map[string]int{})
			continue
		}
		cur := docs[len(docs)-1]
		n := len(ln)
		i := 0
		for i < n {
			if !isWord(ln[i]) {
				i++
				continue
			}
			j := i
			for j < n {
				if isWord(ln[j]) {
					j++
				} else if (ln[j] == '\'' || ln[j] == '-') && j+1 < n && isWord(ln[j+1]) {
					j++
				} else {
					break
				}
			}
			tok := make([]byte, 0, j-i)
			for _, c := range ln[i:j] {
				if c == '\'' {
					continue
				}
				if c >= 'A' && c <= 'Z' {
					c += 32
				}
				tok = append(tok, c)
			}
			i = j
			alld := true
			for _, c := range tok {
				if c < '0' || c > '9' {
					alld = false
					break
				}
			}
			if alld {
				tok = []byte("#" + strconv.Itoa(len(tok)))
			}
			if len(tok) < 2 {
				continue
			}
			if stop[string(tok)] {
				continue
			}
			if len(tok) >= 5 && bytes.HasSuffix(tok, []byte("ing")) {
				tok = tok[:len(tok)-3]
			} else if len(tok) >= 4 && tok[len(tok)-1] == 's' && !bytes.HasSuffix(tok, []byte("ss")) {
				tok = tok[:len(tok)-1]
			}
			cur[string(tok)]++
		}
	}
	N := int64(len(docs))
	df := map[string]int64{}
	total := map[string]int64{}
	for _, d := range docs {
		for t, c := range d {
			df[t]++
			total[t] += int64(c)
		}
	}
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	type item struct {
		t string
		s int64
	}
	emit := func(items []item) {
		sort.Slice(items, func(x, y int) bool {
			if items[x].s != items[y].s {
				return items[x].s > items[y].s
			}
			return items[x].t < items[y].t
		})
		if len(items) > k {
			items = items[:k]
		}
		for _, it := range items {
			w.WriteByte(' ')
			w.WriteString(it.t)
			w.WriteByte('=')
			w.WriteString(strconv.FormatInt(it.s, 10))
		}
		w.WriteByte('\n')
	}
	for i, d := range docs {
		items := make([]item, 0, len(d))
		for t, c := range d {
			tf := int64(c)
			items = append(items, item{t, tf * 1000 * (N + 1) / (df[t] * (tf + 2))})
		}
		w.WriteString("doc " + strconv.Itoa(i+1) + ":")
		emit(items)
	}
	items := make([]item, 0, len(total))
	for t, c := range total {
		items = append(items, item{t, c})
	}
	w.WriteString("all:")
	emit(items)
}
