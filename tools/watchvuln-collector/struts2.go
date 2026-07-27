package main

import (
	"bytes"
	"context"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/imroc/req/v3"
)

const struts2URL = "https://cwiki.apache.org/confluence/display/WW/Security+Bulletins"

var struts2ID = regexp.MustCompile(`S2-\d{3}`)

type Struts2Crawler struct {
	client *req.Client
}

func NewStruts2Crawler() Grabber {
	client := newHTTPClient()
	client.SetCommonHeader("Referer", "https://cwiki.apache.org/")
	client.SetCommonHeader("Origin", "https://cwiki.apache.org/")
	client.SetCommonHeader("Accept-Language", "en-US,en;q=0.9")
	return &Struts2Crawler{client: client}
}

func (s *Struts2Crawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "struts2",
		DisplayName: "Apache Struts2 Security Bulletins",
		Link:        struts2URL,
	}
}

func (s *Struts2Crawler) GetUpdate(ctx context.Context, vulnLimit int) ([]*VulnInfo, error) {
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	resp, err := s.client.R().SetContext(ctx).Get(struts2URL)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	var results []*VulnInfo
	items := doc.Find("#main-content > ul > li")
	total := items.Length()
	items.Each(func(index int, selection *goquery.Selection) {
		if index < total-vulnLimit {
			return
		}
		linkTag := selection.Find("a")
		title := strings.TrimSpace(linkTag.Text())
		link, _ := linkTag.Attr("href")
		fullLink := "https://cwiki.apache.org" + link
		vuln, err := s.getVulnInfoFromURL(ctx, fullLink)
		if err != nil {
			return
		}
		vuln.Title = title
		vuln.UniqueKey = struts2ID.FindString(title)
		if vuln.UniqueKey == "" {
			return
		}
		vuln.Creator = s
		results = append(results, vuln)
	})
	return results, nil
}

func (s *Struts2Crawler) IsValuable(info *VulnInfo) bool {
	return info.Severity == High || info.Severity == Critical
}

func (s *Struts2Crawler) getVulnInfoFromURL(ctx context.Context, rawURL string) (*VulnInfo, error) {
	resp, err := s.client.R().SetContext(ctx).Get(rawURL)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	return &VulnInfo{
		Severity:    severityFromStruts2String(doc.Find("th:contains('Maximum security rating') + td").Text()),
		CVE:         strings.TrimSpace(doc.Find("th:contains('CVE Identifier') + td").Text()),
		Description: strings.TrimSpace(doc.Find(`h2[id$='-Problem'] + p`).Contents().Text()),
		Solutions:   strings.TrimSpace(doc.Find("h2[id$='-Solution'] + p").Contents().Text()),
		Tags:        []string{strings.TrimSpace(doc.Find("th:contains('Impact of vulnerability') + td").Contents().Text())},
		From:        rawURL,
	}, nil
}

func severityFromStruts2String(value string) SeverityLevel {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "critical":
		return Critical
	case "important":
		return High
	case "moderate":
		return Medium
	default:
		return Low
	}
}
