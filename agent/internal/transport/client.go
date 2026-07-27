package transport

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"vulnflanker-agent/internal/collector"
	"vulnflanker-agent/internal/taskrunner"
)

type Client struct {
	baseURL    string
	secret     string
	httpClient *http.Client
}

type Heartbeat struct {
	AgentID  string `json:"agent_id"`
	Hostname string `json:"hostname"`
	Platform string `json:"platform"`
	Version  string `json:"version"`
}

type TaskPollResponse struct {
	Task *taskrunner.Task `json:"task"`
}

type EnrollRequest struct {
	EnrollmentToken string `json:"enrollment_token"`
	AgentID         string `json:"agent_id,omitempty"`
	Hostname        string `json:"hostname"`
	Platform        string `json:"platform"`
	Version         string `json:"version"`
}

type EnrollResponse struct {
	AgentID        string `json:"agent_id"`
	AgentSecret    string `json:"agent_secret"`
	AgentAPIPrefix string `json:"agent_api_prefix"`
}

func New(serverURL string, timeout time.Duration, secret string) (*Client, error) {
	parsed, err := url.Parse(strings.TrimRight(serverURL, "/"))
	if err != nil {
		return nil, err
	}
	return &Client{
		baseURL: parsed.String(),
		secret:  secret,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}, nil
}

func (c *Client) Enroll(request EnrollRequest) (*EnrollResponse, error) {
	var response EnrollResponse
	if err := c.post("/agent/v1/enroll", request, &response); err != nil {
		return nil, err
	}
	return &response, nil
}

func (c *Client) SubmitHeartbeat(heartbeat Heartbeat) error {
	return c.post("/agent/v1/heartbeat", heartbeat, nil)
}

func (c *Client) SubmitSnapshot(snapshot collector.Snapshot) error {
	return c.post("/agent/v1/snapshots", snapshot, nil)
}

func (c *Client) PollTask(agentID string) (*taskrunner.Task, error) {
	var response TaskPollResponse
	if err := c.get("/agent/v1/tasks/next", &response); err != nil {
		return nil, err
	}
	return response.Task, nil
}

func (c *Client) SubmitTaskResult(agentID string, taskID string, result taskrunner.TaskResult) error {
	path := fmt.Sprintf(
		"/agent/v1/tasks/%s/results",
		url.PathEscape(taskID),
	)
	return c.post(path, result, nil)
}

func (c *Client) get(path string, out any) error {
	req, err := http.NewRequest(http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return err
	}
	c.authorize(req)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("GET %s returned %d: %s", path, resp.StatusCode, string(body))
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (c *Client) post(path string, payload any, out any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	c.authorize(req)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("POST %s returned %d: %s", path, resp.StatusCode, string(body))
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (c *Client) authorize(req *http.Request) {
	if c.secret != "" {
		req.Header.Set("Authorization", "Bearer "+c.secret)
	}
}
