package main

import (
	"bytes"
	"context"
	"fmt"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/dop251/goja"
	"github.com/dop251/goja_nodejs/eventloop"
	"github.com/imroc/req/v3"
	"golang.org/x/net/html"
)

var (
	cveIDRegexp  = regexp.MustCompile(`^CVE-\d+-\d+$`)
	scriptRegexp = regexp.MustCompile(`(?m)<script>(.*?)</script>`)
)

type contextKey string

var contextLoopDetect = contextKey("loop_detect")

type AVDCrawler struct {
	client *req.Client
}

func NewAVDCrawler() Grabber {
	crawler := &AVDCrawler{}
	crawler.client = newHTTPClient().OnBeforeRequest(func(client *req.Client, req *req.Request) error {
		ctx := req.Context()
		if ctx == nil {
			ctx = context.Background()
		}
		if ctx.Value(contextLoopDetect) != nil {
			return nil
		}
		ctx = context.WithValue(ctx, contextLoopDetect, struct{}{})
		req.SetContext(ctx)

		newURL, err := crawler.wafBypass(ctx, client, req.RawURL)
		if err != nil {
			return fmt.Errorf("waf bypass failed: %w", err)
		}
		req.RawURL = newURL
		return nil
	})
	return crawler
}

func (a *AVDCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "aliyun-avd",
		DisplayName: "阿里云漏洞库",
		Link:        "https://avd.aliyun.com/high-risk/list",
	}
}

func (a *AVDCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	var results []*VulnInfo
	for page := 1; page <= pageLimit; page++ {
		select {
		case <-ctx.Done():
			return results, ctx.Err()
		default:
		}
		pageResult, err := a.parsePage(ctx, page)
		if err != nil {
			return results, err
		}
		results = append(results, pageResult...)
	}
	return results, nil
}

func (a *AVDCrawler) IsValuable(info *VulnInfo) bool {
	return info.Severity == High || info.Severity == Critical
}

func (a *AVDCrawler) parsePage(ctx context.Context, page int) ([]*VulnInfo, error) {
	rawURL := fmt.Sprintf("https://avd.aliyun.com/high-risk/list?page=%d", page)
	resp, err := a.client.R().SetContext(ctx).Get(rawURL)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	rows := doc.Find("tbody > tr")
	count := rows.Length()
	if count == 0 {
		return nil, fmt.Errorf("goquery found zero AVD rows")
	}

	hrefs := make([]string, 0, count)
	for i := 0; i < count; i++ {
		linkSelection := rows.Eq(i).Find("td > a")
		if linkSelection.Length() != 1 {
			return nil, fmt.Errorf("cannot find AVD detail link")
		}
		linkTag := linkSelection.Get(0)
		for _, attr := range linkTag.Attr {
			if attr.Key == "href" {
				hrefs = append(hrefs, attr.Val)
				break
			}
		}
	}
	if len(hrefs) != count {
		return nil, fmt.Errorf("cannot read all AVD detail links")
	}

	results := make([]*VulnInfo, 0, count)
	base, _ := url.Parse("https://avd.aliyun.com/")
	for _, href := range hrefs {
		select {
		case <-ctx.Done():
			return results, ctx.Err()
		default:
		}
		uri, err := url.ParseRequestURI(href)
		if err != nil {
			return results, nil
		}
		vulnLink := base.ResolveReference(uri).String()
		avdInfo, err := a.parseSingle(ctx, vulnLink)
		if err != nil {
			fmt.Fprintf(os.Stderr, "watchvuln avd detail parse failed %s: %v\n", vulnLink, err)
			return results, nil
		}
		results = append(results, avdInfo)
	}
	return results, nil
}

