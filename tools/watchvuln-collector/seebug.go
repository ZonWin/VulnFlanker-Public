package main

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strconv"
	"strings"
	"sync"

	"github.com/PuerkitoBio/goquery"
	"github.com/dop251/goja"
	"github.com/dop251/goja_nodejs/eventloop"
	"github.com/imroc/req/v3"
)

type SeebugCrawler struct {
	client *req.Client
	mu     sync.Mutex
}

func NewSeebugCrawler() Grabber {
	crawler := &SeebugCrawler{}
	crawler.client = crawler.newClient()
	crawler.client.AddCommonRetryCondition(func(resp *req.Response, err error) bool {
		if err != nil {
			return true
		}
		return resp.StatusCode != 200
	}).AddCommonRetryHook(func(resp *req.Response, err error) {
		if err != nil || resp.StatusCode == 200 {
			return
		}
		if bypassErr := crawler.wafBypass(resp.Request.Context()); bypassErr != nil {
			resp.Err = bypassErr
		}
	})
	return crawler
}

func (s *SeebugCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "seebug",
		DisplayName: "Seebug 漏洞平台",
		Link:        "https://www.seebug.org",
	}
}

func (s *SeebugCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	pageCount, err := s.getPageCount(ctx)
	if err != nil {
		return nil, fmt.Errorf("get page count: %w", err)
	}
	if pageCount == 0 {
		return nil, fmt.Errorf("invalid page count")
	}
	if pageCount > pageLimit {
		pageCount = pageLimit
	}
	var results []*VulnInfo
	for page := 1; page <= pageCount; page++ {
		pageResults, err := s.parsePage(ctx, page)
		if err != nil {
			return results, err
		}
		results = append(results, pageResults...)
	}
	return results, nil
}

func (s *SeebugCrawler) IsValuable(info *VulnInfo) bool {
	return info.Severity == High || info.Severity == Critical
}

func (s *SeebugCrawler) getPageCount(ctx context.Context) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	resp, err := s.client.R().SetContext(ctx).Get("https://www.seebug.org/vuldb/vulnerabilities")
	if err != nil {
		return 0, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return 0, err
	}
	pagination := doc.Find("ul.pagination li")
	if pagination.Length() < 3 {
		return 0, fmt.Errorf("failed to get pagination node")
	}
	countText := strings.TrimSpace(pagination.Last().Prev().Text())
	count, err := strconv.Atoi(countText)
	if err != nil {
		return 0, err
	}
	return count, nil
}

func (s *SeebugCrawler) parsePage(ctx context.Context, page int) ([]*VulnInfo, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	resp, err := s.client.R().SetContext(ctx).Get(fmt.Sprintf("https://www.seebug.org/vuldb/vulnerabilities?page=%d", page))
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	rows := doc.Find(".sebug-table tbody tr")
	if rows.Length() == 0 {
		return nil, fmt.Errorf("goquery found zero seebug rows")
	}
	results := make([]*VulnInfo, 0, rows.Length())
	for index := 0; index < rows.Length(); index++ {
		tds := rows.Eq(index).Find("td")
		if tds.Length() != 6 {
			return nil, fmt.Errorf("unexpected seebug column count")
		}
		idTag := tds.Eq(0).Find("a")
		href, _ := idTag.Attr("href")
		href = strings.TrimSpace(href)
		if href != "" {
			href = "https://www.seebug.org" + href
		}
		uniqueKey := strings.TrimSpace(idTag.Text())
		disclosure := strings.TrimSpace(tds.Eq(1).Text())
		severityTitle, _ := tds.Eq(2).Find("div").Attr("data-original-title")
		severity := Low
		switch strings.TrimSpace(severityTitle) {
		case "高危":
			severity = High
		case "中危":
			severity = Medium
		}
		title := strings.TrimSpace(tds.Eq(3).Text())
		cveID, _ := tds.Eq(4).Find("i.fa-id-card").Attr("data-original-title")
		cveID = strings.TrimSpace(cveID)
		if strings.Contains(cveID, "、") {
			cveID = strings.Split(cveID, "、")[0]
		}
		if !cveIDRegexp.MatchString(cveID) {
			cveID = ""
		}
		var tags []string
		tag, _ := tds.Eq(4).Find("i.fa-file-text-o").Attr("data-original-title")
		if strings.TrimSpace(tag) == "有详情" {
			tags = append(tags, "有详情")
		}
		results = append(results, &VulnInfo{
			UniqueKey:  uniqueKey,
			Title:      title,
			Severity:   severity,
			CVE:        cveID,
			Disclosure: disclosure,
			Tags:       tags,
			From:       href,
			Creator:    s,
		})
	}
	return results, nil
}

func (s *SeebugCrawler) newClient() *req.Client {
	jar, _ := cookiejar.New(nil)
	return newHTTPClient().
		SetCookieJar(jar).
		SetCommonHeader("Referer", "https://www.seebug.org/")
}

func (s *SeebugCrawler) wafBypass(ctx context.Context) error {
	jar, _ := cookiejar.New(nil)
	client := s.newClient().SetCookieJar(jar)

	getScriptContent := func() (string, error) {
		resp, err := client.NewRequest().SetContext(ctx).Get("https://www.seebug.org/")
		if err != nil {
			return "", err
		}
		matches := scriptRegexp.FindStringSubmatch(resp.String())
		if len(matches) != 2 {
			return "", fmt.Errorf("invalid waf response")
		}
		return matches[1], nil
	}

	window := map[string]interface{}{
		"navigator": map[string]interface{}{
			"userAgent": s.client.Headers.Get("User-Agent"),
		},
	}
	document := map[string]interface{}{"cookie": ""}
	location := map[string]interface{}{}

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
		return err
	}
	loop.Run(func(runtime *goja.Runtime) {
		if _, runErr := runtime.RunScript("seebug-waf-1.js", scripts); runErr != nil {
			err = runErr
		}
	})
	if err != nil {
		return err
	}
	cookies, err := s.getCookieFromDocument(document)
	if err != nil {
		return err
	}
	baseURL, _ := url.Parse("https://www.seebug.org/")
	jar.SetCookies(baseURL, cookies)

	scripts, err = getScriptContent()
	if err != nil {
		return nil
	}
	cookieText := ""
	for _, cookie := range jar.Cookies(baseURL) {
		cookieText += fmt.Sprintf("%s=%s; ", cookie.Name, cookie.Value)
	}
	document["cookie"] = cookieText
	loop.Run(func(runtime *goja.Runtime) {
		if _, runErr := runtime.RunScript("seebug-waf-2.js", scripts); runErr != nil {
			err = runErr
		}
	})
	if err != nil {
		return err
	}
	cookies, err = s.getCookieFromDocument(document)
	if err != nil {
		return err
	}
	jar.SetCookies(baseURL, cookies)
	s.client.SetCookieJar(jar)
	return ctx.Err()
}

func (s *SeebugCrawler) getCookieFromDocument(document map[string]interface{}) ([]*http.Cookie, error) {
	cookieText, ok := document["cookie"].(string)
	if !ok {
		return nil, fmt.Errorf("invalid cookie value")
	}
	response := &http.Response{Header: map[string][]string{"Set-Cookie": {cookieText}}}
	return response.Cookies(), nil
}
