# VulnFlanker Frontend

VulnFlanker 前端是内部安全运营台，当前覆盖风险队列、漏洞比对、资产管理、漏洞情报、审计日志和情报采集。

## 技术栈

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Ant Design
- lucide-react

## 本地开发

安装依赖：

```powershell
npm install
```

启动开发服务：

```powershell
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173/
```

如果本机 `5173` 端口不可用，可以指定端口：

```powershell
npm run dev -- --host 0.0.0.0 --port 53173
```

## API 代理

开发服务默认把 `/api` 代理到仓库根目录 `.env` 中的 `VULNFLANKER_API_PORT`：

```text
http://127.0.0.1:8000
```

如果根目录 `.env` 中配置了 `VULNFLANKER_API_PORT=18000`，开发代理会自动变成：

```text
http://127.0.0.1:18000
```

如需手动覆盖代理目标，可以在 `frontend/.env` 中设置：

```text
VITE_API_PROXY_TARGET=http://127.0.0.1:18000
```

如果需要绕过 Vite 代理并直接请求某个后端地址，可以设置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

默认 `.env.example` 中保持为空，表示使用同源 `/api` 路径和 Vite 代理。

## 构建验证

运行类型检查和生产构建：

```powershell
npm run build
```

仅运行 TypeScript 检查：

```powershell
npm run typecheck
```

预览生产构建：

```powershell
npm run preview
```

## 当前页面

| 路由 | 页面 |
|---|---|
| `/risk-queue` | 风险队列 |
| `/matching` | 漏洞比对 |
| `/matching/:matchResultId` | 匹配详情 |
| `/assets` | 资产管理 |
| `/assets/:assetId` | 资产详情 |
| `/vulnerabilities` | 漏洞情报 |
| `/vulnerabilities/:vulnerabilityId` | 漏洞详情 |
| `/audit` | 审计日志 |
| `/intel` | 情报采集 |

## 交付说明

- 当前前端不依赖 mock 数据完成主链路。
- 认证和 RBAC 尚未接入，API client 已保留未来 header 注入位置。
- 页面采用路由级懒加载，生产构建已拆分为多个页面 chunk。
- 前端第一版暂不包含 Dashboard、预警通知、报表中心、用户权限、Agent 管理、自动修复和 PoC 验证。
