# Scholarly Metadata Enrichment — Phase 1B

> 学术元数据增强：识别文献 → 补全元数据 → 匹配期刊等级与指标 → 生成规范引用
> Phase 1B: `/pkb` 接入、批量增强、文献筛选工具

## 功能边界 (Phase 1B)

Phase 1B 已接入 `/pkb` 主流程：

- ✅ Phase 1A 所有功能
- ✅ `/pkb` 自动检测学术文献并增强（同步，fail-open）
- ✅ 学术文献检测器（信号分层：强信号/中等信号/排除信号）
- ✅ 批量增强已有文献：`--scan`, `--write`, `--only-missing`, `--resume`, `--dry-run`, `--jsonl`, `--force`
- ✅ 断点恢复：`.pkb_local/scholarly/jobs/` job 状态管理
- ✅ 结构化文献筛选：`filter_literature.py`（按期刊等级/年份/被引/DOI 等过滤）
- ✅ 幂等写入：重复运行不产生无意义 diff
- ✅ locked 页面保护：`scholarly.locked: true` 跳过自动增强
- ✅ 配置管理：`pkb.config.json` 中 `scholarly` 节
- ❌ JCR / Scopus / 中科院分区（Phase 2）
- ❌ 复杂搜索 UI / Streamlit（Phase 2）

## 数据来源说明

