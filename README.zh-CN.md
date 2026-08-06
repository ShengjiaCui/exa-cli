# exa-cli

[English](README.md) | **[中文](README.zh-CN.md)**

[Exa.ai](https://exa.ai) 搜索 API 的轻量命令行工具。

## 为什么需要

Exa 没有官方 CLI（只有 Python/JS SDK）。这个工具填补了这个空白，让 Exa 能从终端和 AI agent skill 中使用。约定：`EXA_API_KEY` 读环境变量、`--json` 结构化输出、`-o FILE` 存文件、stdin 用 `-`。零运行时依赖（仅标准库）。

## 安装

```bash
uv tool install git+https://github.com/ShengjiaCui/exa-cli.git
```

然后确保 `EXA_API_KEY` 在环境中：

```bash
# 所有平台 — 加到 shell 配置文件（.bashrc / .zshrc / PowerShell profile）：
export EXA_API_KEY=<your-key>
```

验证：

```bash
exa --version
exa search "test" --json | jq '.results | length'
```

## 命令

四个子命令对应 Exa 的四个端点：

| 命令 | 端点 | 用途 |
|------|------|------|
| `exa search` | `POST /search` | 语义 / 关键词搜索 |
| `exa contents` | `POST /contents` | 从 URL 提取干净正文 |
| `exa find-similar` | `POST /findSimilar` | 找与某个 URL 相似的页面（Exa 独有） |
| `exa answer` | `POST /answer` | 带引用的生成答案 |

## 示例

```bash
# 基础搜索
exa search "大语言模型最新进展"

# 一次调用同时拿正文（token 高效的 highlights）
exa search "react hooks 教程" --contents --highlights --num-results 3

# 域名过滤 + 时间范围
exa search "SEC 文件" --include-domains sec.gov --start-date 2026-01-01

# JSON 输出（给 agent / 管道用）
exa search "量子计算" --json | jq '.results[].url'

# 从已知 URL 提取正文
exa contents https://example.com https://exa.ai --text

# 找相似页面（Exa 独有）
exa find-similar https://exa.ai --num-results 5

# 带引用的答案
exa answer "exa.ai 是什么？"
exa answer "谁创办了 exa？" --stream   # 实时流式输出

# 从 stdin 读查询
echo "什么是 RAG" | exa answer - --json

# 保存到文件
exa search "AI 新闻" -o results.json --json
```

## 完整参数覆盖

Exa [API 文档](https://exa.ai/docs/reference/search-api-guide-for-coding-agents)中的**每个参数**都已暴露——包括嵌套 `contents` 对象（`text.maxCharacters`、`highlights.query`、`summary.schema`）、`subpages`/`subpageTarget`、`maxAgeHours`/`livecrawlTimeout`、`outputSchema`（结构化输出）、`systemPrompt`、`moderation`、`stream` 等。运行 `exa search --help` / `exa contents --help` / `exa find-similar --help` / `exa answer --help` 查看完整 flag 列表。

## 成本上报（exa-rotator 集成）

每个 Exa `/search` 和 `/answer` 响应都包含 `costDollars.total` 字段。本 CLI 会把它上报给 [exa-rotator](https://github.com/ShengjiaCui/exa-rotator) daemon（如果正在运行），通过 fire-and-forget POST 到 `127.0.0.1:8732/api/ingest-cost`。这让 rotator 能追踪每个 key 的月度消费，在免费额度用完前轮换账户——无需 Exa 的 admin API。

如果 rotator 没运行，POST 静默失败——CLI 正常工作不受影响。

## 测试

两层测试：

**单元测试**（pytest，不打 API，~0.1s）——mock `client.request`，断言 wire-format body 正确（camelCase 转换、contents 嵌套、过滤逻辑、错误归一化）：

```bash
uv run pytest -v          # 107 个测试
uv run pytest -q          # 安静模式
```

**自检**（bash，打真实 API，~10s）——14 项运维健康检查：

```bash
bash scripts/selftest.sh  # 14 项检查，全过 exit 0
```

提交前都跑一遍：

```bash
uv run pytest -q && bash scripts/selftest.sh
```

## Wire 格式说明

- HTTP 参数用 **camelCase**（`numResults`、`includeDomains`、`startPublishedDate`），遵循 Exa HTTP API 约定。本 CLI 内部处理转换。
- `/search` 上，内容参数（`text`/`highlights`/`summary`）嵌套在 `contents` 对象里——传 `--contents` 时本 CLI 自动处理。
- 已弃用且不暴露的：`useAutoprompt`（无效）、`includeUrls`/`excludeUrls`（用 domains）。

## 卸载

```bash
uv tool uninstall exa-cli
```
