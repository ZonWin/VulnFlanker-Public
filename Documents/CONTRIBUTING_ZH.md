# 贡献指南

感谢你帮助改进 VulnFlanker。

## 本地检查

提交拉取请求前，请运行以下针对性检查：

```powershell
python -m compileall backend\app
$env:PYTHONPATH = "backend;backend/tests"
python -m pytest -q
cd frontend
npm install
npm run build
npm audit
cd ..\agent
go test ./...
cd ..\tools\watchvuln-collector
go test ./...
```

发布前可选择运行以下安全审计：

```powershell
python -m pip install pip-audit
pip-audit
cd agent
govulncheck ./...
cd ..\tools\watchvuln-collector
govulncheck ./...
```

## 开发说明

- 将变更范围限制在当前处理的功能或缺陷内。
- 不要提交本地 `.env` 文件、运行时状态、构建产物或私有规划笔记。
- 对行为变更添加或更新测试。
- 确保公开文档内容完整、可独立使用；公开版本应当无需私有规划文档即可运行。
- 不要在测试夹具中包含真实凭据、私有基础设施名称或专有漏洞情报数据。

## 安全相关变更

对于涉及身份认证、Agent 接入、加密、验证执行或网络暴露的变更，请在拉取请求说明中附上一段简短的安全影响说明。