| 数据 | 来源 | 是否需要密钥 | 许可 |
|------|------|-------------|------|
| 文献元数据 | [Crossref REST API](https://api.crossref.org/) | 否（推荐配置邮箱） | 免费公开 |
| 被引次数、指标 | [OpenAlex REST API](https://api.openalex.org/) | 否（推荐 API Key） | 免费公开，CC0 |
| 期刊等级 | 本地 CSV 导入 | 否 | 用户自行获取 |
| JCR 影响因子 | 未实现 | — | Phase 3 |

## 快速开始

### 1. 配置 API Key（可选）

```bash
# OpenAlex API Key（提升限额，推荐）
# 注册: https://openalex.org/account
export OPENALEX_API_KEY="your_key_here"

# Crossref 联系邮箱（礼仪性，推荐）
export CROSSREF_EMAIL="<USER_EMAIL>"
```

### 2. 导入期刊目录

```bash
# 从 CSV 导入
python tools/import_journal_rankings.py import path/to/rankings.csv

# 查看已导入的体系
python tools/import_journal_rankings.py list

# 验证 CSV 格式（不导入）
python tools/import_journal_rankings.py validate path/to/rankings.csv
```

### 3. 查询文献

```bash
# 按 DOI 查询
python tools/scholarly_enrich.py --doi "10.1234/example"

# JSON 输出
python tools/scholarly_enrich.py --doi "10.1234/example" --json
```

### 4. 批量增强（Phase 1B）

```bash
# 预览（默认不写）
python tools/scholarly_enrich.py --scan wiki/

# 写入
python tools/scholarly_enrich.py --scan wiki/ --write

# 只补全缺失数据
python tools/scholarly_enrich.py --scan wiki/ --write --only-missing

# 断点恢复
python tools/scholarly_enrich.py --scan wiki/ --write --resume

# 干跑预览
python tools/scholarly_enrich.py --scan wiki/ --dry-run

# JSONL 输出（适合脚本处理）
python tools/scholarly_enrich.py --scan wiki/ --jsonl

# 强制更新（跳过 locked 和阈值门控）
python tools/scholarly_enrich.py --scan wiki/ --write --force
```

### 5. 筛选文献（Phase 1B）

```bash
# 按期刊等级
python tools/filter_literature.py --ranking CSSCI

# 按等级 + 版本 + 级别
python tools/filter_literature.py --ranking CSSCI --edition 2025-2026
python tools/filter_literature.py --ranking AMI --level authoritative

# 按年份范围
python tools/filter_literature.py --year-from 2020 --year-to 2026

# 按被引次数
python tools/filter_literature.py --min-citations 10

# 查看需要人工复核的匹配
python tools/filter_literature.py --needs-review

# 查找缺少引用格式的文献
python tools/filter_literature.py --missing citation

# 多条件 AND 组合
python tools/filter_literature.py --ranking CSSCI --year-from 2023 --min-citations 5

# 输出格式
python tools/filter_literature.py --ranking CSSCI --format table   # 表格（默认）
python tools/filter_literature.py --ranking CSSCI --format json    # JSON
python tools/filter_literature.py --ranking CSSCI --format paths   # 路径列表

# 导出引用
python tools/filter_literature.py --ranking CSSCI --export-citations gbt7714-numeric
```

### 6. `/pkb` 自动增强

`/pkb` 采集学术文献时自动执行增强。无需额外操作。

关闭自动增强：
```json
// pkb.config.json
{"scholarly": {"auto_enrich_on_pkb": false}}
```

增强失败时的重试命令会在报告中显示。

## 期刊目录 CSV 格式

CSV 文件需 UTF-8 编码，包含以下列：

```csv
scheme,edition,journal_name,issn,eissn,issn_l,level,category
CSSCI,2025-2026,新闻与传播研究,1005-2577,,1005-2577,source,新闻学与传播学
PKU_CORE,2023,新闻与传播研究,1005-2577,,1005-2577,core,新闻学与传播学
AMI,2022,新闻与传播研究,1005-2577,,1005-2577,authoritative,新闻传播学
CUSTOM,2026,校内A类期刊,1234-5678,,1234-5678,tier_a,计算机科学
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `scheme` | ✅ | CSSCI / PKU_CORE / AMI / CSCD / CUSTOM |
| `edition` | | 版本年份，如 "2025-2026" |
| `journal_name` | ✅ | 原始刊名（会保留） |
| `issn` | | 印刷 ISSN（XXXX-XXXX） |
| `eissn` | | 电子 ISSN |
| `issn_l` | | 链接 ISSN |
| `level` | | source / core / authoritative / top / tier_a / ... |
| `category` | | 学科分类 |

可选列：`source_label`, `source_url`, `verified_at`

## 缓存和离线模式

缓存位置：`.pkb_local/scholarly/cache.sqlite3`

| 数据类型 | 默认 TTL |
|---------|---------|
| 文献元数据（Crossref） | 30 天 |
| 被引次数与指标（OpenAlex） | 7 天 |

### 模式对比

| 模式 | 标志 | 网络 | 缓存 | 用途 |
|------|------|------|------|------|
| 正常 | （无） | ✅ | ✅ 读+写 | 日常查询 |
| 纯缓存 | `--cache-only` | ❌ | ✅ 只读 | 限流后继续工作 |
| 离线 | `--offline` | ❌ | ❌ | 完全无网络环境 |

## 指标命名规则

⚠️ **重要**：OpenAlex 的 `2yr_mean_citedness` 不是 Clarivate 的 Journal Impact Factor。

- 始终标注来源：`OpenAlex 2yr_mean_citedness: 3.82`
- 不得简称为"影响因子"或"JIF"
- 不得混用不同来源的指标

## 引用引擎边界

| 格式 | 引擎 | 状态 | 说明 |
|------|------|------|------|
| GB/T 7714 顺序编码制 | fallback | ✅ 金样验证 | 仅期刊文章有金样验证 |
| GB/T 7714 著者-出版年 | fallback | ✅ 金样验证 | 仅期刊文章有金样验证 |
| APA 7 | citeproc-only | ✅ | 需要 citeproc-py；无可用 fallback |
| BibTeX | direct | ✅ | 不依赖引擎选择 |
| RIS | direct | ✅ | 不依赖引擎选择 |
| MLA / Chicago / IEEE | — | ❌ | Phase 2 |

### APA 7 注意

- AUTO + APA：citeproc 已安装 → citeproc；未安装 → UNAVAILABLE（不静默回落）
- FALLBACK + APA：返回 UNSUPPORTED（APA 无金样验证的 fallback）
- CITEPROC + APA：强制 citeproc；失败 → ERROR（不静默回落）

### citeproc-py

```bash
pip install -r tools/requirements-scholarly.txt
```

## 配置 (Phase 1B)

在 `pkb.config.json` 中配置：

```json
{
  "scholarly": {
    "enabled": true,
    "auto_enrich_on_pkb": true,
    "detection_threshold": 0.9,
    "citation_engine": "auto",
    "use_crossref": true,
    "use_openalex": true,
    "cache_only": false,
    "offline": false,
    "write_metrics": true,
    "write_citations": true,
    "fail_open": true
  }
}
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | `true` | 是否启用学术增强 |
| `auto_enrich_on_pkb` | `true` | `/pkb` 采集时自动增强 |
| `detection_threshold` | `0.9` | 自动增强的最低置信度 |
| `citation_engine` | `"auto"` | AUTO / FALLBACK / CITEPROC |
| `use_crossref` | `true` | 使用 Crossref 补全元数据 |
| `use_openalex` | `true` | 使用 OpenAlex 获取指标 |
| `cache_only` | `false` | 仅使用缓存 |
| `offline` | `false` | 完全离线 |
| `write_metrics` | `true` | 写入指标到 frontmatter |
| `write_citations` | `true` | 写入引用到 frontmatter |
| `fail_open` | `true` | 增强失败不阻断 /pkb |

API Key 始终从环境变量读取，不写入配置文件：
- `OPENALEX_API_KEY`
- `CROSSREF_EMAIL`

## 学术检测规则

检测器使用三层信号：

### 强信号（任一即可触发）
- frontmatter `type: literature`
- frontmatter `scholarly.detected: true`
- 正文或元数据中有 DOI
- arXiv / PubMed ID
- 学术来源 URL（arxiv.org, doi.org 等）
- PDF 元数据中有 DOI

### 中等信号（多个组合）
- 标题 + 作者 + 年份 + 期刊名同时存在
- 卷/期/页码
- ISSN / EISSN
- 摘要/关键词/参考文献等结构标记
- 文件名标记为论文

### 排除信号（自动排除）
- 标题含"新闻""目录""检索结果"等
- 标题含 blog、newsletter 等
- 正文含 news article、press release、blog post 等
- 正文含 readme、changelog 等

### 判定规则
- `confidence >= 0.90` 且有强信号：自动增强
- `0.70 <= confidence < 0.90`：仅记录候选，不联网
- `< 0.70`：跳过
- 存在排除信号：直接排除

## CSSCI、北大核心等数据说明

本仓库**不包含**真实的 CSSCI、北大核心、AMI 或 CSCD 期刊名单。

原因：
1. 这些目录受版权保护，不能随意分发
2. 不同机构可能有不同的认定标准
3. 用户应自行从有权使用的来源获取

### 如何获取期刊目录

- **CSSCI**：南京大学中国社会科学研究评价中心（cssrac.nju.edu.cn）
- **北大核心**：北京大学图书馆《中文核心期刊要目总览》
- **AMI**：中国社会科学评价研究院
- **CSCD**：中国科学院文献情报中心

用户获取后，通过 `import_journal_rankings.py` 导入。

### 测试数据

`tests/fixtures/scholarly/` 中的测试数据仅有少量虚构数据，
不包含真实期刊名单。

## `.pkb_local/scholarly/` 目录

该目录属于用户数据，由 `update_pkb.py` 保护：

- `.pkb_local/scholarly/rankings/` — 导入的期刊等级数据（用户自行管理）
- `.pkb_local/scholarly/styles/` — CSL 样式文件（用户可能自定义）
- `.pkb_local/scholarly/cache.sqlite3` — 运行时缓存（自动管理）

此目录不在 Git 版本控制中（已在 `.gitignore` 中添加）。

## 常见故障排查

### OpenAlex 查询失败

如果 `openalex_status: error`：
1. 检查网络连接
2. 配置 API Key 提升限额：`export OPENALEX_API_KEY="..."` 
3. 使用 `--cache-only` 模式继续工作

### Crossref 查询失败

如果 `crossref_status: error`：
1. 检查 DOI 格式是否正确
2. 检查网络连接
3. 使用 `--offline` 模式跳过网络查询

### 期刊等级匹配为空

1. 确认已导入期刊目录：`python tools/import_journal_rankings.py list`
2. 检查 ISSN 是否匹配（ISSN 是主要匹配键）
3. 如文献无 ISSN，尝试手动添加 ISSN 到 Markdown frontmatter

### 引用格式不符合预期

1. 确认 `citeproc-py` 是否已安装：`python -c "import citeproc"`
2. 检查文献类型是否为 `article-journal`（其他类型暂不支持）
3. 阅读 GB/T 7714 金样测试结果：`python -m pytest tests/test_citation_formatter.py -v`

## 技术架构

```
tools/scholarly/
├── models.py              # 统一数据模型（dataclass）
├── cache.py               # SQLite 缓存层
├── journal_registry.py    # 期刊等级注册表
├── matcher.py             # ISSN 优先匹配器
├── detector.py            # 学术文献检测器 (Phase 1B)
├── enrichment.py          # 主编排逻辑
├── integration.py         # /pkb 集成层 (Phase 1B)
├── citation_formatter.py  # CSL-JSON + GB/T 7714 + citeproc
└── clients/
    ├── crossref.py        # Crossref REST API 客户端
    └── openalex.py        # OpenAlex REST API 客户端

tools/scholarly_enrich.py         # 批量增强 CLI (Phase 1B)
tools/filter_literature.py        # 结构化文献筛选 CLI (Phase 1B)
tools/import_journal_rankings.py  # 期刊目录导入 CLI

tests/
├── test_scholarly_models.py      # 数据模型测试
├── test_journal_registry.py      # 期刊注册表测试
├── test_scholarly_cache.py       # 缓存测试
├── test_scholarly_clients.py     # API 客户端测试（全部 mock）
├── test_scholarly_matcher.py     # 匹配器测试
├── test_citation_formatter.py    # 引用格式金样测试
├── test_scholarly_enrich.py      # 集成 + CLI 测试
├── test_scholarly_detector.py    # 检测器测试 (Phase 1B)
├── test_scholarly_integration.py # 集成层测试 (Phase 1B)
└── test_filter_literature.py     # 筛选工具测试 (Phase 1B)
```