func (a *AVDCrawler) parseSingle(ctx context.Context, vulnLink string) (*VulnInfo, error) {
	resp, err := a.client.R().SetContext(ctx).Get(vulnLink)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}

	title := ""
	description := ""
	fixSteps := ""
	level := ""
	cveID := ""
	disclosure := ""
	var refs []string
	var tags []string

	u, _ := url.Parse(vulnLink)
	avdID := strings.TrimSpace(u.Query().Get("id"))

	metaSelection := doc.Find(`div[class="metric"]`)
	for i := 0; i < metaSelection.Length(); i++ {
		metric := metaSelection.Eq(i)
		label := strings.TrimSpace(metric.Find(".metric-label").Text())
		value := strings.TrimSpace(metric.Find(".metric-value").Text())
		if strings.HasPrefix(label, "CVE") {
			cveID = value
		} else if strings.HasPrefix(label, "利用情况") {
			if value != "暂无" {
				tags = append(tags, strings.ReplaceAll(value, " ", ""))
			}
		} else if strings.HasSuffix(label, "披露时间") {
			disclosure = value
		}
	}

	if !cveIDRegexp.MatchString(cveID) {
		cveID = ""
	}
	if _, err := time.Parse("2006-01-02", disclosure); err != nil {
		disclosure = ""
	}
	if cveID == "" && disclosure == "" {
		return nil, fmt.Errorf("invalid AVD vulnerability data")
	}

	header := doc.Find(`h5[class="header__title"]`)
	level = strings.TrimSpace(header.Find(".badge").Text())
	title = strings.TrimSpace(header.Find(".header__title__text").Text())

	mainContent := doc.Find(`div[class="py-4 pl-4 pr-4 px-2 bg-white rounded shadow-sm"]`).Children()
	for i := 0; i < mainContent.Length(); {
		sentinel := strings.TrimSpace(mainContent.Eq(i).Text())
		if sentinel == "漏洞描述" && i+1 < mainContent.Length() {
			description = strings.TrimSpace(mainContent.Eq(i + 1).Find("div").Eq(0).Text())
			i += 2
			continue
		}
		if sentinel == "解决建议" && i+1 < mainContent.Length() {
			if mainContent.Eq(i+1).Length() != 1 {
				i += 2
				continue
			}
			innerNode := mainContent.Eq(i + 1).Nodes[0].FirstChild
			for ; innerNode != nil; innerNode = innerNode.NextSibling {
				if innerNode.Type != html.TextNode {
					continue
				}
				text := strings.TrimSpace(innerNode.Data)
				if text != "" {
					fixSteps += text + "\n"
				}
			}
			fixSteps = strings.TrimSpace(strings.ReplaceAll(fixSteps, "、", ". "))
			i += 2
			continue
		}
		i++
	}
	refTags := mainContent.Find(`div.reference tbody > tr a`)
	for i := 0; i < refTags.Length(); i++ {
		refText, ok := refTags.Eq(i).Attr("href")
		if !ok {
			continue
		}
		refText = strings.TrimSpace(refText)
		if strings.HasPrefix(refText, "http") {
			refs = append(refs, refText)
		}
	}

	severity := Low
	switch level {
	case "低危":
		severity = Low
	case "中危":
		severity = Medium
	case "高危":
		severity = High
	case "严重":
		severity = Critical
	}

	return &VulnInfo{
		UniqueKey:   avdID,
		Title:       title,
		Description: description,
		Severity:    severity,
		CVE:         cveID,
		Disclosure:  disclosure,
		References:  refs,
		Solutions:   fixSteps,
		From:        vulnLink,
		Tags:        tags,
		Creator:     a,
	}, nil
}

func (a *AVDCrawler) wafBypass(ctx context.Context, client *req.Client, targetURL string) (string, error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	getScriptContent := func() (string, error) {
		resp, err := client.NewRequest().SetContext(ctx).Get(targetURL)
		if err != nil {
			return "", err
		}
		matches := scriptRegexp.FindStringSubmatch(resp.String())
		if len(matches) != 2 {
			return "", fmt.Errorf("invalid waf response")
		}
		return matches[1], nil
	}

	urlParser := func() map[string]interface{} {
		u, err := url.Parse(targetURL)
		if err != nil {
			return nil
		}
		protocol := u.Scheme + ":"
		search := "?" + u.RawQuery
		node := map[string]interface{}{
			"protocol": protocol,
			"host":     u.Host,
			"hostname": u.Hostname(),
			"port":     u.Port(),
			"pathname": u.Path,
			"search":   search,
			"hash":     u.Fragment,
			"url":      u.String(),
			"href":     u.String(),
		}
		node["firstChild"] = node
		return node
	}

	location := map[string]interface{}{"href": targetURL}
	document := map[string]interface{}{
		"cookie":   "",
		"location": location,
		"createElement": func(args ...interface{}) map[string]interface{} {
			return urlParser()
		},
	}
	window := map[string]interface{}{
		"navigator": map[string]interface{}{
			"userAgent": client.Headers.Get("User-Agent"),
		},
		"location": location,
		"document": document,
	}

	loop := eventloop.NewEventLoop()
	defer loop.StopNoWait()
	go func() {
		<-ctx.Done()
		loop.StopNoWait()
	}()

	loop.Run(func(vm *goja.Runtime) {
		globals := vm.GlobalObject()
		_ = globals.Set("window", window)
		_ = globals.Set("document", document)
		_ = globals.Set("location", location)
	})

	scripts, err := getScriptContent()
	if err != nil {
		return "", err
	}
	loop.Run(func(runtime *goja.Runtime) {
		if _, runErr := runtime.RunScript("avd-waf.js", scripts); runErr != nil {
			err = runErr
		}
	})
	if err != nil {
		return "", err
	}
	href, ok := location["href"].(string)
	if !ok || href == "" || href == targetURL {
		return "", fmt.Errorf("waf bypass did not produce a new URL")
	}
	return href, nil
}
