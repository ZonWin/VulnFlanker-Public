package main

import (
	"context"
	"fmt"
)

type SeverityLevel string

const (
	Low      SeverityLevel = "低危"
	Medium   SeverityLevel = "中危"
	High     SeverityLevel = "高危"
	Critical SeverityLevel = "严重"
)

const (
	ReasonBuiltinCollection = "平台内置采集"
	RawMessageTypeVulnInfo  = "watchvuln-vulninfo"
)

type VulnInfo struct {
	UniqueKey                  string        `json:"unique_key"`
	Title                      string        `json:"title"`
	Description                string        `json:"description"`
	Severity                   SeverityLevel `json:"severity"`
	CVE                        string        `json:"cve"`
	Disclosure                 string        `json:"disclosure"`
	Solutions                  string        `json:"solutions"`
	GithubSearch               []string      `json:"github_search"`
	References                 []string      `json:"references"`
	Tags                       []string      `json:"tags"`
	From                       string        `json:"from"`
	Reason                     []string      `json:"reason"`
	WatchVulnSource            string        `json:"watchvuln_source,omitempty"`
	WatchVulnSourceDisplayName string        `json:"watchvuln_source_display_name,omitempty"`

	Creator Grabber `json:"-"`
}

func (v *VulnInfo) String() string {
	return fmt.Sprintf("%s (%s)", v.Title, v.From)
}

type Provider struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Link        string `json:"link"`
}

type Grabber interface {
	ProviderInfo() *Provider
	GetUpdate(ctx context.Context, pageLimit int) ([]*VulnInfo, error)
	IsValuable(info *VulnInfo) bool
}

type RawMessage struct {
	Type    string    `json:"type"`
	Content *VulnInfo `json:"content"`
}
