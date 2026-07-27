package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/imroc/req/v3"
)

const oscsPageSize = 10

type OSCSCrawler struct {
	client *req.Client
}

func NewOSCSCrawler() Grabber {
	client := wrapAPIClient(newHTTPClient())
	client.SetCommonHeader("Referer", "https://www.oscs1024.com/cm")
	client.SetCommonHeader("Origin", "https://www.oscs1024.com")
	return &OSCSCrawler{client: client}
}

func (o *OSCSCrawler) ProviderInfo() *Provider {
	return &Provider{
		Name:        "oscs",
		DisplayName: "OSCS开源安全情报预警",
		Link:        "https://www.oscs1024.com/cm",
	}
}

func (o *OSCSCrawler) GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error) {
	pageCount, err := o.getPageCount(ctx)
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
		pageResults, err := o.parsePage(ctx, page)
		if err != nil {
			return results, err
		}
		results = append(results, pageResults...)
	}
	return results, nil
}

func (o *OSCSCrawler) IsValuable(info *VulnInfo) bool {
	if info.Severity != Critical && info.Severity != High {
		return false
	}
	for _, tag := range info.Tags {
		if tag == "发布预警" {
			return true
		}
	}
	return false
}

func (o *OSCSCrawler) getPageCount(ctx context.Context) (int, error) {
	var body oscsListResponse
	resp, err := o.client.R().
		SetBodyBytes(o.buildListBody(1, oscsPageSize)).
		SetContext(ctx).
		Post("https://www.oscs1024.com/oscs/v1/intelligence/list")
	if err != nil {
		return 0, err
	}
	if err = resp.UnmarshalJson(&body); err != nil {
		return 0, err
	}
	if body.Code != 200 || !body.Success {
		return 0, fmt.Errorf("response error %s", body.Info)
	}
	total := body.Data.Total
	if total <= 0 {
		return 0, fmt.Errorf("invalid total %d", total)
	}
	pageCount := total / oscsPageSize
	if total%oscsPageSize != 0 {
		pageCount++
	}
	if pageCount == 0 {
		pageCount = 1
	}
	return pageCount, nil
}

func (o *OSCSCrawler) parsePage(ctx context.Context, page int) ([]*VulnInfo, error) {
	resp, err := o.client.R().
		SetContext(ctx).
		SetBodyBytes(o.buildListBody(page, oscsPageSize)).
		Post("https://www.oscs1024.com/oscs/v1/intelligence/list")
	if err != nil {
		return nil, err
	}
	var body oscsListResponse
	if err = resp.UnmarshalJson(&body); err != nil {
		return nil, err
	}
	results := make([]*VulnInfo, 0, len(body.Data.Data))
	for _, item := range body.Data.Data {
		tags := []string{}
		if item.IsPush == 1 {
			tags = append(tags, "发布预警")
		}
		eventType := "公开漏洞"
		switch item.IntelligenceType {
		case 2:
			eventType = "墨菲安全独家"
		case 3:
			eventType = "投毒情报"
		}
		tags = append(tags, eventType)
		info, err := o.parseSingleVuln(ctx, item.Mps)
		if err != nil {
			fmt.Fprintf(os.Stderr, "watchvuln oscs detail parse failed %s: %v\n", item.Url, err)
			continue
		}
		info.Tags = tags
		results = append(results, info)
	}
	return results, nil
}

func (o *OSCSCrawler) parseSingleVuln(ctx context.Context, mps string) (*VulnInfo, error) {
	resp, err := o.client.R().
		SetContext(ctx).
		SetBodyString(fmt.Sprintf(`{"vuln_no":"%s"}`, mps)).
		Post("https://www.oscs1024.com/oscs/v1/vdb/info")
	if err != nil {
		return nil, err
	}
	var body oscsDetailResponse
	if err = resp.UnmarshalJson(&body); err != nil {
		return nil, err
	}
	if body.Code != 200 || !body.Success || len(body.Data) == 0 {
		return nil, fmt.Errorf("response error %s", body.Info)
	}
	data := body.Data[0]
	severity := Low
	switch data.Level {
	case "Critical":
		severity = Critical
	case "High":
		severity = High
	case "Medium":
		severity = Medium
	}
	refs := make([]string, 0, len(data.References))
	for _, ref := range data.References {
		if ref.Url != "" {
			refs = append(refs, ref.Url)
		}
	}
	return &VulnInfo{
		UniqueKey:   data.VulnNo,
		Title:       data.VulnTitle,
		Description: data.Description,
		Severity:    severity,
		CVE:         data.CveID,
		Disclosure:  time.UnixMilli(data.PublishTime).Format("2006-01-02"),
		References:  refs,
		Solutions:   buildOSCSSolution(data.SolutionData),
		From:        "https://www.oscs1024.com/hd/" + data.VulnNo,
		Creator:     o,
	}, nil
}

func (o *OSCSCrawler) buildListBody(page, size int) []byte {
	data, _ := json.Marshal(map[string]interface{}{
		"page":     page,
		"per_page": size,
	})
	return data
}

func buildOSCSSolution(solution []string) string {
	var builder strings.Builder
	for index, item := range solution {
		builder.WriteString(fmt.Sprintf("%d. %s\n", index+1, item))
	}
	return strings.TrimSpace(builder.String())
}

type oscsListResponse struct {
	Data struct {
		Total int `json:"total"`
		Data  []*struct {
			Url              string `json:"url"`
			Mps              string `json:"mps"`
			IntelligenceType int    `json:"intelligence_type"`
			IsPush           int    `json:"is_push"`
		} `json:"data"`
	} `json:"data"`
	Success bool   `json:"success"`
	Code    int    `json:"code"`
	Info    string `json:"info"`
}

type oscsDetailResponse struct {
	Data []*struct {
		Description string `json:"description"`
		Level       string `json:"level"`
		CveID       string `json:"cve_id"`
		PublishTime int64  `json:"publish_time"`
		References  []struct {
			Url string `json:"url"`
		} `json:"references"`
		VulnTitle    string   `json:"vuln_title"`
		VulnNo       string   `json:"vuln_no"`
		SolutionData []string `json:"soulution_data"`
	} `json:"data"`
	Success bool   `json:"success"`
	Code    int    `json:"code"`
	Info    string `json:"info"`
}
