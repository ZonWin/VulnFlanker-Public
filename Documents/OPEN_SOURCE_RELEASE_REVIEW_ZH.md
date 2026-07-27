# VulnFlanker 开源发布审查

本清单用于跟踪首次开源发布前需要完成的工作。公开版本预计会移除 `docs/` 目录，因此面向公众的说明必须完整包含在 `README.md` 等根目录文件中。

## 当前准备情况

状态：公开工作树的内容已为 v0.1 发布准备就绪。

在完成第一轮高优先级修复后，项目现已通过主要本地质量门禁。当前分支已从公开工作树中移除私有规划资料、内部文档和真实的第三方漏洞语料快照。

重要提示：如果将现有仓库连同完整 Git 历史记录一起公开，之前的提交可能仍会暴露本分支中已删除的文件。为实现干净的公开发布，请通过一个无旧历史的仓库发布此分支，或采用清理历史记录的发布流程。

## 发布阻塞项

- [x] 移除已跟踪的内部工作笔记。
  - 已跟踪的路径包括 `.planning/`、`task_plan.md`、`findings.md`、`progress.md` 和 `README-old.md`。
  - 这些路径现已被忽略并从公开分支的 Git 跟踪中移除，同时仍保留在本地工作副本中。

- [x] 确保移除 `docs/` 后 `README.md` 仍可独立使用。
  - README 不再链接到私有 `docs/` 路径。
  - 现在已包含项目范围、架构、快速开始、Agent 说明、AI 加密配置、本地检查、仓库结构和安全边界。

- [x] 修复后端测试收集。
  - 添加了缺失的共享测试辅助工具，并更新了过期的匹配与迁移测试夹具。
  - 完整的后端测试现在可以在本地完成收集并全部通过。

- [x] 解决前端依赖审计问题。
  - 将存在漏洞的 React Router 包路径替换为当前的 `react-router` 包，并更新了 `package-lock.json`。
  - `npm audit` 现在报告零个漏洞。

- [x] 审查真实漏洞语料的再分发。
  - 从公开跟踪中移除了 `backend/tests/fixtures/watchvuln_real_corpus`。
  - 使用 `backend/tests/fixtures/public_watchvuln_corpus` 下最小化且可安全公开的合成测试夹具进行替代。
  - 使用 `backend/tests/fixtures/public_ai_enrichment_eval` 下可公开的合成样本替代真实语料 AI 评估样本。

## v0.1 公开发布前的高优先级事项

- [x] 使用真正的服务端加密替换仅使用 Base64 的 AI API 密钥存储。
  - 旧实现使用可逆的 `b64:` 前缀存储密钥。
  - 新增和更新的密钥使用加密的 `fernet:` 存储。
  - 为兼容迁移，旧版 `b64:`/`plain:` 值仍然可读。
  - 文档已说明，加密密钥一旦丢失，已存储的 AI 密钥将无法恢复。
  - 现在，所有保存 AI 密钥的入口（包括后端脚本）均需要设置 `VULNFLANKER_AI_KEY_ENCRYPTION_KEY`。

- [x] 将 `deploy/docker-compose.yml` 明确标记为演示/开发用途，或拆分出面向生产环境的 Compose 文件。
  - 当前 Compose 使用 `uvicorn --reload`、绑定挂载 `..:/workspace`，并包含固定的本地 PostgreSQL 凭据。
  - 这些配置可用于演示，但不应被视为已完成生产安全加固。

- [x] 移除已跟踪的备份文件和容易引起混淆的根模块文件。
  - 不应发布 `deploy/backend.Dockerfile.BAK`。
  - 根目录的 `go.mod` 声明了 `module vulnflanker/a1`，而实际的 Go 模块位于 `agent/` 和 `tools/watchvuln-collector/` 下。

- [x] 添加基本的开源项目文件。
  - 使用 `Documents/SECURITY_EN.md` 和 `Documents/SECURITY_ZH.md` 说明漏洞披露方式。
  - 使用 `Documents/CONTRIBUTING_EN.md` 和 `Documents/CONTRIBUTING_ZH.md` 说明本地设置、测试命令和贡献规则。
  - 使用 `Documents/CHANGELOG_EN.md` 和 `Documents/CHANGELOG_ZH.md` 记录首个版本的发布说明。
  - 为后端、前端和 Go 模块配置 GitHub Actions CI。
  - 配置 Dependabot 或同类依赖更新自动化工具。

- [x] 生成或记录第三方依赖声明。
  - 项目现有许可证为 Apache-2.0。
  - 内置 WatchVuln 采集器已包含针对所改编 MIT 许可逻辑的第三方声明。
  - 已添加 `Documents/THIRD_PARTY_NOTICES_EN.md` 和 `Documents/THIRD_PARTY_NOTICES_ZH.md`，并在 `NOTICE` 中链接到英文声明。
  - 已为 Python 和 Go 添加非阻塞式 CI 依赖审计，同时将 `npm audit` 保留为阻塞式前端检查。

## 需要公开保留的安全说明

- 当前版本适用于本地演示、内部测试和小型受控环境。
- 不要将控制台 API、Agent 接入服务、PostgreSQL 或 Redis 直接暴露在公网。
- 对共享部署或类生产部署使用 HTTPS 并设置安全 Cookie。
- 替换所有示例密码、Webhook 令牌、Redis 密码和引导管理员凭据。
- 系统已支持 Agent Bearer Secret 身份认证，但 HMAC 重放保护和密钥轮换仍是后续安全加固事项。
- 当前版本不包含自动修复或侵入式概念验证执行。

## 验证快照

本次审查期间已运行的命令：

- `python -m alembic heads`：只有一个 Alembic head。
- `python -m compileall backend/app`：通过。
- `python -m pytest -q`：通过，共 215 项测试。
- 公开合成语料测试：通过。
- `npm run build`：通过。
- `npm audit`：通过，零个漏洞。
- 在 `agent/` 中运行 `go test ./...`：通过。
- 在 `tools/watchvuln-collector/` 中运行 `go test ./...`：通过。
- `git diff --check`：通过，仅有 Windows 行尾警告。
- Python 依赖漏洞审计和 Go `govulncheck` 已配置为首个公开发布分支的非阻塞式 CI 检查。

## 建议修复顺序

1. 在最终分支上重新运行完整的本地验证。
2. 检查暂存区差异，确认没有意外暴露私有名称或数据。
3. 如果旧的私有文件不得出现在 Git 历史记录中，请通过无旧历史的公开仓库发布。
4. 从干净的公开发布状态创建 `v0.1.0` 标签。
