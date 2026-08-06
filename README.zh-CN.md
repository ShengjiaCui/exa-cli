<div align="center">

# exa-cli

[Exa.ai](https://exa.ai) 搜索 API 的命令行工具。

搜索网页 · 提取页面内容 · 查找相似页面 · 获取带引用的答案

[English](README.md) | **[中文](README.zh-CN.md)**

</div>

---

## 这是什么？

[Exa.ai](https://exa.ai) 是一个为 AI 设计的搜索引擎——它返回干净、结构化的结果，而不是充满广告的 HTML。但 Exa 只提供 Python/JS SDK，**没有命令行工具**。这个项目填补了这个空白。

安装后，你会得到一个 `exa` 命令，直接在终端使用：

```bash
$ exa search "谁发明了 transformer 架构"

2 result(s) for: 谁发明了 transformer 架构

1. Attention Is All You Need
   https://arxiv.org/abs/1706.03762
   score: 0.95

2. The Illustrated Transformer
   https://jalammar.github.io/illustrated-transformer/
   score: 0.91
```

## 快速开始（2 分钟）

### 第 1 步 — 安装

```bash
# 需要 Python 3.9+ 和 uv（https://docs.astral.sh/uv/）
uv tool install git+https://github.com/ShengjiaCui/exa-cli.git
```

验证安装成功：

```bash
exa --version
# exa-cli 0.1.0
```

### 第 2 步 — 获取 API key

1. 打开 [exa.ai/dashboard](https://exa.ai/dashboard)
2. 注册免费账户（获得 **$20 免费额度** + **每月 $10**）
3. 复制你的 API key

### 第 3 步 — 设置 key

在 shell 配置文件（`~/.bashrc`、`~/.zshrc` 或 PowerShell profile）中加入：

```bash
export EXA_API_KEY=你的key
```

然后重新加载 shell（或开一个新终端）。

### 第 4 步 — 搜索！

```bash
exa search "AI 最新新闻" --num-results 5
```

搞定。🎉

---

## 命令

### `exa search` — 搜索网页

最常用的命令。根据你的查询找到相关网页。

```bash
# 基础搜索
exa search "react hooks 教程"

# 更多结果
exa search "机器学习" --num-results 10

# 搜索 + 同时获取页面内容（省一次请求）
exa search "量子计算" --contents --highlights

# 只搜索特定网站
exa search "SEC 文件" --include-domains sec.gov

# 只看最近的结果
exa search "AI 新闻" --start-date 2026-07-01

# 学术论文
exa search "scaling laws" --category "research paper"
```

**搜索深度** — 用 `--type` 控制速度和质量：

| `--type` | 速度 | 适用场景 |
|----------|------|----------|
| `instant` | ~250ms | 实时自动补全 |
| `fast` | ~450ms | 快速查询 |
| `auto` *（默认）* | ~1s | 通用 |
| `deep` | 数秒 | 复杂的多步查询 |
| `deep-reasoning` | 12-40秒 | 高难度研究任务 |

### `exa contents` — 从 URL 提取内容

已经有 URL 了？直接拿到它的干净正文（去掉导航栏、广告等）。

```bash
# 完整正文
exa contents https://example.com --text

# 只要关键高亮（省 token）
exa contents https://example.com --highlights

# AI 生成的摘要
exa contents https://example.com --summary

# 一次提取多个 URL
exa contents https://a.com https://b.com https://c.com --text
```

### `exa find-similar` — 查找与某个 URL 相似的页面 *（Exa 独有）*

给它一个好页面，返回语义相关的页面。**其他搜索引擎没有这个功能。**

```bash
exa find-similar https://arxiv.org/abs/1706.03762 --num-results 5

# 排除来源域名（避免近似重复）
exa find-similar https://some-blog.com/post --exclude-domains some-blog.com
```

### `exa answer` — 提问，获取带引用的答案

```bash
exa answer "谁创办了 exa.ai？"

# Answer:
# Exa.ai was founded by Will Bryk and Jeff Wang [1][2]...
#
# Sources:
# 1. Exa: The Search Engine for Developers — https://exa.ai/about
# 2. TechCrunch article — https://techcrunch.com/...

# 实时流式输出（逐字显示）
exa answer "LLM scaling 最新进展" --stream
```

---

## 输出选项（所有命令通用）

| 参数 | 作用 |
|------|------|
| `--json` | 结构化 JSON 输出（用于脚本、管道、AI agent） |
| `-o 文件` | 输出保存到文件 |
| `-`（作为查询词） | 从 stdin 读查询：`echo "查询" \| exa search -` |

```bash
# 管道给 jq 只提取 URL
exa search "最好的 python 库" --json | jq -r '.results[].url'

# 保存结果到文件
exa search "AI 新闻" -o results.json --json

# 从管道读取查询
cat my-questions.txt | exa answer - --json
```

---

## 进阶：结构化输出

传入 JSON schema，从多个页面中提取特定字段：

```bash
exa search "航空航天公司" --type deep --num-results 5 \
  --output-schema '{"type":"object","properties":{"companies":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string"},"ceo":{"type":"string"}}}}}}' \
  --json
```

响应会包含 `output` 字段，里面是结构化数据。

---

## 进阶：内容选项

使用 `exa search` 或 `exa find-similar` 时加 `--contents`，可以精细控制返回的内容：

```bash
exa search "融资轮次" --contents \
  --text --text-max-chars 1000 \          # 限制正文长度
  --highlights --highlights-query "融资金额" \  # 高亮聚焦
  --summary --summary-query "提取估值" \        # 摘要聚焦
  --subpages 3 --subpage-target docs \    # 爬取子页面
  --json
```

运行 `exa search --help` 查看完整参数列表。

---

## Key 管理与轮换（可选）

Exa 免费层每账户每月 **$10 额度**。如果你有多个账户，可以用
[exa-rotator](https://github.com/ShengjiaCui/exa-rotator) 在月度额度用完前自动轮换 key。

本 CLI 每次调用会把 API 返回的费用（`costDollars`）上报给 rotator daemon（如果在运行）。
daemon 没运行也不影响——这个功能完全可选。

---

## 测试

```bash
# 单元测试（快，不打 API）
uv run pytest -v

# 集成测试（打真实 Exa API，约 10 秒）
bash scripts/selftest.sh
```

## 卸载

```bash
uv tool uninstall exa-cli
# 删掉 shell 配置文件里的 export 行
```

---

## 许可证

MIT
