package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
)

type tagStat struct {
	count int64
	total int64
}

type userStat struct {
	name  string
	count int64
}

func trimJSONSpace(b []byte) []byte {
	return bytes.Trim(b, " \t\r\n")
}

func decodeString(raw json.RawMessage) (string, bool) {
	r := trimJSONSpace(raw)
	if len(r) == 0 || r[0] != '"' {
		return "", false
	}
	var s string
	if err := json.Unmarshal(r, &s); err != nil {
		return "", false
	}
	return s, true
}

func decodeInt(raw json.RawMessage) (int64, bool) {
	r := trimJSONSpace(raw)
	if len(r) == 0 {
		return 0, false
	}
	if r[0] != '-' && !(r[0] >= '0' && r[0] <= '9') {
		return 0, false
	}
	v, err := strconv.ParseInt(string(r), 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func parseLine(line []byte) (string, int64, string, bool) {
	t := bytes.TrimLeft(line, " \t\r")
	if len(t) == 0 || t[0] != '{' {
		return "", 0, "", false
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(line, &m); err != nil || m == nil {
		return "", 0, "", false
	}
	userRaw, ok := m["user"]
	if !ok {
		return "", 0, "", false
	}
	user, ok := decodeString(userRaw)
	if !ok {
		return "", 0, "", false
	}
	amtRaw, ok := m["amount"]
	if !ok {
		return "", 0, "", false
	}
	amt, ok := decodeInt(amtRaw)
	if !ok {
		return "", 0, "", false
	}
	tag := ""
	if tr, has := m["tag"]; has {
		tag, ok = decodeString(tr)
		if !ok {
			return "", 0, "", false
		}
	}
	return user, amt, tag, true
}

func main() {
	data, _ := io.ReadAll(bufio.NewReader(os.Stdin))
	lines := bytes.Split(data, []byte("\n"))

	bad := 0
	tags := map[string]*tagStat{}
	users := map[string]int64{}

	for _, line := range lines {
		line = bytes.TrimSuffix(line, []byte("\r"))
		if len(bytes.Trim(line, " \t")) == 0 {
			continue
		}
		user, amt, tag, ok := parseLine(line)
		if !ok {
			bad++
			continue
		}
		ts, exists := tags[tag]
		if !exists {
			ts = &tagStat{}
			tags[tag] = ts
		}
		ts.count++
		ts.total += amt
		users[user]++
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "bad %d tags %d users %d\n", bad, len(tags), len(users))

	tagNames := make([]string, 0, len(tags))
	for k := range tags {
		tagNames = append(tagNames, k)
	}
	sort.Strings(tagNames)
	for _, k := range tagNames {
		ts := tags[k]
		fmt.Fprintf(w, "tag %s count %d total %d\n", k, ts.count, ts.total)
	}

	us := make([]userStat, 0, len(users))
	for k, c := range users {
		us = append(us, userStat{name: k, count: c})
	}
	sort.Slice(us, func(i, j int) bool {
		if us[i].count != us[j].count {
			return us[i].count > us[j].count
		}
		return us[i].name < us[j].name
	})
	limit := len(us)
	if limit > 10 {
		limit = 10
	}
	for i := 0; i < limit; i++ {
		fmt.Fprintf(w, "user %s %d\n", us[i].name, us[i].count)
	}
}
