package main

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/imroc/req/v3"
)

type VenustechCrawler struct {
	client *req.Client
}

func NewVenustechCrawler() Grabber {
	return &VenustechCrawler{client: newHTTPClient()}
}

func (v *VenustechCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "venustech",
		DisplayName: "启明星辰漏洞通告",
		Link:        "https://www.venustech.com.cn/new_type/aqtg/",
	}
}

func (v *VenustechCrawler) IsValuable(info *VulnInfo) bool {
	return info.Severity == High || info.Severity == Critical
}

func (v *VenustechCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	var results []*VulnInfo
	for page := 1; page <= pageLimit; page++ {
		pageResults, err := v.parsePage(ctx, page)
		if err != nil {
			return results, err
		}
		results = append(results, pageResults...)
	}
	return results, nil
}

func (v *VenustechCrawler) parsePage(ctx context.Context, page int) ([]*VulnInfo, error) {
	rawURL := "https://www.venustech.com.cn/new_type/aqtg/"
	if page > 1 {
		rawURL = fmt.Sprintf("%sindex_%d.html", rawURL, page)
	}
	resp, err := v.client.R().SetContext(ctx).Get(rawURL)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	items := doc.Find("body > div > div.wrapper.clearfloat > div.right.main-content > div > div.main-inner-bt > ul > li > a")
	if items.Length() == 0 {
		return nil, fmt.Errorf("goquery found zero venustech rows")
	}
	results := make([]*VulnInfo, 0, items.Length())
	items.Each(func(index int, selection *goquery.Selection) {
		if strings.Contains(selection.Text(), "多个安全漏洞") {
			return
		}
		href, ok := selection.Attr("href")
		if !ok {
			return
		}
		vulnURL := "https://www.venustech.com.cn" + href
		vulnInfo, err := v.parseSingle(ctx, vulnURL)
		if err != nil {
			fmt.Fprintf(os.Stderr, "watchvuln venustech detail parse failed %s: %v\n", vulnURL, err)
			return
		}
		results = append(results, vulnInfo)
	})
	return results, nil
}

func (v *VenustechCrawler) parseSingle(ctx context.Context, vulnURL string) (*VulnInfo, error) {
	resp, err := v.client.R().SetContext(ctx).Get(vulnURL)
	if err != nil {
		return nil, err
	}
	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(resp.Bytes()))
	if err != nil {
		return nil, err
	}
	content := doc.Find("body > div > div.wrapper.clearfloat > div.right.main-content > div > div > div.news-content.ctn")
	table := content.Find("div > table").First()
	cells := table.Find("tbody > tr > td")
	if cells.Length() <= 0 || cells.Length()%2 == 1 {
		return nil, fmt.Errorf("invalid vulnerability table")
	}
	var info VulnInfo
	spaceReplacer := strings.NewReplacer(" ", "", "\u00A0", "")
	for index := 0; index < cells.Length(); index += 2 {
		keyText := spaceReplacer.Replace(cells.Eq(index).Text())
		valueText := strings.TrimSpace(cells.Eq(index + 1).Text())
		switch keyText {
		case "漏洞名称":
			info.Title = valueText
		case "CVEID":
			if strings.Contains(valueText, "CVE") {
				info.CVE = strings.Split(valueText, "、")[0]
			}
		case "发现时间":
			if _, err = time.Parse("2006-01-02", valueText); err == nil {
				info.Disclosure = valueText
			}
		case "漏洞等级", "等级":
			info.Severity = Low
			switch valueText {
			case "高危":
				info.Severity = High
			case "中危":
				info.Severity = Medium
			}
		}
	}
	if info.Title == "" {
		title := strings.TrimSpace(content.Find("h3").Text())
		info.Title = strings.TrimPrefix(title, "【漏洞通告】")
	}
	filename := path.Base(resp.Request.URL.Path)
	info.UniqueKey = strings.TrimSuffix(filename, path.Ext(filename)) + "_venustech"
	info.From = vulnURL

	h2Data := strings.TrimSpace(table.NextUntil("h2").Text())
	h3Data := strings.TrimSpace(table.NextUntil("h3").Text())
	if h2Data != "" && h3Data != "" {
		if len(h2Data) < len(h3Data) {
			info.Description = h2Data
		} else {
			info.Description = h3Data
		}
	} else if h2Data != "" {
		info.Description = h2Data
	} else {
		info.Description = h3Data
	}

	content.Find("div > h3").Each(func(index int, selection *goquery.Selection) {
		if !strings.Contains(selection.Text(), "参考链接") {
			return
		}
		selection.NextUntil("h2").Each(func(_ int, section *goquery.Selection) {
			if len(section.Nodes) == 0 || section.Nodes[0].Data != "section" {
				return
			}
			ref := strings.TrimSpace(section.Text())
			if ref != "" {
				info.References = append(info.References, ref)
			}
		})
	})
	info.Creator = v
	return &info, nil
}
