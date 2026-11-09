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
	for _, w := range strings.Fields("an and are as at be but by for from had has have he her his in into is it its not of on or our she so than that the their them then there these they this to was we were which will with you your") {
		stopWords[w] = true
	}
}

func isWord(b byte) bool {
	return (b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') || (b >= '0' && b <= '9') || b >= 0x80
}

func isJoiner(b byte) bool {
	return b == '\'' || b == '-'
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
	s := string(buf)
	if stopWords[s] {
		return "", false
	}
	if len(s) >= 5 && strings.HasSuffix(s, "ing") {
		s = s[:len(s)-3]
	} else if len(s) >= 4 && strings.HasSuffix(s, "s") && !strings.HasSuffix(s, "ss") {
		s = s[:len(s)-1]
	}
	return s, true
}

type item struct {
	term string
	val  int64
}

func sortItems(items []item) {
	sort.Slice(items, func(a, b int) bool {
		if items[a].val != items[b].val {
			return items[a].val > items[b].val
		}
		return items[a].term < items[b].term
	})
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	s := os.Args[1]
	if len(s) == 0 {
		os.Exit(1)
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			os.Exit(1)
		}
	}
	t := strings.TrimLeft(s, "0")
	if t == "" || len(t) > 4 {
		os.Exit(1)
	}
	k, err := strconv.Atoi(t)
	if err != nil || k < 1 || k > 1000 {
		os.Exit(1)
	}

	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}

	var lines [][]byte
	if len(data) > 0 {
		lines = bytes.Split(data, []byte("\n"))
		if len(lines[len(lines)-1]) == 0 {
			lines = lines[:len(lines)-1]
		}
	}

	var docs [][][]byte
	var cur [][]byte
	for _, line := range lines {
		if string(line) == "%%" || string(line) == "%%\r" {
			docs = append(docs, cur)
			cur = nil
		} else {
			cur = append(cur, line)
		}
	}
	docs = append(docs, cur)
	N := int64(len(docs))

	tfs := make([]map[string]int64, len(docs))
	df := map[string]int64{}
	total := map[string]int64{}

	for d, doc := range docs {
		tf := map[string]int64{}
		for _, line := range doc {
			n := len(line)
			i := 0
			for i < n {
				if !isWord(line[i]) {
					i++
					continue
				}
				j := i + 1
				for j < n {
					if isWord(line[j]) {
						j++
					} else if isJoiner(line[j]) && j+1 < n && isWord(line[j+1]) {
						j++
					} else {
						break
					}
				}
				if term, ok := normalize(line[i:j]); ok {
					tf[term]++
				}
				i = j
			}
		}
		tfs[d] = tf
		for t, c := range tf {
			df[t]++
			total[t] += c
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	for d := range docs {
		tf := tfs[d]
		items := make([]item, 0, len(tf))
		for t, c := range tf {
			val := c * 1000 * (N + 1) / (df[t] * (c + 2))
			items = append(items, item{t, val})
		}
		sortItems(items)
		if len(items) > k {
			items = items[:k]
		}
		w.WriteString("doc " + strconv.Itoa(d+1) + ":")
		for _, it := range items {
			w.WriteString(" " + it.term + "=" + strconv.FormatInt(it.val, 10))
		}
		w.WriteString("\n")
	}

	items := make([]item, 0, len(total))
	for t, c := range total {
		items = append(items, item{t, c})
	}
	sortItems(items)
	if len(items) > k {
		items = items[:k]
	}
	w.WriteString("all:")
	for _, it := range items {
		w.WriteString(" " + it.term + "=" + strconv.FormatInt(it.val, 10))
	}
	w.WriteString("\n")
}
